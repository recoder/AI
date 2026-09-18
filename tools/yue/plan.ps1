#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-YueConfig
Write-Host "YuE generation: $($config.Declaration.generation)"
Write-Host "Source: $($config.Declaration.repo) @ $($config.Declaration.revision)"
Write-Host "Application: $($config.Application)"
Write-Host "Runtime: native Windows, Python $($config.Declaration.python), PyTorch 2.10 CUDA 13.0, Triton 3.6"
Write-Host "Shared models: $($config.Models)"
Write-Host 'Models: pinned INT8 acoustic/AR weights and BF16 VAE, about 4.27 GiB; allow additional environment/cache space.'
Write-Host 'Next: just install yue; just models yue; just validate yue'
