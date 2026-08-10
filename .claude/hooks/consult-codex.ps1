$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Codex answers in prose, and prose from a model contains curly quotes, em
# dashes and arrows. Windows PowerShell 5.1 writes stdout through the console's
# OEM codepage, which turned every one of them into the mojibake this repo has
# already paid for once ("yes" arriving as <?oyes<??). The hook's whole output
# is JSON destined for a UTF-8 reader, so say so on both ends: the pipe out,
# and the response file coming in — Get-Content guesses ANSI on a BOM-less
# file, and codex writes one.
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false
$OutputEncoding = [Console]::OutputEncoding

$projectRoot = if ($env:CLAUDE_PROJECT_DIR) {
    [IO.Path]::GetFullPath($env:CLAUDE_PROJECT_DIR)
} else {
    [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
}
$enabledMarker = Join-Path $projectRoot '.claude\codex-consult.enabled'

if (-not (Test-Path -LiteralPath $enabledMarker -PathType Leaf)) {
    exit 0
}

try {
    $hookInput = [Console]::In.ReadToEnd() | ConvertFrom-Json
    if ($hookInput.hook_event_name -ne 'UserPromptSubmit' -or
        [string]::IsNullOrWhiteSpace([string]$hookInput.prompt)) {
        exit 0
    }

    if ($env:CODEX_CONSULT_DRY_RUN -eq '1') {
        $codexResponse = 'Dry-run Codex consultation succeeded.'
    } else {
        if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
            throw 'The codex command is not available on PATH.'
        }

        $runRoot = Join-Path $env:LOCALAPPDATA `
            ('SniperSight\codex-consult\' + [guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
        $responseFile = Join-Path $runRoot 'response.txt'
        $errorFile = Join-Path $runRoot 'stderr.txt'

        $consultPrompt = @"
You are a read-only second opinion for Claude Code in the SniperSight 3.1 repository.
Read AGENTS.md and CLAUDE.md. Do not edit files, invoke another AI, commit, push,
deploy, restart anything, run tests that can touch live state, or call any endpoint.

The user just sent Claude this prompt:

$($hookInput.prompt)

Give Claude a concise, independent consultation: identify likely intent, relevant
repository evidence to verify, safety traps, and any flaws or alternatives Claude
should consider. Do not implement the task. If the prompt is casual or needs no
engineering second opinion, say that briefly.
"@

        # `2>` on a NATIVE command is the trap here. Windows PowerShell 5.1
        # wraps each stderr line in a NativeCommandError, and with
        # $ErrorActionPreference='Stop' that is TERMINATING — it aborts the try
        # block before line 53 ever reads the exit code. codex greets you on
        # stderr on every run ("OpenAI Codex v0.147.0", workdir, model), so
        # this hook could not succeed with a real call at all: the reason it
        # reported as "unavailable" was simply codex's first stderr line,
        # which is why it looked like a different fault every session
        # (a models-cache error while the CLI was stale, the banner once it
        # was not). Dropped to Continue for the call only, so the exit code
        # below stays the thing that decides success.
        $previousErrorAction = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $consultPrompt | & codex exec --ephemeral --sandbox read-only `
                --cd $projectRoot --output-last-message $responseFile - `
                2> $errorFile | Out-Null
        } finally {
            $ErrorActionPreference = $previousErrorAction
        }
        if ($LASTEXITCODE -ne 0) {
            $detail = if (Test-Path $errorFile) {
                (Get-Content -Raw $errorFile).Trim()
            } else {
                'No error detail was returned.'
            }
            throw "Codex exited with code $LASTEXITCODE. $detail"
        }
        $codexResponse = (Get-Content -Raw -Encoding UTF8 $responseFile).Trim()
        if ([string]::IsNullOrWhiteSpace($codexResponse)) {
            throw 'Codex returned an empty consultation.'
        }
    }

    @{
        hookSpecificOutput = @{
            hookEventName = 'UserPromptSubmit'
            additionalContext = @"
Independent Codex consultation (advisory; verify it yourself):

$codexResponse
"@
        }
    } | ConvertTo-Json -Depth 4 -Compress
}
catch {
    @{
        hookSpecificOutput = @{
            hookEventName = 'UserPromptSubmit'
            additionalContext = "Codex consultation was unavailable: $($_.Exception.Message). Continue normally and tell the user only if the missing second opinion materially matters."
        }
    } | ConvertTo-Json -Depth 4 -Compress
    exit 0
}

