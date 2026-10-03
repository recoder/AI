#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-MiniMaxMusic3Config
$state = Get-MiniMaxMusic3State $config
if (-not $state.Runtime -or -not $state.Runner) { throw 'MiniMax Music 3 runtime/config missing. Repair: just install minimax-music3' }
& $state.Python (Join-Path $script:RepositoryRoot 'bin/minimax_music3_backend.py') --probe
if ($LASTEXITCODE -ne 0) { throw 'MiniMax Music 3 import/CUDA probe failed. Repair: just install minimax-music3.' }
& $state.Python (Join-Path $script:RepositoryRoot 'scripts/model_artifacts.py') --manifest (Join-Path $script:RepositoryRoot 'config/models.yaml') --destination $config.Models --group minimax-music3 --check
if ($LASTEXITCODE -ne 0) { throw 'MiniMax Music 3 artifacts failed validation. Repair: just models minimax-music3.' }
& $state.Python (Join-Path $script:RepositoryRoot 'bin/minimax_music3_backend.py') --probe-model $config.Models
if ($LASTEXITCODE -ne 0) { throw 'MiniMax Music 3 offline component mapping failed. Inspect the pinned model index and runtime.' }
& $state.Python (Join-Path $config.Workspace.Paths.bin 'minimax-music3.py') (Join-Path $script:RepositoryRoot 'examples/song-jobs/minimax-music3-first-song.md') --validate
if ($LASTEXITCODE -ne 0) { throw 'MiniMax Music 3 example/config validation failed. Inspect minimax-music3.yaml.' }
Write-Host 'OK MiniMax Music 3 imports, CUDA/BF16, model artifacts, and Markdown job. Audio smoke test is separate.'
