# Shared-account cockpit delivery

The new default interface has Home, Opportunities, Trade, Journal, Research,
and Settings. On phones, Research and Settings sit under More. The backend
shares manual and bot admission, reservation, cash, and account history.

## Resolved design decisions

- **A new admission gate**, not an extension of an old one. Both origins enter
  through `shared_account`; SQLite `BEGIN IMMEDIATE` precedes the budget read
  and encloses the reservation, request receipt, and manual intent fact.
- **Process contention**, not device contention. A spawned-process test
  races manual and bot entries against one SQLite file and one position slot.
- **Paper risk is user-configurable.** Settings accepts a positive percentage
  up to 100% of equity. Existing accounts keep their recorded setting until
  the user saves a change; untouched accounts retain 2%. New $10,000 accounts
  inherit the saved percentage instead of imposing 0.25%. Risk changes are
  audited and serialized with admission, and stale Settings saves are rejected.
  Existing orders keep their recorded size. The daily loss envelope stays 4R
  and the shared position ceiling stays one; research and live policy are
  unchanged. Transitions never force-close trades or delete account history.
- **No replacement confidence score.** The new opportunity view orders by
  readiness, available ATR distance, then stable identity. It omits the old
  composite and displays ungraded evidence as ungraded.
- **Manual consumes the shared slot.** A manual position blocks another bot
  entry and vice versa. Scanning continues. Scale-in remains outside scope.
- **Responses are ordered.** Selection generations and per-resource sequences
  discard stale responses. Editing a ticket invalidates its pending preview.
  Account reads can pin the expected epoch and refuse a cross-epoch response.
- **Source failure is visible.** A failed headline refresh becomes DELAYED;
  evidence older than 24 hours is historical/UNAVAILABLE. Calendar gaps never
  imply an all-clear. Pulse and Spotter are advisory only.

## Implementation boundaries

`engine/shared_account.py` owns admission, persisted request receipts, account
epochs, pending-order recovery, manual-result projection, and account control.
`execution.py` owns order lifecycle and the generic bot paper resolver.
`manual.py` keeps its existing finer-candle, trailing-stop, and partial-exit
resolver. Projection into `paper_positions` is idempotent and cannot regress a
terminal order. Both processes use the SQLite writer lock; network and model
work stay outside it.

Origin is immutable provenance. Controller is mutable ownership.
`grade_eligible` latches false after operator intervention. Attempts, request
identity, and account epoch are stored explicitly. Routing after admission is
conditional on PENDING: recovery can finish an order before its caller returns
without a late caller reopening it.

New settled dollars come from exact filled quantity, effective exit, fees,
and funding. Rounded R is never used to calculate new account cash. This also
handles market entries that fill away from the planned price. Older terminal
rows without exact dollar settlement keep their historical estimate and are
identified visibly. Original and current protective stops are separate fields.

The ticket obtains server sizing, then asks the server to recheck admission
when placed. Preview time identifies the request; server acceptance time
activates the order. A lost reply retains the exact request across reloads.
A proven rejection releases it for a new review. A later retry of an accepted
request returns its original receipt, including after an epoch change.

`ui_api.py` provides `/api/ui/v1/` read models. Account results never fall back
to research. Legacy manual-only terminal records remain available in Archives
without being added to the new account's money. Stock reads branch before
opening the crypto store. Stock trading stays visibly unavailable; Research
can show the existing synthetic training workflow.

The frontend uses native modules, the bundled chart library, and local assets.
There is no framework build or runtime npm dependency. `/classic` is a UI-only
rollback on the same server: it does not restore the old manual budget bypass.
Detailed legacy research and operations tools remain reachable there.

## Dependencies and assets

| Dependency | Purpose | Delivery |
| --- | --- | --- |
| Python 3.12+, FastAPI, uvicorn | Existing application runtime | Existing runtime; install in `.venv` if needed |
| `feedparser` | Fixed official headline feeds | New runtime dependency; tested with 6.0.14 |
| `tzdata` | IANA time zones on Windows | Install with runtime; tested with 2026.4 |
| pytest, httpx | Scratch API and account tests | Development only |
| Playwright 1.63.0 | Desktop Chromium and phone WebKit tests | Pinned in `app/package-lock.json` |
| axe Playwright 4.13.0 | Accessibility checks | Pinned development dependency |
| Lucide static 1.45.0 | Six navigation icons | Selected SVG files committed locally |
| Inter 5.3.0 distribution | Weights 500 and 600 | Selected Latin WOFF2 files committed locally |
| Existing Inter 400, logo, Lightweight Charts | Base typography, identity, chart | Reused local assets |

Font and icon licenses are beside the files in `app/static/assets/ui/`.
No external font CDN, stock photo pack, paid news API, or new model subscription
is required. Spotter continues to use the existing configured local assistant
integration and reports its unavailability when that integration is missing.
Private provider credentials remain encrypted through the existing vault.

Runtime/test setup from the repository root:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install fastapi uvicorn feedparser tzdata pytest httpx
cd app
npm ci
npx playwright install chromium webkit
```

The npm browser dependencies are development tools; an operator running the
application does not need to download browser test binaries. CI installs the
new Python dependencies. The existing repository gate selects the local venv
when present, invokes the installed ESLint directly, and checks new/untracked
source files for invalid UTF-8 and control bytes.

## Verification and rollout

The implementation tests use scratch stores. `tests/cockpit_preview.py` creates
a fresh synthetic database under ignored `artifacts/`, fixes port 8437, stubs
external feeds and credentials writes, and disables protected process effects.
It must never be used as an operator server or as market evidence.

```powershell
./scripts/check.ps1
cd app
npm run test:browser
```

Browser tests verify all six destinations, chart rendering, no horizontal
overflow, WCAG A/AA automated checks, Stocks isolation, edited-preview races,
definite rejection recovery, and uncertain-delivery retries after reload.
Screenshots and retained failing traces go to ignored `artifacts/`.

Verified on 2026-09-13: 1,932 Python tests passed, one skipped, and 230
subtests passed. All JavaScript contract tests, ESLint, and the UTF-8/control
byte scan passed. All eight desktop Chromium and phone WebKit browser tests
passed, including automated accessibility checks. The Python gate and the
final JavaScript gate were run separately after updating a JavaScript source
assertion to match the stronger cancellation guard. Logs are in
`artifacts/release-gate.log`, `artifacts/release-js-gate.log`, and
`artifacts/browser-final.log`. Verification used isolated synthetic stores.

Deploy the code and dependencies together, then restart the supervised app
through the normal operator workflow. Loading the new UI does not start a new
paper epoch. Review and perform the account transition in Settings only when
ready; DRAINING can wait indefinitely or be resumed. Never restore an older
database over newly recorded trades. A UI rollback keeps the shared gate.

This release does not complete the venue-dependent live drills, unlock live
execution, or implement stock-native live-market scanning and routing. Those
capabilities remain blocked in the product. No real account cutover, provider
credential change, live order, or supervised-process restart was performed by
the implementation's verification.
