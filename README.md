# AI Workstation

A version-controlled specification for rebuilding a self-hosted Windows AI workstation.

The profile-driven bootstrap creates workspace directories, reconciles prerequisites, configures shared caches, and installs the selected applications and models. YuE2 has a native Windows installer and Markdown song runner; other music tools remain planned.

Install YuE2 with `just install yue`, acquire its pinned models with `just models yue`, then run `just validate yue`. See [YuE integration](docs/tools/yue.md) for generation commands, hardware requirements and recovery.

On a new Windows machine, Windows PowerShell 5.1 can run `bootstrap.ps1`; Stage 0 acquires WinGet and declared prerequisites, clones the repository when needed, and delegates to PowerShell 7. For an existing checkout, use `just plan core`, `just bootstrap core`, and `just doctor core`, or omit the profile to select `music`. See the [bootstrap guide](docs/bootstrap.md) for privilege handling, configuration, and recovery.

- [Roadmap](ROADMAP.md): planned and completed tasks for the workspace and each candidate tool.
- [Documentation](docs/README.md): operator guides and tool documentation.
- [Bootstrap guide](docs/bootstrap.md): helper packages, directories, commands, and current limitations.
- [Fresh-machine test guide](docs/fresh-machine-test.md): step-by-step setup, validation, and failure reporting on a newly installed Windows machine.
- [Song-generation jobs](docs/song-generation-jobs.md): the shared Markdown format and Python runner contract. Music tools are the first installation priority.
- [Local tool service](docs/tool-service.md): REST, browser downloads, and MCP for the music runners. Install with `just install tool-service`, configure local access keys, then run `just serve`.

Installed applications, models, caches, logs, and user work are excluded from this repository. Installation scripts under `tools/` and shared configuration will remain version-controlled.
