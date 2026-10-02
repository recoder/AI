# ACE-Step 1.5 on native Windows

This workstation uses the official ACE-Step 1.5 Python API on native Windows. The quality-first preset selects the 4B XL SFT DiT and 1.7B planning LM with INT8 weight-only quantization and CPU offload. Both the auxiliary models and the DiT offload between phases so the VAE can decode on the GPU of a 16 GB card. The smaller 2B Turbo DiT is installed as a recovery option, but is not silently selected when quality mode fails.

The integration is intentionally limited to text-to-music. The Gradio UI, REST service, training/LoRA, reference audio, cover, repaint, extract, lego, and complete modes are outside version 1. Unsupported Markdown inputs fail before model loading.

## Install

From a normal PowerShell 7 shell:

```powershell
just plan-tool ace-step
just install ace-step
just models ace-step
just validate ace-step
```

Source, environment, and models are separate reconciliation phases. The official repository is checked out at the exact commit declared in `config/tools.yaml`; ordinary installation refuses to reset a different or modified checkout. `uv sync --frozen` uses that revision's official lock with Python 3.11.13 and its Windows PyTorch 2.7.1/CUDA 12.8 stack. Models use the exact Hugging Face revisions in `config/models.yaml`. Large files download in bounded resumable ranges and are promoted only after size, SHA-256, and safetensors-header checks.

The declared model set is approximately 28 GiB: shared text encoder, 1.7B LM, VAE, 2B Turbo fallback, and the four-shard XL SFT checkpoint. Allow additional space for the 3 GiB PyTorch wheel, environment, uv/Hugging Face caches, compilation cache, logs, and generated audio. At least 45 GiB free is a practical installation minimum.

## Generate

With the default workspace root:

```powershell
apps/ace-step-1.5/.venv/Scripts/python.exe bin/ace-step.py examples/song-jobs/ace-step-first-song.md --validate
apps/ace-step-1.5/.venv/Scripts/python.exe bin/ace-step.py examples/song-jobs/ace-step-first-song.md --dry-run
apps/ace-step-1.5/.venv/Scripts/python.exe bin/ace-step.py examples/song-jobs/ace-step-first-song.md
```

The runner selects `ace-step.yaml` from the invocation directory first, then beside the runner. Installation creates the latter only when absent and never overwrites local configuration. Relative config paths resolve beside the selected config. Validation and dry-run do not load PyTorch models or access the network.

Every generation receives a unique directory under `work/music/generated` by default. It preserves the original job, effective request, selected revisions, stdout/stderr, ACE-Step metadata/timings, and stereo 48 kHz `audio.wav`. Existing runs are never overwritten. Inference is forced offline after explicit model acquisition, and a timeout kills the backend process tree while preserving logs.

## Markdown flavor

Use the [shared song job format](../song-generation-jobs.md) and [tracked example](../../examples/song-jobs/ace-step-first-song.md).

| Input | ACE-Step mapping |
| --- | --- |
| H1 | Output label only; it is not conditioning. |
| Body | Primary ACE-Step `caption`. |
| `song-positive-style` | Appended to the body caption with a paragraph break. |
| `song-lyrics` | Literal `lyrics`; absent lyrics imply instrumental generation. |
| `seed` | Fixed generation seed, 0–2147483647. |
| `duration_seconds` | Requested duration, 10–600 seconds. |
| `steps` | DiT inference steps; XL SFT quality default is 50. |
| `guidance_scale` | XL SFT classifier-free guidance; default 7.0. |
| `temperature`, `top_k`, `top_p` | Planning-LM sampling controls. |
| `tool_options.bpm` | Optional integer tempo, 30–300. |
| `tool_options.keyscale`, `timesignature`, `vocal_language` | Optional musical/language metadata. |
| `tool_options.thinking` | Enable the 1.7B planning LM; quality preset defaults true. |
| `tool_options.shift`, `infer_method` | DiT timestep shift and `ode`/`sde` inference method. |
| `tool_options.instrumental` | Explicit instrumental flag; inferred true when lyrics are absent. |

The planner may refine caption and metadata, but `use_cot_lyrics` is disabled so the supplied lyric block remains the lyric input. A negative-prompt block is rejected: upstream's `lm_negative_prompt` affects the planner rather than serving as a documented DiT negative-conditioning input. Reference audio and non-text2music tasks are likewise rejected in version 1.

## Validation and recovery

`just status` reports declared source/runtime/model/config state. `just validate ace-step` and `just doctor` check the pinned clean source, actual imports, CUDA/BF16 operation, every declared artifact, and the example job without generating audio or downloading models.

- Source mismatch or changes: preserve the checkout and resolve it explicitly; normal reconciliation never resets it.
- Dependency/import failure: inspect `logs/ace-step-install-*.log`, then rerun `just install ace-step`; do not globally install packages.
- Interrupted/corrupt model: rerun `just models ace-step`; verified files skip, revision-named partials resume, and invalid completed bytes are quarantined.
- XL SFT memory pressure: close other GPU applications first. The declared 16 GB preset uses INT8, auxiliary-model offload, and `offload_dit_to_cpu: true`; omitting the latter left only 0.12 GB free for VAE decode in the first workstation test and forced an impractically slow CPU decode. Change to the declared 2B Turbo fallback explicitly only after preserving the failed quality-mode logs.
- Generation failure: inspect the unique run's `stderr.log`, `stdout.log`, and `request.json`. The backend never enables network fallback during inference.

CPU-only parser and model-transfer regression tests run with `just test-music`. A fresh-Windows installation remains required before declaring the integration fully portable.

## Pins and upstream references

Research and compatibility spike performed 2026-09-25 against the [official ACE-Step 1.5 repository](https://github.com/ACE-Step/ACE-Step-1.5), [installation guide](https://ace-step.github.io/ACE-Step-1.5/en/INSTALL), [inference API](https://ace-step.github.io/ACE-Step-1.5/en/INFERENCE), and [GPU compatibility guide](https://ace-step.github.io/ACE-Step-1.5/en/GPU_COMPATIBILITY). The source, main model repository, and XL SFT repository are immutable pins in the manifests. Normal bootstrap does not update them; any update must deliberately change the source/model revisions and re-run import, artifact, and audio validation.

## Workstation compatibility result (2026-10-02)

Tested on Windows 11 with an RTX 5070 Ti (16,303 MiB reported VRAM), NVIDIA driver 610.62, Python 3.11.13, PyTorch 2.7.1+cu128, and Triton Windows 3.3.1. The pinned XL SFT plus 1.7B LM preset generated a 30-second stereo 48 kHz IEEE-float WAV through the official importable Python API without a service. Diffusion used 50 steps; after DiT offload, the VAE reported 9.53 GB effective free VRAM and GPU decode finished in about 1.3 seconds. The first run without DiT offload had 0.12 GB free and timed out in CPU decode. That is a memory-configuration failure, not evidence that XL SFT is unsuitable for this GPU.

| Candidate | Local status | Decision |
| --- | --- | --- |
| 4B XL SFT + 1.7B LM | Generated; quality listening still pending | Preferred quality-first path. |
| 4B XL Turbo | Not acquired or compared | Faster candidate only; do not silently substitute. |
| 2B Turbo + 1.7B LM | Artifact acquired, not generated | Explicit low-memory fallback. |
| 2B base/SFT, XL base, 0.6B/4B LMs | Not acquired or compared | Defer selection until matched-prompt listening and memory tests. |
