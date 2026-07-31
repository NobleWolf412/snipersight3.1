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

from engine import (breakout, cooldowns, cycles, execsim, venues, liquidity, ma, momentum, ranges, regime,
                    risk, scalein, setups, structure, swings, volatility,
                    volume, zones)

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
    "venues": venues.VENUES_VERSION,
    # Observational satellite with no consumers — locked anyway, because
    # "nothing reads it" is exactly how it went dead unnoticed for 21 hours.
    "cycles": cycles.CYCLES_VERSION,
}

EXPECTED = {
    "swing": "swing-v0.8-draft",
    "structure": "structure-v0.10-draft",
    # S50: zone-v0.11 closed a creation-time LOOKAHEAD — the cluster count read
    # swings not yet confirmed, inflating formation_quality on 7.9% of zones.
    # CONSUMERS["zone"] is ("setup",), and setup's own consumers are
    # ("exec", "risk", "scale"), so the whole trading path cascades.
    #
    # zone-v0.12 is the SAME defect one layer down, and the measurement is
    # worse: the cluster counted swing FACTS rather than swings. `swings`
    # re-emits a pivot whenever its accrued evidence changes, so one pivot can
    # hold 18 rows identical in everything zones reads, and `m != k` excludes
    # the row rather than the swing — a zone counted copies of its own anchor.
    # 65.8% of 2,066 anchors carried an inflated cluster; formation_quality was
    # higher in 1,359 cases and lower in ZERO; worst was quality 90 on a cluster
    # of 24 whose true membership was 0. Same cascade as v0.11, plus cooldown:
    # zone -> setup -> (exec, risk, scale) -> (risk, scale, cooldown) -> risk.
    "zone": "zone-v0.12-draft",
    "liquidity": "liq-v0.9-draft",
    "regime": "regime-v0.10-draft",
    "ranges": "ranges-v0.1-draft",
    "ma": "ma-v0.1-draft",
    "momentum": "momentum-v0.1-draft",
    "volatility": "volatility-v0.1-draft",
    "volume": "volume-v0.1-draft",
    "setup": "setup-v0.14-draft",
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
    "exec": "exec-v0.18-draft",
    # risk-v0.18 is NOT a cascade. v0.17 was (from exec-v0.18); v0.18 is risk's
    # own defect — `exits` keyed on `setup_id` alone merged 112 of 452 exits on
    # exec-v0.8, because one plan re-simulated under a changed cost manifest
    # writes several exec facts under one tag. Two changes, two versions, so the
    # label says which book it is. CONSUMERS has no entry for "risk": nothing
    # reads its facts, so this bump stops here.
    "risk": "risk-v0.18-draft",
    "scale": "scale-v0.12-draft",
    "cooldown": "cooldown-v0.6-draft",
    "breakout": "breakout-v0.2-draft",
    "venues": "venues-v0.2-draft",
    "cycles": "cycles-v0.2-draft",
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
    "ma": ("momentum", "volatility", "volume"),
    "swing": ("structure", "zone", "liquidity", "ranges", "momentum"),
    "structure": ("regime", "scale"),
    "zone": ("setup",),
    "liquidity": ("setup",),
    "regime": ("setup",),
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
