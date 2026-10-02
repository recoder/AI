"""Translate a Markdown song job into an offline ACE-Step 1.5 generation call."""
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


DEFAULTS = dict(
    seed=42,
    duration_seconds=30,
    steps=50,
    guidance_scale=7.0,
    temperature=0.85,
    top_k=0,
    top_p=0.9,
    tool_options={"thinking": True, "shift": 1.0, "infer_method": "ode", "output_format": "wav"},
)
TOOL_OPTIONS = {
    "thinking", "shift", "infer_method", "output_format", "instrumental", "bpm",
    "keyscale", "timesignature", "vocal_language", "use_cot_caption", "use_cot_metas",
}


def keys(value, allowed, name):
    if not isinstance(value, dict) or set(value) - set(allowed):
        raise ValueError(f"Invalid/unknown keys in {name}; allowed: {', '.join(sorted(allowed))}")


def number(settings, name, low, high, integer=False):
    value = settings[name]
    if type(value) not in (int, float) or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    if integer and type(value) is not int:
        raise ValueError(f"{name} must be an integer")


def validate_settings(settings):
    number(settings, "seed", 0, 2147483647, True)
    number(settings, "duration_seconds", 10, 600)
    number(settings, "steps", 1, 200, True)
    number(settings, "guidance_scale", 0, 30)
    number(settings, "temperature", 0.01, 2)
    number(settings, "top_k", 0, 1000, True)
    number(settings, "top_p", 0.01, 1)
    options = settings["tool_options"]
    keys(options, TOOL_OPTIONS, "tool_options")
    for name in ("thinking", "instrumental", "use_cot_caption", "use_cot_metas"):
        if name in options and type(options[name]) is not bool:
            raise ValueError(f"tool_options.{name} must be true or false")
    if type(options.get("shift", 1.0)) not in (int, float) or not 0.1 <= options.get("shift", 1.0) <= 10:
        raise ValueError("tool_options.shift must be between 0.1 and 10")
    if options.get("infer_method", "ode") not in ("ode", "sde"):
        raise ValueError("tool_options.infer_method must be ode or sde")
    if options.get("output_format", "wav") != "wav":
        raise ValueError("Version 1 supports WAV output only")
    if "bpm" in options and (type(options["bpm"]) is not int or not 30 <= options["bpm"] <= 300):
        raise ValueError("tool_options.bpm must be an integer from 30 to 300")
    for name in ("keyscale", "timesignature", "vocal_language"):
        if name in options and (not isinstance(options[name], str) or not options[name].strip()):
            raise ValueError(f"tool_options.{name} must be a nonempty string")


def configured_path(config_path, value, kind="file", required=True):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Paths must be nonempty strings")
    path = (config_path.parent / value).resolve()
    exists = path.is_dir() if kind == "directory" else path.is_file()
    if required and not exists:
        raise ValueError(f"Missing configured path: {path}. Repair: just install ace-step / just models ace-step")
    return str(path)


def prepare(job_path):
    filename = Path(__file__).with_suffix(".yaml").name
    candidates = [Path.cwd() / filename, Path(__file__).with_name(filename)]
    config_path = next((path for path in candidates if path.exists()), None)
    if config_path is None:
        raise ValueError("No ace-step.yaml found in current directory or beside runner. Run just install ace-step")
    config = read_yaml(config_path.read_text(encoding="utf-8-sig"))
    keys(config, {"version", "tool", "backend", "paths", "runtime", "defaults", "output", "identities"}, "config")
    if (config.get("version"), config.get("tool"), config.get("backend")) != (1, "ace-step", "official-python-api"):
        raise ValueError("Expected version 1, tool ace-step, backend official-python-api")
    paths = config["paths"]
    keys(paths, {"application", "python", "entrypoint", "models"}, "paths")
    runtime = config["runtime"]
    keys(runtime, {"device", "dit_model", "fallback_dit_model", "lm_model", "lm_backend", "offload_to_cpu", "offload_dit_to_cpu",
                   "quantization", "compile_model", "timeout_seconds"}, "runtime")
    if runtime.get("device") != "cuda" or runtime.get("dit_model") not in {"acestep-v15-xl-sft", runtime.get("fallback_dit_model")}:
        raise ValueError("Use CUDA and the declared XL SFT or explicit fallback DiT")
    if runtime.get("fallback_dit_model") != "acestep-v15-turbo":
        raise ValueError("The declared fallback must be acestep-v15-turbo")
    if runtime.get("lm_backend") not in ("vllm", "pt") or runtime.get("quantization") != "int8_weight_only":
        raise ValueError("Use the declared vllm/pt backend and INT8 weight-only quantization")
    if any(type(runtime.get(name)) is not bool for name in ("offload_to_cpu", "offload_dit_to_cpu", "compile_model")):
        raise ValueError("Runtime offload/compile settings must be booleans")
    if runtime["offload_dit_to_cpu"] and not runtime["offload_to_cpu"]:
        raise ValueError("runtime.offload_dit_to_cpu requires offload_to_cpu")
    if type(runtime.get("timeout_seconds")) is not int or runtime["timeout_seconds"] <= 0:
        raise ValueError("runtime.timeout_seconds must be a positive integer")

    job = read_job(job_path)
    settings = DEFAULTS.copy()
    settings["tool_options"] = DEFAULTS["tool_options"].copy()
    for layer in (config.get("defaults", {}), job["metadata"]):
        keys(layer, set(DEFAULTS) | {"version", "tool"}, "settings")
        if layer.get("version", 1) != 1 or layer.get("tool", "ace-step") != "ace-step":
            raise ValueError("Job version/tool mismatch")
        for key, value in layer.items():
            if key == "tool_options":
                keys(value, TOOL_OPTIONS, "tool_options")
                settings[key].update(value)
            elif key in DEFAULTS:
                settings[key] = value
        validate_settings(settings)

    blocks = job["blocks"]
    unsupported = set(blocks) & {"song-negative-prompt", "song-reference-audio"}
    if unsupported:
        raise ValueError("ACE-Step text2music version 1 does not support negative-prompt or reference-audio blocks")
    style = blocks.get("song-positive-style", "").strip()
    caption = "\n\n".join(part for part in (job["prompt"].strip(), style) if part)
    if not caption:
        raise ValueError("Provide a body caption or song-positive-style block")
    lyrics = blocks.get("song-lyrics", "").strip()
    options = settings["tool_options"]
    instrumental = options.get("instrumental", not lyrics)
    if instrumental and lyrics:
        raise ValueError("Remove song-lyrics when tool_options.instrumental is true")
    if not instrumental and not lyrics:
        raise ValueError("Provide song-lyrics or set tool_options.instrumental to true")
    options["instrumental"] = instrumental

    application = configured_path(config_path, paths["application"], "directory")
    identities = config.get("identities", {})
    keys(identities, {"source_revision", "model_revisions"}, "identities")
    if not re.fullmatch(r"[a-f0-9]{40}", identities.get("source_revision", "")):
        raise ValueError("source_revision must be an exact commit")
    revisions = identities.get("model_revisions", {})
    keys(revisions, {"main", "xl-sft"}, "model_revisions")
    if set(revisions) != {"main", "xl-sft"} or any(not re.fullmatch(r"[a-f0-9]{40}", value) for value in revisions.values()):
        raise ValueError("Both model revisions must be exact commits")
    head = subprocess.check_output(["git", "-C", application, "rev-parse", "HEAD"], text=True, timeout=30).strip()
    if head != identities["source_revision"]:
        raise ValueError("Configured source revision does not match checkout. Repair: just source ace-step")
    output = config["output"]
    keys(output, {"directory"}, "output")
    if not isinstance(output.get("directory"), str) or not output["directory"].strip():
        raise ValueError("output.directory must be a nonempty path")
    request = {
        "application": application,
        "models": configured_path(config_path, paths["models"], "directory", required=False),
        "runtime": runtime,
        "settings": settings,
        "caption": caption,
        "lyrics": lyrics,
        "title": job["title"],
        "prompt": job["prompt"],
        "config": str(config_path.resolve()),
        "job": str(Path(job_path).resolve()),
        "identities": identities,
    }
    root = (config_path.parent / output["directory"]).resolve()
    return request, configured_path(config_path, paths["python"]), configured_path(config_path, paths["entrypoint"]), root


def validate_audio(path):
    import soundfile as sf
    try:
        audio = sf.info(str(path))
    except sf.LibsndfileError as error:
        raise RuntimeError(f"Invalid ACE-Step WAV: {error}") from error
    if audio.format != "WAV" or audio.frames == 0 or audio.channels != 2 or audio.samplerate != 48000:
        raise RuntimeError("Invalid/empty ACE-Step WAV (expected stereo 48 kHz)")
    return audio


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
            print(json.dumps(request, indent=2) if args.dry_run else f"Valid ACE-Step job: {request['title']}")
            return
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", request["title"]).strip("-")[:60] or "untitled"
        output = root / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-ace-step-" + slug + "-" + uuid.uuid4().hex[:8])
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
        validate_audio(output / "audio.wav")
        print(f"Generated: {output / 'audio.wav'}")
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, yaml.YAMLError, subprocess.SubprocessError) as error:
        parser.exit(1, f"ACE-Step: {error}\n")


if __name__ == "__main__":
    main()
