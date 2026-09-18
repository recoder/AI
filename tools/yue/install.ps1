#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-YueConfig
& "$PSScriptRoot/source.ps1"
New-Item -ItemType Directory -Path $config.Workspace.Paths.bin -Force | Out-Null
$log = Join-Path $config.Workspace.Paths.logs "yue-install-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
$savedEnvironment = @{}
foreach ($name in @('UV_PROJECT_ENVIRONMENT', 'UV_CACHE_DIR')) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
try {
    $env:UV_PROJECT_ENVIRONMENT = Join-Path $config.Application '.venv'
    $env:UV_CACHE_DIR = $config.Workspace.Paths.uv_cache
    & uv sync --frozen --project $PSScriptRoot --python $config.Declaration.python
    if ($LASTEXITCODE -ne 0) { throw 'YuE environment sync failed. Inspect this log and retry just install yue.' }
    foreach ($name in @('yue.py', 'song_jobs.py', 'yue_backend.py', 'yue.example.yaml')) {
        $source = Join-Path $script:RepositoryRoot "bin/$name"
        $destination = Join-Path $config.Workspace.Paths.bin $name
        if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($destination)) {
            if (Test-Path -LiteralPath $destination) {
                if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
                    throw "Runner file '$destination' differs from the tracked source. Preserve/resolve it explicitly before retrying installation."
                }
            } else { Copy-Item -LiteralPath $source -Destination $destination }
        }
    }
    $runnerConfig = Join-Path $config.Workspace.Paths.bin 'yue.yaml'
    if (-not (Test-Path -LiteralPath $runnerConfig)) {
        $settings = [ordered]@{ version = 1; tool = 'yue'; backend = 'wan2gp-yue2';
            paths = [ordered]@{ application = $config.Application; python = (Join-Path $config.Application '.venv/Scripts/python.exe');
                entrypoint = (Join-Path $config.Workspace.Paths.bin 'yue_backend.py');
                models = [ordered]@{ acoustic = (Join-Path $config.Models 'YuE2_Acoustic_int8_convrot.safetensors');
                    ar = (Join-Path $config.Models 'YuE2_AR/YuE2_AR_int8_convrot.safetensors');
                    tokenizer = (Join-Path $config.Models 'YuE2_AR/qwen.tiktoken');
                    vae = (Join-Path $config.Models 'yue2/YuE2_VAE_bf16.safetensors');
                    vae_config = (Join-Path $config.Models 'yue2/vae_config.json') } };
            runtime = $config.Declaration.runtime_settings;
            defaults = $config.Declaration.defaults;
            identities = @{ source_revision = $config.Declaration.revision; model_revision = (Read-WorkspaceManifest models).models.yue.revision };
            output = @{ directory = (Join-Path $config.Workspace.Paths.music_work 'generated') } }
        ConvertTo-Yaml $settings | Set-Content -LiteralPath $runnerConfig -Encoding utf8
    }
    $python = Join-Path $config.Application '.venv/Scripts/python.exe'
    & $python (Join-Path $script:RepositoryRoot 'bin/yue_backend.py') --probe $config.Application
    if ($LASTEXITCODE -ne 0) { throw 'YuE GPU/import validation failed. Fix the reported dependency/driver error, then retry just install yue.' }
    Write-Host 'YuE native runtime installed. Models: just models yue. Validate: just validate yue.'
} finally {
    foreach ($name in $savedEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    Stop-Transcript | Out-Null
    Write-Host "Log: $log"
}
