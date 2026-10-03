#requires -Version 7.4
. "$PSScriptRoot/common.ps1"
$config = Get-MiniMaxMusic3Config
$models = (Read-WorkspaceManifest models).models['minimax-music3']
$bytes = 0L
foreach ($artifact in $models.files) { $bytes += [long]$artifact.size }
Write-Host 'MiniMax Music 3: native Diffusers modular pipeline, full BF16 quality preset'
Write-Host "Runtime: Python $($config.Declaration.python), pinned project $($config.RuntimeProject)"
Write-Host "Model: $($models.repo) @ $($models.revision)"
Write-Host "Shared model path: $($config.Models) ($([math]::Round($bytes / 1GB, 1)) GiB selected)"
Write-Host '16 GB GPU strategy: component CPU offload plus leaf-level language-model offload; slower than ACE-Step.'
Write-Host 'Next: just install minimax-music3; just models minimax-music3; just validate minimax-music3'
