"""Immutable setup-time research snapshots; never a trading consumer."""
import json

from . import research, setups, store
from .runlog import RunRecorder

SNAPSHOT_VERSION = "research-snapshot-v0.1-draft"


def unavailable(symbol=None, as_of=None) -> dict:
    return {"version": SNAPSHOT_VERSION, "symbol": symbol, "as_of": as_of,
            "timeframes": list(research.TIMEFRAMES), "rows": [],
            "availability": "UNAVAILABLE",
            "missing_reason": "No immutable setup-time research snapshot was captured.",
            "affects_trading": False,
            "notice": "Research observation — did not affect this setup."}


def run(con, symbol: str, tf: str, tf_seconds: int,
        *, fact_floor: int | None = None) -> dict:
    with RunRecorder(con, "researchsignals", SNAPSHOT_VERSION, symbol, tf) as rec:
        start = research.collection_start(con, "order_block", research.ORDER_BLOCK_VERSION)
        if start is None or fact_floor is None:
            rec.notes = ("inactive" if start is None else
                         "no live-cycle setup boundary — snapshots skipped")
            return {"symbol": symbol, "tf": tf, "snapshots": 0}
        existing = {json.loads(r[0]).get("setup_id") for r in con.execute(
            "SELECT payload FROM facts WHERE symbol=? AND tf=? AND kind='research_snapshot' "
            "AND algo_version=?", (symbol, tf, SNAPSHOT_VERSION))}
        count = 0
        rows = store.get_facts(con, symbol, tf, "setup", setups.SETUP_VERSION)
        rec.n_inputs = len(rows)
        for row in rows:
            # The live cycle records the fact high-water before setup engines
            # run. A setup missed by its own cycle is below every later floor
            # and therefore remains explicitly unavailable forever.
            if int(row["id"]) <= int(fact_floor):
                continue
            payload = json.loads(row["payload"])
            setup_id = payload.get("setup_id")
            if payload.get("state") != "VALIDATED" or not setup_id or setup_id in existing:
                continue
            cutoff = int(row["confirmed_at"])
            if cutoff < start:
                continue
            payload = dict(payload)
            payload.setdefault("symbol", symbol)
            payload.setdefault("tf", tf)
            observations = research.matrix(
                con, symbol, as_of=cutoff, direction=payload.get("direction"),
                setup_payload=payload, now=cutoff)
            snap = {"setup_id": setup_id, "captured_as_of": cutoff,
                    "research_observations": observations,
                    "affects_trading": False}
            if store.insert_fact(con, symbol=symbol, tf=tf,
                                 kind="research_snapshot",
                                 market_time=row["market_time"],
                                 confirmed_at=cutoff,
                                 algo_version=SNAPSHOT_VERSION, payload=snap):
                count += 1
                existing.add(setup_id)
        con.commit()
        rec.n_new_facts = count
        return {"symbol": symbol, "tf": tf, "snapshots": count}


def for_setup(con, setup_id: str) -> dict | None:
    row = con.execute(
        "SELECT payload FROM facts WHERE kind='research_snapshot' "
        "AND algo_version=? AND json_extract(payload,'$.setup_id')=? "
        "ORDER BY confirmed_at,id LIMIT 1", (SNAPSHOT_VERSION, setup_id)).fetchone()
    return json.loads(row[0])["research_observations"] if row else None
