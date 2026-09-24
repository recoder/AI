#requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][string]$Group, [switch]$Check)
. "$PSScriptRoot/application-common.ps1"
$config = Get-ApplicationConfig $Group
$declaration = (Read-WorkspaceManifest models).models[$Group]
if ($declaration.path -ne $config.Declaration.model_path) { throw "Tool/model destination mismatch for '$Group'." }
$python = Join-Path $config.Application '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw "Model environment missing. Run just install $Group first." }
$log = Join-Path $config.Workspace.Paths.logs "models-$Group-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
$savedHome = $env:HF_HOME
$env:HF_HOME = $config.Workspace.Paths.huggingface_cache
try {
    $arguments = @("$PSScriptRoot/model_artifacts.py",'--manifest',(Join-Path $script:RepositoryRoot 'config/models.yaml'),'--destination',$config.Models,'--group',$Group)
    if ($Check) { $arguments += '--check' }
    & $python @arguments
    if ($LASTEXITCODE -ne 0) { throw "Models '$Group' failed validation/reconciliation. Retry just models $Group; partial bytes and logs are preserved." }
} finally { $env:HF_HOME = $savedHome; Stop-Transcript | Out-Null; Write-Host "Log: $log" }
