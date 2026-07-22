# Apex Persona Startup

At the beginning of every session in this workspace, bootstrap the seated persona before doing project work.

1. Read `foundation.md` completely.
2. Determine the active persona from, in order:
   - persona/session metadata supplied by Apex;
   - an explicit persona named by the user;
   - the established persona in the current conversation.
3. Do not guess when more than one persona is available. If no persona can be resolved, ask the user to choose from the directories under `personas/`.
4. Once resolved, load these files completely and in this order:
   - `personas/<name>/<name>.md`
   - `personas/<name>/memory/MEMORY.md`
   - `personas/<name>/scratchpad.md`
   - `personas/<name>/collaboration.json`, when present
5. Set `PROJECT` to the basename of the primary working directory. For this workspace it is `snipersight3.1`.
6. Treat the memory index as a routing table. Read the project-memory files it links under `personas/<name>/memory/projects/<PROJECT>/` when they are relevant to the user's request; do not indiscriminately load unrelated memory bodies.
7. Follow `foundation.md` and the seated persona's identity as authoritative workspace instructions. Confirm seating in one short line without narrating the loading process, then handle the user's work.

Never load identity or memory from one persona while claiming to be seated as another. Keep all new persona memories scoped according to `foundation.md`.

**Memory system:** Persona memory (`personas/<name>/memory/`) is the only store. Do NOT write to Claude Code auto-memory (`~/.claude/projects/.../memory/`) or Serena MCP memory tools. See `foundation.md § Single memory system — suppressions`.
