. "$PSScriptRoot/../../scripts/application-common.ps1"

function Get-AceStepConfig {
    $config = Get-ApplicationConfig 'ace-step'
    $tool = $config.Declaration
    if ($tool.generation -ne 'ACE-Step 1.5' -or $tool.backend -ne 'official-python-api' -or $tool.runtime -ne 'native') {
        throw 'ACE-Step requires the official ACE-Step 1.5 native Python API.'
    }
    if ($tool.runtime_settings.dit_model -ne 'acestep-v15-xl-sft' -or $tool.runtime_settings.fallback_dit_model -ne 'acestep-v15-turbo') {
        throw 'ACE-Step must declare XL SFT as the quality default and 2B Turbo as the fallback.'
    }
    return $config
}

function Get-AceStepState {
    param($Config = (Get-AceStepConfig))
    $source = Get-RepositoryState $Config.Application $Config.Declaration.repo $Config.Declaration.revision
    $entrypoint = Test-Path -LiteralPath (Join-Path $Config.Application $Config.Declaration.entrypoint) -PathType Leaf
    $python = Join-Path $Config.Application '.venv/Scripts/python.exe'
    $runtime = Test-Path -LiteralPath $python -PathType Leaf
    $declaration = (Read-WorkspaceManifest models).models['ace-step']
    if ($declaration.path -ne $Config.Declaration.model_path) { throw 'ACE-Step tool/model destination declarations must agree.' }
    $missing = @($declaration.files | Where-Object {
        $path = [IO.Path]::GetFullPath($_.name, $Config.Models)
        if (-not $path.StartsWith($Config.Models.TrimEnd('\', '/') + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'ACE-Step artifact escapes its destination.' }
        -not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $_.size
    })
    $runner = Test-Path -LiteralPath (Join-Path $Config.Workspace.Paths.bin 'ace-step.yaml') -PathType Leaf
    $sourceReady = $source.Ready -and -not $source.Dirty -and $entrypoint
    return [pscustomobject]@{ Source = $source; SourceReady = $sourceReady; Runtime = $runtime; Python = $python;
        Models = ($missing.Count -eq 0); MissingModels = $missing; Runner = $runner;
        Ready = ($sourceReady -and $runtime -and $missing.Count -eq 0 -and $runner) }
}
