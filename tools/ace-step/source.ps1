#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-AceStepConfig
Initialize-ApplicationSource $config
Write-Host "OK ACE-Step source: $($config.Application) @ $($config.Declaration.revision)"
