#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-AceStepConfig
& "$PSScriptRoot/source.ps1"
New-Item -ItemType Directory -Path $config.Workspace.Paths.bin -Force | Out-Null
$log = Join-Path $config.Workspace.Paths.logs "ace-step-install-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
$savedEnvironment = @{}
foreach ($name in @('UV_PROJECT_ENVIRONMENT', 'UV_CACHE_DIR')) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $config.Application '.venv'
    $env:UV_CACHE_DIR = $config.Workspace.Paths.uv_cache
    & uv sync --frozen --project $config.Application --python $config.Declaration.python
    if ($LASTEXITCODE -ne 0) { throw 'ACE-Step environment sync failed. Inspect this log and retry just install ace-step.' }
    foreach ($name in @('ace-step.py', 'ace_step_backend.py', 'ace-step.example.yaml', 'song_jobs.py')) {
        $source = Join-Path $script:RepositoryRoot "bin/$name"
        $destination = Join-Path $config.Workspace.Paths.bin $name
        if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($destination)) {
            if (Test-Path -LiteralPath $destination) {
                if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
                    throw "Runner file '$destination' differs from tracked source. Preserve/resolve it explicitly before retrying."
                }
            } else { Copy-Item -LiteralPath $source -Destination $destination }
        }
    }
    $runnerConfig = Join-Path $config.Workspace.Paths.bin 'ace-step.yaml'
    if (-not (Test-Path -LiteralPath $runnerConfig)) {
        $models = (Read-WorkspaceManifest models).models['ace-step']
        $settings = [ordered]@{ version = 1; tool = 'ace-step'; backend = 'official-python-api';
            paths = [ordered]@{ application = $config.Application; python = (Join-Path $config.Application '.venv/Scripts/python.exe');
                entrypoint = (Join-Path $config.Workspace.Paths.bin 'ace_step_backend.py'); models = $config.Models };
            runtime = $config.Declaration.runtime_settings; defaults = $config.Declaration.defaults;
            identities = @{ source_revision = $config.Declaration.revision;
                model_revisions = @{ main = $models.repositories.main.revision; 'xl-sft' = $models.repositories['xl-sft'].revision } };
            output = @{ directory = (Join-Path $config.Workspace.Paths.music_work 'generated') } }
        ConvertTo-Yaml $settings | Set-Content -LiteralPath $runnerConfig -Encoding utf8
    }
    $python = Join-Path $config.Application '.venv/Scripts/python.exe'
    & $python (Join-Path $script:RepositoryRoot 'bin/ace_step_backend.py') --probe $config.Application
    if ($LASTEXITCODE -ne 0) { throw 'ACE-Step import/GPU probe failed. Fix the reported dependency or driver error, then retry.' }
    Write-Host 'ACE-Step runtime installed. Models: just models ace-step. Validate: just validate ace-step.'
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    Stop-Transcript | Out-Null
    Write-Host "Log: $log"
}
