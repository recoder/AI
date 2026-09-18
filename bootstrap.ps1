# Stage 0 entry point, compatible with Windows PowerShell 5.1.
[CmdletBinding()]
param([switch]$WhatIf)
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'This bootstrap targets Windows 11.' }
if ([Environment]::OSVersion.Version.Build -lt 19041) { throw 'Windows build 19041 or newer is required for this bootstrap foundation.' }
if ([Environment]::OSVersion.Version.Build -lt 22000) {
    Write-Warning 'Windows 11 is the primary target. Running the bootstrap foundation on Windows 10; individual applications need separate compatibility checks.'
}
$pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
if (-not $pwsh) {
    throw 'Install PowerShell 7.4+ first: winget install --id Microsoft.PowerShell --exact --silent --accept-package-agreements --accept-source-agreements --disable-interactivity. Open a new shell, then rerun bootstrap.ps1.'
}
if (-not $WhatIf) {
    & $pwsh.Source -NoProfile -File "$PSScriptRoot/scripts/setup.ps1"
    if ($LASTEXITCODE -ne 0) { throw 'YAML dependency setup failed. Retry bootstrap.ps1 after resolving the reported error.' }
}
$arguments = @('-NoProfile', '-File', "$PSScriptRoot/scripts/workspace.ps1")
if ($WhatIf) { $arguments += '-WhatIf' }
& $pwsh.Source @arguments
if ($LASTEXITCODE -ne 0) { throw 'Workspace bootstrap failed. See the reported repair command and log path.' }
