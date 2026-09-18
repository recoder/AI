# YuE2 on native Windows

This workstation uses YuE2 through a pinned Wan2GP music pipeline, in its own `uv` environment. It does not require WSL. The older original-YuE checkout, if present, is preserved and is no longer the configured backend.

## Install

First complete [bootstrap](../bootstrap.md). From the repository in a normal PowerShell 7 shell:

```powershell
just plan-tool yue
just install yue
just models yue
just validate yue
```

Installation prepares the exact source revision in `config/tools.yaml`, syncs the frozen `tools/yue/uv.lock`, creates an untracked `<workspace>/bin/yue.yaml` if absent, and checks pipeline imports plus CUDA/BF16 matrix multiplication. Model acquisition is separate and downloads only the five artifacts declared in `config/models.yaml`. Files with correct sizes and declared hashes are skipped; interrupted downloads can resume. The declared HTTP transport uses bounded 64 MiB ranges, retries and persisted partial bytes, verifies range responses, and reports progress; verified complete artifacts are skipped. Existing runner configuration and modified or conflicting source checkouts are preserved. Bootstrap currently reconciles helpers only; run these explicit tool commands after bootstrap.

The selected stack is Python 3.11.13, PyTorch 2.10/CUDA 13.0, Triton Windows 3.6, MMGP 3.8, and the legacy AR engine with PyTorch SDPA attention. An NVIDIA GPU and compatible driver are required. The development target is RTX 5070 Ti, 16 GB VRAM. MMGP profile 4 manages model loading and a 256-frame VAE tile limits decoding memory. The 16 GB preset budgets 5000 MiB for the text encoder, 4000 MiB for the acoustic transformer, and 3000 MiB for other modules. Configure `runtime.budgets` in the local runner config for a different machine; these are model-loading limits, not a total VRAM cap. Other GPUs and long songs need their own validation.

Models occupy approximately 4.27 GiB. Allow additional space for the environment (including the large PyTorch wheel), uv cache, Windows Triton compilation cache, RAM/pagefile, source, and generated audio. Keep at least 15 GiB free for initial installation; cache and longer outputs can require more. This is a music-only adapter, not a full Wan2GP UI installation.

## Generate a song

The interpreter belongs to the application environment. With the default workspace root:

```powershell
apps/wan2gp/.venv/Scripts/python.exe bin/yue.py examples/song-jobs/yue-first-song.md --validate
apps/wan2gp/.venv/Scripts/python.exe bin/yue.py examples/song-jobs/yue-first-song.md --dry-run
apps/wan2gp/.venv/Scripts/python.exe bin/yue.py examples/song-jobs/yue-first-song.md
```

For an overridden workspace root, use its `<workspace>/apps/wan2gp/.venv/Scripts/python.exe` and `<workspace>/bin/yue.py`. The job may be anywhere. The runner first selects `yue.yaml` in the invocation directory, then beside itself. The first existing config wins; an invalid selected config fails rather than silently falling back. Relative config paths resolve beside that config. Installation never overwrites an existing `yue.yaml`; use the tracked `bin/yue.example.yaml` as a reference when changing it.

Validation and dry-run parse the job, resolve the selected config and local paths, and check settings without importing PyTorch or loading models. Generation launches the configured backend with an argument list, not shell interpolation, and prohibits Hugging Face/Transformers network downloads during inference.

Each call creates a unique directory under the configured output directory, normally `<workspace>/work/music/generated`. It preserves `job.md`, effective `request.json` including selected config/job paths, stdout/stderr logs, `audio.wav`, generation metadata and the generated plan where available. Existing outputs are never overwritten. The WAV must be nonempty stereo 48 kHz. A duration setting caps semantic tokens; a song may end earlier. Check `generation.json` for truncation information. Failure/timeout preserves the directory and logs. Generation timeout defaults to 1800 seconds and kills the backend process tree on Windows.

## Markdown flavor

Use the [shared job format](../song-generation-jobs.md) and [example](../../examples/song-jobs/yue-first-song.md).

| Input | YuE2 mapping |
| --- | --- |
| H1 | Song title and output label; excluded from conditioning. |
| Body | Style prompt when no explicit style block exists; otherwise retained creative context. |
| `song-positive-style` | Literal style conditioning (`alt_prompt`). |
| `song-lyrics` | Required literal lyrics (`input_prompt`), typically section-labeled. |
| `seed` | Random seed, nonnegative integer up to 2147483647. |
| `duration_seconds` | Maximum requested duration, 1–600 seconds; start with 30. |
| `steps` | Acoustic flow sampling steps, positive integer; default 32. |
| `guidance_scale` | Acoustic/semantic guidance; default 1.0. |
| `temperature`, `top_k`, `top_p` | AR sampling controls; defaults 1.0, 100, 0.95. |
| `tool_options.planning` | `full`, `melody`, or `off`; default `full`. |

Settings precedence is adapter defaults, selected config defaults, then job frontmatter. `tool_options` merges per key. Unknown fields, duplicate YAML keys/fences, unsafe YAML object tags, multiple H1 titles, unclosed fences, negative prompts and reference-audio blocks fail explicitly. Code blocks contain data and never execute. The parser uses YAML 1.2 boolean spellings so `planning: off` remains a string.

Reference/humming/score modes, LoRAs, advanced custom sampling, original YuE-v1 and a full Wan2GP UI are outside this initial adapter. Separate additions need their own model/config/input mappings.

## Validation and recovery

`just status` summarizes source/environment/artifact-size/config presence. `just validate yue` checks the pinned clean source, actual pipeline imports and CUDA/BF16 operation, artifact sizes and SHA-256 hashes plus safetensors headers, and the example job against the selected config. `just doctor` includes these deeper checks. None of these downloads missing models. Audio generation remains a separate smoke test.

- Missing Python/build: verify `uv python list`, then `just install yue`. The pinned Python build must be obtainable by the installed uv; update uv deliberately if its interpreter catalogue is too old.
- Dependency/import failure: inspect the installation transcript in `<workspace>/logs`, then rerun `just install yue`. The lock defines dependencies; do not globally pip-install fixes.
- Source mismatch/local modifications: preserve the checkout and resolve deliberately; ordinary installation refuses to switch or reset it.
- Model download failure/corruption: retry `just models yue`; sizes/hashes decide what is complete. Credentials, if needed, come from the environment; never commit tokens.
- CUDA/BF16 failure: repair the NVIDIA driver and verify `nvidia-smi`, then retry validation. Detection alone does not prove inference works.
- Generation failure: read the preserved `stderr.log` and `stdout.log`. For memory pressure, close other GPU applications, reduce duration, or use profile 5 after testing. The first quantized call may compile Triton kernels and take longer.
- Job/config failure: inspect dry-run and the selected config path. A current-directory `yue.yaml` intentionally takes precedence.

CPU-only parser/translation and HTTP resume tests: `just test-music` after installation. These use fixtures and a local HTTP server, and perform no model downloads or GPU operations. Source safety/bootstrap tests: `just test`. A clean-machine reinstall test is still required; successful development-machine execution does not replace it.

## Upstream references and version policy

Research checked 2026-09-18: [Wan2GP Windows installation](https://github.com/deepbeepmeep/Wan2GP/blob/bfaff285463ef6124c2357136e8d36c6c93c0fb2/README.md), [pinned YuE2 pipeline](https://github.com/deepbeepmeep/Wan2GP/blob/bfaff285463ef6124c2357136e8d36c6c93c0fb2/models/TTS/yue2/pipeline.py), [pinned TTS model repository](https://huggingface.co/DeepBeepMeep/TTS/tree/5020589aa562cea206a25eea208d7cbb1f6efae7), and [official YuE project](https://github.com/multimodal-art-projection/YuE). Wan2GP is the Windows backend, while YuE2 is the model generation selected here.

The adapter imports the narrow pipeline and bypasses package initializers that eagerly load unrelated handlers/solvers; it does not edit upstream source. It also registers the upstream INT8 ConvRot handler that the full UI normally registers before loading checkpoints. Source/model revisions and the Python dependency lock are intentional pins. Normal install/model commands do not upgrade them. A future update changes declarations/lock explicitly and requires import, artifact and audio smoke validation. There is no automatic `update yue` command yet.



## Development-workstation validation (2026-09-18)

Installation reruns reused the pinned source and frozen environment; model reruns verified and skipped all five complete artifacts. `just test`, `just test-music` (12 CPU-only checks), and full `just doctor` passed. A Markdown job generated `audio.wav` on the RTX 5070 Ti/16 GB workstation: stereo, 48 kHz, approximately 30 seconds, nonzero RMS 0.138 and peak 0.711. Score planning reached its end token; semantic generation reached the requested 750-token duration cap (`semantic: true` in truncation metadata). This validates a capped clip, not complete-song termination or subjective quality. The successful run took about three minutes with the declared loading budgets. Fresh-machine installation remains unverified.

The operator also confirmed a second sample worked: an original 45-second synth-pop job rendered to stereo 48 kHz MP3 under the ignored workspace tmp directory. That sample reached its duration cap as expected.
