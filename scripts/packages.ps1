#requires -Version 7.4
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot/common.ps1"
Update-ProcessPath
$failures = @()
foreach ($package in (Read-WorkspaceManifest packages).packages) {
    $state = Get-PackageState $package
    if ($state.Usable) { Write-Host "OK $($state.Name): $($state.Detail)"; continue }
    if (-not $PSCmdlet.ShouldProcess($package.name, "Install $($package.id) using winget")) { continue }
    try {
        if ($state.Found -and $package.version) { throw $state.Detail }
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'Install Windows App Installer, then retry just packages.' }
        if ($package.scope -eq 'machine') {
            $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
            if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
                throw 'This missing machine package requires elevation. Run just packages in an administrator shell, then return to a normal shell.'
            }
        }
        $arguments = @('install', '--id', $package.id, '--exact', '--source', 'winget', '--scope', $package.scope,
            '--silent', '--disable-interactivity', '--accept-package-agreements', '--accept-source-agreements')
        if ($package.version) { $arguments += @('--version', $package.version) }
        & winget @arguments
        if ($LASTEXITCODE -ne 0) { throw "winget exited with $LASTEXITCODE. Inspect its output; retry just packages after resolving the failure." }
        Update-ProcessPath
        $verified = Get-PackageState $package
        if (-not $verified.Usable) { throw "Installed package is not usable: $($verified.Detail). Open a new shell and retry just packages." }
        Write-Host "OK installed $($package.name)"
    } catch {
        $failures += "$($package.name): $($_.Exception.Message)"
        Write-Host "FAIL $($failures[-1])"
    }
}
if ($failures.Count) { throw "Package reconciliation failed:`n$($failures -join "`n")" }
