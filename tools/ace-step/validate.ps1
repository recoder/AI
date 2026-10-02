#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-AceStepConfig
$state = Get-AceStepState $config
if (-not $state.SourceReady) { throw "ACE-Step source is not pinned/clean with its entrypoint. Repair: just source ace-step. Detail: $($state.Source.Detail)" }
if (-not $state.Runtime -or -not $state.Runner) { throw 'ACE-Step runtime/config missing. Repair: just install ace-step' }
& $state.Python (Join-Path $script:RepositoryRoot 'bin/ace_step_backend.py') --probe $config.Application
if ($LASTEXITCODE -ne 0) { throw 'ACE-Step CUDA/import probe failed. Repair the environment/driver and retry just install ace-step.' }
& $state.Python (Join-Path $script:RepositoryRoot 'scripts/model_artifacts.py') --manifest (Join-Path $script:RepositoryRoot 'config/models.yaml') --destination $config.Models --group ace-step --check
if ($LASTEXITCODE -ne 0) { throw 'ACE-Step artifacts failed validation. Repair: just models ace-step' }
& $state.Python (Join-Path $config.Workspace.Paths.bin 'ace-step.py') (Join-Path $script:RepositoryRoot 'examples/song-jobs/ace-step-first-song.md') --validate
if ($LASTEXITCODE -ne 0) { throw 'ACE-Step example/config validation failed. Inspect ace-step.yaml and retry.' }
Write-Host 'OK ACE-Step pinned source, imports, CUDA/BF16, model artifacts, and Markdown job. Audio generation is a separate smoke test.'
