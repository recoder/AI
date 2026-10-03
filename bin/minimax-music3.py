"""Translate a shared Markdown song job into an offline MiniMax Music 3 run."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid

import yaml
from song_jobs import read_job, read_yaml


DEFAULTS = {"seed": 42, "duration_seconds": 30, "steps": 30, "tool_options": {"output_format": "wav"}}


def keys(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Invalid/unknown keys in {name}; allowed: {', '.join(sorted(allowed))}")


def configured_path(config_path, value, kind="file"):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Configured paths must be nonempty strings")
    path = (config_path.parent / value).resolve()
    exists = path.is_dir() if kind == "directory" else path.is_file()
    if not exists:
        raise ValueError(f"Missing configured path: {path}. Repair: just install minimax-music3 / just models minimax-music3")
    return str(path)


def prepare(job_path):
    filename = Path(__file__).with_suffix(".yaml").name
    candidates = [Path.cwd() / filename, Path(__file__).with_name(filename)]
    config_path = next((path for path in candidates if path.is_file()), None)
    if config_path is None:
        raise ValueError("No minimax-music3.yaml found. Run just install minimax-music3")
    config = read_yaml(config_path.read_text(encoding="utf-8-sig"))
    keys(config, {"version", "tool", "backend", "paths", "runtime", "defaults", "identities", "output"}, "config")
    if (config.get("version"), config.get("tool"), config.get("backend")) != (1, "minimax-music3", "diffusers-modular"):
        raise ValueError("Expected MiniMax Music 3 version 1 Diffusers modular config")
    paths = config["paths"]
    keys(paths, {"python", "entrypoint", "models"}, "paths")
    runtime = config["runtime"]
    keys(runtime, {"device", "dtype", "component_offload", "language_model_group_offload", "group_offload_stream", "timeout_seconds"}, "runtime")
    if runtime.get("device") != "cuda" or runtime.get("dtype") != "bfloat16":
        raise ValueError("The declared quality preset requires CUDA and bfloat16")
    if runtime.get("component_offload") is not True or runtime.get("language_model_group_offload") != "leaf_level":
        raise ValueError("The 16 GB preset requires component and leaf-level language-model CPU offload")
    if type(runtime.get("group_offload_stream")) is not bool:
        raise ValueError("runtime.group_offload_stream must be boolean")
    if type(runtime.get("timeout_seconds")) is not int or runtime["timeout_seconds"] <= 0:
        raise ValueError("runtime.timeout_seconds must be positive")
    identity = config["identities"]
    keys(identity, {"model_revision", "diffusers_version"}, "identities")
    if not re.fullmatch(r"[a-f0-9]{40}", identity.get("model_revision", "")) or identity.get("diffusers_version") != "0.40.0":
        raise ValueError("MiniMax model revision and Diffusers version must match declared pins")

    job = read_job(job_path)
    settings = DEFAULTS.copy()
    settings["tool_options"] = DEFAULTS["tool_options"].copy()
    for layer in (config.get("defaults", {}), job["metadata"]):
        keys(layer, set(DEFAULTS) | {"version", "tool"}, "settings")
        if layer.get("version", 1) != 1 or layer.get("tool", "minimax-music3") != "minimax-music3":
            raise ValueError("Job version/tool mismatch")
        for key, value in layer.items():
            if key == "tool_options":
                keys(value, {"output_format"}, "tool_options")
                settings[key].update(value)
            elif key in DEFAULTS:
                settings[key] = value
    if type(settings["seed"]) is not int or not 0 <= settings["seed"] <= 2147483647:
        raise ValueError("seed must be an integer from 0 to 2147483647")
    if type(settings["duration_seconds"]) not in (int, float) or not 10 <= settings["duration_seconds"] <= 300:
        raise ValueError("duration_seconds must be 10–300")
    if type(settings["steps"]) is not int or not 1 <= settings["steps"] <= 100:
        raise ValueError("steps must be an integer from 1 to 100")
    if settings["tool_options"].get("output_format") != "wav":
        raise ValueError("Version 1 supports WAV only")

    blocks = job["blocks"]
    unsupported = set(blocks) & {"song-negative-prompt", "song-reference-audio"}
    if unsupported:
        raise ValueError("MiniMax Music 3 text-to-music does not support negative-prompt or reference-audio blocks")
    lyrics = blocks.get("song-lyrics", "").strip()
    if not lyrics:
        raise ValueError("MiniMax Music 3 version 1 requires a song-lyrics block")
    for line in lyrics.splitlines():
        if re.match(r"^\s*\[[^]]+\]\s*\S", line):
            raise ValueError("Put lyric section tags on their own lines; MiniMax drops text following a tag")
    prompt = "\n\n".join(part for part in (job["prompt"].strip(), blocks.get("song-positive-style", "").strip()) if part)
    if not prompt:
        raise ValueError("Provide a music description in the body or song-positive-style block")

    output = config["output"]
    keys(output, {"directory"}, "output")
    if not isinstance(output.get("directory"), str) or not output["directory"].strip():
        raise ValueError("output.directory must be a nonempty path")
    request = {"models": configured_path(config_path, paths["models"], "directory"), "runtime": runtime,
               "settings": settings, "prompt": prompt, "lyrics": lyrics, "title": job["title"],
               "config": str(config_path.resolve()), "job": str(Path(job_path).resolve()), "identities": identity}
    root = (config_path.parent / output["directory"]).resolve()
    return request, configured_path(config_path, paths["python"]), configured_path(config_path, paths["entrypoint"]), root


def validate_audio(path):
    import numpy as np
    import soundfile as sf
    try:
        info = sf.info(str(path))
    except sf.LibsndfileError as error:
        raise RuntimeError(f"Invalid MiniMax Music 3 WAV: {error}") from error
    if info.format != "WAV" or info.frames == 0 or info.channels != 2 or info.samplerate != 44100:
        raise RuntimeError("Invalid/empty MiniMax Music 3 WAV (expected stereo 44.1 kHz)")
    peak = 0.0
    for block in sf.blocks(str(path), blocksize=44100, dtype="float32", always_2d=True):
        if not np.isfinite(block).all():
            raise RuntimeError("MiniMax Music 3 WAV contains non-finite audio samples")
        peak = max(peak, float(np.max(np.abs(block))))
    if peak < 1e-5:
        raise RuntimeError("MiniMax Music 3 WAV is silent")
    return info


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--output-dir", type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--validate", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        request, python, entrypoint, root = prepare(args.job)
        if args.output_dir:
            root = args.output_dir.resolve()
        request["output_root"] = str(root)
        if args.validate or args.dry_run:
            print(json.dumps(request, indent=2) if args.dry_run else f"Valid MiniMax Music 3 job: {request['title']}")
            return
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", request["title"]).strip("-")[:60] or "untitled"
        output = root / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-minimax-music3-" + slug + "-" + uuid.uuid4().hex[:8])
        output.mkdir(parents=True, exist_ok=False)
        request["output"] = str(output)
        (output / "job.md").write_bytes(args.job.read_bytes())
        request_path = output / "request.json"
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        print(f"Generating in {output}", flush=True)
        with (output / "stdout.log").open("w", encoding="utf-8") as stdout, (output / "stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([python, entrypoint, "--request", str(request_path)], cwd=str(Path(python).parents[2]), stdout=stdout, stderr=stderr)
            try:
                code = process.wait(timeout=runtime_timeout(request))
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
                process.kill()
                process.wait(timeout=30)
                raise RuntimeError(f"Generation interrupted/timed out. Logs preserved: {output}")
        if code:
            raise RuntimeError(f"Backend failed (exit {code}). Inspect {output / 'stderr.log'}")
        validate_audio(output / "audio.wav")
        print(f"Generated: {output / 'audio.wav'}")
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, yaml.YAMLError, subprocess.SubprocessError) as error:
        parser.exit(1, f"MiniMax Music 3: {error}\n")


def runtime_timeout(request):
    return request["runtime"]["timeout_seconds"]


if __name__ == "__main__":
    main()
