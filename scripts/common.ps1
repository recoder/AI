# Shared configuration and read-only state detection; dot-sourcing does not mutate state.
$ErrorActionPreference = 'Stop'
$script:RepositoryRoot = Split-Path $PSScriptRoot -Parent
$script:YamlVersion = '0.4.12'

function Read-WorkspaceManifest {
    param([Parameter(Mandatory)][string]$Name)
    if (-not (Get-Module powershell-yaml | Where-Object Version -EQ $script:YamlVersion)) {
        try { Import-Module powershell-yaml -RequiredVersion $script:YamlVersion -ErrorAction Stop }
        catch { throw "YAML support is missing. Run pwsh -File scripts/setup.ps1, then retry. $($_.Exception.Message)" }
    }
    $manifestPath = Join-Path $script:RepositoryRoot "config/$Name.yaml"
    try { $data = ConvertFrom-Yaml (Get-Content -LiteralPath $manifestPath -Raw) -Ordered }
    catch { throw "Cannot read manifest '$manifestPath': $($_.Exception.Message)" }
    if ($data -isnot [System.Collections.IDictionary] -or $data.version -ne 1) {
        throw "Invalid manifest '$manifestPath': expected a mapping with version: 1."
    }
    return $data
}

function Get-WorkspaceConfig {
    $data = (Read-WorkspaceManifest workspace).workspace
    if ($data -isnot [System.Collections.IDictionary] -or $data.directories -isnot [System.Collections.IDictionary]) {
        throw 'Invalid config/workspace.yaml: workspace and directories must be mappings.'
    }
    $configuredRoot = if ($env:AI_WORKSPACE_ROOT) { $env:AI_WORKSPACE_ROOT } else { $data.root }
    if ([string]::IsNullOrWhiteSpace($configuredRoot)) { throw 'Workspace root is empty; check config/workspace.yaml.' }
    $root = [IO.Path]::GetFullPath($configuredRoot, (Join-Path $script:RepositoryRoot 'config'))
    $paths = [ordered]@{}
    foreach ($entry in $data.directories.GetEnumerator()) {
        if ($entry.Value -isnot [string] -or [string]::IsNullOrWhiteSpace($entry.Value)) {
            throw "Directory '$($entry.Key)' must be a nonempty relative path."
        }
        if ([IO.Path]::IsPathRooted($entry.Value)) { throw "Directory '$($entry.Key)' must be relative to the workspace." }
        $path = [IO.Path]::GetFullPath($entry.Value, $root)
        $prefix = $root.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar
        if (-not $path.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw "Directory '$($entry.Key)' escapes the workspace root."
        }
        $paths[$entry.Key] = $path
    }
    return [pscustomobject]@{ Root = $root; Paths = $paths }
}

function Get-PackageConfig {
    $packages = (Read-WorkspaceManifest packages).packages
    if ($packages -isnot [System.Collections.IList]) { throw 'Invalid config/packages.yaml: packages must be a list.' }
    $names = @{}
    foreach ($package in $packages) {
        if ($package -isnot [System.Collections.IDictionary]) { throw 'Invalid package declaration: each package must be a mapping.' }
        foreach ($field in @('name', 'id', 'command', 'scope')) {
            if ($package[$field] -isnot [string] -or [string]::IsNullOrWhiteSpace($package[$field])) {
                throw "Invalid package declaration: '$field' must be a nonempty string."
            }
        }
        if ($names.ContainsKey($package.name)) { throw "Duplicate package name '$($package.name)' in config/packages.yaml." }
        $names[$package.name] = $true
        if ($package.scope -notin @('user', 'machine')) { throw "Package '$($package.name)' has invalid scope '$($package.scope)'." }
        if ($package.arguments -isnot [System.Collections.IList]) { throw "Package '$($package.name)' arguments must be a list." }
        foreach ($argument in $package.arguments) {
            if ($argument -isnot [string]) { throw "Package '$($package.name)' arguments must contain strings." }
        }
        foreach ($field in @('probe_timeout_seconds', 'install_timeout_seconds')) {
            if ($package.Contains($field) -and ($package[$field] -isnot [int] -or $package[$field] -lt 1 -or $package[$field] -gt 86400)) {
                throw "Package '$($package.name)' $field must be an integer from 1 to 86400."
            }
        }
        $package
    }
}

function Invoke-WorkspaceCommand {
    param([Parameter(Mandatory)][string]$FilePath, [string[]]$Arguments = @(),
        [ValidateRange(1, 86400)][int]$TimeoutSeconds = 30)
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $FilePath
    $startInfo.UseShellExecute = $false
    $startInfo.CreateNoWindow = $true
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    foreach ($argument in $Arguments) { $startInfo.ArgumentList.Add($argument) }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    try {
        $null = $process.Start()
        # Drain both streams concurrently so a verbose child cannot fill a pipe and deadlock.
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        $timedOut = -not $process.WaitForExit($TimeoutSeconds * 1000)
        if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
        return [pscustomobject]@{ ExitCode = $process.ExitCode; TimedOut = $timedOut;
            Output = $stdout.GetAwaiter().GetResult(); ErrorOutput = $stderr.GetAwaiter().GetResult() }
    } finally { $process.Dispose() }
}

function Get-PackageState {
    param([Parameter(Mandatory)]$Package)
    $command = Get-Command $Package.command -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $usable = $false
    $detail = 'command not found'
    if ($command) {
        try {
            $timeout = if ($Package.probe_timeout_seconds) { $Package.probe_timeout_seconds } else { 30 }
            $result = Invoke-WorkspaceCommand -FilePath $command.Source -Arguments @($Package.arguments) -TimeoutSeconds $timeout
            $output = $result.Output + "`n" + $result.ErrorOutput
            $usable = -not $result.TimedOut -and $result.ExitCode -eq 0
            $detail = if ($result.TimedOut) { "probe timed out after $timeout seconds" }
                elseif ($usable) { "$($output -split '\r?\n' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) } | Select-Object -First 1)" }
                else { "probe exited with $($result.ExitCode)" }
            if ($usable -and $Package.version) {
                $usable = $output -match "(?<![\d.])$([regex]::Escape([string]$Package.version))(?![\d.])"
                if (-not $usable) { $detail = "version does not match declared $($Package.version); updates require explicit action" }
            }
        } catch { $detail = "cannot run probe: $($_.Exception.Message)" }
    }
    return [pscustomobject]@{ Name = $Package.name; Usable = $usable; Detail = $detail; Found = [bool]$command }
}

function Get-InstallerFailureMessage {
    param([int]$ExitCode)
    $hex = '0x{0:X8}' -f [BitConverter]::ToUInt32([BitConverter]::GetBytes($ExitCode), 0)
    $message = "winget exited with $ExitCode ($hex). Inspect its output; retry just packages after resolving the failure."
    if ($hex -eq '0x80070020') {
        $message += ' File-sharing failure: WinGet 1.29.360 has a reported regression after hash verification. Check the WinGet log/version; use the official package installer or a fixed WinGet release. Do not bypass hash verification.'
    }
    return $message
}

function Update-ProcessPath {
    # Add freshly installed command locations without discarding this shell's existing PATH.
    $locations = @($env:PATH, [Environment]::GetEnvironmentVariable('PATH', 'Machine'),
        [Environment]::GetEnvironmentVariable('PATH', 'User'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Links'),
        (Join-Path $env:ProgramFiles 'Git/cmd'), (Join-Path $env:ProgramFiles '7-Zip'),
        (Join-Path $env:ProgramFiles 'PowerShell/7'))
    $env:PATH = (($locations -join ';') -split ';' | Where-Object { $_ } | Select-Object -Unique) -join ';'
}
