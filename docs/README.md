# Documentation

Keep detailed operator documentation in this directory. The root `README.md` is the entry point, `ROADMAP.md` tracks progress, and `AGENTS.md` contains agent instructions.

- [Song-generation jobs and runners](song-generation-jobs.md): proposed shared format, per-tool flavors, YAML configuration lookup, and execution behavior. Implementation is pending.
- [Bootstrap foundation](bootstrap.md): setup, configuration, commands, validation, and recovery.

As implementation progresses, add guides for:

- Initial setup and reconstruction after reinstalling Windows.
- Configuration, profiles, and common commands.
- Adding tools, models, and user repositories.
- Validation, troubleshooting, logs, and recovery after interrupted installs.
- Individual tools under `docs/tools/<tool>.md`, covering prerequisites, model storage, installation, validation, and updates.

Document commands when they exist and have been verified. Track proposed behavior in the [roadmap](../ROADMAP.md).
