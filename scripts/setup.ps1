#requires -Version 7.4
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot/common.ps1"
if (-not (Get-Module -ListAvailable powershell-yaml | Where-Object Version -EQ $script:YamlVersion)) {
    Install-PSResource -Name powershell-yaml -Version $script:YamlVersion -Repository PSGallery -Scope CurrentUser -TrustRepository -Quiet
}
Import-Module powershell-yaml -RequiredVersion $script:YamlVersion -ErrorAction Stop
Write-Host "YAML support ready: powershell-yaml $script:YamlVersion"
