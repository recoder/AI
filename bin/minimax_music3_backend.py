"""Narrow offline Diffusers backend for MiniMax Music 3."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import tempfile


def probe():
    import torch
    import transformers
    import diffusers
    import accelerate
    from diffusers import ComponentsManager, ModularPipeline
    from diffusers.hooks.group_offloading import apply_group_offloading
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 unavailable; repair the NVIDIA driver and retry")
    test = torch.ones((16, 16), dtype=torch.bfloat16, device="cuda")
    assert (test @ test).float().sum().item() == 4096
    if diffusers.__version__ != "0.40.0":
        raise RuntimeError("Expected pinned Diffusers 0.40.0")
    print(f"CUDA OK: {torch.cuda.get_device_name(0)}, torch {torch.__version__}, diffusers {diffusers.__version__}, transformers {transformers.__version__}, accelerate {accelerate.__version__}", flush=True)
    return torch, ComponentsManager, ModularPipeline, apply_group_offloading


def make_local_index(model_root, output):
    model_root = Path(model_root).resolve()
    index = json.loads((model_root / "modular_model_index.json").read_text(encoding="utf-8"))
    for value in index.values():
        if isinstance(value, list) and len(value) == 3 and isinstance(value[2], dict):
            # The published index points back to the Hub even when loaded locally.
            value[2]["pretrained_model_name_or_path"] = str(model_root)
            value[2]["revision"] = None
    runtime_model = output / "runtime-model"
    runtime_model.mkdir()
    (runtime_model / "modular_model_index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return runtime_model


def probe_model(model_root):
    os.environ["HF_HUB_OFFLINE"] = "1"
    from diffusers import ModularPipeline
    with tempfile.TemporaryDirectory() as directory:
        runtime_model = make_local_index(model_root, Path(directory))
        pipe = ModularPipeline.from_pretrained(str(runtime_model), local_files_only=True)
        for name in ("language_model", "transformer", "vocoder", "tokenizer"):
            if str(pipe.get_component_spec(name).pretrained_model_name_or_path) != str(Path(model_root).resolve()):
                raise RuntimeError(f"Component {name} does not resolve to the local model directory")
    print("MiniMax Music 3 offline component paths OK", flush=True)


def available_memory_bytes():
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                    ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                    ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
                    ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                    ("available_extended_virtual", ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("Cannot read available RAM for MiniMax Music 3 safety check")
    return status.available_physical


def require_free_memory(gib, stage):
    available = available_memory_bytes()
    if available is not None and available < gib * 1024**3:
        raise RuntimeError(f"MiniMax Music 3 needs at least {gib} GiB free RAM {stage}; "
                           f"only {available / 1024**3:.1f} GiB is available. Close other memory-heavy work and retry.")


def generate(request):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    torch, ComponentsManager, ModularPipeline, apply_group_offloading = probe()
    require_free_memory(36, "before loading full BF16 components")
    runtime = request["runtime"]
    output = Path(request["output"])
    runtime_model = make_local_index(request["models"], output)
    manager = ComponentsManager()
    manager.enable_auto_cpu_offload(device=runtime["device"])
    pipe = ModularPipeline.from_pretrained(str(runtime_model), components_manager=manager, local_files_only=True)
    # Diffusers' bulk load holds every component in a temporary dict before registration.
    # On 64 GB Windows this can exhaust physical RAM; register the largest model first.
    for name in ("language_model", "transformer", "rvq_depth_decoder", "condition_encoder", "vocoder", "tokenizer", "scheduler"):
        require_free_memory(4, f"before loading {name}")
        print(f"Loading component: {name}", flush=True)
        pipe.load_components(names=name, dtype=torch.bfloat16, local_files_only=True)
        if getattr(pipe, name, None) is None:
            raise RuntimeError(f"Diffusers did not load {name}; inspect stderr.log for the component error")
        if name == "language_model":
            apply_group_offloading(pipe.language_model, onload_device=torch.device(runtime["device"]),
                                   offload_type=runtime["language_model_group_offload"],
                                   use_stream=runtime["group_offload_stream"])
        print(f"Loaded component: {name}", flush=True)
    settings = request["settings"]
    generator = torch.Generator(runtime["device"]).manual_seed(settings["seed"])
    result = pipe(prompt=request["prompt"], lyrics=request["lyrics"], audio_duration=settings["duration_seconds"],
                  num_inference_steps=settings["steps"], generator=generator, output_type="pt", output="audios")
    audio = result[0]
    import soundfile as sf
    sf.write(output / "audio.wav", audio.T.float().cpu().numpy(), pipe.sampling_rate, subtype="FLOAT")
    metadata = {"sample_rate": pipe.sampling_rate, "seed": settings["seed"], "duration_limit": settings["duration_seconds"],
                "steps": settings["steps"], "diffusers_version": request["identities"]["diffusers_version"]}
    (output / "generation.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--request", type=Path)
    parser.add_argument("--probe-model", type=Path)
    args = parser.parse_args()
    if args.probe:
        probe()
    elif args.probe_model:
        probe_model(args.probe_model)
    elif args.request:
        generate(json.loads(args.request.read_text(encoding="utf-8")))
    else:
        parser.error("provide --probe or --request")


if __name__ == "__main__":
    main()
