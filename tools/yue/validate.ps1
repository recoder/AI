#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-YueConfig
$state = Get-YueState $config
if (-not $state.Source.Ready) { throw "YuE source: $($state.Source.Detail). Repair: just source yue" }
if (-not $state.Runtime -or -not $state.Runner) { throw 'YuE runtime/config missing. Repair: just install yue' }
& $state.Python (Join-Path $script:RepositoryRoot 'bin/yue_backend.py') --probe $config.Application
if ($LASTEXITCODE -ne 0) { throw 'YuE CUDA/import validation failed. Inspect errors above; repair driver/dependencies and retry just install yue.' }
& $state.Python "$PSScriptRoot/models.py" --manifest (Join-Path $script:RepositoryRoot 'config/models.yaml') --destination $config.Models --check
if ($LASTEXITCODE -ne 0) { throw 'YuE artifacts failed validation. Repair: just models yue' }
& $state.Python (Join-Path $config.Workspace.Paths.bin 'yue.py') (Join-Path $script:RepositoryRoot 'examples/song-jobs/yue-first-song.md') --validate
if ($LASTEXITCODE -ne 0) { throw 'YuE example/config validation failed. Inspect selected yue.yaml and retry just validate yue.' }
Write-Host 'OK YuE native source, imports, CUDA/BF16, model hashes and Markdown job. Audio generation is a separate smoke test.'
