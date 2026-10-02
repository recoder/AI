#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-AceStepConfig
$models = (Read-WorkspaceManifest models).models['ace-step']
$bytes = 0L
foreach ($artifact in $models.files) { $bytes += [long]$artifact.size }
Write-Host "ACE-Step generation: $($config.Declaration.generation), quality-first XL SFT"
Write-Host "Source: $($config.Declaration.repo) @ $($config.Declaration.revision)"
Write-Host "Application: $($config.Application)"
Write-Host "Runtime: native Windows, Python $($config.Declaration.python), official frozen uv.lock"
Write-Host "Preferred: XL SFT + 1.7B LM, INT8, CPU offload; fallback: 2B Turbo"
Write-Host "Shared models: $($config.Models) ($([math]::Round($bytes / 1GB, 1)) GiB declared)"
Write-Host 'Next: just install ace-step; just models ace-step; just validate ace-step'
