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

from engine import (bias, breakout, cooldowns, cycles, execsim, venues,
                    liquidity, ma, manual, momentum, ranges, regime,
                    risk, scalein, setups, structure, swings, volatility,
                    volume, zones, trend)

# The current, deliberate state of the pipeline. Update WITH the cascade.
LOCKED = {
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
    # S53 cascade — the widest this file has recorded, and the reason it exists.
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
    "swing": "swing-v0.9-draft",
    # S53 addendum, caught in the FIRST live v0.9 cycle: the new consumer
    # collapse keyed pivots on market_time alone, and one bar can host both a
    # promoted HIGH and a promoted LOW (2025-10-10 carries a MAJOR pair on
    # three symbols) — the later row shadowed its twin, so five supply zones
    # store-wide were never created. Pivot identity is (market_time, type).
    # structure/zone/liquidity rules changed, so they and everything downstream
    # move AGAIN — the v0.11/v0.12/v0.10 facts from that one cycle remain in
    # the store as the recorded dud.
    "structure": "structure-v0.12-draft",
    # S50: zone-v0.11 closed a creation-time LOOKAHEAD — the cluster count read
    # swings not yet confirmed, inflating formation_quality on 7.9% of zones.
    # CONSUMERS["zone"] is ("setup",), and setup's own consumers are
    # ("exec", "risk", "scale"), so the whole trading path cascades.
    "zone": "zone-v0.13-draft",
    "liquidity": "liq-v0.11-draft",
    "regime": "regime-v0.12-draft",
    "ranges": "ranges-v0.2-draft",
    "ma": "ma-v0.1-draft",
    "momentum": "momentum-v0.2-draft",
    "volatility": "volatility-v0.1-draft",
    "volume": "volume-v0.1-draft",
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
    "setup": "setup-v0.17-draft",
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
    "exec": "exec-v0.21-draft",
    "risk": "risk-v0.20-draft",
    "scale": "scale-v0.15-draft",
    "cooldown": "cooldown-v0.9-draft",
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
    "breakout": "breakout-v0.5-draft",
    # trend-v0.1: NEW ENGINE, measured and not enabled. It arrives because
    # grading the MA against the book found LONG x ABOVE = 0 and
    # SHORT x BELOW = 0 across all 477 closed trades — both shipped playbooks
    # enter counter-move, so every trend-following factor is a constant here
    # and cannot be graded at all. No cascade DOWNSTREAM (nothing reads
    # trend-*), but it sits downstream of `ma` and `swing`: it computes the
    # ribbon with ma.ema / ma.sma and takes targets from INTERMEDIATE+ swings,
    # so both appear in its CONSUMERS entries and a bump to either moves this.
    "trend": "trend-v0.2-draft",
    # bias-v0.1: NEW SHARED LAYER, record-only. It arrives because three
    # engines answered "does the higher timeframe matter" three different ways
    # — scalein gates hard, setups records and ignores, trend did not look at
    # all — and none of those three answers was chosen by measurement. It reads
    # `regime` and `structure` facts and writes none of its own, so it is
    # downstream of both and upstream of every playbook that records it.
    "bias": "bias-v0.1-draft",
    "venues": "venues-v0.2-draft",
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
    "manual": "manual-v0.3-draft",
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
}


class VersionLockfile(unittest.TestCase):
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
