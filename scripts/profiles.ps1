# Shared declarative profile expansion; loading this file does not mutate state.
. "$PSScriptRoot/common.ps1"

function Get-WorkspaceProfile {
    param([string]$Name)
    $manifest = Read-WorkspaceManifest profiles
    if (-not $Name) { $Name = if ($env:AI_PROFILE) { $env:AI_PROFILE } else { $manifest.default } }
    $selected = [ordered]@{ Name = $Name; packages = @(); tools = @(); models = @(); repos = @() }
    $visiting = @{}
    $expanded = @{}
    function Expand-Profile([string]$ProfileName) {
        if ($ProfileName -notmatch '^[a-z0-9][a-z0-9-]*$' -or -not $manifest.profiles.Contains($ProfileName)) { throw "Unknown profile '$ProfileName'. Check config/profiles.yaml." }
        if ($visiting[$ProfileName]) { throw "Profile include cycle at '$ProfileName'." }
        if ($expanded[$ProfileName]) { return }
        $visiting[$ProfileName] = $true
        $definition = $manifest.profiles[$ProfileName]
        if ($definition -isnot [Collections.IDictionary]) { throw "Profile '$ProfileName' must be a mapping." }
        foreach ($field in $definition.Keys) {
            if ($field -notin @('includes','packages','tools','models','repos') -or $definition[$field] -isnot [Collections.IList]) { throw "Invalid profile field '$ProfileName.$field'; expected a supported list." }
            foreach ($item in $definition[$field]) { if ($item -isnot [string] -or $item -notmatch '^[a-z0-9][a-z0-9-]*$') { throw "Invalid profile component '$item'." } }
        }
        foreach ($include in @($definition.includes)) { if ($include) { Expand-Profile $include } }
        foreach ($field in @('packages','tools','models','repos')) { $selected[$field] = @($selected[$field] + @($definition[$field]) | Where-Object { $_ } | Select-Object -Unique) }
        $visiting.Remove($ProfileName)
        $expanded[$ProfileName] = $true
    }
    Expand-Profile $Name
    $known = @{ packages = @(Get-PackageConfig | ForEach-Object name); tools = @((Read-WorkspaceManifest tools).tools.Keys);
        models = @((Read-WorkspaceManifest models).models.Keys); repos = @((Read-WorkspaceManifest repos).repos.Keys) }
    foreach ($field in $known.Keys) { foreach ($item in $selected[$field]) { if ($item -notin $known[$field]) { throw "Profile '$Name' references unknown $field component '$item'." } } }
    return [pscustomobject]$selected
}

function Set-WorkspaceCacheEnvironment {
    param([switch]$Persist)
    $workspace = Get-WorkspaceConfig
    $environment = (Read-WorkspaceManifest workspace).workspace.environment
    # Validate the complete declaration before changing the process or user environment.
    foreach ($entry in $environment.GetEnumerator()) {
        if ($entry.Key -notin @('UV_CACHE_DIR','HF_HOME','TORCH_HOME','PIP_CACHE_DIR','TRITON_CACHE_DIR') -or -not $workspace.Paths.Contains($entry.Value)) { throw "Invalid shared cache environment mapping '$($entry.Key)'." }
    }
    foreach ($entry in $environment.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $workspace.Paths[$entry.Value], 'Process')
        if ($Persist) { [Environment]::SetEnvironmentVariable($entry.Key, $workspace.Paths[$entry.Value], 'User') }
    }
}
