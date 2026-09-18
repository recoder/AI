# Fresh-machine bootstrap test

Use this procedure to test the bootstrap foundation on a newly installed Windows machine. It covers helper installation, directory creation, diagnostics, and safe reruns. Music applications, models, Python runners, GPU validation, and a complete unattended Stage 0 are not implemented yet.

Windows 11 is the primary target. The foundation also permits Windows 10 build 19041+ with a warning. Use the same Windows user account for setup and normal workspace operations so current-user packages and the YAML module are installed for the intended operator.

## 1. Publish and identify the version being tested

On the development machine, commit and push the intended changes before cloning on the fresh machine. Local uncommitted changes are not included in a clone. At the time this guide was added, the latest debug fixes and this guide were still local changes awaiting publication.

Review and publish only the intended files:

```powershell
git status --short
git diff
# Stage the reviewed files, then:
git commit -m "Harden bootstrap and document fresh-machine testing"
git push origin main
git rev-parse HEAD
```

Save the resulting commit ID. The fresh-machine report should identify that exact version. If another commit is pushed during testing, keep the checkout unchanged until that test is finished; record a new commit ID when testing an update.

## 2. Prepare Windows App Installer

Finish Windows installation, sign in as the intended workstation user, and establish internet access. Use a normal Windows PowerShell or Terminal shell to check WinGet:

```powershell
winget --version
```

If the command is missing, install or update **App Installer** from Microsoft Store, then open a new terminal. See Microsoft's [WinGet setup guidance](https://learn.microsoft.com/en-us/windows/package-manager/winget/).

Record the WinGet version. WinGet 1.29.360 has a [reported file-sharing regression](https://github.com/microsoft/winget-cli/issues/6520) immediately after installer hash verification. If an install fails with `0x80070020`, follow the troubleshooting section below rather than repeatedly clearing caches or disabling hash verification.

## 3. Install the initial prerequisites

The current root bootstrap requires Git/repository access and PowerShell 7.4+ to be available already. It cannot yet acquire them automatically. Install these two machine prerequisites from an administrator shell; do not run the entire bootstrap elevated:

```powershell
winget install --id Git.Git --exact --source winget --scope machine --silent --disable-interactivity --accept-package-agreements --accept-source-agreements
winget install --id Microsoft.PowerShell --exact --source winget --scope machine --silent --disable-interactivity --accept-package-agreements --accept-source-agreements
```

Check each command's result before continuing. If WinGet fails, use the official [Git for Windows installer](https://git-scm.com/download/win) or [PowerShell installation instructions](https://learn.microsoft.com/en-us/powershell/scripting/install/installing-powershell-on-windows).

Close the elevated shell. Open **PowerShell 7** as the normal workstation user and verify:

```powershell
git --version
pwsh --version
$PSVersionTable.PSVersion
```

PowerShell must be 7.4 or newer. You do not need to install `just`, `uv`, or ffmpeg manually for this test; leave missing user-scoped helpers for bootstrap to install.

## 4. Clone the repository and choose the workspace

Choose a location owned by your user. This example uses `C:\AI`; another drive or a path containing spaces is valid. The target should be absent before cloning. If a checkout already exists there, use a different location for the fresh test instead of deleting it.

```powershell
git clone https://github.com/recoder/AI.git C:\AI
Set-Location C:\AI
git rev-parse HEAD
git status --short
```

Confirm that the commit ID matches the version published in step 1 and the working tree is clean. If repository access requires authentication, complete it during this manual preparation step. GitHub CLI is optional; bootstrap does not depend on it.

The default workspace root is the repository directory, so this checkout creates application/model/cache/work directories under `C:\AI`. If testing a separate workspace root, set an absolute path in this normal-user shell before running any bootstrap commands:

```powershell
$env:AI_WORKSPACE_ROOT = 'E:\AI-workspace'
```

Only use a drive that exists. This variable applies to the current shell and its children; reapply it after opening a new shell, including any repair shell. Save its value in the test report. Keep running scripts from the repository checkout even when the workspace root is separate.

## 5. Install YAML support and preview changes

From the repository in the normal-user PowerShell 7 shell:

```powershell
pwsh -NoProfile -File scripts/setup.ps1
pwsh -NoProfile -File bootstrap.ps1 -WhatIf
```

Setup installs `powershell-yaml` 0.4.12 from PowerShell Gallery for the current user. The preview requires that module; it intentionally does not install dependencies itself. Expected output lists existing helpers as `OK` and missing directory/package operations as `What if`.

The preview should create no workspace directories and install no helper packages. Setup itself has already installed the YAML module; that is separate from the preview's no-mutation guarantee. Package probes do execute version commands during the preview.

If local execution policy blocks direct script invocation, use the explicit `pwsh -NoProfile -File ...` commands shown here. On a machine where a locally reviewed script remains blocked, a one-invocation `-ExecutionPolicy Bypass` may be used without changing machine/user policy:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

Organization-enforced policy takes precedence; ask the machine administrator if that prevents execution.

## 6. Run the first bootstrap

Run as the normal workstation user:

```powershell
pwsh -NoProfile -File bootstrap.ps1
```

This ensures YAML support and reconciles configured directories and helpers. It installs missing user-scoped packages with explicit WinGet identifiers and unattended flags. Every real workspace bootstrap prints the path to a unique log under the workspace's `logs/` directory.

A first run may finish with failures for missing machine-scoped packages such as 7-Zip or Git LFS. This is expected with the current privilege handling: bootstrap reports the missing privilege and continues checking other helpers, then returns failure. Save that log. It should not hang waiting for elevation.

The 7-Zip failure can appear after ffmpeg prints `Successfully installed`; ffmpeg remains installed. Exceptions printed by both `packages.ps1` and `bootstrap.ps1` represent the same package failure propagating through the entry point. They do not mean completed installations were undone.

Repair only the named machine prerequisite in an administrator shell. For the default manifest, the relevant commands are:

```powershell
# Run only when Git LFS was reported missing or unusable:
winget install --id GitHub.GitLFS --exact --source winget --scope machine --silent --disable-interactivity --accept-package-agreements --accept-source-agreements

# Run only when 7-Zip was reported missing or unusable:
winget install --id 7zip.7zip --exact --source winget --scope machine --silent --disable-interactivity --accept-package-agreements --accept-source-agreements
```

Git for Windows may already supply Git LFS, so check `git lfs version` before adding another installer. These declarations are in `config/packages.yaml`; if the manifest changes, use the IDs/scopes declared by the tested version.

Close the elevated shell and open a new normal-user PowerShell 7 shell. Return to the checkout, restore `AI_WORKSPACE_ROOT` if you set it, and rerun:

```powershell
Set-Location C:\AI
pwsh -NoProfile -File bootstrap.ps1
```

Then run `just doctor` from the normal-user shell to verify the repair. The operator confirmed this 7-Zip recovery sequence worked on a fresh-machine checkout at `C:\AI` on 2026-09-18. See the [bootstrap repair notes](bootstrap.md#recovering-from-the-7-zip-elevation-failure) for the exact sequence and evidence limits.

If `just` is not yet found in a newly opened shell, continue using the root PowerShell command and save the failure output. Do not treat a successful installer exit as proof that a helper is usable.

## 7. Verify usability and reruns

After bootstrap reports success:

```powershell
just status
just doctor
just bootstrap
just doctor
just test
git status --short
```

Expected results for the current manifests:

- Status reports **7/7 helper packages** and **10/10 configured directories**.
- Doctor reports all helper/directory checks as `OK` and exits successfully. Its application/GPU/model checks remain pending.
- The second bootstrap skips usable helpers, preserves existing directories, and creates another unique log. It should perform no package upgrades or repeat downloads.
- Tests pass, including directory preservation, dry-run, timeout, failed-probe, literal-argument, PATH-rerun, and invalid-configuration checks. Test fixtures remain under the checkout's ignored `cache/bootstrap-tests/` directory.
- `git status --short` is empty unless you intentionally edited tracked manifests. Runtime directories/logs should not appear as untracked repository content.

Check `$LASTEXITCODE` immediately after a command if its success is unclear. A failed doctor/test or a missing helper means the test has not passed even if bootstrap previously printed success.

To exercise the Windows PowerShell 5.1 entry point after the foundation is working, run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File bootstrap.ps1
```

It should dispatch setup/reconciliation to PowerShell 7 and complete successfully. The policy override applies only to that invocation.

Do not interrupt an active MSI installer to simulate resumability. A naturally failed first run followed by repairs already exercises recovery. Directory and user-data preservation are also covered by the isolated test fixtures.

## 8. Troubleshoot failures

| Symptom | Recovery |
| --- | --- |
| `winget` missing | Install/update App Installer and open a new terminal. |
| PowerShell missing or too old | Install PowerShell 7.4+ and open a new shell. |
| YAML module/setup failure | Save the console error, verify PowerShell Gallery access, and retry `scripts/setup.ps1` as the intended user. |
| `FAIL 7zip` requires elevation | Install `7zip.7zip` with `--scope machine` from an administrator shell using step 6, close it, open a new normal-user shell, rerun bootstrap, and run doctor. Completed installs remain intact. |
| Other machine package requires elevation | Install only the named prerequisite from an administrator shell; rerun bootstrap normally. |
| Command missing after installation | Open a new normal-user shell and rerun; save output if it remains missing. |
| `0x80070020` after hash verification | Record WinGet version/logs; use the official installer or a fixed WinGet release. Keep hash verification enabled. |
| Installer timeout | Check installer/machine state before retrying. Termination does not roll back an installation. |
| Reboot requested by installer | Reboot, restore the workspace override, and rerun bootstrap; automatic reboot detection is pending. |
| Configured directory occupied by a file | Inspect that location and choose a corrected path or relocate the file intentionally; bootstrap does not delete it. |
| Pinned version mismatch | Resolve the declared version deliberately; normal bootstrap is not a bulk updater. |

If failure happens before workspace logging starts, save the console output. For persistent capture of setup and early errors, you can wrap a run in a separate operator transcript stored outside the repository:

```powershell
$capturePath = Join-Path $env:TEMP "AI-bootstrap-operator-$(Get-Date -Format yyyyMMdd-HHmmss).log"
Start-Transcript -Path $capturePath
try {
    pwsh -NoProfile -File bootstrap.ps1
} finally {
    Stop-Transcript
}
$capturePath
```

## 9. Report the result

Include:

- Tested commit ID (`git rev-parse HEAD`).
- Windows edition/build, PowerShell version, and `winget --version`.
- Whether this was a fresh install, and which prerequisites were installed manually.
- Checkout location, workspace root/override, and whether each run was elevated.
- First bootstrap outcome, any repair steps, second bootstrap outcome, and status/doctor/test results.
- Exact failure message/exit code and bootstrap log files from both failed and successful runs.

WinGet diagnostic logs normally live under:

```text
%LOCALAPPDATA%\Packages\Microsoft.DesktopAppInstaller_8wekyb3d8bbwe\LocalState\DiagOutputDir
```

Review logs before sharing; redact tokens or other credentials if present. Keep logs out of Git. A successful report validates this foundation on that machine, not the still-planned music tool installations.
