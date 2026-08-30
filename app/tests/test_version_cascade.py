"""Version lockfile — the guard against a defect this project has committed twice.

An engine that reads another engine's facts pins that engine's VERSION constant
by import. So when an upstream version moves, the downstream engine's OUTPUT
changes while its own tag stays put — and because `store.insert_fact` keys on
(symbol, tf, kind, market_time, algo_version, payload_hash), two incompatible
generations end up living under one label. Every consumer trusts that label.

It has happened twice:

  S37  `execsim` kept writing `exec-v0.7-draft` while simulating setup-v0.7
       plans. 130 of 346 exec facts joined to a `setup_id` present in BOTH the
       v0.6 and v0.7 books; one order came back FILLED and MISSED at once.
  S40  `risk` and `scalein` kept v0.7/v0.2 after setup-v0.8 and exec-v0.9 landed
       — the same mistake, made while writing the note explaining the first one.

The fix is not vigilance. It is this file. Changing any version below fails the
suite until the tuple is updated, which forces a deliberate look at everything
downstream of it. That moment is the whole point: the cost of the bug is that
nothing announces itself, so the guard's job is to make the change announce.

**If a test here fails, do not just update the constant.** Ask what consumes the
engine you changed, and bump those too.
"""
import unittest

import live

from engine import (aggregator, basis, bias, breakout, cooldowns, cycles,
                    execsim, venues, liquidity, ma, manual, momentum, ranges,
                    regime, risk, scalein, setups, structure, swings, importer,
                    volatility, volume, zones, trend)
from engine import (automation, autotrader, contracts, execution, lifecycle,
                    stockcalendar, stockdemo, stocks, stockstore)
from engine import apexbridge, phemex_private, positions, quality


# Operational authorities do not write research facts, so they do not belong
# in the research cascade below. They still carry behavior-bearing durable
# state and wire contracts; lock them independently so a rewrite beneath an old
# label fails the same gate instead of relying on review memory.
OPERATIONAL_EXPECTED = {
    # live-v0.2: the cycle runs the daily strategy regrade (fail-closed,
    # read-only, its own strategy_regrades table). v0.1: unresolved simulator
    # orders pin their data source and receive exit-only processing after
    # universe removal.
    "live": "live-v0.2-draft",
    "contracts": "contracts-v0.3-draft",
    # automation-v0.5: every drill names and enforces its required evidence;
    # restart demands a boot-id change, so lost-response recovery inside one
    # process can no longer pass one of the seven TESTNET->LIVE gates.
    "automation": "automation-v0.5-draft",
    # autotrader-v0.4: quantity scales to the dispatch mode's R via
    # risk.dispatch_scale() — the risk fact sizes the paper book (2%), an
    # order sent to TESTNET/LIVE carries 0.25%'s quantity (x0.125).
    "autotrader": "autotrader-v0.4-draft",
    # execution-core-v0.6: private entries honour expires_at (cancel at the
    # venue), a proven pre-wire refusal is SUBMIT_FAILED and retryable
    # instead of stuck-SUBMITTING-forever, and RESTART_RECOVERED carries
    # boot-id evidence.
    "execution_core": "execution-core-v0.6-draft",
    "positions": "positions-v0.3-draft",
    # phemex-private-v0.4: the stop (sent on every order) and every target
    # are tick-validated for all order kinds; submit() sets the leverage the
    # plan implies rather than a hardcoded 1x bucket.
    "phemex_private": "phemex-private-v0.4-draft",
    "lifecycle": "lifecycle-v0.1-draft",
    # opportunity-v0.5: risk reasons are trader-readable, unavailable grades
    # are not rejection reasons, and top-down stays independent of risk state.
    "opportunities": "opportunity-v0.5-draft",
    # quality-v0.2: acknowledged venue voids are durable notes, not warnings;
    # unexplained gaps remain blockers. Operational read-model change only.
    "quality": "quality-v0.2-draft",
    "apexbridge": "apexbridge-v0.1-draft",
    "stocks": "stocks-foundation-v0.2-draft",
    "stock_calendar": "stock-calendar-v0.1-draft",
    "stock_demo": "stock-demo-v0.1-draft",
    "stock_store": "stock-store-v0.1-draft",
}


def operational_versions():
    from engine import opportunities
    return {
        "live": live.LIVE_VERSION,
        "contracts": contracts.CONTRACT_VERSION,
        "automation": automation.AUTOMATION_VERSION,
        "autotrader": autotrader.AUTOTRADER_VERSION,
        "execution_core": execution.EXECUTION_CORE_VERSION,
        "positions": positions.POSITION_VERSION,
        "phemex_private": phemex_private.PHEMEX_PRIVATE_VERSION,
        "lifecycle": lifecycle.LIFECYCLE_VERSION,
        "opportunities": opportunities.OPPORTUNITY_VERSION,
        "quality": quality.QUALITY_VERSION,
        "apexbridge": apexbridge.APEXBRIDGE_VERSION,
        "stocks": stocks.STOCKS_FOUNDATION_VERSION,
        "stock_calendar": stockcalendar.STOCK_CALENDAR_VERSION,
        "stock_demo": stockdemo.STOCK_DEMO_VERSION,
        "stock_store": stockstore.STOCK_STORE_VERSION,
    }

# The current, deliberate state of the pipeline. Update WITH the cascade.
LOCKED = {
    # Writes candles rather than facts, but still changes every fact stream
    # downstream. v0.6 pins one cycle clock across import and quality so crossing
    # a candle boundary cannot falsely skip markets as DEVELOPING_CANDLES.
    "importer": importer.IMPORTER_VERSION,
    # Not a fact producer — it writes CANDLES — and locked anyway, for the
    # strongest reason in this file: it sits UPSTREAM of every engine below,
    # so a rule change here changes their output while every version constant
    # they import stays put. It went unlocked from birth to 2026-08-09, over
    # which time its constant was stamped on nothing and cited by nothing —
    # a version that cannot force a question is decoration.
    "agg": aggregator.AGG_VERSION,
    "swing": swings.SWING_VERSION,
    "structure": structure.STRUCTURE_VERSION,
    "zone": zones.ZONE_VERSION,
    "liquidity": liquidity.LIQ_VERSION,
    "regime": regime.REGIME_VERSION,
    "ranges": ranges.RANGES_VERSION,
    "ma": ma.MA_VERSION,
    "momentum": momentum.MOMENTUM_VERSION,
    "volatility": volatility.VOLATILITY_VERSION,
    "volume": volume.VOLUME_VERSION,
    "setup": setups.SETUP_VERSION,
    "exec": execsim.EXEC_VERSION,
    "risk": risk.RISK_VERSION,
    "scale": scalein.SCALE_VERSION,
    "cooldown": cooldowns.COOLDOWN_VERSION,
    "breakout": breakout.BREAKOUT_VERSION,
    # Measured and not enabled, like breakout. Locked from the first commit
    # because a version that only starts being tracked once something reads it
    # is a version whose early facts nobody can place.
    "trend": trend.TREND_VERSION,
    # The shared top-down layer. It writes NO facts of its own and still gets a
    # version, for the reason `cycles` does: it decides the content of facts
    # other engines write, so a rule change here changes their payloads while
    # every version constant they import stays put. That is the cascade in its
    # most invisible form and it is exactly what this file exists to catch.
    "bias": bias.BIAS_VERSION,
    "venues": venues.VENUES_VERSION,
    # Reads two candle series nothing else pairs (execution venue vs the
    # reference feed) and writes one fact stream nothing reads. Locked from
    # birth for the reason `trend` was: a version that only starts being
    # tracked once something consumes it is a version whose early facts
    # nobody can place.
    "basis": basis.BASIS_VERSION,
    # Observational satellite with no consumers — locked anyway, because
    # "nothing reads it" is exactly how it went dead unnoticed for 21 hours.
    "cycles": cycles.CYCLES_VERSION,
    # The operator's hand-armed paper book. It has NO entry in CONSUMERS and
    # that is the design, not an omission: no strategy engine may ever read
    # `manual-*`, because the moment one does, discretionary trades enter the
    # record that decides whether live execution is unlocked. Locked here so
    # that if anyone ever wires it into the cascade, this file has to be
    # edited in the same commit and the decision becomes visible.
    "manual": manual.MANUAL_VERSION,
}

#: Superseded manual versions the resolver still READS. They are not in LOCKED
#: because they are not the current generation of anything — but they are not
#: dead either, and this file is where a version that still has live meaning
#: has to be written down. Every one of them must stay outside every strategy
#: tag, for the reason `manual` is locked at all.
RETIRED_MANUAL = tuple(v for v in manual.MANUAL_VERSIONS
                       if v != manual.MANUAL_VERSION)

EXPECTED = {
    "importer": "importer-v0.6-draft",
    # agg-v0.2 cascade, 2026-08-09 — wider than S53, and the first to start
    # from CANDLES rather than facts. The aggregator now builds a 4H/1W bucket
    # from the source candles that exist when every missing one is a bucket
    # the venue acknowledged serving nothing for (import_log, gap-honesty
    # rule). Thin markets regain the windows v0.1 discarded — BICO-USD 4H
    # alone regains ~621 bars carrying 1,442 real hours; all 93 symbols move
    # at least slightly. No downstream RULE changed anywhere, but the input
    # series change retroactively, and a full-series recompute under an
    # unmoved tag would append a second generation beside the first — S53's
    # defect at pipeline width. So: every engine reading 4H/1W candles
    # directly (swing, structure, ranges, ma, momentum, volatility, volume,
    # liquidity, setup, exec, scale, breakout, trend) and every fact-level
    # dependent (zone, regime, bias, risk, cooldown) moves one step.
    # venues/cycles/manual stay: venues reads no candles, cycles reads BTC 1D
    # (native), and manual resolves on the finest NATIVE series by design.
    # The graded book restarts under the new tags — measured cost at the
    # moment of the change: baseline started 2026-08-08, ZERO trades graded,
    # zero shadow/testnet days. fvg and volprofile also read 4H/1W: both moved
    # (v0.2) in this cascade, but remain OUTSIDE this lockfile — locking them
    # is its own decision, still open.
    "agg": "agg-v0.2-draft",
    # S53 cascade — the widest this file had recorded before the above, and
    # the reason it exists.
    # swing-v0.9 stopped the promotion payload accruing per bar: v0.8 embedded
    # evidence.held_candles — which increments every candle a pivot holds —
    # inside the content-hashed, append-only fact, so every scan cycle appended
    # a near-duplicate of every promoted pivot. Measured: 193,718 promotion rows
    # for 15,603 pivots; zones counted the copies as cluster neighbours and
    # liquidity as pool members, so zone strength (a REVERSAL gate) inflated
    # monotonically as the scanner ran. held is now censored at HELD_FULL (90 —
    # the cap the score card always applied) and the fact is emitted once, when
    # that window closes; confirmed_at moved with it. Every fact-level reader of
    # swings moved: structure, zone, liquidity, ranges, momentum, setup,
    # breakout — the last two were missing from CONSUMERS["swing"] and are added
    # below — then regime (reads structure), and the trading tail exec / risk /
    # scale / cooldown through setup. ma, volatility, volume, venues, cycles,
    # manual are the only engines that stay put.
    "swing": "swing-v0.10-draft",
    # S53 addendum, caught in the FIRST live v0.9 cycle: the new consumer
    # collapse keyed pivots on market_time alone, and one bar can host both a
    # promoted HIGH and a promoted LOW (2025-10-10 carries a MAJOR pair on
    # three symbols) — the later row shadowed its twin, so five supply zones
    # store-wide were never created. Pivot identity is (market_time, type).
    # structure/zone/liquidity rules changed, so they and everything downstream
    # move AGAIN — the v0.11/v0.12/v0.10 facts from that one cycle remain in
    # the store as the recorded dud.
    "structure": "structure-v0.13-draft",
    # S50: zone-v0.11 closed a creation-time LOOKAHEAD — the cluster count read
    # swings not yet confirmed, inflating formation_quality on 7.9% of zones.
    # CONSUMERS["zone"] is ("setup",), and setup's own consumers are
    # ("exec", "risk", "scale"), so the whole trading path cascades.
    "zone": "zone-v0.14-draft",
    "liquidity": "liq-v0.12-draft",
    "regime": "regime-v0.13-draft",
    "ranges": "ranges-v0.3-draft",
    "ma": "ma-v0.2-draft",
    "momentum": "momentum-v0.3-draft",
    "volatility": "volatility-v0.2-draft",
    "volume": "volume-v0.2-draft",
    # setup-v0.16: WHY prices scale decimals to magnitude — a flat .2f wrote
    # every sub-dollar zone as a degenerate range ("supply zone 0.09-0.09").
    # No strategy rule changed, but the WHY sits inside the content-hashed
    # fact, so the same candidates re-derived under v0.15 would have appended
    # near-duplicates. setup_id is version-scoped, and the trading tail
    # (exec / risk / scale / cooldown) reads the new book, so all four move.
    # setup-v0.17 + the whole trading tail: VALIDATED setups now carry the
    # top-down bias block from `engine/bias.py`. No strategy rule changed, no
    # trade differs (the policy is ALLOW everywhere) and nothing downstream
    # READS the block — but `setup_id` is version-scoped and the payload moved,
    # so every exec/order fact of this generation joins to a v0.17 plan.
    # CONSUMERS["setup"] is ("exec", "risk", "scale") and CONSUMERS["exec"]
    # adds "cooldown": risk replays the account from these facts, scalein only
    # adds to a position the simulator says is open, and cooldowns are derived
    # purely from recorded exits. All five move together.
    # setup-v0.18: cascade from risk-v0.22. No setup RULE changed — the FORMING
    # payload bakes risk.size_order() output in at arming, so a sizing change
    # IS a payload change. risk-v0.21 proved it by omission: it moved RISK_PCT
    # under a live setup tag and left 91 armed v0.17 facts carrying 2% sizing
    # while fresh emissions would have carried 0.25%. CONSUMERS now names
    # risk -> setup, so the EXPECTED diff below is where the next risk bump
    # forces the question — the enforcement is that diff plus this map, the
    # same human-attention gate every producer here relies on.
    "setup": "setup-v0.19-draft",
    # S50 cascade. exec-v0.13 -> v0.14 corrected the MAKER_THEN_MARKET crossing
    # leg, which booked a market fill at the PLAN's price — two bars stale, and
    # outside the fill bar's own [low, high] on 78 of 95 crossed orders, never
    # adversely. CONSUMERS["exec"] is ("risk", "scale", "cooldown") and all
    # three read exec facts: risk replays the account from them, scalein only
    # adds to a position the simulator says is open, and cooldowns are derived
    # purely from recorded exits. All four moved together.
    # S52 cascade. exec-v0.16 -> v0.17 split funding out of `fees_price_units`
    # (it was folded in while ALSO reported separately, so any consumer summing
    # the two double-counted it) and dropped the cost profile from the execution
    # manifest, which had made a fill-model hash vary by venue. Net P&L is
    # unchanged, but the recorded facts differ. CONSUMERS["exec"] is
    # ("risk", "scale", "cooldown"): risk replays the account from exec facts,
    # scalein only adds to a position the simulator says is open, and cooldowns
    # are derived purely from recorded exits. All four move together.
    # scale ALSO changed on its own account — its economics gate now prices the
    # add on the add's own venue instead of the process-wide Coinbase default.
    "exec": "exec-v0.23-draft",
    # risk-v0.22: the envelope restated in R, sized by mode (paper/shadow 2%,
    # testnet/live 0.25%), gates identical everywhere; DECISIONs record their
    # pct. The v0.21 note above this line claimed "no cascade follows risk" —
    # true about facts, FALSE about code: setups.py calls risk.size_order()
    # at arming and bakes the result into FORMING payloads. That miss is the
    # S37/S40 defect made a third time, caught by audit rather than by this
    # file. CONSUMERS["risk"] now names the coupling so the EXPECTED diff a
    # risk bump forces has the answer in view — the map informs the human
    # gate; it does not mechanically fail on an incomplete cascade.
    "risk": "risk-v0.23-draft",
    "scale": "scale-v0.17-draft",
    "cooldown": "cooldown-v0.11-draft",
    # breakout-v0.5 / trend-v0.2: both now RECORD the top-down bias block on
    # every setup they emit. No rule changed in either and no trade differs —
    # both policies are ALLOW everywhere — but the payload does, and a payload
    # change under a live tag is two generations under one label.
    #
    # NOTHING DOWNSTREAM MOVES, and the reason is worth stating rather than
    # inferring from the absence: neither engine has consumers. `execsim` and
    # `risk` read SETUP_VERSION and SCALE_VERSION only, so no exec fact, no
    # equity curve and no cooldown series changes. `setup` does not move
    # either: it now imports the ladder from `bias` instead of defining it, and
    # the values are identical, so every setup payload is byte-for-byte what it
    # was. The day `setups.py` starts recording a bias block — step 3 of the
    # plan — that stops being true and setup/exec/risk/scale/cooldown all move
    # together.
    "breakout": "breakout-v0.6-draft",
    # trend-v0.1: NEW ENGINE, measured and not enabled. It arrives because
    # grading the MA against the book found LONG x ABOVE = 0 and
    # SHORT x BELOW = 0 across all 477 closed trades — both shipped playbooks
    # enter counter-move, so every trend-following factor is a constant here
    # and cannot be graded at all. No cascade DOWNSTREAM (nothing reads
    # trend-*), but it sits downstream of `ma` and `swing`: it computes the
    # ribbon with ma.ema / ma.sma and takes targets from INTERMEDIATE+ swings,
    # so both appear in its CONSUMERS entries and a bump to either moves this.
    "trend": "trend-v0.3-draft",
    # bias-v0.1: NEW SHARED LAYER, record-only. It arrives because three
    # engines answered "does the higher timeframe matter" three different ways
    # — scalein gates hard, setups records and ignores, trend did not look at
    # all — and none of those three answers was chosen by measurement. It reads
    # `regime` and `structure` facts and writes none of its own, so it is
    # downstream of both and upstream of every playbook that records it.
    "bias": "bias-v0.2-draft",
    # venues-v0.3: the REFERENCE contract — a per-symbol pointer to the
    # deepest venue's candle series (operator ruling 2026-08-09), stored under
    # '@'-keys that venue_for REFUSES, which is the enforcement keeping every
    # money path (sizing, liquidation, participation, fills) off the deep
    # venue's numbers. Venue descriptors are unchanged, so nothing downstream
    # moves — the same no-cascade shape as manual's bumps, for the same
    # reason: what changed is policy this module owns alone.
    "venues": "venues-v0.3-draft",
    # basis-v0.1: NEW ENGINE, measured and nothing more — records the close-
    # to-close spread between the execution venue and the reference feed, per
    # bar, on the trading symbol. Gates nothing, sizes nothing, and has no
    # CONSUMERS entry; the day something reads a basis fact it gains one, in
    # the same commit. The recorded number deliberately blends venue spread
    # with USD/USDT (ref_quote is on every fact) — normalising is an operator
    # decision deferred to grading.
    "basis": "basis-v0.1-draft",
    "cycles": "cycles-v0.2-draft",
    # manual-v0.2: partial exits. The one bump on this line with NO cascade, and
    # the reason is the same reason `manual` has no CONSUMERS entry — nothing
    # downstream reads it, by design. It still had to move: a scale-out splits
    # one position into several settlements, so `r_multiple` becomes a blend of
    # legs and a v0.1 reader of that fact is wrong about the trade. `trail_r`
    # rode v0.1 precisely because a v0.1 reader stayed right.
    #
    # The migration is inside the engine rather than here: `MANUAL_VERSIONS`
    # keeps the read set wider than the write set, so every intent still open
    # under v0.1 resolves normally and the settled book does not blank itself
    # the day the tag moved. See engine/manual.py.
    # manual-v0.3: an override now covers a ZONE, not one generation of the
    # code that described it. `setup_id` embeds SETUP_VERSION, the portfolio
    # view suppressed on an exact id match, so every bump of `setups` silently
    # expired every operator close: UNIUSDT 4H sat in `active_positions` under
    # setup-v0.17 while its own close sat in `operator_closed` under v0.15, and
    # `open_risk_usd` reported $194.60 against a trade closed for +$136.22.
    # Suppression is now keyed on `manual.setup_zone_key` — the id with its
    # version tail stripped.
    #
    # WHY THIS BUMPS AT ALL, since no payload changed and nothing new is
    # written. What moved is what an override fact MEANS: a v0.2 reader takes
    # it to cover one setup_id, a v0.3 reader takes it to cover the zone under
    # any engine version. Two readings of one fact is exactly the condition
    # this file exists to make visible, and MANUAL_VERSIONS widens rather than
    # moves so the facts already on disk keep resolving.
    #
    # And the honest caveat, because the bump does not actually segregate the
    # two readings: facts written under v0.1 and v0.2 are re-read under the
    # v0.3 rule. That is deliberate — the old reading was the defect, and
    # leaving those facts on it would leave the phantom exposure on screen.
    # The bump buys the announcement, not a partition.
    #
    # NO CASCADE, for the reason `manual` has no CONSUMERS entry: no strategy
    # engine may read `manual-*`, so no setup, exec, risk or cooldown fact
    # differs. Only `/api/portfolio`'s reading of its own book changes.
    # manual-v0.4: an open intent now resolves against the FINEST series the
    # store holds for its symbol rather than against its own chart, so a 4H
    # order fills on the 15m bar that actually traded through it. Causality is
    # unchanged — only bars opening at or after the fill anchor are eligible.
    #
    # THE UNIT MOVED, and that is the part to read twice. `bars_held` and
    # `bars_to_fill` on the exit fact now count RESOLUTION bars, not the
    # intent's own: a 4H trade settled on 15m reports 96 where v0.3 reported 6
    # for the same twenty-four hours. `atr_at_exit` is read off the same series
    # and changes scale with it, and three fields are new — `resolution_tf`,
    # `resolution_tf_seconds`, `resolution_degraded`. A v0.3 reader of a v0.4
    # fact is not merely missing fields, it is wrong about how long the trade
    # was held, which is the condition this file exists to make visible.
    #
    # The live rows from `manual.status` are NOT affected: they divide back by
    # `res["scale"]` and stay in the chart's own bars, because the screen
    # prints that count beside a 4H chart. Only the stored fact carries the
    # finer unit, and `resolution_tf` on the fact names it.
    #
    # Landed while nothing on disk was ambiguous: 9 facts under v0.1, 5 under
    # v0.2, ZERO under v0.3. NO CASCADE, same reason as above.
    "manual": "manual-v0.4-draft",
}

# Who reads whose facts. Bumping a key REQUIRES considering every value.
#
# The four indicator engines (ma, momentum, volatility, volume) appear here only
# as a CONSUMER of swing — `momentum` reads swing facts to find divergences.
# None of them is a producer with consumers, and that absence is deliberate:
# nothing in the strategy path may read them until `engine/factorstats.py` has
# graded them (house convention 6). The day one of them earns a gate, it gains a
# CONSUMERS entry here in the same commit.
#
# There is a SECOND kind of coupling this map does not express, and it is worth
# naming rather than leaving to be discovered. `momentum`, `volatility` and
# `volume` import `ma.ema` / `ma.sma` / `ma.sig` — shared CODE, not shared facts,
# the same way zones/liquidity/ranges share `swings.compute_atr`. So an `ma`
# rule change silently changes their output even though they read no `ma` fact.
# All four must bump together; each of their docstrings says so.
CONSUMERS = {
    # A THIRD kind of coupling, above both others: these engines read the
    # CANDLE SERIES the aggregator writes (4H and 1W), so an aggregation rule
    # change moves their output without a fact or an import in sight. Only
    # direct candle readers are listed — the fact cascade (zone, regime, bias,
    # risk, cooldown) follows from their own entries below. `cycles` reads
    # BTC 1D (native) and `manual` resolves on the finest NATIVE series, so
    # neither appears; fvg/volprofile also read these series but are not in
    # this file (they moved with the agg-v0.2 cascade anyway — locking them
    # is a separate open decision, flagged 2026-08-09).
    "agg": ("swing", "structure", "ranges", "ma", "momentum", "volatility",
            "volume", "liquidity", "setup", "exec", "scale", "breakout",
            "trend"),
    # CODE-level coupling, not fact-level, and it counts the same. momentum,
    # volatility and volume import `ma.ema` / `ma.sma` / `ma.sig` directly, so a
    # change to the EMA formula changes THEIR facts without touching a line of
    # their source. That is the version cascade in its most invisible form: no
    # import of a VERSION constant to grep for, just a shared function.
    # `trend` joins this list on the same CODE-level terms and is the strongest
    # case of it yet: it reads no `ma` FACT at all, it computes the ribbon with
    # ma.ema / ma.sma / ma.stack / ma.position, so an EMA change moves its
    # entries without touching its source or any version constant it imports.
    "ma": ("momentum", "volatility", "volume", "trend"),
    # S53: setup and breakout were MISSING here despite reading swing facts
    # directly (setups.py takes targets from INTERMEDIATE+ swings; breakout.py
    # does the same) — and the cascade plan drafted from this map missed them,
    # which is precisely the failure mode the map exists to prevent. Same for
    # structure: setup and breakout both read structure facts.
    "swing": ("structure", "zone", "liquidity", "ranges", "momentum",
              "setup", "breakout", "trend"),
    "structure": ("regime", "scale", "setup", "breakout", "bias"),
    "zone": ("setup",),
    "liquidity": ("setup",),
    "regime": ("setup", "bias"),
    # The bias layer's consumers are the playbooks that RECORD its reading.
    # `setup` is listed on CODE-level terms only for now — it imports the
    # ladder constant, and identical values mean its facts did not change —
    # but the entry is here rather than added later because the moment step 3
    # lands and setups records a bias block, the coupling becomes a fact-level
    # one and this map must already have said so. A consumer added in the same
    # commit as the bump it was supposed to warn about warns nobody.
    "bias": ("trend", "breakout", "setup"),
    "setup": ("exec", "risk", "scale"),
    "exec": ("risk", "scale", "cooldown"),
    "cooldown": ("risk",),
    # CODE-level coupling, same class as "ma": setups.py calls
    # risk.size_order() at arming time and bakes units/risk_usd/notional into
    # every FORMING payload. No setup ever reads a risk FACT — which is why
    # this entry was missing, and why risk-v0.21 moved the sizing policy under
    # a live setup tag with a fully green suite. A risk sizing change is a
    # setup payload change, full stop.
    "risk": ("setup",),
}


class VersionLockfile(unittest.TestCase):
    def test_operational_versions_are_locked(self):
        self.assertEqual(
            operational_versions(), OPERATIONAL_EXPECTED,
            "an operational behavior version moved; inspect its durable wire, "
            "state, adapter, and promotion consumers before updating this lock")

    def test_pipeline_versions_are_what_we_think_they_are(self):
        """Fails on ANY version move. That failure is the feature — it is the
        moment to ask what downstream of it also has to change."""
        self.assertEqual(LOCKED, EXPECTED,
                         "a pipeline version moved. Before updating this tuple, "
                         "check CONSUMERS below and bump everything downstream — "
                         "see this module's docstring for what happens otherwise.")

    def test_every_consumer_relationship_names_a_real_engine(self):
        for producer, consumers in CONSUMERS.items():
            self.assertIn(producer, LOCKED, f"unknown producer {producer!r}")
            for c in consumers:
                self.assertIn(c, LOCKED, f"unknown consumer {c!r} of {producer!r}")

    def test_downstream_engines_actually_import_what_they_claim_to_consume(self):
        """The consumer map must describe the code, not an intention. If an
        engine stops reading an upstream version this catches the stale entry;
        if it starts reading a new one, the map has to say so."""
        import inspect
        sources = {"exec": execsim, "risk": risk, "scale": scalein,
                   "regime": regime, "setup": setups, "momentum": momentum}
        pins = {"setup": "SETUP_VERSION", "exec": "EXEC_VERSION",
                "structure": "STRUCTURE_VERSION", "zone": "ZONE_VERSION",
                "liquidity": "LIQ_VERSION", "regime": "REGIME_VERSION",
                "swing": "SWING_VERSION"}
        for producer, consumers in CONSUMERS.items():
            const = pins.get(producer)
            if not const:
                continue
            for c in consumers:
                mod = sources.get(c)
                if mod is None:
                    continue
                src = inspect.getsource(mod)
                self.assertIn(const, src,
                              f"{c} is listed as consuming {producer} but its "
                              f"source never references {const}")

    def test_function_level_dependents_import_what_the_map_claims(self):
        """`ma` is consumed by importing its primitives, not its version. The
        generic check above looks for a `*_VERSION` constant and would pass this
        vacuously, so the coupling gets its own assertion."""
        import inspect

        from engine import momentum, volatility, volume
        for name, mod in (("momentum", momentum), ("volatility", volatility),
                          ("volume", volume)):
            with self.subTest(engine=name):
                self.assertIn(name, CONSUMERS["ma"])
                self.assertIn("from .ma import", inspect.getsource(mod),
                              f"{name} is listed as consuming ma but does not "
                              f"import it — the map has gone stale")
        # risk -> setup is the same class of coupling and earned its entry the
        # hard way: risk-v0.21 moved the sizing policy and nothing failed.
        with self.subTest(engine="setups"):
            self.assertIn("setup", CONSUMERS["risk"])
            self.assertIn("size_order", inspect.getsource(setups),
                          "setup is listed as consuming risk but never calls "
                          "size_order — the map has gone stale")

    def test_a_retired_manual_version_is_still_read_and_still_isolated(self):
        """The migration, held in place.

        `manual` is the one engine whose old facts must stay legible: an armed
        order is a position, not a derivation that can be recomputed under a new
        tag, so the resolver reads every version it has ever written. That makes
        the retired tags LIVE strings, and a live string that ever collided with
        a strategy version would put discretionary trades into the graded book —
        the exact thing the current tag is locked here to prevent.
        """
        self.assertIn(manual.MANUAL_VERSION, manual.MANUAL_VERSIONS,
                      "the resolver must read what it writes")
        for old in RETIRED_MANUAL:
            with self.subTest(version=old):
                self.assertNotIn(old, LOCKED.values(),
                                 "a retired manual tag has been reused by an engine")
                self.assertTrue(old.startswith("manual-v"),
                                "a non-manual version is being read as one")

    def test_no_two_engines_share_a_version_string(self):
        """Two engines under one label is the collision itself, in its purest
        form — a fact would be unattributable to the code that made it."""
        self.assertEqual(len(set(LOCKED.values())), len(LOCKED),
                         f"duplicate version string across engines: {LOCKED}")

    def test_every_version_is_namespaced_to_its_engine(self):
        """`exec-v0.9-draft` must not be readable as a swing version. The prefix
        is what makes a stray version string self-describing in a log."""
        for kind, ver in LOCKED.items():
            stem = ver.split("-v")[0]
            self.assertTrue(
                kind.startswith(stem) or stem.startswith(kind[:4]),
                f"{kind} version {ver!r} does not name its own engine")


if __name__ == "__main__":
    unittest.main()
