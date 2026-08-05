# SniperSight on Android — attack plan

Target: the **full cockpit** on an Android phone, reachable over the existing
tailnet, with a real home-screen icon. No app store, no fees, no Mac, no cloud.

Produced 2026-08-04 from a 20-agent research pass (codebase recon, 2026 Android
landscape, three competing plans, three adversarial judges). Claims marked
*verified* were re-checked by hand against the files on disk.

---

## STATUS — all six phases built, 2026-08-05

| Phase | State | Commit |
|---|---|---|
| 1. Icon, front door, cheap safety | done | `7c365d7` |
| 2. The phone stops being able to lie | done | `203286c` |
| 3. The cockpit fits the phone | done | `8215959` |
| 4. Arm and close with a thumb | done | `27adcae` |
| 5. The chart owns the screen | done, **scope corrected** | `38b4c8a` |
| 6. The phone tells you when something happened | done, **needs a watchdog restart** | `ab85af4` |

**Two things still need the operator.**

1. **Restart the watchdog** so phase 6 runs. `/api/system/restart` restarts the
   scanner and the server; the supervisor holding the new code is neither.
   Stop `watchdog.py` and run `start.bat`.
2. **Copy `docs/alerts.example.json` to `app/data/alerts.json`** if you want
   alerts on the phone rather than only toasts on the PC. Left off
   deliberately — an alert names your symbol, direction and P&L.

**Where the plan was wrong**, recorded because the plan is evidence too:

- Phase 5's layout items were largely obsolete by the time they were reached.
  Measured at 412×915 before touching anything: the chart already got 529px and
  the toolbar was 98px in three rows. The "toolbar taller than the chart" and
  "the ticket cannot fit by stacking" described the pre-fix layout. The toolbar
  consolidation and the order-ticket bottom sheet were therefore **not built** —
  they would have been churn. The data work in that phase was real and was done.
- Phase 4's "every POST is a bare fetch with no pending state" was wrong for
  Arm, which already disabled its button. The genuine defect next to it was
  worse and unlisted: on a dropped reply it asserted `nothing was armed`, which
  it cannot know.
- Phase 2's health-chip visibility fix had already been made by another session.
- The `/api/facts` saving is real but **timeframe-dependent**: 66% at 1H and
  55% at 15m, and currently **zero** at 4H and 1D, where the store holds less
  history than the chart's 1500-bar window. It grows as the store does.

**Three bugs were introduced and caught by verification rather than by review** —
a lower-cased timeframe table that switched Arm off after a minute on a 4H
chart, a kill-switch key that collapsed 23 events into 2, and a heartbeat field
read as `at` instead of `ts` that would have cried wolf every tick. All three
would have passed any amount of reading. Each now has a test.

---

## 1. The answer

**Keep the engine where it is and make the phone a careful window onto it.**

One command puts a real HTTPS address in front of the server without changing
how it binds. That single change unlocks the home-screen icon, the APK route
and phone alerts at once. The same cockpit grows a phone layout — one codebase,
not two.

### The APK question, answered

When Chrome on Android says **Install**, it does not make a bookmark. It asks a
Google service to build and sign a genuine Android package (a *WebAPK*) for the
site, which then appears in the app drawer and in Settings → Apps with no
address bar. That is the free sideloaded APK, with no keystore and no store.

The catch: that packaging happens on a Google server, and the app only exists
inside the tailnet, so Google may not be able to reach it. **This is a
ten-minute test, not an argument.**

| Outcome of `chrome://webapks` after installing | What you have | What to do |
|---|---|---|
| SniperSight **is** listed | A real installed Android package — app drawer, Settings → Apps, per-app notification permission | Nothing. Done. |
| SniperSight is **not** listed | A full-screen home-screen shortcut. Opens with no address bar, own card in the app switcher, behaves like the app. No app-drawer entry. | Optional: build the APK locally with Bubblewrap (below). |

The local fallback works because Digital Asset Links verification runs **on the
phone**, which is on the tailnet — so a private origin is fine. Cost: Node plus
the Android command-line tools (~2GB) on the Windows box, two to three days,
still free, still no account. Android's developer-verification rollout
permanently exempts installs done this way.

**Rejected outright:** exposing the app publicly via Tailscale Funnel so
Google's packaging server can reach it. That publishes a trading cockpit with
no login and live write endpoints to the entire internet. The correct response
to "the packaging server can't reach my private network" is to build locally.

---

## 2. Cost

| Phase | You get | Size |
|---|---|---|
| 1. Icon, front door, cheap safety | Tappable icon, full-screen cockpit, login | **~1 week** (icon on day one) |
| 2. The phone stops being able to lie | Trustworthy staleness signalling | days |
| 3. The cockpit fits the phone | All five surfaces readable | 2–3 weeks |
| 4. Arm and close with your thumb | Trade from the phone, safely | 2–3 weeks |
| 5. The chart owns the screen | Usable chart, sane data cost | 2–3 weeks |
| 6. The phone tells you when something happened | Alerts that work | 2–3 weeks |

**Total to full parity: seven to nine weeks of part-time work.** The tappable
icon lands in the first few days. Phases 1–3 give a genuinely useful read-only
phone in about a month; phase 4 is where it starts acting.

Money: **£0**, unless the PC needs to be replaced by a server (see §6).

---

## 3. Phases

### Phase 1 — The icon, the front door, and the cheap safety · ~1 week

*You get: an icon on the Pixel that opens the full cockpit, full-screen, no
address bar, encrypted, reachable only by your own devices — and it asks you to
log in once.*

- **Set the Windows power plan to never sleep or hibernate**, and confirm
  `install_autostart.py` actually starts `watchdog.py` at boot. Zero code, and
  the single most likely real-world failure: the icon opening onto nothing.
- Run `tailscale serve --bg --https=443 http://127.0.0.1:8422`. *Verified: no
  serve config exists yet; the machine is `noblewolf`.* **Leave the bind in
  `watchdog.py` alone** — 127.0.0.1 is exactly what a same-machine proxy wants,
  so nothing new appears on the home wifi or the internet. HTTPS and MagicDNS
  must be toggled on in the Tailscale admin console first.
- Reconnect the Pixel to the tailnet (100.99.215.76, offline 11 days) and turn
  on always-on VPN in the Tailscale Android app.
- Add `app.add_middleware(GZipMiddleware, minimum_size=1000)` to `server.py`.
  *Verified: no middleware of any kind today.* Measured on this data: **8×** on
  overview, **10×** on telemetry, **29×** on pipeline-health. One import; the
  difference between usable and broken on cellular. Restart after.
- **Move four safety arguments off the query string into JSON bodies:**
  `server.py:816` (system_restart), `:2060` (analyse_symbol), `:2482`
  (reset_baseline), `:2705` (scan_now). *Verified: these four take query params;
  the other eight POSTs take `payload: dict`.* A query-only POST can be fired by
  any web page you visit, today, on loopback, with no phone involved. Baseline
  reset is undoable only by hand-editing the database.
- Add a ~25-line middleware requiring a session cookie on `/api/*`, exempting
  `/` and `/static`, plus a small `/login` route. **Cookie, not a bearer token**
  — cookies ride same-origin requests automatically, so none of the ~17 raw
  `fetch()` calls across eight files need touching. Add `TrustedHostMiddleware`
  pinned to the ts.net name while there.
- Write `app/static/manifest.webmanifest` (name, `start_url: "/"`,
  `display: standalone`, colours from the ss.css tokens) plus 192px and 512px
  icons from `snipersight-logo.png` — and re-encode it: it is 349KB shown 26px
  tall, currently the heaviest single download.
- **Serve the service worker from the ROOT, not `/static/`.** *Verified:
  `server.py:2791` mounts `/static` and that is the only mount* — a worker at
  `/static/sw.js` can only control `/static/`, so the install prompt may never
  appear. Add a dedicated route serving `sw.js` from `/`, or set
  `Service-Worker-Allowed`. All three draft plans got this wrong; it is the most
  likely way this phase looks like it worked while doing nothing.
- **That worker must never intercept `/api/`.** Not network-first —
  network-only, no interception. *Verified: `server.py:2234` calls
  `manual.run()` inside a GET handler*, so `/api/manual/open` and
  `/api/manual/live` write fills and exits to the book. Any caching or replay
  layer over those would resolve trades on a schedule nobody authored. Cache
  `/static/*` only; never pre-cache `shell.html`.
- Measure the top bar at 412px before changing it. The comment at
  `ss.css:476-481` describes HALT sitting 86px off-screen, but the shed ladder
  below it fixed that. Fix what you actually see, then add a boot assertion that
  HALT's rectangle is inside the viewport so it cannot silently regress.
- Install from Chrome on the phone, then open `chrome://webapks`. **This is the
  decision point.**

**Exit:** icon on the home screen; tapping it opens the cockpit full-screen with
its own card in the app switcher and equity matching the desktop. From a second
tailnet device with no cookie, `/api/manual/arm` returns 401 instead of writing.
You know from `chrome://webapks` whether you have a package or a shortcut.

**Risk:** the service-worker scope trap makes this phase silently half-work if
missed. The Tailscale certificate is issued on first request — test it through a
full Windows reboot before relying on it.

---

### Phase 2 — The phone stops being able to lie to you · days

*You get: the phone always tells you which of three things is true — everything
is current, the scanner is dead, or the phone lost the tunnel — somewhere no
layout rule can hide it. This is what makes it safe to act on later.*

- **Fix the bug that only exists on a phone.** Every link verified:
  `ssdata.js` keeps showing the last good numbers when a fetch fails, and its
  own comment justifies that by saying the health chip reports staleness in
  words; `shell.js:209` writes `API DEGRADED` into exactly that chip; and
  `ss.css:486` sets `#healthChip{display:none}` inside the 900px block. **So on
  any phone the warning is invisible.** On the desk this never fires because
  loopback fetches don't fail. On cellular they fail constantly, and the app
  shows last-hour prices with a completely confident face.
- Give `ssdata.js` a last-**good** timestamp per data path, separate from its
  current one. Today the same field is stamped on both success and failure, so
  it cannot report how old the good data is.
- Put a connection indicator in an element with **no `display:none` rule at any
  width** — the fixed-position family `.toasts` already uses. Not the top bar
  (sheds at 1100/900/640), not the health chip, not the status bar (clipped by
  the 100vh layout). Add a boot check that its rectangle is on screen.
- Say the three states in **words, not colour**. "Scanner has not reported for 6
  minutes" is a different problem from "this phone has not reached the PC for 90
  seconds" — the second is new, and it is the one where the scanner light looks
  healthy while you're reading a snapshot from before you walked into a lift.
- Add a `visibilitychange` handler next to the 30-second timer in `shell.js`.
  Android backgrounds tabs hard; on unlock the timer hasn't fired.
- Swap `100vh` for `100dvh` at `ss.css:454` (`.shell`) and the `#s-chart.on`
  calc. On Android `100vh` is the height with the address bar retracted, so the
  status bar — carrying the connection light and the standing "Sim only" notice
  — sits below the fold in a body that can't scroll. Change both together; the
  comment at `ss.css:435-442` records a 16px disagreement between those two
  already costing someone an hour.

**Exit:** mid-session on the phone, turn Tailscale off. Within one refresh the
screen says in plain words that it cannot reach the PC and how old the numbers
are. Turn it back on and it recovers without a reload. Lock the phone two
minutes; on unlock it refreshes immediately.

---

### Phase 3 — The cockpit actually fits the phone · 2–3 weeks

*You get: all five surfaces readable on the Pixel, no sideways scrolling, no
column crushed to nothing. Legible, not yet comfortable.*

- **Collapse `.deck-row`.** *Verified: it has no responsive rule at all — its
  only media queries are reduced-motion ones.* It is `120px 92px 1fr 150px auto`
  with gaps and padding: a **454px floor squeezed into about 356px**, so the
  column carrying the engine's reasoning gets crushed to nothing on the first
  thing you look at. Its siblings `.jnl-row`, `.pos-row`, `.radar-row` and
  `.budget-grid` all collapse at 900px correctly — the deck was simply missed.
- Collapse `.cols-2`. *Verified: appears in no media query, while `.cols-3` and
  `.cols-4` get one on the next line.* It holds the two four-column performance
  tables on Results and the two Diagnostics panels. Wrap `.data-table` in a
  horizontally scrolling container so wide tables scroll rather than wrap.
- Collapse `.fail-row` in `diagnostics-ui.css` (five columns, ~328px floor, no
  breakpoint).
- **Sweep for the whole bug class mechanically** rather than hunting by hand:
  every `grid-template-columns` with a fixed px track, cross-checked against the
  media query list. `.deck-row` hid for months precisely because its neighbours
  looked done.
- Add a **headless-browser check** that loads the cockpit at 412px and 1440px
  and asserts nothing exceeds the viewport, HALT is on screen, and the chart
  canvas has non-zero width. ~50 lines. The JS suites assert against the *text*
  of static files, so they cannot catch a layout regression in either direction
  — and this is about to become a two-viewport product with other sessions
  editing the same CSS.
- Add a test pinning `ss.css` to exactly four breakpoints (640/900/1100/1180).
  The file's own header records being rescued from twelve ad-hoc thresholds.
- **Raise touch targets on the controls that write.** `ss.css:1177` deliberately
  sizes the position-row buttons to the 24px accessibility floor and the comment
  names CLOSE-on-a-live-position as one of them. Android's floor is 48. On a
  phone, CLOSE should be a full-width action inside an expanded row, with the
  same confirmation Arm already gets.
- Give the nav strip a scroll hint — it becomes a horizontal scroller at 900px
  then hides its own scrollbar, so Settings and Diagnostics sit off the right
  edge with nothing indicating they exist.
- Promote the ~8 load-bearing hover tooltips to visible text. Android has no
  hover, and some are the only explanation of a refusal — why Auto-trade is
  locked, why SHORT is dead on a spot venue. Follow the pattern already in the
  file where the ticket puts its blocking reason *on* the control.

**Risk:** another session is editing `ss.css`, `shell.html` and `chart.js` right
now, uncommitted — the 900px collapse this builds on came from there. **Commit
or branch the responsive baseline before touching it**, so a collision shows up
as a merge conflict rather than a silent overwrite. Line numbers here will have
drifted; search by selector.

---

### Phase 4 — Arm and close with your thumb · 2–3 weeks

*You get: set entry, stop and target with a finger, watch the dollars at risk
change, and arm or close from the phone — knowing for certain whether your tap
landed.*

- Convert the level drag in `chart.js` from mouse to **pointer events with
  capture**. *Verified: lines 161/184/188/189 are the only mouse-only handlers
  left*; every other listener is a click, which Android synthesises from a tap.
  The same conversion already exists in this repo for the equity curve.
- Add `touch-action:none` to `.lvl`. *Verified: no `touch-action` anywhere in
  `chart.js`* — without it the browser claims the gesture as a scroll before the
  handler sees it. Check the chart's pan/zoom freeze releases on
  `pointercancel`, not just `pointerup`.
- Grow the grab target to 44px with a transparent overlay while keeping the
  small visible pill; add a pressed state (no hover on touch to signal
  "grabbable"); fan the three handles apart when entry and stop sit close.
- **Add a rate-of-change guard.** Today the drag rejects only impossible prices,
  so a fling that lands the stop 10% away is arithmetically valid, sizes a
  smaller position, and arms without complaint.
- **Build a nudge editor as the primary phone path, not a fallback**: tap a
  level, then step it in ticks and in 0.1R with buttons, risk updating live. On
  a small chart one pixel of finger travel is several ticks.
- **Make retries provably safe and visibly safe.** The engine is already sound —
  it refuses a second unresolved intent on the same symbol and side, and
  identical facts collapse to one row. The phone just can't tell. Generate the
  trade's timestamp **once** on confirm and reuse it on every retry, so a
  dropped connection collapses to one trade — and reject a timestamp far from
  server time so a phone with a wrong clock can't stamp a false moment onto the
  record.
- Surface existing refusals as **answers, not errors**: a duplicate arm says
  "your first tap landed — this is the trade you already have"; a close that
  returns not-found says "that close already succeeded".
- **Never show "armed" optimistically.** Every POST is a bare fetch with no
  pending state; on a 20-second cellular round trip the phone looks idle. Block
  the second tap; paint only what the server returns.
- Add the **stop's distance from entry** to the arm confirmation. It already
  restates side, symbol, all three levels, dollars at risk, the scale-out rung
  and how far entry sits from market — and says nothing about the stop, which is
  the number a mis-drag actually corrupts. Apply the same restatement to close
  and adopt, which have none today.
- Gate the Arm button on the connection age from phase 2: if the last good fetch
  is older than one bar of the selected timeframe, it refuses with that written
  on it.

**Exit:** set a full bracket with a finger on three symbols. Put the phone in
airplane mode the instant you confirm an arm, then reconnect: **exactly one
trade exists**, and the phone tells you which state you are in. Deliberately
fling a level across the chart — it is refused or flagged, not silently taken.

**Risk:** the touch conversion is the one item whose outcome could change the
plan. Nobody has exercised this chart library's touch handling on a phone-sized
canvas with three draggable price lines, and the drag deliberately disables the
chart's own pan/zoom while active — a much sharper conflict with a finger. The
nudge editor is inside this phase, not deferred, precisely so that if the honest
answer is "dragging isn't viable at this size", the alternative already exists.

---

### Phase 5 — The chart owns the screen · 2–3 weeks

*You get: a chart worth looking at — full width, sensible height, ticket sliding
up from the bottom — and a data cost you can leave running on cellular.*

- **Give the chart real height.** *Verified: `ss.css:659` sets
  `#s-chart.on{height:auto}` while the row above keeps `minmax(260px,1fr)`* —
  with no definite parent height that `1fr` resolves to its 260px floor on a
  915px screen, on the surface whose own section heading reads "the chart owns
  the screen".
- Consolidate the chart toolbar. Seven controls including a 170px symbol button
  wrap to four or five rows at phone width, making the toolbar taller than the
  chart. Symbol and timeframe stay; price and regime chips move onto the canvas;
  Layers and Analyze go into an overflow.
- **Redesign the order ticket as a bottom sheet.** This is genuine redesign, not
  reflow — nine controls plus a cost breakdown plus a verdict block in a 320px
  column does not fit 412px by stacking. The pattern already exists in the repo:
  the diagnostics drawer goes full-width at 640px and the modal full-height.
  This is where the trade commits, so it gets designed rather than squeezed.
- Restore the candle readout below 640px. Hidden there today on reasoning that
  is right for a narrow laptop and wrong for a phone, where the crosshair is
  long-press-driven and hardest to place.
- **Bound the facts endpoint.** It has no limit clause at all, so the chart asks
  for nine kinds of data and receives every fact ever written — **575KB** of
  swing data and **588KB** of moving averages for one symbol on one timeframe,
  growing forever, to draw 18 markers.
- **Fix the duplicate 135KB fetch:** `shell.js` asks for `limit=200`,
  `funnel.js` asks for `limit=500`, there are 24 records so both return
  byte-identical, and the cache keys on the URL so it can't tell. Making the
  strings match removes **271 KB/min** of pure duplication in one token.
- Gate the 30-second refresh on the visible surface. It fires eight loaders
  regardless of which surface you're on; the console poller already checks this.
  Cache the 6-second database integrity check behind a time limit — it sits
  inside that loop against a 2.6GB file.
- Cap markers per layer on narrow screens. Only the signals layer is capped
  today; swing, structure, sweep and cycle are unbounded, and ~50 price lines
  redraw every frame during a pinch.
- **Measure on the actual phone over cellular, before and after**: time to first
  paint, and data per hour. Every research agent cited loopback numbers; none
  proposed a single measurement from the device.

**Exit:** open the chart on cellular — it fills the screen, pinch and pan are
smooth, the ticket slides up from the bottom. A full chart load moves roughly
**150KB rather than 840KB**, and an idle Command surface costs under
**10 MB/hour**, measured on the phone.

**Risk:** with every layer on, a dense symbol will still judder. No amount of
CSS fixes that.

---

### Phase 6 — The phone tells you when something happened · 2–3 weeks

*You get: a buzz when a setup fires, when your stop is hit, when the kill switch
trips — and, critically, when the desk PC has gone quiet. Silence stops being
ambiguous.*

> **Correction to the research.** One agent reported this as "the notification
> path has been dead in production and nobody noticed". That is wrong and worth
> correcting, because the reason matters. `watchdog.py:377-378` sets
> `SNIPERSIGHT_NO_TOAST=1` on the scanner child *deliberately*, and the comment
> at `:361-374` explains why: every toast spawns a PowerShell process, and the
> scanner died at 254s with toasts on against 1055s and 13 clean cycles with
> them off. `SNIPERSIGHT_TOASTS=1` restores them for testing, and the watchdog
> itself still toasts on restarts and audit events. So the scanner's setup
> announcements reach nobody **on purpose** — and that documented history is
> precisely why the phone-alert path must not spawn work from the scan loop.

- Turn `notify.py` from a Windows-toast function into a **fan-out**: one entry
  point, a list of destinations, toast as one of them. The four callers already
  pass `(title, message)` and already check a boolean, so none changes shape.
  This seam is what lets the delivery method change later without touching a
  caller.
- **Careful:** the `SNIPERSIGHT_NO_TOAST` early return sits at the very top of
  `toast()`. It must gate **only the toast sink**. Leave it in the shared entry
  point and you ship an alert system that is silent in the scanner on day one
  and looks like a delivery bug.
- **Deliver from the watchdog's existing 60-second tick, not from the scanner.**
  This is the constraint, not a preference — see the correction above.
- Add a `notifications` table so replayed facts can't double-buzz. The risk
  engine replays the whole book each run, and one halted day in July produced
  **eight** kill-switch records with different P&L values. Key it on
  `(event, day, baseline)` and deliberately ignore the P&L figure, which is the
  field that varies across replays.
- Wire the events with no alert at all: the kill switch (fired 23 times, silent
  every time), the drawdown halt (never fired, so untested — seed it against a
  scratch database), and your own trade resolving at stop or target. **Do not**
  alert on the shadow simulation, which runs 100–400 events a day.
- Two priorities. Setups, kill switch and your own trades closing go **loud** —
  about 3/day. Drift alerts run **13–44/day**, land in every hour including
  overnight, and are explicitly awareness-only. Burying three actionable alerts
  under thirty unactionable ones is the failure to avoid.
- **Add a dead-man's check.** The scanner-is-dead condition already computes
  from a 90-second heartbeat and nothing acts on it. Send a scheduled check-in
  to an outside service that alarms on its *absence* — a heartbeat from the PC
  cannot report the PC's own death.
- Start with a dozen lines posting to ntfy or a Telegram bot — free, no new
  dependency, working in an hour. Move to notifications from the app itself only
  once the alert mix has proved out, because that needs a cryptography library,
  which would be this project's first dependency beyond its web framework.

**Exit:** a setup fires and the phone buzzes within a scan cycle with symbol and
direction, app closed. Trigger a kill-switch condition against a scratch
database and it buzzes **once, not eight times**. Pull the power on the PC and
the phone tells you it went dark rather than just going quiet.

---

## 4. What we are not doing, and why

**A separate phone-only version** (a second set of files at `/static/m/`). The
most tempting option and the most expensive. The frontend moves at roughly a
hundred commits a month and there is one of you — a second copy is behind within
weeks and becomes the one you stop trusting. It would also genuinely be a
rewrite, not a reuse: `shell.js` is 3,200 lines in one block with 35 places that
write HTML directly into hard-coded element IDs. One cockpit costs CSS
discipline, paid once. A fork costs a tax paid forever. *This is a decision, not
an accident — if nobody writes it down, a future session forks without realising
anyone ever chose.*

**A native Android app** (React Native, Flutter, Kotlin). There is no native
version of the charting library and no equivalent exposing the two functions the
whole trade-planning interaction depends on — converting a pixel position to a
price and back. Every workable route ends with the existing web chart embedded
in a native shell anyway, handing back the performance argument you went native
for. The community answer for this library is literally "put it in a web view".
The things native genuinely buys — widgets, a lock-screen live activity, a
fingerprint lock — are not things you asked for, and the last is cosmetic while
the API itself has no login.

**A Capacitor or Cordova wrapper.** With no store involved, its main selling
point — a store-legitimate package — is irrelevant. Its documented way of
pointing at a remote URL is explicitly dev-only, so the supported design is
bundling the static files and calling the API cross-origin, which breaks the
cache-busting the `/` route currently owns (it rewrites every `?v=N` from file
timestamps, and a bundled app never hits that route). It also drags an npm build
step into a repo that has deliberately never had one, and whose JS suites assert
against the raw text of served files — those suites would keep passing while
testing something you no longer ship.

**Moving the backend to a cloud server.** Roughly £5–6/month, and it introduces
the one risk that would actually break data collection: the home connection is
residential and the exchanges accept it, while datacentre ranges are exactly
what those gateways challenge. There is real hidden work too — credential
storage is tied to this Windows account, process control shells out to Windows
commands, and the copilot spawns the local CLI. Do this when home uptime has
actually cost a trade. If it ever comes to it, the one test that decides it is
to rent a server for an hour and hit the exchanges from it before moving
anything.

**Tailscale Funnel** to make the packaging question go away. See §1.

**A watch-only phone app.** You asked for the full cockpit and it is achievable,
so this is not the destination. Noted only as sequencing: phases 1–3 give a
useful read-only phone in about a month, and if you had to stop early that is
where stopping would hurt least.

**Offline support.** Deliberately refused, and this is a correctness decision
rather than a scope cut. For this product a cached price is a lie. It is
sharper than usual here: two endpoints resolve trades and record fills from a
plain GET, so any offline replay queue would write to the book on a schedule
nobody authored. The service worker is forbidden from touching the API at all,
and the offline state is a screen naming the failure — "not connected to the
tailnet" — rather than a stale cockpit that looks fine.

---

## 5. First step — today, ~15 minutes

1. Set the Windows power plan to **never sleep, never hibernate**.
2. In the Tailscale admin console, switch on **HTTPS** and **MagicDNS**.
3. On the PC:

   ```
   tailscale serve --bg --https=443 http://127.0.0.1:8422
   ```

   *Verified: no serve config exists yet, so this is a clean first run, and it
   needs no change to how the server binds.*
4. Open the Tailscale app on the Pixel, reconnect it (offline 11 days), turn on
   always-on VPN.
5. Open `https://noblewolf.<your-tailnet>.ts.net` on the phone.

You will see the cockpit, ugly and cramped, over a proper padlock. That result
tells you the whole plan is viable; everything after it is layout and safety
work rather than plumbing.

---

## 6. Open questions

1. **Can the Windows box stay awake permanently?** If yes, the phone is reliable
   and this plan works as written. If it must sleep, the phone works only when
   you're lucky, and the honest answer becomes a small server at ~£6/month —
   a different project with a real risk the exchanges block a datacentre address.
2. **Has anything other than your two devices ever been on the tailnet?** If
   only the PC and the Pixel, the login in phase 1 is prudence. If anything else
   joins, it stops being optional — there is no authentication on any of the ~45
   endpoints today.
3. **If Chrome gives a shortcut rather than a package, do you want the local
   APK?** Free and permanently allowed, but it means Node plus ~2GB of Android
   tools on the PC and rebuilding by hand when signing details change. The
   shortcut still opens full-screen with no address bar; what you'd buy is the
   app-drawer entry and per-app notification permissions.
4. **Telegram/ntfy alerts, or notifications from the app itself?** Telegram/ntfy
   works in an hour with no new dependencies. App notifications are tidier but
   need a cryptography library — this project's first dependency beyond its web
   framework.
