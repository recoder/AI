#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-MiniMaxMusic3Config
New-Item -ItemType Directory -Path $config.Application, $config.Workspace.Paths.bin -Force | Out-Null
$log = Join-Path $config.Workspace.Paths.logs "minimax-music3-install-$([guid]::NewGuid().ToString('N')).log"
Start-Transcript -LiteralPath $log | Out-Null
try {
    Initialize-ApplicationEnvironment -Config $config -Project $config.RuntimeProject
    foreach ($name in @('minimax-music3.py', 'minimax_music3_backend.py', 'minimax-music3.example.yaml', 'song_jobs.py')) {
        $source = Join-Path $script:RepositoryRoot "bin/$name"
        $destination = Join-Path $config.Workspace.Paths.bin $name
        if ([IO.Path]::GetFullPath($source) -ne [IO.Path]::GetFullPath($destination)) {
            if (Test-Path -LiteralPath $destination) {
                if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
                    throw "Runner file '$destination' differs from tracked source. Preserve/resolve it explicitly."
                }
            } else { Copy-Item -LiteralPath $source -Destination $destination }
        }
    }
    $runnerConfig = Join-Path $config.Workspace.Paths.bin 'minimax-music3.yaml'
    if (-not (Test-Path -LiteralPath $runnerConfig)) {
        $model = (Read-WorkspaceManifest models).models['minimax-music3']
        $settings = [ordered]@{ version = 1; tool = 'minimax-music3'; backend = 'diffusers-modular';
            paths = [ordered]@{ python = (Join-Path $config.Application '.venv/Scripts/python.exe');
                entrypoint = (Join-Path $config.Workspace.Paths.bin 'minimax_music3_backend.py'); models = $config.Models };
            runtime = $config.Declaration.runtime_settings; defaults = $config.Declaration.defaults;
            identities = @{ model_revision = $model.revision; diffusers_version = '0.40.0' };
            output = @{ directory = (Join-Path $config.Workspace.Paths.music_work 'generated') } }
        ConvertTo-Yaml $settings | Set-Content -LiteralPath $runnerConfig -Encoding utf8
    }
    $python = Join-Path $config.Application '.venv/Scripts/python.exe'
    & $python (Join-Path $script:RepositoryRoot 'bin/minimax_music3_backend.py') --probe
    if ($LASTEXITCODE -ne 0) { throw 'MiniMax Music 3 import/CUDA probe failed. Inspect the log and retry just install minimax-music3.' }
    Write-Host 'MiniMax Music 3 runtime installed. Models: just models minimax-music3. Validate: just validate minimax-music3.'
} finally { Stop-Transcript | Out-Null; Write-Host "Log: $log" }
