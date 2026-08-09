[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)]
    [string]$Task,

    [ValidateSet('Codex', 'Claude')]
    [string]$Writer = 'Codex',

    [ValidateRange(1, 5)]
    [int]$MaxRounds = 3,

    [ValidateRange(1, 100)]
    [decimal]$ClaudeBudgetUsd = 10,

    [switch]$SkipChecks
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory)][string]$Command,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$OutputFile
    )

    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments 2>&1 | Tee-Object -FilePath $OutputFile
        if ($LASTEXITCODE -ne 0) {
            throw "$Command exited with code $LASTEXITCODE. See $OutputFile"
        }
        return Get-Content -Raw $OutputFile
    }
    finally {
        Pop-Location
    }
}

function Invoke-Writer {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$OutputFile
    )

    if ($Name -eq 'Codex') {
        $args = @(
            'exec', '--ephemeral', '--sandbox', 'workspace-write',
            '--cd', $WorkingDirectory, '--output-last-message', $OutputFile, '-'
        )
        $Prompt | & codex @args
        if ($LASTEXITCODE -ne 0) {
            throw "Codex writer exited with code $LASTEXITCODE. See $OutputFile"
        }
        return Get-Content -Raw $OutputFile
    }

    $args = @(
        '--print', '--no-session-persistence', '--permission-mode', 'acceptEdits',
        '--max-budget-usd', $ClaudeBudgetUsd.ToString([cultureinfo]::InvariantCulture),
        $Prompt, '--tools', 'Read,Edit,Write,Glob,Grep'
    )
    return Invoke-CapturedCommand -Command 'claude' -Arguments $args `
        -WorkingDirectory $WorkingDirectory -OutputFile $OutputFile
}

function Invoke-Reviewer {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Prompt,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$OutputFile
    )

    if ($Name -eq 'Codex') {
        $args = @(
            'exec', '--ephemeral', '--sandbox', 'read-only',
            '--cd', $WorkingDirectory, '--output-last-message', $OutputFile, '-'
        )
        $Prompt | & codex @args
        if ($LASTEXITCODE -ne 0) {
            throw "Codex reviewer exited with code $LASTEXITCODE. See $OutputFile"
        }
        return Get-Content -Raw $OutputFile
    }

    $args = @(
        '--print', '--no-session-persistence', '--permission-mode', 'dontAsk',
        '--max-budget-usd', $ClaudeBudgetUsd.ToString([cultureinfo]::InvariantCulture),
        $Prompt, '--tools', 'Read,Glob,Grep,Bash',
        '--allowedTools', 'Bash(git diff *)', 'Bash(git status *)'
    )
    return Invoke-CapturedCommand -Command 'claude' -Arguments $args `
        -WorkingDirectory $WorkingDirectory -OutputFile $OutputFile
}

$repoRoot = (& git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw 'Run this script from inside the SniperSight Git repository.'
}

foreach ($commandName in @('git', 'codex', 'claude')) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "Required command '$commandName' was not found."
    }
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$runId = "$stamp-$([guid]::NewGuid().ToString('N').Substring(0, 8))"
$branch = "agent-loop/$runId"
$runRoot = Join-Path $env:LOCALAPPDATA "SniperSight\agent-loop\$runId"
$worktree = Join-Path $runRoot 'worktree'
$logs = Join-Path $runRoot 'logs'

Write-Host "Run:    $runId"
Write-Host "Branch: $branch"
Write-Host "Files:  $runRoot"

if (-not $PSCmdlet.ShouldProcess($worktree, "Create isolated worktree on $branch")) {
    return
}

New-Item -ItemType Directory -Path $logs -Force | Out-Null
$metadata = [ordered]@{
    run_id = $runId
    started_at = (Get-Date).ToString('o')
    source_head = (& git -C $repoRoot rev-parse HEAD).Trim()
    branch = $branch
    worktree = $worktree
    writer = $Writer
    reviewer = $(if ($Writer -eq 'Codex') { 'Claude' } else { 'Codex' })
    max_rounds = $MaxRounds
    task = $Task
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $runRoot 'run.json')

& git -C $repoRoot worktree add -b $branch $worktree HEAD
if ($LASTEXITCODE -ne 0) {
    throw 'Could not create the isolated worktree.'
}

$reviewer = if ($Writer -eq 'Codex') { 'Claude' } else { 'Codex' }
$feedback = 'No previous review. Implement the task, test narrowly where safe, and report what changed.'
$passedReview = $false

try {
    for ($round = 1; $round -le $MaxRounds; $round++) {
        Write-Host "Round $round/$MaxRounds`: $Writer writes; $reviewer reviews."

        $writerPrompt = @"
You are the only writer in an isolated SniperSight 3.1 worktree.
Read AGENTS.md and CLAUDE.md before acting. Preserve repository safety rules.
Do not commit, push, deploy, restart processes, or call any live/write endpoint.
Do not invoke another AI or agent. Work only on this task:

$Task

Reviewer feedback from the previous round:
$feedback

Make the smallest correct change. You may edit files. End with a concise summary.
"@
        $writerFile = Join-Path $logs "round-$round-writer.txt"
        [void](Invoke-Writer -Name $Writer -Prompt $writerPrompt `
            -WorkingDirectory $worktree -OutputFile $writerFile)

        $reviewPrompt = @"
Act as a cold, read-only reviewer of the current SniperSight 3.1 worktree.
Read AGENTS.md and CLAUDE.md. Do not edit files, invoke another AI, commit, push,
deploy, restart processes, or call live/write endpoints.

Original task:
$Task

Inspect the current diff and relevant source. Check correctness, safety, scope,
tests, and version-cascade requirements. Put exactly one of these on the first line:
VERDICT: PASS
VERDICT: CHANGES_REQUESTED
Then give concise, actionable findings. PASS only when no required work remains.
"@
        $reviewFile = Join-Path $logs "round-$round-review.txt"
        $feedback = Invoke-Reviewer -Name $reviewer -Prompt $reviewPrompt `
            -WorkingDirectory $worktree -OutputFile $reviewFile

        $firstLine = ($feedback -split "`r?`n", 2)[0].Trim()
        if ($firstLine -eq 'VERDICT: PASS') {
            $passedReview = $true
            break
        }
        if ($firstLine -ne 'VERDICT: CHANGES_REQUESTED') {
            throw "Reviewer returned an invalid verdict. See $reviewFile"
        }
    }

    $checkPassed = $null
    if ($passedReview -and -not $SkipChecks) {
        Write-Host 'Review passed. Running scripts/check.ps1 in the isolated worktree.'
        $checkFile = Join-Path $logs 'check.txt'
        Push-Location $worktree
        try {
            & powershell -NoProfile -File .\scripts\check.ps1 2>&1 |
                Tee-Object -FilePath $checkFile
            $checkPassed = ($LASTEXITCODE -eq 0)
        }
        finally {
            Pop-Location
        }
    }

    & git -C $worktree status --short | Set-Content (Join-Path $runRoot 'status.txt')
    & git -C $worktree diff --binary | Set-Content (Join-Path $runRoot 'changes.patch')

    $result = [ordered]@{
        review_passed = $passedReview
        checks_run = (-not $SkipChecks -and $passedReview)
        checks_passed = $checkPassed
        finished_at = (Get-Date).ToString('o')
        branch = $branch
        worktree = $worktree
        patch = (Join-Path $runRoot 'changes.patch')
        logs = $logs
    }
    $result | ConvertTo-Json | Set-Content (Join-Path $runRoot 'result.json')

    Write-Host ''
    Write-Host "Review passed: $passedReview"
    Write-Host "Checks passed: $checkPassed"
    Write-Host "Branch retained: $branch"
    Write-Host "Patch: $(Join-Path $runRoot 'changes.patch')"
}
finally {
    if (Test-Path $worktree) {
        Write-Host "Isolated worktree retained: $worktree"
    }
}
