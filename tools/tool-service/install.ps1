#requires -Version 7.4
. "$PSScriptRoot/../../scripts/common.ps1"
$workspace = Get-WorkspaceConfig
$declaration = (Read-WorkspaceManifest tools).tools['tool-service']
$environmentPath = Join-Path (Join-Path $workspace.Root $declaration.path) '.venv'
$savedEnvironment = $env:UV_PROJECT_ENVIRONMENT
$savedCache = $env:UV_CACHE_DIR
New-Item -ItemType Directory -Path $workspace.Paths.logs -Force | Out-Null
$log = Join-Path $workspace.Paths.logs "tool-service-install-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
try {
    $env:UV_PROJECT_ENVIRONMENT = $environmentPath
    $env:UV_CACHE_DIR = $workspace.Paths.uv_cache
    & uv sync --frozen --no-dev --project (Join-Path $script:RepositoryRoot $declaration.runtime_project) --python $declaration.python
    if ($LASTEXITCODE -ne 0) { throw 'Service environment sync failed; retry just install tool-service.' }
    & (Join-Path $environmentPath 'Scripts/python.exe') -c 'import mcp, starlette, uvicorn, yaml, soundfile, win32job'
    if ($LASTEXITCODE -ne 0) { throw 'Service dependency probe failed; retry just install tool-service.' }
    Write-Host 'Tool service installed. Configure access keys as described in docs/tool-service.md, then run just serve.'
} finally {
    $env:UV_PROJECT_ENVIRONMENT = $savedEnvironment
    $env:UV_CACHE_DIR = $savedCache
    Stop-Transcript | Out-Null
    Write-Host "Log: $log"
}
