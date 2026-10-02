"""Narrow offline backend for the pinned official ACE-Step 1.5 Python API."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def probe(application):
    sys.path.insert(0, str(Path(application)))
    import torch
    import torchao
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("CUDA/BF16 is unavailable; repair the NVIDIA driver and retry")
    test = torch.ones((16, 16), dtype=torch.bfloat16, device="cuda")
    assert (test @ test).float().sum().item() == 4096
    print(f"CUDA OK: {torch.cuda.get_device_name(0)}, torch {torch.__version__}, torchao {torchao.__version__}", flush=True)
    return AceStepHandler, LLMHandler, GenerationParams, GenerationConfig, generate_music


def generate(request):
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["ACESTEP_CHECKPOINTS_DIR"] = request["models"]
    api = probe(request["application"])
    AceStepHandler, LLMHandler, GenerationParams, GenerationConfig, generate_music = api
    runtime, settings, options = request["runtime"], request["settings"], request["settings"]["tool_options"]
    dit = AceStepHandler()
    status, ok = dit.initialize_service(
        project_root=request["application"], config_path=runtime["dit_model"], device=runtime["device"],
        compile_model=runtime["compile_model"], offload_to_cpu=runtime["offload_to_cpu"],
        offload_dit_to_cpu=runtime["offload_dit_to_cpu"],
        quantization=runtime["quantization"], prefer_source="huggingface",
    )
    if not ok:
        raise RuntimeError(f"DiT initialization failed: {status}")
    lm = LLMHandler()
    status, ok = lm.initialize(
        checkpoint_dir=request["models"], lm_model_path=runtime["lm_model"], backend=runtime["lm_backend"],
        device=runtime["device"], offload_to_cpu=runtime["offload_to_cpu"],
    )
    if not ok:
        raise RuntimeError(f"LM initialization failed: {status}")
    params = GenerationParams(
        task_type="text2music", caption=request["caption"], lyrics=request["lyrics"] or "[Instrumental]",
        instrumental=options["instrumental"], vocal_language=options.get("vocal_language", "unknown"),
        bpm=options.get("bpm"), keyscale=options.get("keyscale", ""), timesignature=options.get("timesignature", ""),
        duration=settings["duration_seconds"], inference_steps=settings["steps"], seed=settings["seed"],
        guidance_scale=settings["guidance_scale"], shift=options["shift"], infer_method=options["infer_method"],
        thinking=options["thinking"], lm_temperature=settings["temperature"], lm_top_k=settings["top_k"],
        lm_top_p=settings["top_p"], use_cot_caption=options.get("use_cot_caption", True),
        use_cot_metas=options.get("use_cot_metas", True), use_cot_lyrics=False,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[settings["seed"]], audio_format="wav")
    output = Path(request["output"])
    result = generate_music(dit, lm, params, config, save_dir=str(output))
    if not result.success or not result.audios:
        raise RuntimeError(result.error or result.status_message or "ACE-Step returned no audio")
    generated = Path(result.audios[0]["path"])
    final = output / "audio.wav"
    if generated.resolve() != final.resolve():
        shutil.copy2(generated, final)
    metadata = {
        "status": result.status_message,
        "sample_rate": result.audios[0].get("sample_rate"),
        "seed": result.audios[0].get("params", {}).get("seed", settings["seed"]),
        "source_audio": str(generated),
        "time_costs": result.extra_outputs.get("time_costs", {}),
        "lm_metadata": result.extra_outputs.get("lm_metadata", {}),
    }
    (output / "generation.json").write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=Path)
    parser.add_argument("--request", type=Path)
    args = parser.parse_args()
    if args.probe:
        probe(args.probe)
        return
    if not args.request:
        parser.error("provide --probe or --request")
    generate(json.loads(args.request.read_text(encoding="utf-8")))


if __name__ == "__main__":
    main()
