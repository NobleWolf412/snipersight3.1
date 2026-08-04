# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

**Primary: the operator** — the person who built the system and trades from it. One
user today, on a local machine, running the app the watchdog opened for them.

The session shape is genuinely variable and future work must not optimise for one:

- long sessions reading charts and watching the scan cycle;
- short checks that ask "what should I do right now?" and close;
- deep dives into Results and Diagnostics when a number looks wrong.

Any of the three can happen on a given day. Confirmed by the operator: *"it really
depends."* A surface tuned only for the twenty-second check fails the two-hour dive,
and the reverse.

**Secondary, confirmed as a direction rather than a fact: other people later.** The
product is built for the operator now but is headed toward a wider audience. This is
why the LEARN surface and the 40-term glossary exist, and it is a live design
constraint rather than a someday concern: terminology has to carry its own
explanation at the point of use, and a newcomer must be able to arrive on any surface
without prior briefing. No second audience exists yet — do not invent their needs,
job titles, or workflows.

## Product Purpose

A deterministic, explainable market-structure trading platform for crypto across
three venues (Coinbase spot, Phemex perps, Kraken perps). It maps market structure
objectively, detects setups, sizes them through a risk authority, and paper-trades
them with full accounting, recording every decision as an append-only, versioned,
reproducible fact.

Success is a forward paper record honest enough to justify live execution, or honest
enough to refuse it. The system is currently measuring itself and reporting that no
strategy clears zero. That result being visible is the product working, not the
product failing.

## Positioning

The mechanism a neighbouring product could not truthfully copy is the fact contract,
not the strategies:

- **`confirmed_at` vs `market_time` on every fact.** Each fact records when it
  happened and when it became knowable. No engine can act on a swing before its
  right-side bars closed. This is what makes the backtest honest, and most retail
  backtesters get it wrong without ever finding out.
- **Content-hash idempotency.** Re-running the pipeline over identical data writes
  zero facts. Determinism is checked, not claimed.
- **Versioned append-only storage.** A rule change is a new version, never an edit to
  an old one, so every past decision stays reconstructable and A/B losers remain in
  the store as evidence.
- **Rejections are as auditable as approvals**, and there is no uncalibrated
  "mystery score."

## Operating Context

- Local FastAPI server on `http://localhost:8422`, launched by `app/start.bat`, a
  watchdog that owns the scanner, the API and the browser window together.
- Full scans take roughly four to five minutes, so the interface regularly shows work
  in progress rather than a settled state.
- Current surfaces: Command, Chart (draggable levels plus order ticket), Results,
  Settings, Diagnostics, plus a LEARN surface and the glossary.
- The operator arms trades by hand from the chart ticket. Hand-armed trades are
  recorded under their own version so they can never reach the graded strategy record.
- Some operations exist only as scripts with no UI control, notably
  `python reset_baseline.py` for starting a clean forward paper record.

## Capabilities and Constraints

- **Paper trading only.** There is no order-placement function anywhere in the
  codebase and `live_enabled` is a hard-coded literal rather than a setting. The
  interface must never imply live execution is available.
- **Decimal end to end.** No float touches a price.
- **Venue is derived from the symbol**, never globally selected (`BTC-USD` → spot,
  `BTCUSDT` → Phemex perp, `PF_XBTUSD` → Kraken perp). Each venue carries its own
  fees, funding schedule, short permission, leverage cap and ISOLATED liquidation
  model.
- 78 tracked symbols, 19 in the live scan universe, over 1.9M facts and 743k candles.
- Four indicator engines (ma, momentum, volatility, volume) are recorded but **not
  consumed** — nothing may read them until `factorstats` has graded them.
- The nested cycle satellite is observational only and has zero consumers.
- Closed candles only; the aggregator builds 4H and 1W rather than importing them.
- Risk authority holds portfolio-scoped position sizing, exposure caps, a
  venue-derived leverage cap, a liquidation-safety gate and a daily-loss kill switch.
  Strategies request; the authority approves, reduces or rejects.

## Brand Commitments

- **Name: SniperSight.** The sniper / tactical identity is binding, confirmed by the
  operator, and follows from the name itself. Design work may reinterpret how that
  identity is expressed but may not abandon it for a neutral or generic register.
- **Logo asset:** `app/static/assets/snipersight-logo.png`.
- **Explicitly open, confirmed by the operator as "open to change":** the specific
  gunmetal-ring-with-green-reticle execution described in `docs/REDESIGN-PLAN.md`,
  the three currently shipped typefaces, and the five-surface navigation structure.
  None of these are locked. `docs/REDESIGN-PLAN.md` is marked HISTORICAL and its
  design intent is evidence, not a standing commitment.

## Evidence on Hand

- **Real record:** 1.9M facts over 743k candles, 78 symbols. REVERSAL sits at +0.15 R
  with a confidence interval through zero. That figure was +0.27 R until the execution
  simulator was found handing out free entries on crossed orders.
- **Documentation:** `app/BUILDLOG.md` is an append-only build journal including the
  duds and retractions. `docs/PROGRAM-PLAN.md` is canonical for forward work.
  `docs/DESIGN-SYSTEM.md` records the current token system.
  `sources/ss3_v0.1.txt` is the product constitution.
- **Absences that future work must not fabricate:** there is no live trading record,
  no customers, no testimonials, no pricing, no user count beyond the operator, and no
  benchmark against any competing product. No strategy currently clears zero, and no
  surface may present the record as better than that.

## Product Principles

1. **Honest before flattering.** The record is shown as it is. A result that
   embarrasses the system is displayed with the same weight as one that flatters it.
2. **Terminology explains itself where it is used.** Given a future audience beyond
   the operator, a term a newcomer cannot decode is a defect on the surface that used
   it, not a gap in the glossary.
3. **Serve all three session shapes.** Every surface must answer its stated question
   immediately for the short check while still rewarding the long dive. Neither may be
   sacrificed for the other.
4. **Every number is traceable.** A displayed figure carries, or can reach, the fact
   version and time it came from. No uncalibrated scores.
5. **Never document or imply a control that does not exist.** Describing a button
   that was never built costs the operator more than describing nothing.

## Accessibility & Inclusion

No formal standard has been set, but the codebase already treats accessibility as
live work and future work must not regress it:

- Contrast ratios are annotated inline in `app/static/ss.css` against both `--bg` and
  `--card`, with `--fg-3` and `--fg-4` explicitly raised to meet them.
- `prefers-reduced-motion: reduce` is honoured in multiple places.
- A skip link, `aria-live="polite"` status region, and 35 aria/role attributes are
  present in `shell.html`.

The confirmed future audience makes plain-language labelling a stated requirement
rather than a nicety.
