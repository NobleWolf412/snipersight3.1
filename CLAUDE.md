# SniperSight 3.1 — working notes

Deterministic market-structure research platform. Append-only, content-hashed
fact store; every engine writes facts under an `algo_version` and nothing
mutates. The product constitution is `sources/ss3_v0.1.txt`.

**The conventions the code does not state live here**, under "The conventions"
below. They were `docs/PROGRAM-PLAN.md` §6 until 2026-08-07; comments in the
code citing `§6` mean that list. They are in this file because this is the one
that is always loaded — a rule nobody opens cannot stop anybody. Otherwise this
file summarises nothing: it holds what is not written down anywhere else.

## What belongs in this file

**Behaviour, not inventory.** This repo is refactored constantly. A note that
describes *how the code is arranged today* is wrong within a week and is then
worse than nothing, because it is the thing someone reads **instead of** the
code. A note that describes *how the system behaves, and what it does to you
when you forget* survives a rename.

A rule earns a place here when it is all three:

- **Invariant** — still true after the file it names is split, renamed or
  rewritten.
- **Costly** — it has already burned an hour, or it can write to the operator's
  real book.
- **Invisible** — the suites and the linter cannot catch it, so only prose can.

Keep out: what a module contains (the code and `graphify-out/` answer that, and
they update themselves), which version any engine is on (they move most
sessions), and counts of anything. **A count rots silently** — nothing fails
when it drifts, so it quietly becomes a lie.

When a rule cites a function, a number or a commit, that citation is **evidence
for the rule, not the rule**. If the code moves on, keep the rule and let the
example stand as history — it still explains why the rule exists. Fix the rule
only when the *behaviour* changes.

## How to answer me

I am a trader, not a backend engineer. Long paragraphs of implementation detail
stop me reading, and if I stop reading I cannot check your work.

**Lead with the answer.** First line says what happened or what is true. Not the
journey, not the caveats, not what you looked at first.

**Then the plain-English why, in a sentence or two.** No module names, no
function names, no version tags in the explanation itself. "The app was showing
one market's price under another market's name" — not "the seq guard in load()
did not blank cPx".

**Then the detail, only if it changes what I do.** Put the file paths, the
version strings and the measurements below that line, where I can look if I
want them. A number I cannot act on is not worth a sentence.

Rules of thumb:

- Short paragraphs. Two or three sentences, then a break.
- Use a table for more than three numbers. Bold the number that matters.
- If a term is unavoidable (R-multiple, confidence interval, algo_version), say
  what it means the first time in that answer — briefly, not a lecture.
- Say "I don't know" and "I was wrong" plainly. Do not bury either.
- Never dress a maybe as a finding. If the interval crosses zero, the honest
  sentence is "this hasn't proven anything yet", and I would rather have that
  in six words than a paragraph explaining why it is nearly significant.
- Skip the narration of what you tried. I care what is true now, and what it
  costs me to act on it.

Length is not the goal — clarity is. A hard answer can be long, but every
sentence has to earn its place, and the first one has to stand alone.

## Run

The app is supervised. `watchdog.py` owns the scanner and the API server and
restarts them; port **8422**.

```
cd app
start.bat                      # watchdog: scanner + server + browser
```

`POST /api/system/restart` restarts it in place. A bare server, for verifying a
change without the scanner:

```
cd app
python -m uvicorn server:app --port 8422
```

Run it **from `app/`**. `server.py` imports the engine package by bare name, so
from the repo root both spellings fail and neither says so usefully:
`uvicorn app.server:app` gives `ModuleNotFoundError: No module named 'engine'`,
and `uvicorn server:app` gives `Could not import module "server"`.

## Test

```
cd app
python -m unittest discover -s tests     # what CI runs
python -m pytest tests -q                # same suite, quicker to read
for f in tests/test_*.js; do node "$f"; done
npm ci && npx eslint .                   # first run only needs the npm ci
```

`pytest` also works from the repo root (`python -m pytest app/tests -q`); the
server does not.

The JavaScript suites assert against the **text of the static files**, not a
rendered DOM — they pin contracts (which helper is called, which token, which
field), so a passing JS suite means the source still says what it should, not
that the page works. Confirm behaviour in the running app as well.

**The linter is there for the gap that leaves.** A name read but never bound is
legal JavaScript that throws only when the line runs, so no text assertion and
no `node --check` can see it — `renderDeck` passed a `now` that did not exist,
the Setup Deck dropped every row under its own heading, and the suite stayed
green. `no-undef` catches exactly that. It is the repo's only npm dependency
and it is a **bug gate, not a style gate**: no formatting rule is on, and none
should be added. Warnings do not fail; `eslint.config.mjs` names every
reporting-only rule and what is still outstanding under each.

`no-redeclare` is the second one, and it caught a live defect on the linter's
first run: `shell.js` held **two** functions named `renderScoreboard`, one for
Command's today tile and one for the Results scoreboard. Declarations hoist, so
the later won and the earlier had never run. Nothing errored, both call sites
resolved to something real, and the only symptom was the "Closed today" tile
showing an em-dash beside a Results panel reporting 7 trades from the same
journal. The JS suites cannot see this by construction: they pin which helper
is called and which token appears, and neither question distinguishes two
functions sharing a name.

Run it with the suites, not occasionally. After the first `npm ci` it is
`npx eslint .` and about a second.

`ticket-math.js` decides how big a trade is and re-implements
`venues.liquidation_price`. It is the only thing proving the ticket and the
engine agree about where a position dies.

## Traps that have each cost an hour

**Restart after any Python change.** A running server holds the imported module.
A duplicate-order guard that existed on disk was absent from the live endpoint,
and testing against it wrote a real duplicate order onto the operator's paper
book.

**Do not POST to write endpoints to test them.** `/api/manual/arm`,
`/api/positions/close` and `/api/positions/adopt` write to the operator's actual
book. Use the suites, or a scratch database.

**...and the suites are not automatically safe either.** `TestClient` drives the
real app against the real store and the real processes. Two instances, both
found on 2026-08-05:

`tests/test_system_restart.py` forced `_watchdog_alive` to `True` — the one
guard that stops the restart endpoint proceeding — and then POSTed for real, so
every run of the suite taskkilled the live scanner. That is the entire
explanation for 356 exits, all `rc=1`, all "NOT ended by this supervisor". They
were not a crash: `rc=1` is what `taskkill` produces, `TerminateProcess` never
runs `atexit`, and the supervisor was telling the exact truth — the API server
ended them, on the suite's instruction. It clustered during development and went
quiet for 4h47m overnight because that is when nobody ran tests.

`tests/test_arm_from_a_phone.py` was one mutation away from arming a real trade
while checking a clamp; it was stopped by an unrelated validation, not by
design.

The rule that falls out: when a test forces a safety guard open, stub the thing
the guard was protecting in the same breath. Both suites now assert that
property about themselves.

**Symptoms that mean "something outside killed it", not "it crashed":** exit
code 1 with no traceback, and nothing in `data/live-exit.log` — `live.py`
registers `atexit`, installs `faulthandler` and traps signals, so a process
that exits through Python leaves at least one note. 178 starts with zero exit
notes is a hard external kill every time.

And **`_last_error()` in the watchdog is not where it died** unless the child
runs with `-u`. Its stderr is redirected to a file, Python block-buffers that,
and a killed process never flushes — so "last output" is whatever crossed the
last 4KB boundary. It made 39 exits appear to end at `UNIVERSE onboarded
PF_SPCXXUSD`, which was a red herring that cost hours; the same run read
unbuffered had completed two full cycles and died asleep in `time.sleep`.

**Other sessions are editing this repo.** They commit to `main`, they push, and
they will sweep your uncommitted working tree into their commits. `git log -3`
then looks as though your work vanished — it has not; it is further back, under
someone else's commit. Check before concluding anything:

```
git branch --contains <sha>
git grep -l "<a marker from your change>" HEAD -- app
```

**`?v=N` in `shell.html` is cosmetic.** The `/` route rewrites every one of them
from the newest mtime under `static/`, so hand-editing them changes nothing and
asserting on the numbers on disk tests a value that is never served.
`test_default_cockpit_route.py` pins the real behaviour.

**Scripted edits and escapes.** Writing an escape into a file through a patch
script can land the byte it denotes instead of the characters that spell it.
`\b` becomes a literal `0x08`. A CSS `\25B8` gets read as C octal and becomes
`0x15` followed by the leftover text `B8`. The result passes `node --check`,
matches on a served-file diff and reads correctly in the source, so nothing
announces it. What breaks depends on where it lands — a regex that silently
never matches, or a `content:` rule that paints the leftover hex on screen.

Searching will not surface it; it hides it. On a directory traversal ripgrep
classifies the file as binary and skips it with no message at all, and `grep
-r` prints `Binary file ... matches` with the line suppressed. Handed the path
explicitly, ripgrep reads it as text either way, so a targeted check looks
fine while a broad one silently loses the file.

Scan bytes after any scripted edit containing an escape. Counting `0x08` alone
misses most of them — `0x0b` and `0x0c` in particular fall in the range most
filters skip. From the repo root:

```
python -c "import pathlib;bad=lambda r:[i for i,b in enumerate(r) if b<32 and b not in (9,10,13)];[print(p,bad(p.read_bytes())[:8]) for p in pathlib.Path('app').rglob('*') if p.suffix in {'.js','.py','.css','.html'} and bad(p.read_bytes())]"
```

Silence is a pass. At `c30f031` it printed two files and nine bytes, fixed in
`216c819` and `84aa15c`.

**Verifying in the browser.** The hidden preview pane does not composite, and
three separate things follow from that, each of which looks exactly like a bug
in the code under test: it cannot screenshot, `requestAnimationFrame` **never
fires**, and `scrollIntoView({behavior:'smooth'})` never animates. Anything the
app defers to rAF — `go()` defers its scroll-to-panel that way — appears simply
not to happen. Shim both before concluding anything:

```js
window.requestAnimationFrame = cb => setTimeout(() => cb(performance.now()), 0);
window.matchMedia = q => /reduce/.test(q) ? {matches: true, addListener(){},
  removeListener(){}, addEventListener(){}, removeEventListener(){}} : real(q);
```

Drive the page with `javascript_tool` rather than screenshots. Chart price lines are drawn on a
canvas and their labels are not in the DOM; to read them, wrap
`createPriceLine` on the series prototype before triggering a redraw. The
portfolio polls every 30s, which collides with the 30s tool timeout, so poll in
a loop capped near 25s rather than sleeping through a cycle.

## The conventions

This codebase has strong conventions that are **not stated in the code**. An
agent that has not been given them will write something that passes the whole
suite and still violates the constitution. That is the failure these exist to
prevent, and it is why they live in this file rather than a document someone
has to think to open.

**The one that bites hardest: a behaviour change is a version bump, never an
edit under an existing `algo_version`.** Two generations of output under one
label is the defect the entire store design exists to prevent.
`tests/test_version_cascade.py` is the lockfile — it fails when a version moves
without its consumers.

Nine rules about how the system behaves, and what actually holds each one up:

1. **Facts are append-only, content-hash idempotent, and carry an
   `algo_version`.** The schema enforces it — `UNIQUE (content_hash)` — so
   re-running an engine over identical data is a no-op rather than a duplicate.
2. **A rule change means a new version**, never an edit to an old one. See
   above; this is the one with a lockfile.
3. **`confirmed_at` ≠ `market_time`.** `confirmed_at` is when the engine could
   first have known; `market_time` is when the market did it. Nothing may act
   on a fact before it was knowable — that is what stops a backtest cheating.
4. **Closed candles only**, never a developing bar.
   `test_only_complete_closed_bucket_is_emitted` pins it.
5. **Decimal end to end; no float touches a price.** Held up by the store
   rather than by a guard test: prices live in the schema as *text* (`"100"`,
   not `100.0`), so a float cannot survive a round trip by accident. Do not go
   looking for the test that enforces this — the representation is the
   enforcement.
6. **Loud-fallback rule — a degraded path must never degrade silently.** A
   fallback nobody can see is a bug, not a safety net.
7. **Evidence is recorded, not filtered on, until it has been graded.** An
   engine writes its readings from the day it exists; nothing gates a trade on
   them until they have proven edge against the book. `MEASURED_NOT_ENABLED` in
   `pipeline.py` is this rule in code.
8. **Rejections are as auditable as approvals.** "Why did nothing fire" has to
   be as answerable as "why did this fire" — the rejection funnel is the
   surface that keeps it honest.
9. **One authority per number — the UI reads it, never re-derives it.** With
   exactly one deliberate exception: `ticket-math.js` re-implements
   `venues.liquidation_price` so the order ticket can warn without a round
   trip, and a test pins the two to agree. **A second exception is precisely
   how two surfaces come to disagree.** Do not add one.

And one rule about writing rather than behaviour, which no test will ever
catch: **comments explain _why_, and carry the measurement that motivated
them.** It is the reason the engine files can be read at all, and it decays the
moment someone writes a comment restating what the line already says.

Venue, leverage and shorts are a per-symbol contract, not a global setting —
`docs/HARDENING.md` is current on this and `venues.venue_for()` raises rather
than guessing.

## There is a map of this repo — read it before hunting

`graphify-out/` holds a knowledge graph of the codebase: every symbol, what it
connects to, grouped into named articles under `graphify-out/wiki/` — roughly
one per file. Check it **before** grepping around for where something lives. It
is cheaper than a search sweep and it will not miss a file because the name was
unexpected. Article counts move on every rebuild, so the index header is the
only trustworthy statement of what is in there.

Two ways in. The `graphify` MCP server is registered and reads this graph live —
`query_graph`, `get_node`, `get_neighbors`, `god_nodes`, `shortest_path`. Or read
`graphify-out/wiki/index.md`, which opens with a grouped map: engines, server,
UI, docs, then the suites, then the vendored chart library.

**Know what it is not.** The overwhelming majority of edges in this graph stay
inside a single file (92% when last measured), so the clustering had almost
nothing to group by except which file a symbol lives in. That makes it a
reliable answer to "where does this live, and what sits next to it", and an
unreliable answer to "how does a setup become a trade". Do not narrate a
cross-file flow from the graph alone; read the code for that. The exact ratio
does not matter to the caveat — it holds at any figure near that.

A large block of the articles are `lightweight-charts.js`, which is vendored
third-party code. They are grouped and marked as such in the index. Skip them.

**Freshness.** A post-commit hook rebuilds `graph.json` and `GRAPH_REPORT.md` in
the background after every commit, code files only, no LLM. It remaps community
IDs onto the previous run, so the hand-written article names stay attached to
the code they describe; a genuinely new community gets an auto-name from its hub
symbol rather than a bare number. `GRAPHIFY_SKIP_HOOK=1` opts out of a commit.

The **wiki is not rebuilt by the hook**. `python graphify-out/refresh_wiki.py`
from the repo root regenerates the articles and re-applies the grouped index,
which `graphify export wiki` on its own would flatten. It stamps
`wiki/index.md` with the commit the graph was built from and says **Stale** in
the header when that is behind HEAD — so check the top of the index before
trusting an article, rather than guessing at its age.

Doc and prose changes are invisible to the hook, which only ever looks at code.
Those need `/graphify --update`, and that one does cost tokens.

## Not part of this project

**Apex**, a persona system that once shared this working directory, was removed
on 2026-08-07 (`foundation.md`, `personas/`, and the old `war-room/` notes —
all recoverable in git history). `engine/apexbridge.py` keeps the `brief`
command and recreates `war-room/` on demand when it writes a dossier.
