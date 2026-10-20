#requires -Version 7.4
[CmdletBinding()]
param([ValidateSet('serve','status','validate')][string]$Operation = 'serve')
. "$PSScriptRoot/common.ps1"
$workspace = Get-WorkspaceConfig
$declaration = (Read-WorkspaceManifest tools).tools['tool-service']
$python = Join-Path (Join-Path $workspace.Root $declaration.path) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    if ($Operation -eq 'status') { Write-Host 'Tool service: environment absent. Install: just install tool-service'; return }
    throw 'Tool service environment is missing. Run just install tool-service, then retry.'
}
$arguments = @((Join-Path $script:RepositoryRoot 'services/tool-service/main.py'))
if ($Operation -ne 'serve') { $arguments += '--check' }
if ($Operation -eq 'validate') { $arguments += '--deep' }
& $python @arguments
if ($LASTEXITCODE -ne 0 -and $Operation -ne 'status') { throw 'Tool service validation/start failed. See repair instructions above and docs/tool-service.md.' }
