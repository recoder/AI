# AI Workstation

A version-controlled specification for rebuilding a self-hosted Windows AI workstation.

The bootstrap foundation creates workspace directories and reconciles helper packages. YuE2 has a native Windows installer and Markdown song runner; other music tools remain planned.

Install YuE2 with `just install yue`, acquire its pinned models with `just models yue`, then run `just validate yue`. See [YuE integration](docs/tools/yue.md) for generation commands, hardware requirements and recovery.

With PowerShell 7.4+ and this repository available locally, run `./bootstrap.ps1`. For an existing `just` setup, run `just setup`, `just plan`, and `just bootstrap`, then `just doctor-helpers`. Full `just doctor` also validates the configured YuE2 installation. See the [bootstrap guide](docs/bootstrap.md) for prerequisite installation, configuration, and recovery.

- [Roadmap](ROADMAP.md): planned and completed tasks for the workspace and each candidate tool.
- [Documentation](docs/README.md): operator guides and tool documentation.
- [Bootstrap guide](docs/bootstrap.md): helper packages, directories, commands, and current limitations.
- [Fresh-machine test guide](docs/fresh-machine-test.md): step-by-step setup, validation, and failure reporting on a newly installed Windows machine.
- [Song-generation jobs](docs/song-generation-jobs.md): the shared Markdown format and Python runner contract. Music tools are the first installation priority.

Installed applications, models, caches, logs, and user work are excluded from this repository. Installation scripts under `tools/` and shared configuration will remain version-controlled.
