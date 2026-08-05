# SniperSight 3.1 — working notes

Deterministic market-structure research platform. Append-only, content-hashed
fact store; every engine writes facts under an `algo_version` and nothing
mutates. The product constitution is `sources/ss3_v0.1.txt`; the convention list
is `docs/PROGRAM-PLAN.md` §6. This file is **not** a summary of those — it holds
what is not written down anywhere else.

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
```

`pytest` also works from the repo root (`python -m pytest app/tests -q`); the
server does not.

The JavaScript suites assert against the **text of the static files**, not a
rendered DOM — they pin contracts (which helper is called, which token, which
field), so a passing JS suite means the source still says what it should, not
that the page works. Confirm behaviour in the running app as well.

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

## The convention that bites hardest

**A behaviour change is a version bump, never an edit under an existing
`algo_version`.** Two generations of output under one label is the defect the
whole store design exists to prevent. `tests/test_version_cascade.py` is the
lockfile: it will fail if a version moves without its consumers.

Related, and enforced by tests rather than by review:

- Decimal end to end. No float touches a price.
- One authority per number. The UI reads; it never re-derives.
- Degraded paths are audible — a fallback that is silent is a bug.
- `confirmed_at` is when the engine could have known; `market_time` is when the
  market did it. Closed candles only.

Venue, leverage and shorts are a per-symbol contract, not a global setting —
`docs/HARDENING.md` is current on this and `venues.venue_for()` raises rather
than guessing.

## Not part of this project

`AGENTS.md` used to bootstrap the **Apex** persona system before any project
work. Apex is a separate project; `foundation.md` and `personas/` remain on disk
but are not SniperSight and should not be loaded to work on it.
