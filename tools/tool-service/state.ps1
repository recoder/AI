#requires -Version 7.4
. "$PSScriptRoot/../../scripts/common.ps1"
$workspace = Get-WorkspaceConfig
$declaration = (Read-WorkspaceManifest tools).tools['tool-service']
$runtime = Test-Path -LiteralPath (Join-Path (Join-Path $workspace.Root $declaration.path) '.venv/Scripts/python.exe') -PathType Leaf
$settings = Read-WorkspaceManifest tool-service
$keys = Test-Path -LiteralPath ([IO.Path]::GetFullPath($settings.keys_file, (Join-Path $script:RepositoryRoot 'config'))) -PathType Leaf
[pscustomobject]@{ Ready = ($runtime -and $keys); Runtime = $runtime; Models = $true; Runner = $keys }
