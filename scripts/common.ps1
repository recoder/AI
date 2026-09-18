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
    $data = ConvertFrom-Yaml (Get-Content -LiteralPath $manifestPath -Raw)
    if ($data -isnot [System.Collections.IDictionary] -or $data.version -ne 1) {
        throw "Invalid manifest '$manifestPath': expected a mapping with version: 1."
    }
    return $data
}

function Get-WorkspaceConfig {
    $data = (Read-WorkspaceManifest workspace).workspace
    $configuredRoot = if ($env:AI_WORKSPACE_ROOT) { $env:AI_WORKSPACE_ROOT } else { $data.root }
    if ([string]::IsNullOrWhiteSpace($configuredRoot)) { throw 'Workspace root is empty; check config/workspace.yaml.' }
    $root = [IO.Path]::GetFullPath($configuredRoot, (Join-Path $script:RepositoryRoot 'config'))
    $paths = [ordered]@{}
    foreach ($entry in $data.directories.GetEnumerator()) {
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

function Get-PackageState {
    param([Parameter(Mandatory)]$Package)
    $command = Get-Command $Package.command -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $usable = $false
    $detail = 'command not found'
    if ($command) {
        $output = & $command.Source @($Package.arguments) 2>&1
        $usable = $LASTEXITCODE -eq 0
        $detail = if ($usable) { "$($output | Where-Object { -not [string]::IsNullOrWhiteSpace("$_") } | Select-Object -First 1)" } else { "probe exited with $LASTEXITCODE" }
        if ($usable -and $Package.version) {
            $usable = "$output" -match "(?<![\d.])$([regex]::Escape([string]$Package.version))(?![\d.])"
            if (-not $usable) { $detail = "version does not match declared $($Package.version); updates require explicit action" }
        }
    }
    return [pscustomobject]@{ Name = $Package.name; Usable = $usable; Detail = $detail; Found = [bool]$command }
}

function Update-ProcessPath {
    # Add freshly installed command locations without discarding this shell's existing PATH.
    $locations = @($env:PATH, [Environment]::GetEnvironmentVariable('PATH', 'Machine'),
        [Environment]::GetEnvironmentVariable('PATH', 'User'),
        (Join-Path $env:LOCALAPPDATA 'Microsoft/WinGet/Links'),
        (Join-Path $env:ProgramFiles 'Git/cmd'), (Join-Path $env:ProgramFiles '7-Zip'),
        (Join-Path $env:ProgramFiles 'PowerShell/7'))
    $env:PATH = ($locations | Where-Object { $_ }) -join ';'
}
