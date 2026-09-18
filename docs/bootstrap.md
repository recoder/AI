# Bootstrap foundation

The first implementation reconciles helper packages and workspace directories using PowerShell 7.4 or newer. Windows 11 is the primary target; Windows 10 build 19041+ is allowed with a warning for the foundation, and skip/rerun behavior has been checked on this Windows 10 22H2 workstation. YuE2 now has a separately invoked native Windows installer, pinned model downloads, runner environment and GPU validation; see [YuE2](tools/yue.md). Other application installers, profile selection and software updates remain planned. This is not yet a complete unattended fresh-machine bootstrap.

## Initial setup

For a newly installed machine, follow the [fresh-machine test guide](fresh-machine-test.md), including publication of the tested revision, prerequisite preparation, privilege handling, and result collection.

Start with this repository already cloned or copied locally and PowerShell 7.4+ installed. If PowerShell is missing, install it using Windows App Installer's `winget`:

```powershell
winget install --id Microsoft.PowerShell --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity
```

Open a new shell and run from the repository:

```powershell
.\bootstrap.ps1
```

The root script can be launched from Windows PowerShell 5.1. It verifies the Windows build, locates PowerShell 7, installs pinned `powershell-yaml` 0.4.12 for the current user if missing, and invokes workspace reconciliation through PowerShell 7. It does not require `just` to be installed before starting. Install Windows App Installer manually if `winget` is unavailable. Automatic acquisition of these initial prerequisites and repository cloning remain roadmap tasks.

For an existing PowerShell/`just` setup:

```powershell
just setup
just plan
just bootstrap
just doctor-helpers
```

`just setup` installs only the YAML parser. A plan requires that parser to be available already; it does not install it. `bootstrap.ps1 -WhatIf` also avoids dependency installation.

## Configuration

`config/workspace.yaml` defines the workspace root and derived directories. Its default root is the repository directory, independent of the current working directory and drive letter. Set `AI_WORKSPACE_ROOT` to select another workspace for the current process:

```powershell
$env:AI_WORKSPACE_ROOT = 'E:\AI'
just plan
```

Relative manifest root paths resolve against `config/`; an environment override follows the same rule if relative. Prefer an absolute environment override. Derived directory paths must stay below the workspace root. Directory reconciliation creates missing paths and preserves existing content; a file blocking a configured directory is an error.

`config/packages.yaml` declares helper commands, version probes, WinGet identifiers, installation scope, and optional exact versions. `version: null` accepts an existing executable whose probe succeeds. This verifies usability, not which installer originally supplied the executable. Bootstrap skips usable packages and never runs a bulk upgrade. If a version is pinned and an existing executable mismatches it, the command reports the mismatch for explicit operator resolution.

Manifest order determines directory/package processing order. Invalid package mappings, duplicate package names, invalid scopes, and invalid timeout values are rejected before any package installs. Probes default to a 30-second timeout; installs default to 1800 seconds. Override these per package with `probe_timeout_seconds` and `install_timeout_seconds` (integers from 1 to 86400). A hung process is terminated with its child processes; diagnostics report the timeout instead of blocking indefinitely. Process-launch failures are reported as unusable package state so later checks can continue. Installer stdout/stderr are captured separately and printed when the installer finishes or times out.

Missing packages install using exact WinGet identifiers, explicit scopes, silent mode, disabled interactivity, and accepted source/package agreements. Machine-scoped packages require an administrator shell only when missing or unusable. The default set includes machine-scoped Git, Git LFS, PowerShell, and 7-Zip. Prepare those prerequisites before unattended runs; the script fails with repair instructions instead of launching a UAC prompt. Return to a normal shell for subsequent workspace operations.

### Recovering from the 7-Zip elevation failure

If bootstrap reports `FAIL 7zip: This missing machine package requires elevation`, open PowerShell **as Administrator** and install only 7-Zip:

```powershell
winget install --id 7zip.7zip --exact --source winget --scope machine --silent --disable-interactivity --accept-package-agreements --accept-source-agreements
```

Close the elevated shell and open a new **normal-user PowerShell** shell. Return to the checkout, restore `AI_WORKSPACE_ROOT` if you used an override, and rerun:

```powershell
Set-Location C:\AI
pwsh -NoProfile -File bootstrap.ps1
just doctor-helpers
```

Use your actual checkout path in place of `C:\AI`. Completed helper installations are preserved and skipped. Prefer this targeted repair over running the entire package reconciliation elevated, which can install user-scoped helpers under the wrong account.

An installer message saying PATH changed means a new shell may be needed. The exceptions from `packages.ps1` and `bootstrap.ps1` describe the same failure propagating through the entry point, rather than two separate installation failures. Keep the failed-run log and the successful retry log.

On 2026-09-18, the operator reported that a fresh-machine run under `C:\AI` installed ffmpeg, stopped at the 7-Zip elevation check, and recovered successfully using the targeted administrator install followed by a normal-shell bootstrap/doctor retry. This confirms that repair path; it does not establish that every helper's missing-package installation or the complete fresh-machine workflow has been tested.

Package discovery adds known installer directories and refreshed user/machine PATH values to the current process only. It does not change persistent PATH or globally initialize Git LFS. If an installer requires a reboot or still cannot expose its command, reconciliation fails verification; follow the installer guidance, restart as needed, and rerun. Automatic reboot detection remains planned.

## Commands and recovery

| Command | Behavior |
| --- | --- |
| `just setup` | Ensure the pinned YAML parser exists for the current user. |
| `just plan` | Probe packages and show intended directory/package changes without mutation. |
| `just bootstrap` | Reconcile directories and helpers, then print the summary and log path. |
| `just directories` | Create missing configured directories. |
| `just packages` | Check helpers and attempt missing package installs. |
| `just status` | Summarize helpers, directories and configured YuE2 state. |
| `just doctor-helpers` | Probe helpers/directories, report repairs, and fail if problems remain. |
| `just doctor` | Include configured YuE2 source, imports, CUDA, model hashes and runner checks; missing tool state fails. |
| `just test` | Exercise isolated directory reruns, data preservation, dry-run, path validation, and failed probes. |

Each real workspace bootstrap writes a unique transcript under the configured `logs/` directory. It records command output, errors, and the final summary. Direct `just packages` output is currently terminal-only; use `just bootstrap` when persistent installation logs are needed. Package reconciliation collects failures across the package set and reports them together; application/model reconciliation is currently invoked separately with `just install yue` and `just models yue`. If log-directory creation or configuration loading fails, the error appears before a transcript can start.

Rerun `just bootstrap` after fixing a reported failure. Already usable tools and existing directories are skipped. User content is never reset or removed. The test command retains its isolated fixtures under ignored `cache/bootstrap-tests/` for inspection.

Installer errors include decimal and hexadecimal exit codes. On this workstation, WinGet 1.29.360 failed with `0x80070020` after hash verification, matching a [reported upstream regression](https://github.com/microsoft/winget-cli/issues/6520). If this happens, inspect WinGet's diagnostic log and install the affected package through its official installer or a fixed WinGet release. Do not disable installer hash verification. Bootstrap remains rerunnable once the helper's version probe succeeds. After a timeout, check the installer/machine state before retrying; terminating a process does not roll back an installation.

Implementation sources: [WinGet install options](https://learn.microsoft.com/en-us/windows/package-manager/winget/install), [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [just](https://github.com/casey/just), [powershell-yaml 0.4.12](https://www.powershellgallery.com/packages/powershell-yaml/0.4.12), and [Install-PSResource](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.psresourceget/install-psresource).
