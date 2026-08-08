[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

$Head = (git rev-parse --short HEAD).Trim()
$Status = @(git status --short)
$WikiIndex = Join-Path $Repo "graphify-out/wiki/index.md"
$WikiCommit = $null
if (Test-Path $WikiIndex) {
    $WikiLine = Select-String -LiteralPath $WikiIndex -Pattern 'Built from commit `([0-9a-f]+)`' | Select-Object -First 1
    if ($WikiLine) { $WikiCommit = $WikiLine.Matches[0].Groups[1].Value }
}

$WikiState = "missing"
if ($WikiCommit) {
    $CodeChanges = @(git diff --name-only "$WikiCommit..HEAD" -- "app/*.py" "app/*.js" "app/*.css" "app/*.html")
    $WikiState = if ($CodeChanges.Count -eq 0) { "current for code ($WikiCommit)" } else { "STALE ($WikiCommit; $($CodeChanges.Count) code files changed)" }
}

$Port = Get-NetTCPConnection -LocalPort 8422 -State Listen -ErrorAction SilentlyContinue
$PortState = if ($Port) { "LISTENING (live app may be running)" } else { "free" }
$StorePath = Join-Path $Repo "app/data/snipersight.db"
$StoreState = if (Test-Path $StorePath) { " present - treat as LIVE" } else { " not present" }

Write-Output "SniperSight workspace preflight"
Write-Output "HEAD:          $Head"
Write-Output "Working tree:  $(if ($Status.Count) { "$($Status.Count) change(s)" } else { 'clean' })"
Write-Output "Wiki:          $WikiState"
Write-Output "Port 8422:     $PortState"
Write-Output "Default store:$StoreState"
Write-Output "MCP tools:     verify Graphify and Serena in the active Codex tool list"

if ($Status.Count) {
    Write-Output ""
    Write-Output "Working-tree changes (preserve unrelated work):"
    $Status | ForEach-Object { Write-Output $_ }
}

if ($WikiState.StartsWith("STALE")) { exit 2 }
