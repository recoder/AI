#requires -Version 7.4
. "$PSScriptRoot/../tools/yue/common.ps1"
$python = Join-Path (Get-YueConfig).Application '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Music test dependencies missing. Run just install yue, then just test-music.' }
foreach ($test in @('song_jobs.tests.py', 'yue_models.tests.py')) {
    & $python (Join-Path $PSScriptRoot $test)
    if ($LASTEXITCODE -ne 0) { throw "Music test failed: $test" }
}
