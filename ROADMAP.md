# Roadmap

Use unchecked tasks (`[ ]`) for planned work and checked tasks (`[x]`) for completed work. Keep completed tasks in their original section and update this file as work lands. Check installation tasks only after validating actual state.

Music generation is the first installation priority: YuE, ACE-Step, LeVo, and HeartMuLa. Define their unified job and runner interface before implementing installers. Other tool sections remain candidates from `AGENTS.md`. Detailed documentation belongs in `docs/`.

Order of work: job/runner contract → bootstrap and helper tools → shared runner implementation → music tool installation and adapters → validation and operator guides.

## Repository and workspace foundation

- [x] Establish workstation design and agent instructions in `AGENTS.md`.
- [x] Create this roadmap with per-tool task lists.
- [x] Create `docs/` with a documentation index and a root README.
- [x] Add a basic `.gitignore` for credentials, runtime state, dependencies, and user work.
- [x] Initialize a local Git repository.
- [x] Create the initial local commit and configure the GitHub remote.
- [x] Push `main` to `recoder/AI` using GitHub CLI authentication over HTTPS.
- [ ] Define YAML manifests for workspace paths, prerequisites, tools, models, repositories, and profiles.
- [x] Implement shared workspace configuration and helper-package state detection.
- [ ] Extend manifests and state detection to applications, models, repositories, and profiles.
- [ ] Implement Stage 0 bootstrap and thin `just` recipes for Stage 1 reconciliation.
- [ ] Implement resumable model downloads and safe repository reconciliation.
- [ ] Add `just status`, `just doctor`, persistent logs, and an actionable bootstrap summary.
- [ ] Verify reruns and recovery from interrupted operations without affecting user work.
- [ ] Document setup, common commands, troubleshooting, and the reinstall workflow.

## Bootstrap and helper tools

- [x] Define configurable workspace paths, including `bin/`, application environments, shared models/caches, and user work.
- [x] Declare the initial dependency set: Git, Git LFS, PowerShell 7, `just`, and `uv`.
- [x] Declare ffmpeg and 7-Zip; add build tools only when required by a selected tool.
- [ ] Implement unattended prerequisite detection and installation with targeted elevation and restart handling.
- [x] Implement directory reconciliation, package probes/install logic, and thin `just` commands.
- [ ] Configure shared cache environment variables and the Python runner environment.
- [x] Add helper-tool status/doctor checks and document recovery commands.
- [x] Document a detailed fresh-machine test procedure with prerequisite setup, privilege handling, rerun checks, and failure reporting.
- [x] Debug process timeouts, probe launch failures, literal arguments, manifest order/validation, PATH reruns, and WinGet error diagnostics with isolated regression checks.
- [ ] Expand Stage 0 to acquire PowerShell/App Installer and clone the repository when absent.
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
- [ ] Verify the full native install on a fresh Windows machine.
- [ ] Add an explicit update operation with compatibility validation.

## ACE-Step

- [ ] Choose the upstream generation/revision and verify Windows support, Python/GPU requirements, dependencies, models, and disk usage.
- [ ] Finalize the `ace-step` flavor and `bin/ace-step.py` adapter, including caption, lyrics, and supported tuning/negative controls.
- [ ] Declare isolated runtime, model/cache paths, version policy, and profile membership.
- [ ] Implement idempotent installation, resumable model acquisition, and separate updates.
- [ ] Validate a small generation through a Markdown job; integrate status and doctor checks.
- [ ] Document setup, supported inputs, and recovery in `docs/tools/ace-step.md`.

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

## MiniMax-Music

- [ ] Confirm the intended upstream project and selection; research official installation, Windows support, Python/CUDA requirements, model access, and disk usage.
- [ ] Choose and document native Windows or WSL execution based on upstream support.
- [ ] Declare revision, isolated environment, dependencies, profile membership, and shared model/cache paths.
- [ ] Implement resumable installation and model acquisition with credentials kept external.
- [ ] Validate dependencies, GPU access where required, and a small generation; integrate status and doctor checks.
- [ ] Document operation, output preservation, updates, and recovery in `docs/tools/minimax-music.md`.

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
