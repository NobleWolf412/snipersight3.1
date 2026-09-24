"""Research-only indicator observations and point-in-time read models.

Nothing in this module is imported by setup, risk, execution, sizing or routing.
It records independent evidence after the descriptive/trend engines have run and
later joins those observations to closed outcomes.  Missing evidence remains
missing; no observation is converted into a setup score or trading permission.
"""
from __future__ import annotations

import json
from decimal import Decimal

from . import factorstats, liquidity, ma, momentum, store, structure, zones
from .ma import plain, sig
from .runlog import RunRecorder


RESEARCH_VERSION = "research-v0.1-draft"
ORDER_BLOCK_VERSION = "order-block-v0.1-draft"
STRUCTURE_SEQUENCE_VERSION = "structure-sequence-v0.1-draft"
STOCH_RSI_VERSION = "stoch-rsi-v0.1-draft"
HIDDEN_DIVERGENCE_VERSION = "hidden-divergence-v0.1-draft"
OPEN_INTEREST_SIGNAL_VERSION = "open-interest-signal-v0.1-draft"
READ_MODEL_VERSION = "research-observation-v0.1-draft"
EVIDENCE_VERSION = "research-evidence-v0.1-draft"

TIMEFRAMES = ("15m", "1H", "4H", "1D")
TF_SECONDS = {"5m": 300, "15m": 900, "1H": 3600, "4H": 14400,
              "1D": 86400, "1W": 604800}
STOCH_PERIOD = 14
STOCH_K = 3
STOCH_D = 3
PRIMARY_EXIT_BARS = 3
HIDDEN_MAX_BARS = 10
ORDER_BLOCK_LOOKBACK = 20
SEQUENCE_LOOKBACK = 20
MIN_TRADES = 30
MIN_SYMBOLS = 8
OI_STALE_AFTER = 2 * 3600

FAMILIES = (
    ("trend", "Trend"),
    ("structure", "Structure"),
    ("order_block", "Order block"),
    ("structure_sequence", "Sweep → break → block"),
    ("rsi_divergence", "RSI divergence"),
    ("hidden_divergence", "Hidden divergence"),
    ("stoch_rsi", "Stoch RSI"),
    ("open_interest", "Open interest"),
)

DETECTOR_VERSIONS = {
    "trend": ma.MA_VERSION,
    "structure": structure.STRUCTURE_VERSION,
    "order_block": ORDER_BLOCK_VERSION,
    "structure_sequence": STRUCTURE_SEQUENCE_VERSION,
    "rsi_divergence": momentum.MOMENTUM_VERSION,
    "hidden_divergence": HIDDEN_DIVERGENCE_VERSION,
    "stoch_rsi": STOCH_RSI_VERSION,
    "open_interest": OPEN_INTEREST_SIGNAL_VERSION,
}


def activate(con, started_at: int) -> None:
    """Register collection once. Existing rows are never moved or replaced."""
    for detector, version in {**DETECTOR_VERSIONS,
                              "structure_sequence": STRUCTURE_SEQUENCE_VERSION}.items():
        con.execute("INSERT OR IGNORE INTO research_collections "
                    "(detector,version,started_at) VALUES (?,?,?)",
                    (detector, version, int(started_at)))
    commit = getattr(con, "commit", None)
    if commit:
        commit()


def collection_start(con, detector: str, version: str) -> int | None:
    row = con.execute("SELECT started_at FROM research_collections "
                      "WHERE detector=? AND version=?", (detector, version)).fetchone()
    return int(row[0]) if row else None


def _effective_confirmation(con, detector: str, version: str, original: int) -> int:
    start = collection_start(con, detector, version)
    return max(int(original), start or int(original))

HYPOTHESES = {
    "order_block": "A direction-matched last opposite candle before the break overlaps the setup's originating zone.",
    "structure_sequence": "An ordered sweep, then break, then block linked to that break outperforms the same components when unordered or unlinked.",
    "stoch_rsi": "Stoch RSI exits 20/80 in the trade direction within three closed setup-timeframe candles.",
    "hidden_divergence": "Trend-aligned hidden RSI divergence appears within ten closed setup-timeframe candles.",
    "open_interest": "Phemex perpetual price and open interest expand together over one hour in the trade direction.",
}

EXPLORATORY = {
    "order_block": ["Rejection/engulfing variant", "Structural-extreme variant"],
    "structure_sequence": ["Individual component", "Paired components"],
    "stoch_rsi": ["Static extreme", "K/D-only cross", "Other timeframe"],
    "hidden_divergence": ["MACD divergence", "No trend filter"],
    "open_interest": ["Other price/OI quadrants", "Continuous threshold"],
}


def _facts(con, symbol, tf, kind, version, as_of=None) -> list[dict]:
    rows = []
    for row in store.get_facts(con, symbol, tf, kind, version, as_of):
        rows.append({"market_time": row["market_time"],
                     "confirmed_at": row["confirmed_at"],
                     "algo_version": row["algo_version"],
                     **json.loads(row["payload"])})
    return rows


def compute_stoch_rsi(closes: list[Decimal]) -> tuple[list, list, list]:
    """TradingView-compatible Stoch RSI(14,14,3,3), Decimal end to end.

    Wilder RSI comes from momentum.compute_rsi.  Every rolling stochastic and
    smoothing step uses ma.sig; unavailable windows stay None.
    """
    rsi = momentum.compute_rsi(closes, momentum.RSI_PERIOD)
    raw = [None] * len(closes)
    for i in range(len(closes)):
        start = i - STOCH_PERIOD + 1
        if start < 0:
            continue
        window = rsi[start:i + 1]
        if any(v is None for v in window):
            continue
        lo, hi = min(window), max(window)
        if hi == lo:
            continue
        raw[i] = sig((rsi[i] - lo) * Decimal(100) / (hi - lo))

    def smooth(values, period):
        out = [None] * len(values)
        for i in range(len(values)):
            start = i - period + 1
            if start < 0:
                continue
            window = values[start:i + 1]
            if any(v is None for v in window):
                continue
            out[i] = sig(sum(window) / Decimal(period))
        return out

    k = smooth(raw, STOCH_K)
    d = smooth(k, STOCH_D)
    return raw, k, d


def _latest_ma(facts: list[dict], as_of: int) -> dict | None:
    latest = None
    for row in facts:
        if row["confirmed_at"] <= as_of:
            latest = row
    return latest


def _emit_stoch(con, symbol, tf, candles, tf_seconds) -> int:
    closes = [Decimal(c["close"]) for c in candles]
    raw, ks, ds = compute_stoch_rsi(closes)
    count = 0
    prev_k = None
    for i, candle in enumerate(candles):
        k, d = ks[i], ds[i]
        if k is None or d is None:
            prev_k = None
            continue
        event = "NEUTRAL"
        direction = "NEUTRAL"
        if prev_k is not None and prev_k <= Decimal(20) < k:
            event, direction = "OVERSOLD_EXIT", "BULL"
        elif prev_k is not None and prev_k >= Decimal(80) > k:
            event, direction = "OVERBOUGHT_EXIT", "BEAR"
        elif k <= Decimal(20):
            event = "OVERSOLD"
        elif k >= Decimal(80):
            event = "OVERBOUGHT"
        elif k > d:
            event, direction = "RISING", "BULL"
        elif k < d:
            event, direction = "FALLING", "BEAR"
        payload = {"event": event, "direction": direction,
                   "rsi_stoch": plain(raw[i]) if raw[i] is not None else None,
                   "k": plain(k), "d": plain(d), "bar_index": i,
                   "overbought": "80", "oversold": "20"}
        confirmed = _effective_confirmation(
            con, "stoch_rsi", STOCH_RSI_VERSION, candle["open_ts"] + tf_seconds)
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="stoch_rsi",
                             market_time=candle["open_ts"],
                             confirmed_at=confirmed,
                             algo_version=STOCH_RSI_VERSION, payload=payload):
            count += 1
        prev_k = k
    return count


def _emit_order_blocks(con, symbol, tf, candles) -> tuple[int, list[dict]]:
    by_ts = {c["open_ts"]: i for i, c in enumerate(candles)}
    blocks, count = [], 0
    for br in _facts(con, symbol, tf, "structure", structure.STRUCTURE_VERSION):
        if br.get("event") not in ("BOS", "CHOCH"):
            continue
        i = by_ts.get(br["market_time"])
        if i is None:
            continue
        direction = br.get("direction")
        chosen = None
        for j in range(i - 1, max(-1, i - ORDER_BLOCK_LOOKBACK - 1), -1):
            c = candles[j]
            o, close = Decimal(c["open"]), Decimal(c["close"])
            opposite = close < o if direction == "BULL" else close > o
            if opposite:
                chosen = c
                break
        if chosen is None:
            continue
        bottom, top = Decimal(chosen["low"]), Decimal(chosen["high"])
        block_id = f"{symbol}|{tf}|{direction}|{chosen['open_ts']}|{br['market_time']}"
        payload = {"event": "CREATED", "variant": "LAST_OPPOSITE_BEFORE_BREAK",
                   "block_id": block_id, "direction": direction,
                   "bottom": plain(bottom), "top": plain(top),
                   "source_candle_ts": chosen["open_ts"],
                   "break_ts": br["market_time"],
                   "break_event": br.get("event"),
                   "break_level": br.get("level")}
        confirmed = _effective_confirmation(
            con, "order_block", ORDER_BLOCK_VERSION, br["confirmed_at"])
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="order_block",
                             market_time=chosen["open_ts"],
                             confirmed_at=confirmed,
                             algo_version=ORDER_BLOCK_VERSION, payload=payload):
            count += 1
        blocks.append({"market_time": chosen["open_ts"],
                       "confirmed_at": confirmed, **payload})
    return count, blocks


def _emit_sequences(con, symbol, tf, blocks, tf_seconds) -> int:
    sweeps = [r for r in _facts(con, symbol, tf, "liquidity", liquidity.LIQ_VERSION)
              if r.get("event") == "SWEEP"]
    count = 0
    for block in blocks:
        want_side = "LOW" if block["direction"] == "BULL" else "HIGH"
        nearby = [s for s in sweeps
                  if s.get("side") == want_side
                  and abs(block["break_ts"] - s["market_time"])
                  <= SEQUENCE_LOOKBACK * tf_seconds]
        ordered = [s for s in nearby
                   if s["market_time"] < block["break_ts"]
                   and s["confirmed_at"] < block["confirmed_at"]]
        sweep = (max(ordered, key=lambda s: (s["confirmed_at"], s["market_time"]))
                 if ordered else
                 min(nearby, key=lambda s: (abs(s["market_time"] - block["break_ts"]),
                                            s["confirmed_at"]))
                 if nearby else None)
        state = "COMPLETE" if ordered else "UNORDERED" if sweep else "PARTIAL"
        payload = {"event": "SEQUENCE", "state": state,
                   "direction": block["direction"],
                   "block_id": block["block_id"],
                   "block_ts": block["source_candle_ts"],
                   "break_ts": block["break_ts"],
                   "sweep_ts": sweep["market_time"] if sweep else None,
                   "sweep_pool_id": sweep.get("pool_id") if sweep else None,
                   "ordered": bool(ordered), "linked": True}
        causal_confirmation = max(block["confirmed_at"],
                                  sweep["confirmed_at"] if sweep else 0)
        confirmed = _effective_confirmation(
            con, "structure_sequence", STRUCTURE_SEQUENCE_VERSION,
            causal_confirmation)
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="structure_sequence",
                             market_time=block["break_ts"],
                             confirmed_at=confirmed,
                             algo_version=STRUCTURE_SEQUENCE_VERSION,
                             payload=payload):
            count += 1
    return count


def _emit_hidden_divergence(con, symbol, tf, candles, tf_seconds) -> int:
    closes = [Decimal(c["close"]) for c in candles]
    rsi = momentum.compute_rsi(closes)
    ts_index = {c["open_ts"]: i for i, c in enumerate(candles)}
    pivots = momentum._pivots(con, symbol, tf)
    ma_facts = _facts(con, symbol, tf, "ma", ma.MA_VERSION)
    count = 0
    for k in range(2, len(pivots)):
        prev, cur = pivots[k - 2], pivots[k]
        i1, i2 = ts_index.get(prev["market_time"]), ts_index.get(cur["market_time"])
        if i1 is None or i2 is None or i2 - i1 > momentum.MAX_PIVOT_GAP_BARS:
            continue
        if rsi[i1] is None or rsi[i2] is None:
            continue
        p1, p2 = Decimal(prev["price"]), Decimal(cur["price"])
        r1, r2 = rsi[i1], rsi[i2]
        trend = _latest_ma(ma_facts, cur["confirmed_at"])
        stack = trend.get("stack") if trend else None
        if cur["type"] == "LOW" and p2 > p1 and r2 < r1 and stack == "BULL":
            direction, kind = "BULL", "BULLISH_HIDDEN"
        elif cur["type"] == "HIGH" and p2 < p1 and r2 > r1 and stack == "BEAR":
            direction, kind = "BEAR", "BEARISH_HIDDEN"
        else:
            continue
        confirmed = max(prev["confirmed_at"], cur["confirmed_at"],
                        candles[i2]["open_ts"] + tf_seconds,
                        trend["confirmed_at"] if trend else 0)
        confirmed = _effective_confirmation(
            con, "hidden_divergence", HIDDEN_DIVERGENCE_VERSION, confirmed)
        payload = {"event": "HIDDEN_DIVERGENCE", "divergence": kind,
                   "direction": direction, "trend_stack": stack,
                   "trend_version": ma.MA_VERSION,
                   "price": plain(p2), "price_prev": plain(p1),
                   "rsi": plain(r2), "rsi_prev": plain(r1),
                   "prev_pivot_ts": prev["market_time"],
                   "bars_apart": i2 - i1, "bar_index": i2}
        if store.insert_fact(con, symbol=symbol, tf=tf, kind="hidden_divergence",
                             market_time=cur["market_time"],
                             confirmed_at=confirmed,
                             algo_version=HIDDEN_DIVERGENCE_VERSION,
                             payload=payload):
            count += 1
    return count


def run(con, symbol: str, tf: str, tf_seconds: int) -> dict:
    """Record all candle/fact-derived research observations for one series."""
    with RunRecorder(con, "research", RESEARCH_VERSION, symbol, tf) as rec:
        if collection_start(con, "order_block", ORDER_BLOCK_VERSION) is None:
            rec.notes = "inactive — no research collection boundary"
            return {"symbol": symbol, "tf": tf, "new": 0,
                    "availability": "INACTIVE"}
        candles = [dict(r) for r in store.get_candles(con, symbol, tf)]
        rec.n_inputs = len(candles)
        if not candles:
            return {"symbol": symbol, "tf": tf, "new": 0}
        stoch = _emit_stoch(con, symbol, tf, candles, tf_seconds)
        blocks_n, blocks = _emit_order_blocks(con, symbol, tf, candles)
        sequences = _emit_sequences(con, symbol, tf, blocks, tf_seconds)
        hidden = _emit_hidden_divergence(con, symbol, tf, candles, tf_seconds)
        con.commit()
        rec.n_new_facts = stoch + blocks_n + sequences + hidden
        rec.notes = (f"stoch={stoch} order_blocks={blocks_n} "
                     f"sequences={sequences} hidden={hidden}")
        return {"symbol": symbol, "tf": tf, "stoch_rsi": stoch,
                "order_blocks": blocks_n, "structure_sequences": sequences,
                "hidden_divergence": hidden, "new": rec.n_new_facts}


def _status(signal_direction: str | None, trade_direction: str | None) -> str:
    if signal_direction in (None, "", "UNKNOWN"):
        return "NEUTRAL"
    if signal_direction == "NEUTRAL" or trade_direction not in ("LONG", "SHORT"):
        return "NEUTRAL"
    wanted = "BULL" if trade_direction == "LONG" else "BEAR"
    return "ALIGNED" if signal_direction == wanted else "OPPOSED"


def _cell(family, tf, *, raw="None", direction="NEUTRAL", status="NEUTRAL",
          confirmed_at=None, version=None, source_tf=None, values=None,
          missing_reason=None):
    return {"family": family, "timeframe": tf, "raw": raw,
            "direction": direction, "status": status,
            "confirmed_at": confirmed_at, "detector_version": version,
            "source_timeframe": source_tf or tf, "values": values or {},
            "missing_reason": missing_reason}


class ResearchIndex:
    """Small per-request timeline cache; it never writes or derives trading state."""
    def __init__(self, con):
        self.con = con
        self.cache = {}

    def rows(self, symbol, tf, kind, version):
        key = (symbol, tf, kind, version)
        if key not in self.cache:
            self.cache[key] = _facts(self.con, symbol, tf, kind, version)
        return self.cache[key]

    def through(self, symbol, tf, kind, version, as_of):
        return [r for r in self.rows(symbol, tf, kind, version)
                if r["confirmed_at"] <= as_of]


def _latest(rows, predicate=lambda _r: True):
    chosen = None
    for row in rows:
        if predicate(row) and (chosen is None or
                (row["confirmed_at"], row["market_time"]) >
                (chosen["confirmed_at"], chosen["market_time"])):
            chosen = row
    return chosen


def _zone_overlap(block, setup_payload):
    try:
        lo = Decimal(str(setup_payload.get("zone_bottom", setup_payload.get("bottom"))))
        hi = Decimal(str(setup_payload.get("zone_top", setup_payload.get("top"))))
        return Decimal(block["bottom"]) <= hi and Decimal(block["top"]) >= lo
    except Exception:
        return None


def _setup_zone_payload(idx, symbol, setup_payload, as_of):
    """Resolve the exact originating 3.1 zone without inventing UI geometry."""
    zone_id = setup_payload.get("zone_id")
    setup_tf = setup_payload.get("tf")
    if not zone_id or not setup_tf:
        return setup_payload
    rows = idx.through(symbol, setup_tf, "zone", zones.ZONE_VERSION, as_of)
    zone = _latest(rows, lambda row: row.get("zone_id") == zone_id)
    if not zone:
        return setup_payload
    enriched = dict(setup_payload)
    enriched["zone_bottom"] = zone.get("bottom")
    enriched["zone_top"] = zone.get("top")
    return enriched


def matrix(con, symbol: str, *, as_of: int, direction: str | None = None,
           setup_payload: dict | None = None, now: int | None = None,
           index: ResearchIndex | None = None) -> dict:
    """Server-owned multi-timeframe signal map at one causal cutoff."""
    idx = index or ResearchIndex(con)
    setup_payload = setup_payload or {}
    setup_payload = _setup_zone_payload(idx, symbol, setup_payload, as_of)
    cells = []

    def available(detector, version):
        start = collection_start(con, detector, version)
        return start is not None and as_of >= start

    for tf in TIMEFRAMES:
        # Trend
        rows = idx.through(symbol, tf, "ma", ma.MA_VERSION, as_of)
        row = _latest(rows)
        if row:
            signal = row.get("stack", "MIXED")
            d = "BULL" if signal == "BULL" else "BEAR" if signal == "BEAR" else "NEUTRAL"
            cells.append(_cell("trend", tf, raw=signal.title(), direction=d,
                               status=_status(d, direction), confirmed_at=row["confirmed_at"],
                               version=ma.MA_VERSION,
                               values={"stack": signal, "position": row.get("position")}))
        else:
            cells.append(_cell("trend", tf, raw="—", status="MISSING",
                               version=ma.MA_VERSION,
                               missing_reason="No confirmed moving-average trend reading."))

        # Structure
        rows = idx.through(symbol, tf, "structure", structure.STRUCTURE_VERSION, as_of)
        row = _latest(rows, lambda r: r.get("event") in ("BOS", "CHOCH"))
        if row:
            d = row.get("direction", "NEUTRAL")
            arrow = "↑" if d == "BULL" else "↓" if d == "BEAR" else "Mixed"
            cells.append(_cell("structure", tf, raw=f"{arrow} {row.get('event')}",
                               direction=d, status=_status(d, direction),
                               confirmed_at=row["confirmed_at"],
                               version=structure.STRUCTURE_VERSION,
                               values={k: row.get(k) for k in ("event", "level", "close")}))
        else:
            cells.append(_cell("structure", tf, raw="—", status="MISSING",
                               version=structure.STRUCTURE_VERSION,
                               missing_reason="No confirmed structure break."))

        # Order block
        rows = (idx.through(symbol, tf, "order_block", ORDER_BLOCK_VERSION, as_of)
                if available("order_block", ORDER_BLOCK_VERSION) else [])
        primary = [r for r in rows if r.get("variant") == "LAST_OPPOSITE_BEFORE_BREAK"]
        wanted = "BULL" if direction == "LONG" else "BEAR" if direction == "SHORT" else None
        matched = [r for r in primary
                   if r.get("direction") == wanted and
                   _zone_overlap(r, setup_payload) is True]
        # Exposure asks whether ANY qualifying block existed at the cutoff. A
        # later opposed/non-overlapping block must not mask that observation.
        row = _latest(matched) or _latest(primary)
        if row:
            overlap = _zone_overlap(row, setup_payload) if setup_payload else None
            raw = "Aligned" if _status(row.get("direction"), direction) == "ALIGNED" else row.get("direction", "Block").title()
            if overlap is False:
                raw = "No overlap"
            overlap_unknown = bool(setup_payload.get("zone_id")) and overlap is None
            cells.append(_cell("order_block", tf, raw=raw,
                               direction=row.get("direction"),
                               status=("MISSING" if overlap_unknown else
                                       _status(row.get("direction"), direction)
                                       if overlap is not False else "NEUTRAL"),
                               confirmed_at=row["confirmed_at"],
                               version=ORDER_BLOCK_VERSION,
                               values={"bottom": row.get("bottom"), "top": row.get("top"),
                                       "variant": row.get("variant"), "overlaps_setup_zone": overlap,
                                       "break_ts": row.get("break_ts")},
                               missing_reason=("The originating 3.1 zone bounds are unavailable."
                                               if overlap_unknown else None)))
        else:
            is_available = available("order_block", ORDER_BLOCK_VERSION)
            cells.append(_cell("order_block", tf,
                               raw="None" if is_available else "—",
                               status="NEUTRAL" if is_available else "MISSING",
                               version=ORDER_BLOCK_VERSION,
                               missing_reason=("No order block was confirmed." if is_available
                                               else "Order-block collection is not active.")))

        # Ordered sequence
        rows = (idx.through(symbol, tf, "structure_sequence", STRUCTURE_SEQUENCE_VERSION, as_of)
                if available("structure_sequence", STRUCTURE_SEQUENCE_VERSION) else [])
        wanted_sequence = ("BULL" if direction == "LONG" else
                           "BEAR" if direction == "SHORT" else None)
        exposed_sequences = [r for r in rows if r.get("state") == "COMPLETE"
                             and r.get("direction") == wanted_sequence]
        control_sequences = [r for r in rows if r.get("state") in (
            "UNORDERED", "UNLINKED") and r.get("direction") == wanted_sequence]
        # A later partial/opposed event must not erase a qualifying causal
        # observation that was already available at the decision cutoff.
        row = (_latest(exposed_sequences) or _latest(control_sequences)
               or _latest(rows))
        if row:
            d = row.get("direction")
            state = row.get("state")
            cells.append(_cell("structure_sequence", tf,
                               raw={"COMPLETE": "Complete", "UNORDERED": "Unordered",
                                    "UNLINKED": "Unlinked"}.get(state, "Partial"),
                               direction=d,
                               status=_status(d, direction) if state == "COMPLETE" else "NEUTRAL",
                               confirmed_at=row["confirmed_at"],
                               version=STRUCTURE_SEQUENCE_VERSION,
                               values={k: row.get(k) for k in ("state", "sweep_ts", "break_ts", "block_ts", "block_id")}))
        else:
            is_available = available("structure_sequence", STRUCTURE_SEQUENCE_VERSION)
            cells.append(_cell("structure_sequence", tf,
                               raw="None" if is_available else "—",
                               status="NEUTRAL" if is_available else "MISSING",
                               version=STRUCTURE_SEQUENCE_VERSION,
                               missing_reason=("No linked sweep-break-block sequence." if is_available
                                               else "Structure-sequence collection is not active.")))

        # Regular divergence
        rows = idx.through(symbol, tf, "momentum", momentum.MOMENTUM_VERSION, as_of)
        row = _latest(rows, lambda r: r.get("event") == "DIVERGENCE")
        if row:
            d = row.get("direction")
            cells.append(_cell("rsi_divergence", tf,
                               raw=("Bullish" if d == "BULL" else "Bearish"),
                               direction=d, status=_status(d, direction),
                               confirmed_at=row["confirmed_at"], version=momentum.MOMENTUM_VERSION,
                               values={k: row.get(k) for k in ("rsi", "rsi_prev", "price", "price_prev", "prev_pivot_ts")}))
        else:
            cells.append(_cell("rsi_divergence", tf, raw="None", status="NEUTRAL",
                               version=momentum.MOMENTUM_VERSION,
                               missing_reason="No confirmed regular RSI divergence."))

        # Hidden divergence, only primary when recent enough.
        rows = (idx.through(symbol, tf, "hidden_divergence", HIDDEN_DIVERGENCE_VERSION, as_of)
                if available("hidden_divergence", HIDDEN_DIVERGENCE_VERSION) else [])
        row = _latest(rows)
        recent = row and as_of - row["confirmed_at"] <= HIDDEN_MAX_BARS * TF_SECONDS[tf]
        if recent:
            d = row.get("direction")
            cells.append(_cell("hidden_divergence", tf,
                               raw=("Bullish" if d == "BULL" else "Bearish"),
                               direction=d, status=_status(d, direction),
                               confirmed_at=row["confirmed_at"], version=HIDDEN_DIVERGENCE_VERSION,
                               values={k: row.get(k) for k in ("rsi", "rsi_prev", "price", "price_prev", "trend_stack", "prev_pivot_ts")}))
        else:
            is_available = available("hidden_divergence", HIDDEN_DIVERGENCE_VERSION)
            cells.append(_cell("hidden_divergence", tf,
                               raw="None" if is_available else "—",
                               status="NEUTRAL" if is_available else "MISSING",
                               version=HIDDEN_DIVERGENCE_VERSION,
                               missing_reason=("No trend-aligned hidden divergence within ten closed candles."
                                               if is_available else "Hidden-divergence collection is not active.")))

        # Stoch RSI: primary exit remains active for three closed candles.
        rows = (idx.through(symbol, tf, "stoch_rsi", STOCH_RSI_VERSION, as_of)
                if available("stoch_rsi", STOCH_RSI_VERSION) else [])
        row = _latest(rows)
        exits = [r for r in rows if r.get("event") in ("OVERSOLD_EXIT", "OVERBOUGHT_EXIT")
                 and as_of - r["confirmed_at"] <= PRIMARY_EXIT_BARS * TF_SECONDS[tf]]
        exit_row = _latest(exits)
        show = exit_row or row
        if show:
            d = exit_row.get("direction") if exit_row else show.get("direction", "NEUTRAL")
            raw = ({"OVERSOLD_EXIT": "Oversold exit", "OVERBOUGHT_EXIT": "Overbought exit",
                    "RISING": "Rising", "FALLING": "Falling",
                    "OVERSOLD": "Oversold", "OVERBOUGHT": "Overbought"}
                   .get(show.get("event"), "Neutral"))
            cells.append(_cell("stoch_rsi", tf, raw=raw, direction=d,
                               status=_status(d, direction) if exit_row else "NEUTRAL",
                               confirmed_at=show["confirmed_at"], version=STOCH_RSI_VERSION,
                               values={"k": show.get("k"), "d": show.get("d"),
                                       "event": show.get("event"),
                                       "primary_exit_within_bars": PRIMARY_EXIT_BARS if exit_row else None}))
        else:
            cells.append(_cell("stoch_rsi", tf, raw="—", status="MISSING",
                               version=STOCH_RSI_VERSION,
                               missing_reason=("Stoch RSI warmup or candle data is unavailable."
                                               if available("stoch_rsi", STOCH_RSI_VERSION)
                                               else "Stoch RSI collection is not active.")))

        # OI is a one-hour venue observation. It applies to 15m/1H only.
        if tf not in ("15m", "1H"):
            cells.append(_cell("open_interest", tf, raw="—", status="NOT_APPLICABLE",
                               version=OPEN_INTEREST_SIGNAL_VERSION, source_tf="1H",
                               missing_reason="Open-interest primary hypothesis is one hour only."))
        else:
            rows = (idx.through(symbol, "1H", "open_interest_signal",
                                OPEN_INTEREST_SIGNAL_VERSION, as_of)
                    if available("open_interest", OPEN_INTEREST_SIGNAL_VERSION) else [])
            row = _latest(rows)
            if row:
                stale = (now or as_of) - row["confirmed_at"] > OI_STALE_AFTER
                d = row.get("direction", "NEUTRAL")
                cells.append(_cell("open_interest", tf,
                                   raw="Stale" if stale else row.get("label", "Neutral"),
                                   direction=d, status="STALE" if stale else _status(d, direction),
                                   confirmed_at=row["confirmed_at"],
                                   version=OPEN_INTEREST_SIGNAL_VERSION, source_tf="1H",
                                   values={k: row.get(k) for k in ("value", "change_1h", "change_1h_pct", "price_change_1h_pct", "quadrant")}))
            else:
                venue = "phemex-perp" if symbol.endswith("USDT") else None
                cells.append(_cell("open_interest", tf, raw="—",
                                   status="MISSING" if venue else "NOT_APPLICABLE",
                                   version=OPEN_INTEREST_SIGNAL_VERSION, source_tf="1H",
                                   missing_reason=("No causal Phemex OI observation is available."
                                                   if venue else "Open interest is only collected for Phemex perpetuals.")))

    rows = []
    for key, label in FAMILIES:
        rows.append({"key": key, "label": label,
                     "cells": [c for c in cells if c["family"] == key]})
    gradeable = [c for c in cells if c["status"] != "NOT_APPLICABLE"]
    unavailable = sum(c["status"] == "MISSING" for c in gradeable)
    availability = ("UNAVAILABLE" if gradeable and unavailable == len(gradeable) else
                    "PARTIAL" if unavailable or any(c["status"] == "STALE" for c in gradeable)
                    else "AVAILABLE")
    return {"version": READ_MODEL_VERSION, "symbol": symbol, "as_of": int(as_of),
            "direction": direction, "timeframes": list(TIMEFRAMES), "rows": rows,
            "availability": availability,
            "affects_trading": False,
            "notice": "Research observation — did not affect this setup."}


def primary_exposure(matrix_payload: dict, setup_tf: str) -> dict[str, str]:
    """EXPOSED/CONTROL/MISSING for the five locked primary hypotheses."""
    cells = {(row["key"], cell["timeframe"]): cell
             for row in matrix_payload.get("rows", []) for cell in row.get("cells", [])}
    out = {}
    for family in HYPOTHESES:
        tf = "1H" if family == "open_interest" else setup_tf
        cell = cells.get((family, tf))
        if not cell or cell.get("status") in ("MISSING", "STALE", "NOT_APPLICABLE"):
            out[family] = "MISSING"
        elif cell.get("status") == "ALIGNED" and (
                family != "structure_sequence" or cell.get("raw") == "Complete"):
            out[family] = "EXPOSED"
        elif family == "structure_sequence" and (
                cell.get("raw") not in ("Unordered", "Unlinked") or
                cell.get("direction") != (
                    "BULL" if matrix_payload.get("direction") == "LONG" else
                    "BEAR" if matrix_payload.get("direction") == "SHORT" else None)):
            # The locked control is the same components in the wrong order or
            # without a causal link. Absence/partial detection is not a control.
            out[family] = "MISSING"
        else:
            out[family] = "CONTROL"
    return out


def _stability(exposed: list[tuple[int, float]], control: list[tuple[int, float]]) -> bool:
    combined = sorted([(t, 1, r) for t, r in exposed] + [(t, 0, r) for t, r in control])
    if len(combined) < 4:
        return False
    middle = combined[len(combined) // 2][0]
    signs = []
    for before in (True, False):
        hi = [r for t, flag, r in combined if flag and ((t <= middle) == before)]
        lo = [r for t, flag, r in combined if not flag and ((t <= middle) == before)]
        if not hi or not lo:
            return False
        signs.append((sum(hi) / len(hi)) - (sum(lo) / len(lo)))
    return signs[0] > 0 and signs[1] > 0


def sample_ready(exposed_count: int, control_count: int,
                 exposed_symbols: int, control_symbols: int) -> bool:
    """The locked two-sided grading floor, kept explicit for boundary tests."""
    return (exposed_count >= MIN_TRADES and control_count >= MIN_TRADES and
            exposed_symbols >= MIN_SYMBOLS and control_symbols >= MIN_SYMBOLS)


def _cluster_uplift_interval(exposed: list[dict], control: list[dict],
                             resamples: int = 5000) -> dict | None:
    """Deterministic 95% interval resampling whole symbol clusters."""
    groups = {"EXPOSED": {}, "CONTROL": {}}
    for name, rows in (("EXPOSED", exposed), ("CONTROL", control)):
        for row in rows:
            groups[name].setdefault(row["symbol"], []).append(float(row["r"]))
    symbols = sorted(set(groups["EXPOSED"]) | set(groups["CONTROL"]))
    if (len(groups["EXPOSED"]) < MIN_SYMBOLS or
            len(groups["CONTROL"]) < MIN_SYMBOLS or not symbols):
        return None
    state = 0x2545F4914F6CDD1D
    mask = (1 << 64) - 1
    values = []
    for _ in range(resamples):
        high, low = [], []
        for _ in range(len(symbols)):
            state = (state * 6364136223846793005 + 1442695040888963407) & mask
            symbol = symbols[(state >> 33) % len(symbols)]
            high.extend(groups["EXPOSED"].get(symbol, ()))
            low.extend(groups["CONTROL"].get(symbol, ()))
        if high and low:
            values.append(sum(high) / len(high) - sum(low) / len(low))
    if not values:
        return None
    values.sort()
    uplift = (sum(r["r"] for r in exposed) / len(exposed) -
              sum(r["r"] for r in control) / len(control))
    below = sum(1 for value in values if value <= 0) / len(values)
    above = sum(1 for value in values if value >= 0) / len(values)
    return {"uplift_r": uplift,
            "ci_lo": values[int(0.025 * len(values))],
            "ci_hi": values[min(len(values) - 1, int(0.975 * len(values)))],
            "p_value": min(1.0, 2 * min(below, above)),
            "resamples": len(values)}


def _bh_q_values(rows: list[dict]) -> None:
    """Benjamini-Hochberg correction for the detector-level hypotheses."""
    tested = sorted((row for row in rows if row.get("p_value") is not None),
                    key=lambda row: (row["p_value"], row["detector"]))
    total, next_q = len(tested), 1.0
    for rank in range(total, 0, -1):
        row = tested[rank - 1]
        q_value = min(next_q, row["p_value"] * total / rank)
        row["q_value"] = round(q_value, 6)
        next_q = q_value


def evidence_report(con) -> dict:
    """Closed-trade exposed/control report with both sample floors enforced."""
    candidates, warnings = factorstats.load_candidates(con)
    closed = [c for c in candidates if c.get("r") is not None]
    buckets = {family: {"EXPOSED": [], "CONTROL": [], "MISSING": []}
               for family in HYPOTHESES}
    # The setup-time observation is a durable snapshot. Reconstructing an old
    # setup from today's detector output would let a new deployment explain a
    # decision that predates it, even with an `as_of` filter.
    from . import researchsignals
    for candidate in closed:
        matrix_payload = researchsignals.for_setup(con, candidate["setup_id"])
        flags = (primary_exposure(matrix_payload, candidate["tf"])
                 if matrix_payload else {family: "MISSING" for family in HYPOTHESES})
        for family, flag in flags.items():
            buckets[family][flag].append({"r": float(candidate["r"]),
                                          "symbol": candidate["symbol"],
                                          "confirmed_at": candidate["confirmed_at"]})
    rows = []
    for family in HYPOTHESES:
        exposed, control, missing = (buckets[family][k] for k in ("EXPOSED", "CONTROL", "MISSING"))
        exp_symbols = len({r["symbol"] for r in exposed})
        ctl_symbols = len({r["symbol"] for r in control})
        sample_ok = sample_ready(
            len(exposed), len(control), exp_symbols, ctl_symbols)
        interval = _cluster_uplift_interval(exposed, control) if sample_ok else None
        stable = _stability([(r["confirmed_at"], r["r"]) for r in exposed],
                            [(r["confirmed_at"], r["r"]) for r in control]) if sample_ok else False
        row = {"detector": family, "label": dict(FAMILIES).get(family, family),
               "primary": True, "hypothesis": HYPOTHESES[family],
               "affects_trading": False, "used_in_trading": "No",
               "detector_version": DETECTOR_VERSIONS[family],
               "collection_start": collection_start(
                   con, family, DETECTOR_VERSIONS[family]),
               "exposed_count": len(exposed), "control_count": len(control),
               "exposed_symbol_clusters": exp_symbols,
               "control_symbol_clusters": ctl_symbols,
               "symbol_clusters": min(exp_symbols, ctl_symbols),
               "progress": {"trades_required_each": MIN_TRADES,
                            "symbols_required_each": MIN_SYMBOLS,
                            "exposed_trades": min(len(exposed), MIN_TRADES),
                            "control_trades": min(len(control), MIN_TRADES),
                            "exposed_symbols": min(exp_symbols, MIN_SYMBOLS),
                            "control_symbols": min(ctl_symbols, MIN_SYMBOLS)},
               "coverage": round((len(exposed) + len(control)) / len(closed), 4) if closed else 0,
               "missing_rate": round(len(missing) / len(closed), 4) if closed else 1,
               "uplift_r": round(interval["uplift_r"], 4) if interval else None,
               "ci_lo": round(interval["ci_lo"], 4) if interval else None,
               "ci_hi": round(interval["ci_hi"], 4) if interval else None,
               "p_value": round(interval["p_value"], 6) if interval else None,
               "q_value": None, "stable": stable, "sample_ok": sample_ok,
               "status": "MEASURED" if sample_ok else "UNKNOWN",
               "other_patterns_observed": [
                   {"label": name, "status": "EXPLORATORY_UNCOLLECTED",
                    "observation_count": 0, "may_be_proven": False,
                    "note": "Definition not locked; no observations collected."}
                   for name in EXPLORATORY[family]],
               "warnings": ([] if sample_ok else [
                   "Both exposed and control groups require 30 closed trades and 8 symbol clusters."])}
        rows.append(row)
    _bh_q_values(rows)
    for row in rows:
        row["passes_evidence"] = bool(
            row["sample_ok"] and row["stable"] and row["ci_lo"] is not None
            and row["ci_lo"] > 0 and row["q_value"] is not None and row["q_value"] <= 0.10)
        if row["collection_start"] is None:
            row["verdict"] = "Data unavailable"
        elif not row["exposed_count"] and not row["control_count"]:
            row["verdict"] = "Collecting evidence"
        elif row["passes_evidence"]:
            row["verdict"] = "Proven useful"
        elif not row["sample_ok"]:
            row["verdict"] = "Too few completed trades"
        elif row["uplift_r"] is not None and row["uplift_r"] > 0:
            row["verdict"] = "Promising, still unproven"
        else:
            row["verdict"] = "No reliable improvement"
    if all(row["collection_start"] is None for row in rows):
        verdict = "Data unavailable"
    elif all(not row["exposed_count"] and not row["control_count"] for row in rows):
        verdict = "Collecting evidence"
    elif all(not r["sample_ok"] for r in rows):
        verdict = "Too few completed trades"
    elif any(r["passes_evidence"] for r in rows):
        verdict = "Proven useful"
    elif any(r["verdict"] == "Promising, still unproven" for r in rows):
        verdict = "Promising, still unproven"
    else:
        verdict = "No reliable improvement"
    return {"version": EVIDENCE_VERSION, "verdict": verdict,
            "affects_trading": False, "minimums": {"closed_trades_each": MIN_TRADES,
                                                     "symbol_clusters_each": MIN_SYMBOLS},
            "closed_trades": len(closed), "rows": rows, "warnings": warnings}
