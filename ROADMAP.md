# Roadmap

Use unchecked tasks (`[ ]`) for planned work and checked tasks (`[x]`) for completed work. Keep completed tasks in their original section and update this file as work lands. Check installation tasks only after validating actual state.

Tool sections below are initial candidates drawn from `AGENTS.md`; inclusion does not mean a tool has been selected or installed. Add a section for each newly selected tool. Detailed documentation belongs in `docs/`.

## Repository and workspace foundation

- [x] Establish workstation design and agent instructions in `AGENTS.md`.
- [x] Create this roadmap with per-tool task lists.
- [x] Create `docs/` with a documentation index and a root README.
- [x] Add a basic `.gitignore` for credentials, runtime state, dependencies, and user work.
- [x] Initialize a local Git repository.
- [ ] Define YAML manifests for workspace paths, prerequisites, tools, models, repositories, and profiles.
- [ ] Implement shared configuration and state-detection helpers.
- [ ] Implement Stage 0 bootstrap and thin `just` recipes for Stage 1 reconciliation.
- [ ] Implement resumable model downloads and safe repository reconciliation.
- [ ] Add `just status`, `just doctor`, persistent logs, and an actionable bootstrap summary.
- [ ] Verify reruns and recovery from interrupted operations without affecting user work.
- [ ] Document setup, common commands, troubleshooting, and the reinstall workflow.

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
