#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-YueConfig
$python = Join-Path $config.Application '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'YuE environment missing. Run just install yue before just models yue.' }
$log = Join-Path $config.Workspace.Paths.logs "yue-models-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
$savedHome = $env:HF_HOME
$env:HF_HOME = $config.Workspace.Paths.huggingface_cache
try {
    & $python "$PSScriptRoot/models.py" --manifest (Join-Path $script:RepositoryRoot 'config/models.yaml') --destination $config.Models
    if ($LASTEXITCODE -ne 0) { throw 'YuE model reconciliation failed. Downloads are resumable; inspect this log and retry just models yue.' }
} finally { $env:HF_HOME = $savedHome; Stop-Transcript | Out-Null; Write-Host "Log: $log" }
