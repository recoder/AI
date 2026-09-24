#requires -Version 7.4
[CmdletBinding(SupportsShouldProcess)]
param([string[]]$Names, [switch]$DefinitionsOnly)
. "$PSScriptRoot/common.ps1"

function Invoke-WorkspaceGit {
    param([string[]]$Arguments)
    $result = Invoke-WorkspaceCommand -FilePath (Get-Command git -CommandType Application).Source -Arguments $Arguments -TimeoutSeconds 600
    if ($result.TimedOut -or $result.ExitCode -ne 0) { throw "Git failed (exit $($result.ExitCode), timeout $($result.TimedOut)): $($result.ErrorOutput). Check network/authentication and retry; local work is preserved." }
    return $result.Output.Trim()
}

function Get-RepositoryState {
    param([string]$Path, [string]$Remote, [string]$Revision)
    if (-not (Test-Path -LiteralPath $Path)) { return [pscustomobject]@{ Ready=$false; Detail='absent'; Missing=$true; Dirty=$false } }
    try {
        if (-not (Test-Path -LiteralPath (Join-Path $Path '.git'))) { throw 'path exists without a Git repository' }
        $actual = Invoke-WorkspaceGit @('-C',$Path,'remote','get-url','origin')
        if ($actual -ne $Remote) { throw 'remote mismatch' }
        $head = Invoke-WorkspaceGit @('-C',$Path,'rev-parse','HEAD')
        if ($Revision -match '^[a-f0-9]{40}$') { if ($head -ne $Revision) { throw "revision mismatch: $head" } }
        else {
            $branch = Invoke-WorkspaceGit @('-C',$Path,'symbolic-ref','--quiet','--short','HEAD')
            if ($branch -ne $Revision) { throw "branch mismatch: expected $Revision, found $branch" }
        }
        $dirty = [bool](Invoke-WorkspaceGit @('-C',$Path,'status','--porcelain'))
        return [pscustomobject]@{ Ready=$true; Detail=$(if($dirty){'local changes preserved'}else{'ready'}); Missing=$false; Dirty=$dirty }
    } catch { return [pscustomobject]@{ Ready=$false; Detail=$_.Exception.Message; Missing=$false; Dirty=$false } }
}

function Get-UserRepositoryConfig {
    $workspace = Get-WorkspaceConfig
    foreach ($entry in (Read-WorkspaceManifest repos).repos.GetEnumerator()) {
        if ($entry.Key -notmatch '^[a-z0-9][a-z0-9-]*$' -or $entry.Value -isnot [Collections.IDictionary]) { throw 'Invalid user repository declaration.' }
        $repo = $entry.Value
        if ($repo.url -notmatch '^(https://|git@)' -or -not $repo.revision -or [IO.Path]::IsPathRooted($repo.path)) { throw "Invalid repository '$($entry.Key)': specify url, relative path, and revision (branch or commit)." }
        $path = [IO.Path]::GetFullPath($repo.path, $workspace.Root)
        if (-not $path.StartsWith($workspace.Paths.work.TrimEnd('\','/') + '\',[StringComparison]::OrdinalIgnoreCase)) { throw 'User repository path must remain under workspace work/.' }
        [pscustomobject]@{ Name=$entry.Key; Path=$path; Remote=$repo.url; Revision=$repo.revision }
    }
}

if ($DefinitionsOnly) { return }
foreach ($repo in @(Get-UserRepositoryConfig)) {
    if ($Names -and $repo.Name -notin $Names) { continue }
    $state = Get-RepositoryState $repo.Path $repo.Remote $repo.Revision
    if ($state.Ready) { Write-Host "OK repository $($repo.Name): $($state.Detail)"; continue }
    if (-not $state.Missing) { throw "Repository '$($repo.Name)': $($state.Detail). Resolve explicitly before retrying just repos; no reset is performed." }
    if (-not $PSCmdlet.ShouldProcess($repo.Path,'Clone user repository')) { continue }
    New-Item -ItemType Directory -Path (Split-Path $repo.Path) -Force | Out-Null
    if ($repo.Revision -match '^[a-f0-9]{40}$') {
        Invoke-WorkspaceGit @('clone','--no-checkout',$repo.Remote,$repo.Path) | Write-Host
        Invoke-WorkspaceGit @('-C',$repo.Path,'checkout','--detach',$repo.Revision) | Write-Host
    } else { Invoke-WorkspaceGit @('clone','--branch',$repo.Revision,$repo.Remote,$repo.Path) | Write-Host }
    $state = Get-RepositoryState $repo.Path $repo.Remote $repo.Revision
    if (-not $state.Ready) { throw "Repository validation failed: $($state.Detail). Existing content is preserved." }
}
