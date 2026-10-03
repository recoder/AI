. "$PSScriptRoot/../../scripts/application-common.ps1"

function Get-MiniMaxMusic3Config {
    $config = Get-ApplicationConfig 'minimax-music3'
    $tool = $config.Declaration
    if ($tool.generation -ne 'MiniMax Music 3' -or $tool.backend -ne 'diffusers-modular' -or $tool.runtime -ne 'native') {
        throw 'MiniMax Music 3 requires the pinned native Diffusers modular runtime.'
    }
    if ($tool.repo -or $tool.revision) { throw 'MiniMax Music 3 is package-managed; source revisions belong in the runtime lock and model manifest.' }
    $project = [IO.Path]::GetFullPath($tool.runtime_project, $script:RepositoryRoot)
    if (-not $project.StartsWith($script:RepositoryRoot.TrimEnd('\','/') + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'MiniMax Music 3 runtime project escapes the repository.'
    }
    if (-not (Test-Path -LiteralPath (Join-Path $project 'uv.lock') -PathType Leaf)) {
        throw 'MiniMax Music 3 frozen runtime lock is missing.'
    }
    $config | Add-Member -NotePropertyName RuntimeProject -NotePropertyValue $project
    return $config
}

function Get-MiniMaxMusic3State {
    param($Config = (Get-MiniMaxMusic3Config))
    $python = Join-Path $Config.Application '.venv/Scripts/python.exe'
    $runtime = Test-Path -LiteralPath $python -PathType Leaf
    $declaration = (Read-WorkspaceManifest models).models['minimax-music3']
    if ($declaration.path -ne $Config.Declaration.model_path) { throw 'MiniMax Music 3 tool/model destinations disagree.' }
    $missing = @($declaration.files | Where-Object {
        $path = [IO.Path]::GetFullPath($_.name, $Config.Models)
        if (-not $path.StartsWith($Config.Models.TrimEnd('\', '/') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw 'MiniMax Music 3 artifact escapes its destination.'
        }
        -not (Test-Path -LiteralPath $path -PathType Leaf) -or (Get-Item -LiteralPath $path).Length -ne $_.size
    })
    $runner = Test-Path -LiteralPath (Join-Path $Config.Workspace.Paths.bin 'minimax-music3.yaml') -PathType Leaf
    return [pscustomobject]@{ Runtime = $runtime; Python = $python; Models = ($missing.Count -eq 0);
        MissingModels = $missing; Runner = $runner; Ready = ($runtime -and $missing.Count -eq 0 -and $runner) }
}
