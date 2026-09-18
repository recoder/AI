"""Translate a Markdown song job into an offline native YuE2 call."""
import argparse
import datetime
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import wave
import yaml
from song_jobs import read_job, read_yaml

DEFAULTS = dict(seed=42, duration_seconds=30, steps=32, guidance_scale=1.0,
                temperature=1.0, top_k=100, top_p=0.95, tool_options={"planning": "full"})


def keys(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Invalid/unknown keys in {name}; allowed: {', '.join(allowed)}")


def validate_settings(settings):
    for key, low, high in [("seed", 0, 2147483647), ("duration_seconds", 1, 600), ("steps", 1, 1000),
                            ("guidance_scale", 1, 100), ("temperature", 0.001, 10), ("top_k", 0, 100000), ("top_p", 0.001, 1)]:
        value = settings[key]
        if type(value) not in (int, float) or not low <= value <= high:
            raise ValueError(f"{key} must be between {low} and {high}")
        if key in ("seed", "steps", "top_k") and type(value) is not int:
            raise ValueError(f"{key} must be an integer")
    if settings["tool_options"]["planning"] not in ("full", "melody", "off"):
        raise ValueError("planning must be full, melody or off")


def prepare(job_path):
    filename = Path(__file__).with_suffix(".yaml").name
    candidates = [Path.cwd() / filename, Path(__file__).with_name(filename)]
    config_path = next((p for p in candidates if p.exists()), None)
    if config_path is None:
        raise ValueError("No yue.yaml found in current directory or beside runner. Run just install yue")
    config = read_yaml(config_path.read_text(encoding="utf-8-sig"))
    keys(config, ["version", "tool", "backend", "paths", "runtime", "defaults", "output", "identities"], "config")
    if type(config.get("version")) is not int or (config.get("version"), config.get("tool"), config.get("backend")) != (1, "yue", "wan2gp-yue2"):
        raise ValueError("Expected version 1, tool yue, backend wan2gp-yue2")
    paths = config["paths"]
    keys(paths, ["application", "python", "entrypoint", "models"], "paths")
    keys(paths["models"], ["acoustic", "ar", "tokenizer", "vae", "vae_config"], "models")
    def resolve(value, directory=False):
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Paths must be nonempty strings")
        path = (config_path.parent / value).resolve()
        if not (path.is_dir() if directory else path.is_file()):
            raise ValueError(f"Missing configured path: {path}. Repair: just install yue / just models yue")
        return str(path)
    runtime = config["runtime"]
    keys(runtime, ["profile", "vae_tile_size", "timeout_seconds", "budgets"], "runtime")
    if "budgets" in runtime:
        keys(runtime["budgets"], ["transformer", "text_encoder", "*"], "runtime.budgets")
        if set(runtime["budgets"]) != {"transformer", "text_encoder", "*"} or any(type(v) is not int or not 100 <= v <= 16000 for v in runtime["budgets"].values()):
            raise ValueError("Budgets must specify transformer/text_encoder/* in MiB (100–16000)")
    if runtime.get("profile") not in (4, 5) or runtime.get("vae_tile_size") not in (256, 1024):
        raise ValueError("Use MMGP profile 4/5 and VAE tile size 256/1024")
    if type(runtime.get("timeout_seconds")) is not int or runtime["timeout_seconds"] <= 0:
        raise ValueError("timeout_seconds must be a positive integer")
    job = read_job(job_path)
    settings = DEFAULTS.copy()
    settings["tool_options"] = DEFAULTS["tool_options"].copy()
    for layer in (config.get("defaults", {}), job["metadata"]):
        keys(layer, list(DEFAULTS) + ["version", "tool"], "settings")
        if type(layer.get("version", 1)) is not int or layer.get("version", 1) != 1 or layer.get("tool", "yue") != "yue":
            raise ValueError("Job version/tool mismatch")
        for key, value in layer.items():
            if key == "tool_options":
                keys(value, ["planning"], "tool_options")
                settings[key].update(value)
            elif key in DEFAULTS:
                settings[key] = value
        validate_settings(settings)
    blocks = job["blocks"]
    if set(blocks) & {"song-negative-prompt", "song-reference-audio"}:
        raise ValueError("This YuE2 flavor currently supports lyrics and positive style only")
    lyrics = blocks.get("song-lyrics", "")
    style = blocks.get("song-positive-style", job["prompt"])
    if not lyrics or not style:
        raise ValueError("Provide song-lyrics and a body prompt or song-positive-style")
    keys(config["output"], ["directory"], "output")
    output = config["output"]["directory"]
    if not isinstance(output, str) or not output.strip():
        raise ValueError("output.directory must be a nonempty path")
    request = dict(application=resolve(paths["application"], True), models={k: resolve(paths["models"][k]) for k in ["acoustic", "ar", "tokenizer", "vae", "vae_config"]},
                   runtime=runtime, settings=settings, lyrics=lyrics, style=style, title=job["title"], prompt=job["prompt"],
                   config=str(config_path.resolve()), job=str(Path(job_path).resolve()))
    identities = config.get("identities", {})
    keys(identities, ["source_revision", "model_revision"], "identities")
    for value in identities.values():
        if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{40}", value):
            raise ValueError("Identity revisions must be exact 40-character commit hashes")
    request["identities"] = identities
    if identities.get("source_revision"):
        head = subprocess.check_output(["git", "-C", request["application"], "rev-parse", "HEAD"], text=True, timeout=30).strip()
        if head != identities["source_revision"]:
            raise ValueError("Configured source revision does not match installed checkout. Repair: just source yue")
    request["model_sizes"] = {key: Path(value).stat().st_size for key, value in request["models"].items()}
    return request, resolve(paths["python"]), resolve(paths["entrypoint"]), (config_path.parent / output).resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("--output-dir", type=Path, help="Output root, relative to the invocation directory")
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
            print(json.dumps(request, indent=2) if args.dry_run else f"Valid YuE2 job: {request['title']}")
            return
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", request["title"]).strip("-")[:60] or "untitled"
        output = root / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-song-" + slug + "-" + uuid.uuid4().hex[:8])
        output.mkdir(parents=True, exist_ok=False)
        request["output"] = str(output)
        (output / "job.md").write_bytes(args.job.read_bytes())
        request_path = output / "request.json"
        request_path.write_text(json.dumps(request, indent=2), encoding="utf-8")
        print(f"Generating in {output}", flush=True)
        with (output / "stdout.log").open("w", encoding="utf-8") as stdout, (output / "stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen([python, entrypoint, "--request", str(request_path)], cwd=request["application"], stdout=stdout, stderr=stderr)
            try:
                code = process.wait(timeout=request["runtime"]["timeout_seconds"])
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=30)
                process.kill()
                process.wait(timeout=30)
                raise RuntimeError(f"Generation interrupted/timed out. Logs preserved: {output}")
        if code:
            raise RuntimeError(f"Backend failed (exit {code}). Inspect {output / 'stderr.log'}")
        with wave.open(str(output / "audio.wav"), "rb") as audio:
            if audio.getnframes() == 0 or audio.getnchannels() != 2 or audio.getframerate() != 48000:
                raise RuntimeError("Invalid/empty generated WAV")
        print(f"Generated: {output / 'audio.wav'}")
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, yaml.YAMLError, subprocess.SubprocessError) as error:
        parser.exit(1, f"YuE: {error}\n")


if __name__ == "__main__":
    main()
