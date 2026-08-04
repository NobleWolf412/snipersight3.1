# SniperSight 3.1

Read **`CLAUDE.md`** in this directory. It is the single set of working notes
for this project: how to run and test it, the traps that have each cost an
hour, and the store conventions that are enforced by tests rather than review.

It is not duplicated here on purpose. Two copies of an instruction drift, and
this codebase already treats a document that misdescribes the code as worse
than no document — it is the thing someone checks *instead of* the code.

## What this file used to say

It bootstrapped the **Apex** persona system: read `foundation.md`, resolve a
persona from `personas/`, load that persona's memory, and only then start
project work. Apex is a separate project that happens to share this working
directory. `foundation.md` and `personas/` are still on disk and are left
alone, but they are not SniperSight, and loading them to work on SniperSight
only spends context.

That version also forbade writing to Claude Code's own memory store. That rule
belonged to Apex's single-memory-system policy and does not apply here.
