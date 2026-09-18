"""Narrow, offline adapter to the pinned Wan2GP YuE2 pipeline."""
import argparse
import json
import os
from pathlib import Path
import sys
import types


def probe(application):
    application = Path(application)
    sys.path.insert(0, str(application))
    # Their package initializers eagerly load unrelated TTS handlers and video solvers.
    # Namespace packages expose only the pinned modules needed by this adapter.
    for name, relative in (("models.TTS", "models/TTS"), ("shared.utils", "shared/utils")):
        package = types.ModuleType(name)
        package.__path__ = [str(application / relative)]
        sys.modules[name] = package
    import torch
    import triton
    from mmgp import quant_router
    # The UI registers this checkpoint format globally; the standalone adapter must do so too.
    quant_router.register_handler("shared.qtypes.int8_convrot")
    from models.TTS.yue2.pipeline import YuE2Pipeline
    from shared.llm_engines.nanovllm.llm import LLM
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 is unavailable; repair NVIDIA driver and run just install yue")
    test = torch.ones((16, 16), dtype=torch.bfloat16, device="cuda")
    assert (test @ test).float().sum().item() == 4096
    print(f"CUDA OK: {torch.cuda.get_device_name(0)}, torch {torch.__version__}, Triton {triton.__version__}", flush=True)
    return YuE2Pipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    if args.probe:
        probe(args.probe)
        return
    request = json.loads(args.request.read_text(encoding="utf-8"))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    pipeline_type = probe(request["application"])
    import torch
    import soundfile as sf
    from mmgp import offload
    models = request["models"]
    torch.set_grad_enabled(False)
    pipeline = pipeline_type(ar_weights=models["ar"], acoustic_weights=models["acoustic"],
        tokenizer_path=models["tokenizer"], vae_weights=models["vae"], vae_config=models["vae_config"],
        dtype=torch.bfloat16, vae_dtype=torch.bfloat16, lm_decoder_engine="legacy")
    manager = offload.profile({"text_encoder": pipeline.text_encoder, "transformer": pipeline.transformer,
        "vae": pipeline.vae}, profile_no=request["runtime"]["profile"], quantizeTransformer=False,
        budgets=request["runtime"].get("budgets", {"transformer": 100, "text_encoder": 100, "*": 3000}))
    settings = request["settings"]
    try:
        result = pipeline.generate(input_prompt=request["lyrics"], alt_prompt=request["style"],
            seed=settings["seed"], duration_seconds=settings["duration_seconds"], sampling_steps=settings["steps"],
            guide_scale=settings["guidance_scale"], temperature=settings["temperature"], top_k=settings["top_k"],
            top_p=settings["top_p"], model_mode={"full": 0, "melody": 1, "off": 2}[settings["tool_options"]["planning"]],
            VAE_tile_size=request["runtime"]["vae_tile_size"], offloadobj=manager)
        if result is None:
            raise RuntimeError("YuE2 produced no audio")
        output = Path(request["output"])
        sf.write(output / "audio.wav", result["x"].detach().float().cpu().numpy().T, result["audio_sampling_rate"])
        (output / "generation.json").write_text(json.dumps({"truncated": pipeline.last_truncated,
            "sample_rate": result["audio_sampling_rate"]}, indent=2), encoding="utf-8")
        if pipeline.last_plan is not None:
            (output / "plan.json").write_text(json.dumps(pipeline.last_plan, indent=2), encoding="utf-8")
            (output / "plan.abc").write_text(pipeline.last_plan["abc"], encoding="utf-8")
    finally:
        pipeline.release()
        manager.unload_all()


if __name__ == "__main__":
    main()
