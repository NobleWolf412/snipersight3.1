[CmdletBinding(SupportsShouldProcess, ConfirmImpact = 'High')]
param([switch]$RemoveRunData)

$ErrorActionPreference = 'Stop'
$toolDirectory = $PSScriptRoot
$expectedLeaf = 'agent-loop'

if ((Split-Path $toolDirectory -Leaf) -ne $expectedLeaf) {
    throw "Refusing to remove unexpected directory: $toolDirectory"
}

if ($RemoveRunData) {
    $runData = Join-Path $env:LOCALAPPDATA 'SniperSight\agent-loop'
    $resolvedParent = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'SniperSight'))
    $resolvedRunData = [IO.Path]::GetFullPath($runData)
    if (-not $resolvedRunData.StartsWith($resolvedParent, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove unexpected run-data path: $resolvedRunData"
    }
    $retainedWorktrees = @(
        Get-ChildItem -LiteralPath $resolvedRunData -Directory -ErrorAction SilentlyContinue |
            Where-Object { Test-Path (Join-Path $_.FullName 'worktree\.git') }
    )
    if ($retainedWorktrees.Count -gt 0) {
        throw 'Run data contains registered Git worktrees. Review and remove them with git worktree remove before deleting run data.'
    }
    if ((Test-Path $resolvedRunData) -and
        $PSCmdlet.ShouldProcess($resolvedRunData, 'Remove Claude/Codex run logs')) {
        Remove-Item -LiteralPath $resolvedRunData -Recurse -Force
    }
}

if ($PSCmdlet.ShouldProcess($toolDirectory, 'Remove the Claude/Codex agent-loop tool')) {
    $backupParent = Join-Path $env:LOCALAPPDATA 'SniperSight\agent-loop-uninstalled'
    New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
    $backup = Join-Path $backupParent (Get-Date -Format 'yyyyMMdd-HHmmss')
    Move-Item -LiteralPath $toolDirectory -Destination $backup
    Write-Host "Tool moved to recoverable backup: $backup"
}
