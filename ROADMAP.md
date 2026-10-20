# Roadmap

Use unchecked tasks (`[ ]`) for planned work and checked tasks (`[x]`) for completed work. Keep completed tasks in their original section and update this file as work lands. Check installation tasks only after validating actual state.

Music generation is the first installation priority: YuE, ACE-Step, LeVo, and HeartMuLa. YuE and ACE-Step 1.5 have working native adapters; comparative ACE-Step listening and fresh-Windows validation remain open. Define each tool's unified job mapping before implementing its installer. Other tool sections remain candidates from `AGENTS.md`. Detailed documentation belongs in `docs/`.

Order of work: job/runner contract → bootstrap and helper tools → shared runner implementation → music tool installation and adapters → validation and operator guides.

## Repository and workspace foundation

- [x] Establish workstation design and agent instructions in `AGENTS.md`.
- [x] Create this roadmap with per-tool task lists.
- [x] Create `docs/` with a documentation index and a root README.
- [x] Add a basic `.gitignore` for credentials, runtime state, dependencies, and user work.
- [x] Initialize a local Git repository.
- [x] Create the initial local commit and configure the GitHub remote.
- [x] Push `main` to `recoder/AI` using GitHub CLI authentication over HTTPS.
- [x] Define manifests for workspace paths, prerequisites, tools, models, repositories, and profiles.
- [x] Implement shared workspace configuration and helper-package state detection.
- [x] Extend manifests and state detection to applications, models, repositories, and profiles.
- [x] Implement Stage 0 bootstrap and thin `just` recipes for Stage 1 reconciliation.
- [x] Implement resumable model downloads and safe repository reconciliation.
- [x] Add `just status`, `just doctor`, persistent logs, and an actionable bootstrap summary.
- [ ] Verify reruns and recovery from interrupted operations without affecting user work.
- [ ] Document setup, common commands, troubleshooting, and the reinstall workflow.

## Bootstrap and helper tools

- [x] Define configurable workspace paths, including `bin/`, application environments, shared models/caches, and user work.
- [x] Declare the initial dependency set: Git, Git LFS, PowerShell 7, `just`, and `uv`.
- [x] Declare ffmpeg and 7-Zip; add build tools only when required by a selected tool.
- [x] Implement unattended prerequisite detection and installation with targeted elevation and restart handling.
- [x] Implement directory reconciliation, package probes/install logic, and thin `just` commands.
- [x] Configure shared cache environment variables and isolated Python runner environments.
- [x] Add helper-tool status/doctor checks and document recovery commands.
- [x] Document a detailed fresh-machine test procedure with prerequisite setup, privilege handling, rerun checks, and failure reporting.
- [x] Debug process timeouts, probe launch failures, literal arguments, manifest order/validation, PATH reruns, and WinGet error diagnostics with isolated regression checks.
- [x] Expand Stage 0 to acquire PowerShell/App Installer and clone the repository when absent.
- [ ] Verify missing-package installations in a clean Windows environment; current-machine checks exercise skip/rerun behavior.
- [x] Record operator-confirmed fresh-machine ffmpeg installation and recovery from the 7-Zip elevation failure using a targeted administrator install and normal-shell retry (2026-09-18).

## Shared music job format and runners

- [x] Document Markdown jobs: YAML tuning parameters, H1 song title, prose prompt, and named data fences.
- [x] Document per-tool flavors and a common runner/configuration contract in `docs/song-generation-jobs.md`.
- [x] Define current-directory-first YAML lookup with fallback beside the Python runner in `<workspace>/bin/`.
- [ ] Confirm each flavor's supported fields and upstream mappings against the selected revision before installing its tool.
- [x] Implement shared parsing, config selection, default precedence, path resolution, and actionable validation for the first adapter.
- [ ] Implement a Python runner for each tool in `bin/`, with local YAML configs and tracked example templates.
- [x] Add YuE2 `--validate` and `--dry-run` without loading models or starting inference.
- [x] Test parsing, config lookup, defaults, unsupported inputs, paths with spaces, and translation without requiring GPU installs.
- [x] Preserve job inputs and generation outputs; record effective settings and failure logs for every YuE2 run.

## YuE

- [x] Research original YuE and YuE2, compare native Windows backends and record the initial GPU/WSL preflight.
- [x] Select Wan2GP YuE2 on native Windows and pin source/model revisions and a frozen dependency lock.
- [x] Prepare isolated Python 3.11.13 runtime with PyTorch 2.10/CUDA 13.0, MMGP 3.8 and Triton Windows 3.6.
- [x] Verify pipeline imports and CUDA/BF16 matrix multiplication on RTX 5070 Ti (16 GB).
- [x] Implement shared safe Markdown/YAML parsing and `bin/yue.py`, current-directory-first config lookup, defaults, validation/dry-run, unique output preservation and logs.
- [x] Pass CPU-only regression checks for parsing, malformed inputs, config lookup, paths with spaces, precedence and literal conditioning.
- [x] Declare five shared model artifacts with exact sizes/revisions and weight hashes; implement separate resumable downloads and offline validation.
- [x] Add native source/environment/model/config state reporting and deep YuE2 checks to doctor.
- [x] Document installation, job flavor, generation, storage and recovery in `docs/tools/yue.md`.
- [x] Complete model acquisition and verify all five artifact hashes on the development workstation.
- [x] Validate a 30-second stereo 48 kHz clip through the native Markdown runner on RTX 5070 Ti, 16 GB (2026-09-18); record the duration-cap truncation.
- [x] Upgrade the frozen YuE Transformers runtime past the reviewed advisories; verify imports, CUDA, full generation, and byte-identical output against the prior baseline (2026-10-05).
- [ ] Verify the full native install on a fresh Windows machine.
- [ ] Add an explicit update operation with compatibility validation.

## ACE-Step

Target the official ACE-Step 1.5 native-Windows stack rather than the legacy ACE-Step generation. Start with the upstream Python inference API and a conservative text-to-music scope; defer the Gradio UI, training/LoRA, cover/repaint/extract/lego/complete modes, and third-party packaged builds until the basic adapter is reproducible. Optimize defaults for output quality rather than generation speed. The initial development target is the existing RTX 5070 Ti (16 GB): test the 4B **XL SFT** DiT with the 1.7B language model as the preferred configuration using INT8 and CPU offload. Retain XL Turbo as the faster 4B alternative and 2B Turbo with the 0.6B or 1.7B language model as the lower-memory fallback. Final selection remains contingent on the compatibility spike and comparative listening tests.

### 1. Pin the supported stack

- [x] Run a native-Windows compatibility spike against the official `ACE-Step/ACE-Step-1.5` repository; record the tested source commit, release/API version, Python version, PyTorch/CUDA build, Triton requirement, driver, and exact install commands.
- [ ] Compare the official 2B turbo/base/SFT and 4B XL turbo/base/SFT DiT checkpoints plus the 0.6B/1.7B/4B language models for audio quality, prompt/lyric adherence, diversity, artifacts, VRAM, RAM, generation time, download size, and license; select and justify the quality-first default and fallback pairs using repeatable prompts and seeds.
- [x] Confirm that the selected stack works through the importable inference API without starting Gradio or a persistent service, and identify a stable upstream entry point that can be called with an argument list or narrow local shim.
- [x] Inventory every required model artifact with immutable Hugging Face revisions, paths, byte sizes, and hashes; confirm whether gated access or credentials are required.
- [x] Record a 16 GB VRAM preset and lower-memory recovery settings, including CPU offload/quantization behavior, batch size 1, VAE decode fallback, and any Windows-specific Triton limitations.
- [ ] Write the decision and compatibility matrix in `docs/tools/ace-step.md` before freezing manifests or dependency locks.

### 2. Finalize the job contract

- [x] Map the Markdown body and `song-positive-style` deterministically to ACE-Step `caption`, and map `song-lyrics` literally to `lyrics`; define instrumental behavior without silently rewriting user input.
- [x] Confirm and document supported version-1 fields and ranges for seed, duration, inference steps, guidance, BPM, key, time signature, vocal language, LM thinking/refinement, and output format against the pinned API.
- [x] Decide whether `song-negative-prompt` has a real DiT conditioning mapping in the pinned API; reject it explicitly if only the language-model planner exposes a differently scoped negative prompt.
- [x] Keep version 1 to `text2music`; reject reference-audio blocks and editing task types until separate contracts and preservation tests exist.
- [ ] Add a tracked `examples/song-jobs/ace-step-first-song.md` plus parser/translation fixtures covering instrumental and lyric-driven jobs, malformed fields, unsupported blocks, and paths with spaces.

### 3. Declare and reconcile state

- [x] Add `ace-step` to `config/tools.yaml` with the pinned source revision, native runtime, exact Python version, isolated environment, model path, safe defaults, timeout, and the selected 16 GB preset.
- [x] Add the selected model artifacts to `config/models.yaml`, stored under `models/music/ace-step` and acquired separately from the source/runtime install through the existing resumable verified-download subsystem.
- [x] Add `ace-step` to the `music` profile only after targeted install/model/validation commands work independently; ensure reruns skip verified source, environment, and model state.
- [x] Create `tools/ace-step/` install, state, model, validation, and planning scripts using the existing application helpers; freeze Python dependencies and preserve modified/conflicting source checkouts.
- [ ] Define an explicit update operation that changes source/model pins and the dependency lock reviewably; normal bootstrap must never float to a newer ACE-Step release or checkpoint.

### 4. Implement the runner

- [x] Implement `bin/ace-step.py`, `bin/ace-step.example.yaml`, and a narrow backend entry point using the shared safe job parser/config precedence and current-directory-first config lookup established by YuE.
- [x] Add `--validate` and `--dry-run` paths that do not import PyTorch, initialize CUDA, load models, or access the network.
- [x] Preserve each job, effective request, selected revisions/config paths, seeds, upstream metadata, timings, stdout/stderr, and all generated audio in a unique output directory; never overwrite an existing run.
- [x] Enforce offline inference after explicit model acquisition, a bounded timeout with process-tree cleanup, and output checks for nonempty stereo 48 kHz audio in the selected format.

### 5. Validate and document

- [ ] Add CPU-only regression tests for parsing, mapping, defaults/precedence, unsupported controls, malformed jobs, config lookup, path handling, command construction, and output-directory preservation.
- [x] Extend `just status` with ACE-Step source/runtime/model/config summaries and `just doctor` with pinned-source, model hash/header, import, CUDA/BF16, and example-job checks; neither command downloads models.
- [ ] Add an exact frozen-environment audit to `just doctor`, beyond the current import/CUDA probe and idempotent `uv sync --frozen` install.
- [ ] Generate and inspect matched instrumental and lyric-driven clips with XL SFT, XL Turbo, and the lower-memory fallback on the RTX 5070 Ti; record elapsed time, peak VRAM where practical, audio format/rate/channels/duration, seed reproducibility, prompt/lyric adherence, audible artifacts, and comparative quality findings.
- [x] Generate a first 30-second lyric-driven XL SFT + 1.7B LM clip on the RTX 5070 Ti (2026-10-02); confirm stereo 48 kHz IEEE-float WAV and GPU VAE decode with 9.53 GB effective free VRAM after DiT offload. Comparative listening remains separate.
- [ ] Verify install/model/validate reruns and recovery from an interrupted model download, then complete one fresh-Windows installation before declaring ACE-Step support complete.
- [x] Finish `docs/tools/ace-step.md` with installation, job fields, selected models, storage/disk budget, generation examples, update policy, failure recovery, deferred features, and links to the pinned official sources.

## LeVo

- [ ] Choose the SongGeneration/LeVo revision and verify Windows/WSL support, dependencies, GPU requirements, models, and disk usage.
- [ ] Finalize the `levo` flavor and `bin/levo.py` adapter, including structured song inputs and optional reference audio where supported.
- [ ] Declare isolated runtime, model/cache paths, version policy, and profile membership.
- [ ] Implement idempotent installation, resumable model acquisition, and separate updates.
- [ ] Validate a small generation through a Markdown job; integrate status and doctor checks.
- [ ] Document setup, supported inputs, and recovery in `docs/tools/levo.md`.

## HeartMuLa

- [ ] Verify official heartlib revision, Windows/WSL support, runtime/GPU requirements, model/codec dependencies, and disk usage.
- [ ] Finalize the `heartmula` flavor and `bin/heartmula.py` adapter, including lyrics, style tags, and supported sampling settings.
- [ ] Declare isolated runtime, model/cache paths, version policy, and profile membership.
- [ ] Implement idempotent installation, resumable model acquisition, and separate updates.
- [ ] Validate a small generation through a Markdown job; integrate status and doctor checks.
- [ ] Document setup, supported inputs, and recovery in `docs/tools/heartmula.md`.

## WavePrompt

Moved to [optional manual installations](docs/optional-manual-installations.md) on 2026-10-20 because it uses YuE2, which is already available in this workstation. No managed bootstrap, runner, or service integration is planned.

- [x] Review and locally test WavePrompt 1.2.3 on RTX 5070 Ti; verify an offline stereo 48 kHz/24-bit loop (2026-10-20). Retain the local installation and generated work as an optional manual tool.

## llama.cpp and local model management

- [ ] Plan a local llama.cpp installation: review official Windows/CUDA support, choose a version and binary/build approach, and identify dependencies and disk requirements.
- [ ] Evaluate and select tools to manage local models for llama.cpp, including model discovery, GGUF compatibility/quantization selection, resumable downloads, inventory, and model switching.
- [ ] Declare the runtime, selected management tools, initial models, profile membership, and shared storage under `models/llm/`; avoid duplicate model copies and preserve manually added models.
- [ ] Implement idempotent installation and configuration with explicit updates; validate GPU inference, server health where applicable, and model-management operations through status and doctor checks.
- [ ] Document installation, model management, operation, updates, and recovery in `docs/tools/llama-cpp.md`.

## Ollama

- [ ] Confirm selection and research current official Windows installation, GPU requirements, disk usage, and unattended operation.
- [ ] Declare installation/version policy, profile membership, and shared model storage.
- [ ] Implement idempotent installation, configuration, and separate updates.
- [ ] Declare initial models and support resumable acquisition without duplicate downloads.
- [ ] Validate executable, server health, and a small inference request; integrate status and doctor checks.
- [ ] Document installation, model management, updates, and recovery in `docs/tools/ollama.md`.

## Open WebUI

- [ ] Confirm selection and research current official requirements and native Windows versus container support.
- [ ] Declare runtime/version policy, dependencies, persistent data paths, and profile membership.
- [ ] Implement idempotent installation and configuration, including connection to the selected inference backend.
- [ ] Preserve user accounts, settings, and conversation data across reruns and updates; keep credentials external.
- [ ] Validate startup, health, and backend connectivity; integrate status and doctor checks.
- [ ] Document operation, updates, and recovery in `docs/tools/open-webui.md`.

## ComfyUI

- [ ] Confirm selection and research current official Windows support, Python/PyTorch/CUDA compatibility, dependencies, and disk usage.
- [ ] Declare repository revision, isolated environment, profile membership, and shared model/cache paths.
- [ ] Implement idempotent installation and configuration with separate updates that preserve local workflows.
- [ ] Declare initial image models and configure shared model discovery.
- [ ] Validate imports, GPU availability, startup, and a minimal workflow; integrate status and doctor checks.
- [ ] Document model paths, workflows, updates, and recovery in `docs/tools/comfyui.md`.

## MiniMax Music 3

Target the official `MiniMaxAI/MiniMax-Music3` checkpoint through Diffusers 0.40.0's modular pipeline. Prefer full BF16 quality with CPU/language-model offload on the 16 GB RTX 5070 Ti; do not select the unrelated MiniMax-M3 coding model or download duplicate native/server checkpoint files.

- [x] Confirm the official model, Diffusers entry point, community license, CUDA/BF16 requirements, selected artifact sizes, and published low-VRAM path.
- [x] Choose a native-Windows compatibility spike with an isolated, frozen Diffusers runtime; avoid a persistent SGLang service for the first adapter.
- [x] Declare the pinned runtime, immutable model revision, 26.6 GiB Diffusers-only artifact set, and shared model/cache paths.
- [x] Add resumable acquisition, package reconciliation, job translation, logs, and basic CUDA/import and parser validation.
- [x] Complete a lyric-driven 10-second generation on the RTX 5070 Ti; verify stereo 44.1 kHz WAV, non-silence, duration, memory behavior, and preserved run metadata.
- [x] Verify idempotent installer/model reruns and add MiniMax Music 3 to the music profile so `just status` and `just doctor` include it.
- [ ] Exercise an interrupted MiniMax model transfer and confirm partial-file resume on a fresh download.
- [ ] Listen against matched ACE-Step and YuE prompts; assess lyric fidelity, artifacts, structure, RAM/VRAM usage, and whether quality justifies the slower offload path.
- [ ] Run a fresh-Windows reconstruction and add an explicit reviewable update procedure.
- [x] Document operation, output preservation, update policy, license pointer, and recovery in `docs/tools/minimax-music3.md`.

## Hermes-related tooling

- [ ] Identify the intended application and official upstream project before choosing an installation approach.
- [ ] Research Windows support, runtime/GPU requirements, dependencies, model storage, and unattended operation.
- [ ] Declare revision, isolated runtime, paths, and profile membership.
- [ ] Implement idempotent installation, configuration, and separate updates while preserving user work.
- [ ] Validate a minimal supported operation; integrate status and doctor checks.
- [ ] Add tool-specific documentation under `docs/tools/` once the application is selected.

## Transcription and audio tooling

- [ ] Select concrete applications and split them into individual tool sections.
- [ ] Research official Windows support, runtime/GPU requirements, system dependencies, model formats, and disk usage.
- [ ] Declare versions, isolated environments, profile membership, and shared audio model/cache paths.
- [ ] Implement idempotent installation and resumable model acquisition.
- [ ] Validate a short audio sample; integrate status and doctor checks.
- [ ] Document operation, preservation of recordings and outputs, updates, and recovery under `docs/tools/`.
