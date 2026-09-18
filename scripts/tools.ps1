#requires -Version 7.4
[CmdletBinding()]
param([Parameter(Mandatory)][ValidateSet('source', 'validate', 'plan', 'install', 'models')][string]$Operation,
    [Parameter(Mandatory)][string]$Tool)
. "$PSScriptRoot/common.ps1"
if ($Tool -notmatch '^[a-z0-9][a-z0-9-]*$') { throw 'Tool name must contain lowercase letters, digits, or hyphens.' }
$component = Join-Path $script:RepositoryRoot "tools/$Tool/$Operation.ps1"
if (-not (Test-Path -LiteralPath $component -PathType Leaf)) { throw "Tool '$Tool' does not implement '$Operation'. Check ROADMAP.md for supported work." }
& $component
