# SniperSight 3.1 — working notes

Deterministic market-structure research platform. Append-only, content-hashed
fact store; every engine writes facts under an `algo_version` and nothing
mutates. The product constitution is `sources/ss3_v0.1.txt`; the convention list
is `docs/PROGRAM-PLAN.md` §6. This file is **not** a summary of those — it holds
what is not written down anywhere else.

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

**Scripted edits and regex escapes.** Writing `\b` into a file through a patch
script can land a literal `0x08` byte instead of the two characters. The result
passes `node --check`, matches on a served-file diff and reads correctly in the
source, while the regex silently never matches. Check bytes after any scripted
edit that contains an escape:

```
python -c "raw=open('static/tracer.js','rb').read(); print(raw.count(b'\x08'))"
```

**Verifying in the browser.** The preview pane cannot screenshot while hidden —
drive the page with `javascript_tool` instead. Chart price lines are drawn on a
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
