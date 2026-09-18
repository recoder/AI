# AGENTS.md

## Project Mission

This repository defines a **reproducible, self-hosted AI workstation for Windows**.

Its purpose is to let the user rebuild a freshly installed Windows machine with as little manual work as practical:

1. Install a small bootstrap dependency set.
2. Run `bootstrap.ps1`.
3. Clone or initialize this repository.
4. Run one or a small number of `just` commands.
5. Leave the machine unattended while the workspace is reconstructed.

Treat this repository as more than an installer. It is the **version-controlled specification of the workstation**.

The Windows installation itself should be considered disposable.

---

# Core Design Principles

## 1. Declarative State Over Procedural Scripts

Prefer configuration files that describe desired state instead of hard-coding that state inside installation logic.

Good:

```yaml id="ua556z"
tools:
  comfyui:
    repo: https://github.com/comfyanonymous/ComfyUI.git
    path: apps/comfyui
    python: "3.12"
```

Less desirable:

```powershell id="za7otm"
git clone https://github.com/comfyanonymous/ComfyUI.git D:\AI\apps\comfyui
cd D:\AI\apps\comfyui
...
```

Scripts should mostly **interpret manifests and reconcile actual state with desired state**.

Keep configuration in data files when it represents state. Move something into code only when it genuinely represents behavior.

---

## 2. Idempotency Is Mandatory

Every operation must be safe to rerun.

All of these should be valid:

```powershell id="9seuej"
just bootstrap
just bootstrap
just bootstrap
```

A second or third invocation should normally detect existing state, validate it, and skip completed work rather than create duplicates or fail.

A failed bootstrap must also be resumable.

Example:

* 15 tools install successfully.
* Hugging Face becomes unavailable.
* A model download fails.
* The user reruns `just bootstrap`.
* Already completed operations are detected and skipped.
* Bootstrap resumes from the missing state.

Do not rely only on marker files such as:

```text id="2wgpgg"
.install-complete
```

Prefer checking actual state.

Examples:

* executable exists and reports a usable version
* Git repository exists and has the expected remote
* Python environment exists and imports required packages
* model files exist and pass basic sanity checks

Marker files may be used as optimization hints, but never as the sole source of truth.

---

## 3. Separate Machine, Applications, Models, and User Work

Treat these as different classes of state.

### Machine prerequisites

Examples:

* Git
* Git LFS
* PowerShell 7
* `just`
* `uv`
* Node.js
* ffmpeg
* 7-Zip
* CMake
* Visual Studio Build Tools
* NVIDIA tooling
* Docker or Podman
* WSL

These belong to machine/bootstrap configuration.

### Applications

Examples:

* ComfyUI
* Ollama
* MiniMax-Music
* Open WebUI
* Hermes-related tooling
* inference servers
* transcription tools

Applications should live under a predictable workspace hierarchy.

### Models

Models are **reconstructible data/cache**.

Keep them outside application directories whenever practical.

Prefer structures such as:

```text id="90gmne"
models/
    llm/
    image/
    music/
    audio/
    embeddings/
    whisper/
```

and shared caches such as:

```text id="99opef"
cache/
    huggingface/
    torch/
    pip/
    uv/
```

Applications should reference shared models or caches through configuration, environment variables, symbolic links, or junctions where practical.

Avoid downloading duplicate model copies for different applications.

### User work

Keep user-created repositories and content conceptually separate from installed tools.

Examples:

```text id="4yt4i9"
work/
    repos/
    experiments/
    music/
    prompts/
    agents/
```

Bootstrap code may clone or initialize these repositories.

Bootstrap code must **never treat user work as disposable installation state**.

---

# Repository Architecture

The intended structure is approximately:

```text id="u2ho7k"
ai-workspace/
│
├── AGENTS.md
├── README.md
├── bootstrap.ps1
├── justfile
│
├── config/
│   ├── workspace.yaml
│   ├── packages.yaml
│   ├── tools.yaml
│   ├── models.yaml
│   ├── repos.yaml
│   └── profiles.yaml
│
├── scripts/
│   ├── common.ps1
│   ├── directories.ps1
│   ├── packages.ps1
│   ├── repositories.ps1
│   ├── models.ps1
│   ├── status.ps1
│   └── doctor.ps1
│
├── tools/
│   ├── comfyui/
│   │   ├── install.ps1
│   │   ├── update.ps1
│   │   └── validate.ps1
│   └── ...
│
└── docs/
```

This is guidance, not an immutable schema.

Change the structure when there is a clear architectural reason, but preserve the separation of concerns.

---

# Technology Choices

## PowerShell

PowerShell 7 is the primary implementation language for Windows orchestration.

Target:

```text id="owx57v"
pwsh
```

rather than legacy Windows PowerShell where practical.

Prefer PowerShell for:

* Windows setup
* filesystem manipulation
* registry interaction
* environment variables
* `winget`
* service management
* symbolic links / junctions
* process invocation
* prerequisite detection

Scripts should fail clearly and predictably.

Use:

```powershell id="baqf74"
$ErrorActionPreference = "Stop"
```

where appropriate.

Do not silently swallow errors.

If an error is intentionally ignored, document why.

---

## `just`

`just` is the primary human-facing task runner.

It should expose discoverable commands such as:

```text id="xfseoo"
just bootstrap
just status
just doctor
just update

just install <tool>
just validate <tool>

just models
just models <group>

just repos
just packages
```

Keep recipes thin.

A `just` recipe should generally delegate substantive behavior to PowerShell or another implementation script instead of containing large inline programs.

Good:

```just id="k29gb1"
doctor:
    pwsh scripts/doctor.ps1
```

Avoid embedding hundreds of lines of PowerShell inside the `justfile`.

---

## YAML

YAML is preferred for declarative manifests unless another format provides a strong advantage.

Configuration files should remain:

* readable by humans
* easy for agents to modify
* suitable for code review
* stable under source control

Do not invent unnecessarily complicated schemas.

---

# Bootstrap Architecture

Keep a clear distinction between two bootstrap stages.

## Stage 0: Initial Bootstrap

`bootstrap.ps1` must work on a machine with very little installed.

Its job is to obtain enough tooling to run the repository properly.

Typical responsibilities:

* verify supported Windows version
* verify/admin privilege when necessary
* install or locate `winget`
* install Git
* install PowerShell 7 if needed
* install `just`
* install `uv`
* install Git LFS
* clone this repository if needed
* invoke the main bootstrap

Keep Stage 0 intentionally small.

Do not let `bootstrap.ps1` become the entire workstation installer.

---

## Stage 1: Workspace Reconciliation

Once the repository and required task runner exist, `just bootstrap` should reconcile the workstation.

Conceptually:

```text id="ibgq76"
directories
→ prerequisites
→ tools
→ repositories
→ models
→ configuration
→ validation
```

Keep individual components independently runnable.

---

# Workspace Root

Do not scatter AI applications throughout arbitrary filesystem locations.

The workspace root must be configurable.

Example default:

```text id="3px11d"
D:\AI
```

Do not assume `D:` always exists.

A configuration value such as:

```yaml id="433h5d"
workspace:
  root: D:\AI
```

should determine derived locations.

Every script should obtain paths from shared configuration/helpers rather than duplicating literal paths.

Avoid:

```powershell id="oh5og8"
$path = "D:\AI\models"
```

in random scripts.

Prefer:

```powershell id="ml51k0"
$workspace = Get-WorkspaceConfig
$path = Join-Path $workspace.Root "models"
```

---

# Tools

Treat each substantial application as an independent component.

A tool may define:

```text id="7o5zq8"
install
update
validate
configure
remove
```

Not every tool needs every operation.

Avoid modifying global machine state unless the application actually requires it.

Prefer isolated environments.

For Python applications, prefer `uv` and application-specific virtual environments unless the application explicitly requires another environment manager.

Do not globally `pip install` packages merely because it is convenient.

---

# Version Pinning

Balance reproducibility with maintainability.

Pin versions when:

* upstream releases are known to break compatibility
* exact versions matter for CUDA/PyTorch compatibility
* a repository's main branch is unstable
* model format compatibility depends on a specific revision

Do not blindly pin every package forever.

Make intentional pinning visible in configuration.

Example:

```yaml id="qp5tew"
comfyui:
  repo: https://github.com/comfyanonymous/ComfyUI.git
  revision: v0.3.60
```

or:

```yaml id="m3q0nh"
revision: main
```

The distinction should always be explicit.

---

# Git Repositories

Repository declarations should contain enough information to reconstruct them.

Example:

```yaml id="qsft9u"
repos:
  music-tools:
    url: git@github.com:example/music-tools.git
    path: work/repos/music-tools
```

Behavior should distinguish between:

1. repository absent
2. repository present and clean
3. repository present with local changes
4. wrong remote
5. detached HEAD
6. failed authentication

Never destroy or reset local modifications automatically.

Commands such as:

```text id="fqzq8n"
git reset --hard
git clean -fdx
```

must not be run against user repositories without explicit user intent.

For managed third-party application repositories, destructive synchronization may occasionally be appropriate, but it must be clearly scoped and intentional.

---

# Models

Model installation deserves its own subsystem.

A model declaration should ideally describe:

* logical name
* provider/source
* repository or model identifier
* revision when necessary
* destination group/path
* expected format
* optional applications using it

Example:

```yaml id="2v0a5r"
models:
  whisper-large-v3:
    source: huggingface
    repo: openai/whisper-large-v3
    group: audio

  qwen3-30b:
    source: ollama
    model: qwen3:30b
    group: llm
```

Model downloads must be resumable whenever the provider supports it.

Do not redownload large files merely because installation is rerun.

Large downloads should display meaningful progress.

---

# Profiles

Profiles group optional capabilities.

Example:

```yaml id="kycol3"
profiles:
  core:
    - git
    - uv
    - ffmpeg

  llm:
    - ollama
    - open-webui

  image:
    - comfyui

  music:
    - minimax-music
    - audio-tools

  full:
    - core
    - llm
    - image
    - music
```

Profiles should describe intent rather than duplicate detailed installation configuration.

Adding a component to a profile should not require duplicating that component's configuration.

---

# Secrets and Credentials

Never commit secrets.

This includes:

* API keys
* access tokens
* passwords
* SSH private keys
* Hugging Face tokens
* GitHub tokens
* cloud credentials
* personal authentication cookies

The repository may describe **where credentials should come from**.

Supported mechanisms may include:

* environment variables
* Windows Credential Manager
* 1Password CLI
* SSH agent
* Git credential manager
* local untracked `.env` files

Examples of local-only configuration:

```text id="vzd0t1"
.env
.env.local
config/local.yaml
```

These should be excluded by `.gitignore`.

Provide `.example` templates when useful.

Never print secret values during diagnostics.

A diagnostic may say:

```text id="f9qibs"
✓ HF_TOKEN is available
```

but never:

```text id="fghs7z"
HF_TOKEN=hf_xxxxxxxxxxxxx
```

---

# Privilege Management

Do not run the entire bootstrap elevated merely because one operation needs administrator privileges.

Prefer elevation only for operations that require it.

Keep a distinction between:

* user-level installation
* machine-level installation
* Windows feature changes

When elevation is required, make that requirement clear.

---

# Restart Handling

Some Windows changes require:

* reboot
* logout/login
* new shell
* WSL restart
* service restart

Detect these conditions where practical.

Do not continue blindly if a reboot is required for later steps to work correctly.

The process should support:

```text id="cpxbsw"
bootstrap
→ reboot
→ bootstrap
```

without losing progress.

---

# Validation

Every important subsystem should be verifiable.

Installation is not complete merely because a command exited with status 0.

Examples:

Git:

```text id="f0d1ce"
git --version
```

Python:

```text id="yhspsh"
uv --version
```

CUDA/PyTorch:

```python id="nfka1e"
import torch
assert torch.cuda.is_available()
```

Repository:

* expected remote exists
* expected executable or entry point exists

Service:

* process can start
* health endpoint responds when applicable

Model:

* expected artifact exists
* obvious partial-download files are absent
* provider recognizes the model when appropriate

---

# `just doctor`

Maintain a diagnostic command:

```text id="xbkagx"
just doctor
```

Its job is to answer:

> Is this workstation actually usable?

The report should check categories such as:

```text id="5n6xsl"
System
GPU
Developer tools
Python
Containers
Applications
Models
Repositories
Credentials
Disk space
Workspace configuration
```

Keep output compact and actionable.

Preferred style:

```text id="964r0b"
GPU
  ✓ NVIDIA GPU detected
  ✓ driver available
  ✓ CUDA visible to PyTorch

Applications
  ✓ Ollama
  ✓ ComfyUI
  ✗ MiniMax-Music: virtual environment missing

Models
  ✓ qwen3:30b
  ! whisper-large-v3: download incomplete
```

Failures should explain what command is likely to repair them.

---

# `just status`

`status` and `doctor` serve different purposes.

`status` should summarize configured state:

```text id="vqqpxb"
Installed tools: 8/10
Models: 14/16
Repositories: 6/6
Profiles: core,llm,music
```

`doctor` should perform deeper validation.

---

# Logging

Long-running installations must leave useful logs.

Prefer:

```text id="hrdjpr"
logs/
```

under an appropriate state/cache location.

A failed unattended bootstrap should preserve enough information to determine:

* which component failed
* which command failed
* exit code
* relevant output
* whether retry is safe

Do not require the user to reconstruct failures from terminal scrollback.

---

# Destructive Operations

Be conservative.

Commands that can remove:

* user repositories
* generated media
* prompts
* experiments
* manually downloaded models
* configuration files
* credentials

must require explicit intent.

Do not make:

```text id="bfd3nd"
just clean
```

mean "delete everything."

If cleanup functionality exists, separate levels clearly:

```text id="v7hz2v"
just clean-cache
just clean-downloads
just clean-tool <tool>
```

Any destructive full reset should have an unmistakable name and a confirmation mechanism.

---

# Updating Software

Updates must preserve reproducibility.

Do not make normal bootstrap runs automatically upgrade every dependency to the newest available release.

Keep:

```text id="5yw76n"
bootstrap
```

separate from:

```text id="laihml"
update
```

A useful model is:

```text id="c06sbn"
just bootstrap
```

Reconcile against currently declared versions.

```text id="8e0x1l"
just update
```

Update mutable applications within allowed constraints.

```text id="vydjom"
just update <tool>
```

Update one tool.

When an update changes a pinned revision in configuration, make that change explicit and reviewable.

---

# Testing Strategy

Changes to bootstrap logic should be testable without wiping the developer workstation.

Where practical, separate:

* pure configuration parsing
* state detection
* state mutation

Prefer functions such as:

```text id="q6e5p1"
Get-ToolState
Install-Tool
Test-Tool
```

over one enormous procedural script.

Important scripts should support diagnostics or dry-run behavior where feasible.

A full reinstall test remains valuable, but it should not be the only testing method.

---

# Agent Workflow

When modifying this repository:

1. Read this file.
2. Read the relevant manifests.
3. Inspect existing helper functions before creating new ones.
4. Identify whether the change represents:

   * configuration
   * reconciliation logic
   * tool-specific behavior
   * machine bootstrap behavior
5. Put the change in the narrowest appropriate layer.
6. Preserve idempotency.
7. Preserve resumability.
8. Preserve user data.
9. Add or update validation.
10. Update documentation when user-visible behavior changes.

Do not duplicate existing abstractions merely to complete a task quickly.

---

# Before Adding a New Tool

Determine:

* official repository/site
* Windows support status
* required Python version
* CUDA requirements
* system dependencies
* model dependencies
* expected disk usage
* whether the application has its own model directory
* whether that model directory can be redirected
* whether installation can be unattended
* how installation can be validated
* how updates work

Then add the tool through the normal configuration/install/validate architecture.

Do not special-case a tool in top-level bootstrap logic unless there is a real architectural need.

---

# Research

AI software changes quickly.

When adding or updating third-party software, verify current upstream installation documentation rather than relying entirely on remembered commands.

Prefer primary sources:

1. official documentation
2. official GitHub repository
3. official release notes
4. upstream package metadata

Use community instructions only when primary documentation is incomplete.

Record non-obvious compatibility findings in comments or documentation.

---

# Avoid Unnecessary Dependencies

Do not add a framework merely to save a small amount of scripting.

This repository should still be understandable after months of inactivity.

Preferred stack:

```text id="a19e9b"
PowerShell
just
YAML
Git
uv
```

Add another dependency only when it provides clear value.

---

# Maintainability Rules

Prefer boring code.

This project values:

```text id="2wfc0u"
predictability
> cleverness

explicit state
> implicit state

small scripts
> giant orchestration scripts

reconciliation
> one-shot installation

validation
> optimistic assumptions

recoverability
> maximum automation at any cost
```

Comments should explain **why**, not narrate obvious code.

---

# Error Messages

Errors should identify both the problem and a likely recovery path.

Bad:

```text id="jv8ala"
Install failed.
```

Better:

```text id="nfv6zx"
MiniMax-Music installation failed because Python 3.11 is unavailable.

Run:
    just packages

Then retry:
    just install minimax-music
```

For unattended operation, failures should also appear in the final summary.

---

# Unattended Execution

A primary project goal is unattended reconstruction.

Commands used during bootstrap must therefore avoid unexpected prompts.

When a command would normally prompt interactively:

* supply explicit options
* preconfigure required values
* detect the condition beforehand
* or mark the component as requiring manual action

Never allow a hidden interactive prompt to hang a multi-hour bootstrap indefinitely.

---

# Final Bootstrap Summary

At the end of a bootstrap, print a concise summary.

Example:

```text id="06qqzw"
AI Workspace Bootstrap

✓ Machine prerequisites
✓ Directory structure
✓ 8 applications
✓ 6 repositories
✓ 12 models
! 1 model download failed
! Reboot recommended

Failures:
  whisper-large-v3
    Network transfer interrupted.
    Retry with:
        just models audio

Next:
    just doctor
```

The user should not need to inspect logs just to determine whether installation succeeded.

---

# Documentation

`README.md` is for the human operator.

It should explain:

* what this repository does
* initial installation
* common commands
* directory layout
* configuration
* adding tools/models/repos
* troubleshooting
* reinstall workflow

`AGENTS.md` is for autonomous coding agents.

Do not push large amounts of agent-specific implementation guidance into the README.

---

# Scope Discipline

This repository manages the workstation environment.

Do not let it gradually become:

* a generic dotfiles repository
* a Windows debloating system
* a personal backup solution
* a secrets manager
* an AI experiment repository
* a model benchmarking framework

Integration with those systems may exist, but their actual responsibilities should remain separate.

---

# Compatibility

Primary target:

```text id="p9jgw5"
Windows 11
PowerShell 7
NVIDIA GPU workstation
```

WSL may be used where a tool benefits substantially from Linux, but do not move applications into WSL by default simply because Linux installation instructions are easier to find.

Prefer native Windows execution when it is well supported.

If an application is significantly more reliable under WSL, make that decision explicit in its configuration and documentation.

---

# Agent Decision Rule

When deciding how to implement something, optimize for this scenario:

> Windows was reinstalled this morning. The user starts the bootstrap, walks away, and returns several hours later.

Ask:

* Would this step block waiting for input?
* Would rerunning it be safe?
* Would an interrupted download resume?
* Would local work survive?
* Would failures be obvious?
* Could the user determine what remains broken?
* Could the agent understand this code six months from now?

If not, improve the design before adding more automation.

---

# Definition of Done

A change is complete when:

* configuration represents desired state clearly
* operations are idempotent
* interruptions are recoverable
* secrets remain external
* user-created data is protected
* validation exists where practical
* unattended execution remains possible
* failure output is actionable
* relevant documentation is updated
* `just doctor` can detect the resulting state

The goal is not merely:

> "the installation command worked once."

The goal is:

> **the workstation can be reconstructed, inspected, repaired, and evolved from this repository.**
