[CmdletBinding()]
param(
    [switch]$SkipPython,
    [switch]$SkipJavaScript,
    [switch]$SkipLint
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
$App = Join-Path $Repo "app"

# These tests previously reached protected live effects. Refuse the full suite
# if their self-contained safety contracts disappear.
$RestartTest = Get-Content -Raw (Join-Path $App "tests/test_system_restart.py")
$ArmTest = Get-Content -Raw (Join-Path $App "tests/test_arm_from_a_phone.py")
if ($RestartTest -notmatch '_watchdog_alive = lambda: True' -or
    $RestartTest -notmatch '_stop_pid = lambda') {
    throw "Restart endpoint safety contract is missing; refusing to run the full suite."
}
if ($ArmTest -notmatch 'patch\("engine\.store\.connect"' -or
    $ArmTest -notmatch 'def _scratch') {
    throw "Manual-arm scratch-store safety contract is missing; refusing to run the full suite."
}

if (-not $SkipPython) {
    Write-Output "Running Python suite..."
    Push-Location $App
    try { python -m pytest tests -q; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
    finally { Pop-Location }
}

if (-not $SkipJavaScript) {
    Write-Output "Running JavaScript contract suites..."
    Get-ChildItem (Join-Path $App "tests/test_*.js") | Sort-Object Name | ForEach-Object {
        node $_.FullName
        if ($LASTEXITCODE) { exit $LASTEXITCODE }
    }
}

if (-not $SkipLint) {
    Write-Output "Running ESLint..."
    Push-Location $App
    try { npx eslint .; if ($LASTEXITCODE) { exit $LASTEXITCODE } }
    finally { Pop-Location }
}

Write-Output "Scanning source files for unexpected control bytes..."
$BadFiles = @()
$SourceFiles = @(git -C $Repo ls-files -- "app/*.js" "app/*.py" "app/*.css" "app/*.html")
$SourceFiles | ForEach-Object {
    $SourcePath = Join-Path $Repo $_
    $Bytes = [System.IO.File]::ReadAllBytes($SourcePath)
    $BadCount = 0
    foreach ($Byte in $Bytes) {
        if ($Byte -lt 32 -and $Byte -ne 9 -and $Byte -ne 10 -and $Byte -ne 13) {
            $BadCount++
        }
    }
    if ($BadCount) { $BadFiles += "${SourcePath}: $BadCount byte(s)" }
}
if ($BadFiles.Count) {
    $BadFiles | ForEach-Object { Write-Error $_ }
    throw "Unexpected control bytes found."
}

Write-Output "All requested checks passed."
