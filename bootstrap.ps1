# Stage 0: Windows PowerShell 5.1 compatible; acquires prerequisites, then delegates.
[CmdletBinding()]
param([switch]$WhatIf, [switch]$MachineOnly, [string]$Profile,
    [string]$RepositoryPath, [string]$RepositoryUrl = 'https://github.com/recoder/AI.git')
$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne 'Win32NT' -or [Environment]::OSVersion.Version.Build -lt 19041) { throw 'Windows build 19041+ is required; Windows 11 is the primary target.' }
if ([Environment]::OSVersion.Version.Build -lt 22000) { Write-Warning 'Windows 10 is a compatibility target; Windows 11 is preferred.' }
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$administrator = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($administrator -and -not $MachineOnly -and -not $WhatIf) { throw 'Use -MachineOnly in this administrator shell. Run full bootstrap from your normal user shell so user packages, caches and environments use the correct account.' }
if ($MachineOnly -and -not $administrator -and -not $WhatIf) { throw '-MachineOnly requires an administrator shell; full bootstrap runs in a normal shell.' }
function Update-Stage0Path {
    $locations = @($env:PATH, [Environment]::GetEnvironmentVariable('PATH','Machine'), [Environment]::GetEnvironmentVariable('PATH','User'),
        "$env:LOCALAPPDATA\Microsoft\WindowsApps", "$env:LOCALAPPDATA\Microsoft\WinGet\Links", "$env:ProgramFiles\Git\cmd", "$env:ProgramFiles\7-Zip", "$env:ProgramFiles\PowerShell\7")
    $env:PATH = (($locations -join ';') -split ';' | Where-Object { $_ } | Select-Object -Unique) -join ';'
}
function ConvertTo-NativeArgument([string]$Value) {
    # Windows CRT quoting: escape backslashes before quotes and at the closing quote.
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Invoke-Stage0Command([string]$File, [string[]]$Arguments, [int]$Timeout = 1800) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName=$File; $info.Arguments=($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $info.UseShellExecute=$false; $info.CreateNoWindow=$true; $info.RedirectStandardOutput=$true; $info.RedirectStandardError=$true
    $process = New-Object Diagnostics.Process
    $process.StartInfo=$info
    try {
        $null=$process.Start(); $stdout=$process.StandardOutput.ReadToEndAsync(); $stderr=$process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit($Timeout*1000)) {
            & "$env:SystemRoot\System32\taskkill.exe" /PID $process.Id /T /F | Out-Null
            throw "Command timed out after $Timeout seconds. Inspect installation state before retrying."
        }
        $output=$stdout.GetAwaiter().GetResult(); $errorText=$stderr.GetAwaiter().GetResult()
        if ($output) { Write-Host $output }; if ($errorText) { Write-Host $errorText }
        if ($process.ExitCode -in @(3010,1641)) { throw 'Installation requires a reboot. Restart Windows, then rerun bootstrap with the same options.' }
        if ($process.ExitCode -ne 0) { throw "Command exited with $($process.ExitCode). See transcript; retry after repairing the reported failure." }
        return $output
    } finally { $process.Dispose() }
}
Update-Stage0Path
$localCheckout = Test-Path -LiteralPath "$PSScriptRoot/scripts/workspace.ps1"
if (-not $RepositoryPath) {
    if ($localCheckout) { $RepositoryPath=$PSScriptRoot }
    elseif ($env:AI_WORKSPACE_ROOT) { $RepositoryPath=$env:AI_WORKSPACE_ROOT }
    elseif (Test-Path D:\) { $RepositoryPath='D:\AI' }
    else { $RepositoryPath=Join-Path $env:SystemDrive 'AI' }
}
$RepositoryPath=[IO.Path]::GetFullPath($RepositoryPath)
$manifestPath=Join-Path $PSScriptRoot 'config/packages.json'
if (Test-Path -LiteralPath $manifestPath) { $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json }
elseif ($WhatIf) { Write-Host 'PLAN acquire prerequisite manifest, WinGet if missing, machine prerequisites with -MachineOnly, then clone and reconcile the selected profile.'; return }
else {
    [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
    $manifest=Invoke-RestMethod 'https://raw.githubusercontent.com/recoder/AI/main/config/packages.json' -TimeoutSec 30
}
if ($manifest.version -ne 1) { throw 'Unsupported prerequisite manifest version.' }
if ($WhatIf) {
    foreach ($package in $manifest.packages) { if (-not $MachineOnly -or $package.scope -eq 'machine') { Write-Host "PLAN ensure $($package.name) [$($package.scope)]" } }
    Write-Host "PLAN repository: $RepositoryUrl -> $RepositoryPath"
    if ($localCheckout -and (Get-Command pwsh -ErrorAction SilentlyContinue)) {
        $arguments=@('-NoProfile','-File',"$PSScriptRoot/scripts/workspace.ps1",'-WhatIf'); if ($Profile) { $arguments+=@('-Profile',$Profile) }
        & pwsh @arguments; if ($LASTEXITCODE -ne 0) { throw 'Workspace plan failed.' }
    }
    return
}
$log=Join-Path $env:TEMP ("AI-stage0-"+[guid]::NewGuid().ToString('N')+'.log')
Start-Transcript -LiteralPath $log | Out-Null
try {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        # Microsoft documents registration for newly logged-in users; repair acquires missing App Installer.
        $installed=Get-AppxPackage -Name Microsoft.DesktopAppInstaller -ErrorAction SilentlyContinue
        if ($installed) { Add-AppxPackage -RegisterByFamilyName -MainPackage Microsoft.DesktopAppInstaller_8wekyb3d8bbwe }
        Update-Stage0Path
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
            Write-Host 'Acquiring WinGet with Microsoft.WinGet.Client 1.9.25190 (CurrentUser module).'
            [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
            Install-PackageProvider -Name NuGet -MinimumVersion 2.8.5.201 -Scope CurrentUser -Force | Out-Null
            Install-Module Microsoft.WinGet.Client -RequiredVersion 1.9.25190 -Scope CurrentUser -Repository PSGallery -Force -AllowClobber
            Import-Module Microsoft.WinGet.Client -RequiredVersion 1.9.25190
            if ($MachineOnly) { Repair-WinGetPackageManager -AllUsers } else { Repair-WinGetPackageManager }
            Update-Stage0Path
            if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw 'WinGet unavailable after repair. Install official App Installer, open a new shell and retry bootstrap.' }
        }
    }
    foreach ($package in $manifest.packages) {
        if ($MachineOnly -and $package.scope -ne 'machine') { continue }
        $command=Get-Command $package.command -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        $usable=$false
        if ($command) {
            try {
                $probe=Invoke-Stage0Command $command.Source @($package.arguments) 30
                $usable=$true
                if ($package.version -and $probe -notmatch [regex]::Escape($package.version)) { throw "Declared version mismatch for $($package.name); update explicitly." }
                if ($package.name -eq 'powershell' -and $probe -notmatch 'PowerShell (7\.[4-9]|[89]\.)') { $usable=$false }
            } catch { $usable=$false; Write-Host "Probe $($package.name): $($_.Exception.Message)" }
        }
        if ($usable) { Write-Host "OK $($package.name)"; continue }
        if ($package.scope -eq 'machine' -and -not $administrator) { throw "Missing machine prerequisite '$($package.name)'. In an administrator shell run this bootstrap.ps1 with -MachineOnly, then return to a normal shell and rerun. No UAC prompt is launched unattended." }
        Write-Host "Installing $($package.name) [$($package.scope)]"
        $arguments=@('install','--id',$package.id,'--exact','--source','winget','--scope',$package.scope,'--silent','--disable-interactivity','--accept-package-agreements','--accept-source-agreements')
        if ($package.version) { $arguments+=@('--version',$package.version) }
        Invoke-Stage0Command (Get-Command winget).Source $arguments | Out-Null
        Update-Stage0Path
        $command=Get-Command $package.command -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $command) { throw "Installed $($package.name) not on PATH. Open a new shell and retry." }
        Invoke-Stage0Command $command.Source @($package.arguments) 30 | Out-Null
    }
    if ($MachineOnly) { Write-Host 'Machine prerequisites ready. Return to the normal-user shell and rerun bootstrap.ps1.'; return }
    if (-not (Test-Path -LiteralPath (Join-Path $RepositoryPath '.git'))) {
        if ((Test-Path -LiteralPath $RepositoryPath) -and @(Get-ChildItem -LiteralPath $RepositoryPath -Force).Count) { throw 'Repository target is nonempty without .git. Preserve it and select an empty -RepositoryPath; bootstrap will not replace files.' }
        Invoke-Stage0Command (Get-Command git).Source @('clone','--branch','main',$RepositoryUrl,$RepositoryPath) 600 | Out-Null
    }
    $actual=Invoke-Stage0Command (Get-Command git).Source @('-C',$RepositoryPath,'remote','get-url','origin') 30
    $normalize={param($Url) ($Url.Trim().Replace('git@github.com:','https://github.com/').TrimEnd('/') -replace '\.git$','')}
    if ((& $normalize $actual) -ne (& $normalize $RepositoryUrl)) { throw 'Workspace repository origin differs from requested source; preserve and resolve explicitly.' }
    $pwsh=(Get-Command pwsh).Source
    Invoke-Stage0Command $pwsh @('-NoProfile','-File',"$RepositoryPath/scripts/setup.ps1") 600 | Out-Null
    $arguments=@('-NoProfile','-File',"$RepositoryPath/scripts/workspace.ps1"); if ($Profile) { $arguments+=@('-Profile',$Profile) }
    # Stage 1 streams long-running progress and manages its own component logs.
    & $pwsh @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Workspace reconciliation failed. Use the summary/log repair commands and retry the same bootstrap.' }
} finally { Stop-Transcript | Out-Null; Write-Host "Stage 0 log: $log" }
