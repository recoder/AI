# MiniMax Music 3 on native Windows

This integration uses the official MiniMax Music 3 checkpoint through the Diffusers 0.40.0 modular pipeline. It is a quality-first, full-bfloat16 configuration for lyric-driven text-to-music. On a 16 GB GPU it uses automatic component CPU offload plus leaf-level language-model offload; expect much slower generation than a no-offload server. The selected checkpoint files live in the shared model directory, separate from the isolated Python runtime and generated songs.

## Install and generate

```powershell
just plan-tool minimax-music3
just install minimax-music3
just models minimax-music3
just validate minimax-music3

apps/minimax-music3/.venv/Scripts/python.exe bin/minimax-music3.py examples/song-jobs/minimax-music3-first-song.md --validate
apps/minimax-music3/.venv/Scripts/python.exe bin/minimax-music3.py examples/song-jobs/minimax-music3-first-song.md
```

The install uses the tracked `uv.lock` under `tools/minimax-music3/runtime` and creates `bin/minimax-music3.yaml` only if absent. Re-running install does not overwrite local settings or upgrade pinned packages. The model command uses the shared resumable transfer and verifies exact sizes, upstream LFS SHA-256 checksums for large files, and safetensors headers. Invalid completed files are quarantined rather than silently accepted. The model revision is immutable in `config/models.yaml`.

The selected 23 Diffusers-format files total 26.6 GiB; the full upstream repository is 57.4 GB because it also contains a separate native/server checkpoint layout. Allow at least 40 GiB for selected models, runtime, caches, and outputs. The development PC has an RTX 5070 Ti with 16 GB VRAM and 64 GB system RAM. The official low-VRAM method claims operation down to 8 GB VRAM. A native-Windows 10-second generation succeeded on this PC after loading components one at a time; bulk loading nearly exhausted its available system RAM. The runner therefore requires at least 36 GiB free physical RAM before loading and 4 GiB before each next component. Close other memory-heavy work if this guard fails.

The first smoke run produced a 9.996-second stereo 44.1 kHz float WAV (peak 1.0, RMS 0.073), with the job, effective request, logs, and generation metadata retained in its unique output directory. GPU memory remained below 5 GiB during the observed generation phase; roughly 14 GiB system RAM remained available after component loading. This proves feasibility on the test workstation, not audio quality or performance on other hardware. Subjective listening and a fresh-Windows reconstruction remain open.

## Job contract

The [tracked example](../../examples/song-jobs/minimax-music3-first-song.md) uses the [shared song-job syntax](../song-generation-jobs.md):

| Input | Mapping |
| --- | --- |
| Body plus `song-positive-style` | Music description / `prompt`, joined with a paragraph break. |
| `song-lyrics` | Literal lyrics. Section tags must occupy their own lines. |
| `seed` | Torch CUDA generator seed, default 42. |
| `duration_seconds` | Upper bound on duration, 10–300 seconds. The model may stop earlier. |
| `steps` | Flow-matching steps per acoustic chunk, default 30. |

Version 1 requires lyrics and rejects instrumental-only jobs, negative prompts, reference audio, and unrelated sampler controls. The backend keeps the upstream guidance defaults. It saves the vocoder's native stereo 44.1 kHz audio as float WAV; the SGLang reference server instead resamples to 32 kHz. The runner validates the WAV, saves the original job and effective request, captures stdout/stderr and metadata, and never overwrites a prior run. Inference is offline after model acquisition. A timeout terminates the process tree and preserves logs.

## Recovery and update policy

- Missing runtime or imports: rerun `just install minimax-music3`; inspect `logs/minimax-music3-install-*.log`.
- Interrupted or corrupt model: rerun `just models minimax-music3`; completed verified files skip and partial transfers resume.
- CUDA out of memory: close other GPU work, inspect the unique run's `stderr.log`, and verify both CPU-offload controls remain enabled. Do not silently substitute a smaller model.
- Slow generation: leaf-level language-model streaming is intentional on 16 GB VRAM; review system RAM and logs before changing the preset.
- Tokenizer/offload warnings: the pinned Transformers/Diffusers versions emit warnings about tokenizer regex and automatic placement estimates. They did not prevent the smoke run, but should be re-evaluated with future dependency updates.

Normal bootstrap never floats the model or runtime. Updating requires a deliberate review of the model revision, dependency pins/lock, GPU behavior, output format, and a new audio smoke test. A fresh-Windows reconstruction remains unverified.

## Upstream basis

Research checked 2026-10-02 against the [official model card and license](https://huggingface.co/MiniMaxAI/MiniMax-Music3), [official Diffusers pipeline documentation](https://huggingface.co/docs/diffusers/v0.40.0/en/api/pipelines/minimax_music3), and [Diffusers 0.40.0 release](https://github.com/huggingface/diffusers/releases/tag/v0.40.0). The model uses the MiniMax-Music3 Community License; read its conditions before commercial or hosted use. The published `modular_model_index.json` names Hub paths even in a local checkout, so the backend preserves the original pinned file and writes a run-local index pointing at the shared model directory for offline loading.
