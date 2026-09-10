"""A retired market must not strand the sole paper slot after an upgrade.

All writes use a scratch store; cycle tests stub every external effect.
"""
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import live
from engine import execsim, quality, risk, setups, store, universe


class ExecutionRebuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = store.connect(Path(self.tmp.name) / "scratch.db")
        store.start_baseline(self.con, started_at=3600, label="test")
        store.insert_fact(
            self.con, symbol="UNIVERSE", tf="ALL", kind="universe",
            market_time=0, confirmed_at=0, algo_version=universe.UNIVERSE_VERSION,
            payload={"members": [{"symbol": s, "state": "ADMITTED"}
                                 for s in ("UNIUSDT", "BTCUSDT")]})
        self.con.commit()

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def fact(self, kind, sid, ts=72000, symbol="UNIUSDT", version=None, **p):
        store.insert_fact(
            self.con, symbol=symbol, tf="1H", kind=kind,
            market_time=ts, confirmed_at=ts,
            algo_version=version or (setups.SETUP_VERSION if kind == "setup"
                                     else execsim.EXEC_VERSION),
            payload={"setup_id": sid, **p})
        self.con.commit()

    def plan(self, sid="old", **kw):
        self.fact("setup", sid, state="VALIDATED", strategy="PULLBACK",
                  direction="LONG", entry="100", sl="95", tp="110",
                  entry_model="MARKET_NEXT_OPEN", rr="2", rank=50, **kw)
        # The order bar. Recovery ignores a plan the simulator could not have
        # placed yet, so a plan meant to READ as missing work needs one; OR
        # IGNORE because seed_book() lays its own series over the same slots.
        self.con.execute(
            "INSERT OR IGNORE INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            (kw.get("symbol", "UNIUSDT"), "1H", kw.get("ts", 72000),
             "100", "101", "99", "100", "1", "test", 0))
        self.con.commit()

    def test_old_generation_close_does_not_hide_missing_current_work(self):
        self.plan()
        self.fact("order", "old", version="exec-retired", event="FILLED")
        self.fact("exec", "old", version="exec-retired", outcome="SL",
                  r_multiple="-1")
        self.assertEqual(execsim.unresolved(self.con), {})
        self.assertEqual(live.execution_rebuild_work(self.con), {
            ("UNIUSDT", "1H"): [{"setup_id": "old", "event": "REBUILD"}]})

    def test_only_current_baseline_enabled_plans_need_rebuilding(self):
        self.plan("before", ts=0)
        self.plan("retired", version="setup-retired")
        self.plan("research", version="trend-research")
        self.plan("watch-only", symbol="PF_XBTUSD")
        self.fact("setup", "forming", state="FORMING")
        self.plan("closed")
        self.fact("exec", "closed", outcome="TP", r_multiple="2")
        self.plan("missed")
        self.fact("exec", "missed", outcome="MISSED", r_multiple="0")
        self.plan("open")
        self.fact("order", "open", event="FILLED")
        self.assertEqual(live.execution_rebuild_work(self.con), {})
        self.assertEqual(execsim.unresolved(self.con)[("UNIUSDT", "1H")],
                         [{"setup_id": "open", "event": "FILLED"}])

    def seed_book(self):
        for symbol in ("UNIUSDT", "BTCUSDT"):
            self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (symbol, "1D", 0, "100", "101", "99", "100",
                              "1", "test", 0))
            for i in range(30):
                high = "112" if symbol == "UNIUSDT" and i == 21 else "101"
                self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                                 (symbol, "1H", i * 3600, "100", high, "99",
                                  "100", "1", "test", i * 3600))
        self.plan()
        self.plan("next", ts=25 * 3600, symbol="BTCUSDT")
        self.fact("exec", "old", ts=22 * 3600, version="exec-retired",
                  outcome="SL", r_multiple="-1")
        self.con.commit()

    def decisions(self):
        return {json.loads(r[0])["setup_id"]: json.loads(r[0])
                for r in self.con.execute(
                    "SELECT payload FROM facts WHERE kind='risk' AND algo_version=?"
                    " AND json_extract(payload,'$.event')='DECISION' ORDER BY id",
                    (risk.RISK_VERSION,))}

    def test_real_replay_releases_ghost_but_keeps_a_genuinely_open_slot(self):
        self.seed_book()
        with patch.object(risk, "admitted_at", return_value=True), \
             patch.object(live.quality, "cached_audit", return_value=None):
            risk.run(self.con)
            self.assertEqual(self.decisions()["next"]["reasons"],
                             ["CONCURRENT_LIMIT(1)"])
            execsim.run(self.con, "UNIUSDT", "1H", 3600)
            risk.run(self.con)
            self.assertIn(self.decisions()["next"]["decision"],
                          ("APPROVED", "REDUCED"))
            # It is the new simulation's TP, not the retired SL copied over.
            result = store.get_facts(self.con, "UNIUSDT", "1H", "exec",
                                     execsim.EXEC_VERSION)
            self.assertEqual(json.loads(result[-1]["payload"])["outcome"], "TP")
            self.plan("later", ts=26 * 3600, symbol="BTCUSDT")
            risk.run(self.con)
            self.assertEqual(self.decisions()["later"]["reasons"],
                             ["CONCURRENT_LIMIT(1)"])
            before = self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
            execsim.run(self.con, "UNIUSDT", "1H", 3600)
            risk.run(self.con)
            self.assertEqual(self.con.execute("SELECT COUNT(*) FROM facts").fetchone()[0],
                             before, "recovery must be idempotent")

    def cycle(self, blocked=False, retired=False):
        """Run orchestration with network, routing and housekeeping stubbed."""
        with ExitStack() as stack:
            def stub(target, **kw):
                return stack.enter_context(patch(target, **kw))
            stub("live.time.time", return_value=111600)
            stub("live.universe.scan_symbols", return_value=["BTCUSDT"])
            stub("live.universe.all_tracked_symbols", return_value=[])
            stub("live.importer.native_tfs", return_value={"1H": 3600})
            imports = stub("live.importer.backfill", return_value={"candles": 0, "gaps": 0})
            stub("live.venues.REFERENCE", new={})
            stub("engine.manual.unresolved", return_value={})
            stub("live.aggregator.aggregate")
            ready = stub("live.quality.assert_market_ready",
                         return_value=[{"code": "RETIRED_SEQUENCE_GAPS"}] if retired else [],
                         side_effect=RuntimeError("quality blocked") if blocked else None)
            run = stub("live.execsim.run")
            cool = stub("live.cooldowns.run")
            pipeline = stub("live.pipeline.run_symbol", return_value={"blocked": None})
            stub("live.risk.run")
            stub("live.execution.monitor_paper")
            stub("live.automation.current", return_value=(live.automation.AutomationMode.PAPER, 0))
            stub("live.positions.private_environments_with_exposure", return_value=set())
            broker = stub("live.broker_factory.phemex_for_mode")
            stub("live.autotrader.run", return_value={"routed": [], "refused": []})
            stub("live.quality.audit")
            stub("prune.maybe_auto_prune_runs")
            stub("engine.regrade.maybe_run")
            stub("live.announceable", return_value=[])
            log = Mock()
            live.cycle(self.con, log)
            broker.assert_not_called()
            if blocked or retired:
                cool.assert_not_called()
            else:
                cool.assert_called_once_with(self.con, "UNIUSDT", "1H", 3600)
            return imports, ready, run, pipeline, log

    def test_cycle_recovers_removed_market_even_without_new_candles(self):
        self.seed_book()
        imports, ready, run, pipeline, log = self.cycle()
        self.assertIn("UNIUSDT", [c.args[1] for c in imports.call_args_list])
        ready.assert_called_once_with(self.con, "UNIUSDT", 111600)
        run.assert_called_once_with(self.con, "UNIUSDT", "1H", 3600)
        self.assertEqual([c.args[1] for c in pipeline.call_args_list], ["BTCUSDT"])
        self.assertTrue(any("execution rebuild" in c.args[0] for c in log.warning.call_args_list))

    def test_quality_failure_never_fabricates_a_close(self):
        self.seed_book()
        _, _, run, _, log = self.cycle(blocked=True)
        run.assert_not_called()
        self.assertTrue(any("resolution blocked" in c.args[0] for c in log.warning.call_args_list))
        self.assertIn(("UNIUSDT", "1H"), live.execution_rebuild_work(self.con))

    def test_retired_gap_note_cannot_be_used_to_reconstruct_a_trade(self):
        self.seed_book()
        _, _, run, _, log = self.cycle(retired=True)
        run.assert_not_called()
        self.assertTrue(any("retired sequence gaps" in c.args[0]
                            for c in log.warning.call_args_list))

    def test_the_veto_can_never_reach_a_market_holding_a_slot(self):
        """What makes the retired-gap veto safe, asserted where it is used.

        The veto refuses reconstruction, and refusing to resolve a live order
        would strand it instead — the XLMUSDT failure the pin exists to
        prevent. It cannot: quality keeps every unresolved market blocking, so
        RETIRED_SEQUENCE_GAPS is unreachable for one. If this ever fails, the
        veto in live.cycle needs a live-order carve-out; until then, one
        would be dead code.
        """
        self.plan()
        self.fact("order", "old", event="FILLED")
        self.assertIn(("UNIUSDT", "1H"), execsim.unresolved(self.con))
        self.assertIn("UNIUSDT",
                      quality._symbols_that_must_keep_blocking(self.con))

    def test_a_timeframe_risk_cannot_size_is_not_missing_work(self):
        """Deleting the risk.TFS filter must fail something."""
        odd = next(tf for tf in ("3m", "2H", "8H") if tf not in risk.TFS)
        store.insert_fact(
            self.con, symbol="UNIUSDT", tf=odd, kind="setup", market_time=72000,
            confirmed_at=72000, algo_version=setups.SETUP_VERSION,
            payload={"setup_id": "offbeat", "state": "VALIDATED"})
        self.con.execute("INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
                         ("UNIUSDT", odd, 72000, "100", "101", "99", "100",
                          "1", "test", 0))
        self.con.commit()
        self.assertEqual(live.execution_rebuild_work(self.con), {})

    def test_a_plan_whose_order_bar_has_not_printed_is_not_missing_work(self):
        """Otherwise every fresh setup reads as missing until its next bar."""
        self.fact("setup", "fresh", ts=999999, state="VALIDATED",
                  strategy="PULLBACK", direction="LONG", entry="100",
                  sl="95", tp="110", entry_model="MARKET_NEXT_OPEN")
        self.assertEqual(live.execution_rebuild_work(self.con), {})
        self.con.execute(
            "INSERT INTO candles VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("UNIUSDT", "1H", 999999, "100", "101", "99", "100", "1", "t", 0))
        self.con.commit()
        self.assertEqual(live.execution_rebuild_work(self.con), {
            ("UNIUSDT", "1H"): [{"setup_id": "fresh", "event": "REBUILD"}]})
