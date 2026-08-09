# Claude + Codex agent loop

This tool gives one task to a writer and sends its work to the other model for
an independent review. It repeats for a bounded number of rounds, then runs the
repository verification gate. The active checkout is never used for agent work.

## Run it

From the repository root:

```powershell
.\tools\agent-loop\Invoke-AgentLoop.ps1 -Task "Describe the change you want"
```

Codex writes and Claude reviews by default. To reverse the roles:

```powershell
.\tools\agent-loop\Invoke-AgentLoop.ps1 -Writer Claude -Task "Describe the change"
```

Claude writing is deliberately limited to file-reading and file-editing tools;
the orchestrator runs checks after review. Each run has at most three rounds by
default. Use `-MaxRounds 1` through `5` to change that bound.

## Safety and reversibility

- Every run starts from `HEAD` in a separate Git worktree under
  `%LOCALAPPDATA%\SniperSight\agent-loop`.
- Current uncommitted changes are not included and cannot be overwritten.
- Agents are told not to commit, push, deploy, restart, or call write endpoints.
- Codex writers use `workspace-write`; reviewers are read-only.
- Claude writers have no shell tool; Claude reviewers only have read/search tools.
- No result is merged into your checkout automatically.
- The worktree, run branch, patch, review logs, and verification output are retained.

Inspect `result.json` and `changes.patch` in the printed run folder. A successful
result is still only a candidate change: review it before merging or applying it.

To remove this tool and optionally its run data:

```powershell
.\tools\agent-loop\Uninstall-AgentLoop.ps1
.\tools\agent-loop\Uninstall-AgentLoop.ps1 -RemoveRunData
```

The uninstall script moves this tool to a dated backup instead of destroying it.
It refuses to remove run data while a retained worktree exists. Run data and Git
branches therefore require deliberate cleanup after you have reviewed them.

## Automatic consultation from Claude

This repository also has a project-local Claude `UserPromptSubmit` hook. Whenever
you send Claude a prompt in this project, it asks Codex for a read-only second
opinion and injects the result into Claude's context before Claude answers.

Disable it without changing settings:

```powershell
Remove-Item .\.claude\codex-consult.enabled
```

Re-enable it:

```powershell
New-Item .\.claude\codex-consult.enabled -ItemType File
```

The hook never lets Codex edit files. If Codex is unavailable or exceeds the
hook timeout, Claude continues normally with a short unavailable notice in its
private context.
