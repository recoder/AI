# Bootstrap foundation

The bootstrap has two stages. `bootstrap.ps1` runs under Windows PowerShell 5.1, acquires WinGet and declared prerequisites, clones the repository when absent, and delegates to PowerShell 7. Stage 1 expands a selected profile and reconciles directories, packages, shared caches, applications, repositories, models, and validation. Windows 11 is the primary target; Windows 10 build 19041+ receives a compatibility warning. YuE2 is the first application integration; see [YuE2](tools/yue.md).

## Initial setup

For a newly installed machine, follow the [fresh-machine test guide](fresh-machine-test.md), including publication of the tested revision, prerequisite preparation, privilege handling, and result collection.

From an existing checkout, a normal user shell can run:

```powershell
.\bootstrap.ps1 -Profile core
```

If machine-scoped prerequisites are missing, Stage 0 stops with an actionable message. Open an administrator shell only for that phase:

```powershell
.\bootstrap.ps1 -MachineOnly
```

Return to a normal shell and rerun the first command. Stage 0 can repair a missing WinGet installation through Microsoft's `Microsoft.WinGet.Client` module, and it can clone `recoder/AI` to `D:\AI` (or `C:\AI` when `D:` is unavailable). Use `-RepositoryPath` or `AI_WORKSPACE_ROOT` to select another location. It never replaces a nonempty directory or a repository with the wrong origin.

For an existing PowerShell/`just` setup:

```powershell
just setup
just plan core
just bootstrap core
just doctor core
```

Omit `core` to use the manifest's default `music` profile, which includes YuE2 and its pinned models. `bootstrap.ps1 -WhatIf` and `just plan <profile>` avoid mutation.

## Configuration

`config/workspace.yaml` defines the workspace root and derived directories. Its default root is the repository directory, independent of the current working directory and drive letter. Set `AI_WORKSPACE_ROOT` to select another workspace for the current process:

```powershell
$env:AI_WORKSPACE_ROOT = 'E:\AI'
just plan
```

Relative manifest root paths resolve against `config/`; an environment override follows the same rule if relative. Prefer an absolute environment override. Derived directory paths must stay below the workspace root. Directory reconciliation creates missing paths and preserves existing content; a file blocking a configured directory is an error.

`config/packages.json` declares helper commands, version probes, WinGet identifiers, installation scope, and optional exact versions. JSON is used for this Stage 0 manifest because Windows PowerShell 5.1 can parse it before the YAML module exists. `config/profiles.yaml` groups packages, tools, model groups, and user repositories; includes are expanded once and cycles or unknown components are rejected. `version: null` accepts an existing executable whose probe succeeds. Bootstrap skips usable packages and never runs a bulk upgrade.

`config/workspace.yaml` also maps `UV_CACHE_DIR`, `HF_HOME`, `TORCH_HOME`, `PIP_CACHE_DIR`, and `TRITON_CACHE_DIR` to declared workspace directories. Stage 1 validates the whole mapping before persisting it for the user. `config/repos.yaml` declares optional repositories under `work/`; reconciliation clones absent repositories and refuses wrong remotes, revisions, or conflicting content without resetting local work.

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

Package discovery adds known installer directories and refreshed user/machine PATH values to the current process only. It does not change persistent PATH or globally initialize Git LFS. Bootstrap detects common Component Based Servicing and Windows Update reboot flags and stops dependent work when a package creates a new reboot requirement. If an installer requires another kind of reboot or still cannot expose its command, follow its guidance, restart, and rerun the same profile.

## Commands and recovery

| Command | Behavior |
| --- | --- |
| `just setup` | Ensure the pinned YAML parser exists for the current user. |
| `just plan [profile]` | Show selected components and intended changes without mutation. |
| `just bootstrap [profile]` | Reconcile the selected profile and print an actionable summary and log path. |
| `just directories` | Create missing configured directories. |
| `just packages` | Check helpers and attempt missing package installs. |
| `just status [profile]` | Summarize configured state for a profile. |
| `just doctor-helpers` | Probe helpers/directories, report repairs, and fail if problems remain. |
| `just doctor [profile]` | Deeply validate the selected packages, caches, tools, models, repositories, credentials, and disk space. |
| `just repos` | Reconcile declared user repositories without resetting local changes. |
| `just test` | Exercise isolated directory reruns, data preservation, dry-run, path validation, and failed probes. |

Each real workspace bootstrap writes a unique transcript under the configured `logs/` directory. It records component output, failures, repair commands, and the final summary. Model reconciliation is shared across tool groups, verifies declared sizes and hashes, and preserves resumable partial downloads. If a prerequisite or cache phase fails, dependent application/model work is skipped and completed state remains intact.

Rerun `just bootstrap` after fixing a reported failure. Already usable tools and existing directories are skipped. User content is never reset or removed. The test command retains its isolated fixtures under ignored `cache/bootstrap-tests/` for inspection.

Installer errors include decimal and hexadecimal exit codes. On this workstation, WinGet 1.29.360 failed with `0x80070020` after hash verification, matching a [reported upstream regression](https://github.com/microsoft/winget-cli/issues/6520). If this happens, inspect WinGet's diagnostic log and install the affected package through its official installer or a fixed WinGet release. Do not disable installer hash verification. Bootstrap remains rerunnable once the helper's version probe succeeds. After a timeout, check the installer/machine state before retrying; terminating a process does not roll back an installation.

Implementation sources: [WinGet install options](https://learn.microsoft.com/en-us/windows/package-manager/winget/install), [uv installation](https://docs.astral.sh/uv/getting-started/installation/), [just](https://github.com/casey/just), [powershell-yaml 0.4.12](https://www.powershellgallery.com/packages/powershell-yaml/0.4.12), and [Install-PSResource](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.psresourceget/install-psresource).
