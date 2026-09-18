#requires -Version 7.4
[CmdletBinding(SupportsShouldProcess)]
param()
. "$PSScriptRoot/common.ps1"
$workspace = Get-WorkspaceConfig
foreach ($path in @($workspace.Root) + @($workspace.Paths.Values)) {
    if (Test-Path -LiteralPath $path -PathType Container) { Write-Host "OK directory: $path"; continue }
    if (Test-Path -LiteralPath $path) { throw "Cannot create directory '$path': a file already occupies that location." }
    if ($PSCmdlet.ShouldProcess($path, 'Create directory')) {
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}
