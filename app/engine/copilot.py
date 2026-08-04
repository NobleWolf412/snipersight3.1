"""Claude copilot bridge — an ANALYST over the fact store, never an actor.

## What this is

The operator feeds a setup (or just a chart) into a chat and gets analysis
grounded in the same facts the engine decided on: the trace, the draft and its
basis, regime weather, venue costs, and the honest state of the book. The
model is invoked through the LOCAL `claude` CLI in print mode, so it runs on
the operator's Claude subscription — the same login as their coding sessions —
not on a pay-per-token API key. `total_cost_usd` in the CLI envelope is
informational; subscription auth bills quota, not dollars.

## Boundaries, all deliberate

  · OBSERVER ONLY. Same constitution rule the Apex bridge states: nothing
    here can arm, size, or edit anything. The endpoint returns prose; the Arm
    button stays human. Even "apply to ticket" is refused as a feature —
    the moment the copilot can touch the ticket, the manual book stops
    meaning "the operator's judgement".
  · NOTHING IT SAYS ENTERS THE STORE. No facts, no version, no consumers.
    It is an opinion layer, and the UI labels it as one.
  · TOOLS DISABLED in the spawned session (belt: --disallowedTools; braces:
    the system preamble forbids them; suspenders: cwd is an empty scratch
    dir, so file tools would find nothing). A chat box must not be a shell.
  · FACT-CITED OR SILENT. The preamble requires grounding in the pack and
    forbids inventing indicators the engine does not compute — there is no
    RSI anywhere in this system, so the copilot may not conjure one.

## Sessions

`claude -p` returns a session_id; passing it back with --resume continues the
conversation with full context server-side, so the pack is sent ONCE per
conversation rather than per message. The UI holds the id per context.
"""
import json
import shutil
import subprocess
from decimal import Decimal
from pathlib import Path

from . import store, venues, draft as draft_mod, manual
from .setups import SETUP_VERSION
from .regime import REGIME_VERSION
from .risk import RISK_VERSION

#: Where the spawned CLI runs. Empty on purpose — no CLAUDE.md, no repo, so
#: even a tool call that slipped every other guard would find bare floor.
CWD = Path(__file__).resolve().parents[1] / "data" / "copilot-cwd"

TIMEOUT_S = 180
DEFAULT_MODEL = "sonnet"
ALLOWED_MODELS = ("sonnet", "haiku", "opus")

#: Tool names denied outright. The preamble also forbids tool use; this makes
#: the refusal structural rather than behavioural.
DENY_TOOLS = ("Bash", "Edit", "Write", "NotebookEdit", "Read", "Glob", "Grep",
              "WebFetch", "WebSearch", "Task", "Agent", "TodoWrite")

PREAMBLE = """You are the SniperSight copilot: a trading ANALYST embedded in a
deterministic market-structure research platform. You are an observer. You
cannot place, arm, size, or modify trades, and you must never imply you did.

Ground rules, non-negotiable:
- Base every claim on the FACT PACK provided in this conversation. Cite which
  fact you used in plain words ("the confirming bar closed on 1.56x volume").
- If the pack does not contain what you need, say so plainly. Never invent
  data. This system computes zones, structure breaks, regime, liquidity pools,
  volume expansion and costs — it does NOT compute RSI, MACD, moving-average
  crossovers or any indicator not in the pack, so never reference those as if
  it did.
- Always weigh the trade AGAINST the recorded edge state in the pack. If no
  strategy clears zero, an individual setup inherits that uncertainty and you
  must say so rather than radiating confidence.
- Costs are real: cite the venue's round-trip fees and funding when relevant.
- Be concise and direct. A trader is reading this between bars. Lead with the
  verdict-shaped summary, then the reasoning. No headers, no bullet spam —
  short paragraphs.
- Do not use any tools. Reply with text only.
- Never present yourself as certain about the future. You assess evidence."""


def _fmt_pct(x) -> str:
    return f"{float(x) * 100:.3f}%"


def _latest_regimes(con, symbol: str) -> list[str]:
    out = []
    for tf in ("15m", "1H", "4H", "1D", "1W"):
        r = con.execute(
            "SELECT payload FROM facts WHERE symbol=? AND tf=? AND kind='regime' "
            "AND algo_version=? ORDER BY confirmed_at DESC LIMIT 1",
            (symbol, tf, REGIME_VERSION)).fetchone()
        if r:
            out.append(f"{tf}: {json.loads(r[0]).get('regime', '?')}")
    return out


def _setup_block(con, symbol: str, tf: str, setup_id: str | None) -> str:
    """The engine setup under discussion, plus its risk verdict — if any."""
    q = ("SELECT payload FROM facts WHERE symbol=? AND tf=? AND kind='setup' "
         "AND algo_version=? ")
    args = [symbol, tf, SETUP_VERSION]
    if setup_id:
        q += "AND json_extract(payload,'$.setup_id')=? "
        args.append(setup_id)
    q += "ORDER BY confirmed_at DESC LIMIT 1"
    r = con.execute(q, args).fetchone()
    if not r:
        return "No engine setup exists on this chart at the current version."
    p = json.loads(r[0])
    lines = [f"Engine setup {p.get('setup_id', '')}:",
             f"  state={p.get('state')} direction={p.get('direction')} "
             f"strategy={p.get('strategy')}",
             f"  entry={p.get('entry')} tp={p.get('tp')} sl={p.get('sl')} "
             f"rr={p.get('rr')} rank={p.get('rank')}",
             f"  why: {p.get('why', '—')}"]
    conf = p.get("confluence") or {}
    if conf:
        keep = {k: conf[k] for k in ("htf_regime", "htf_state", "volume_expansion",
                                     "zone_strength", "zone_quality",
                                     "premium_discount", "sweep_nearby")
                if k in conf}
        lines.append("  confluence: " + json.dumps(keep))
    d = con.execute(
        "SELECT payload FROM facts WHERE symbol=? AND kind='risk' AND algo_version=? "
        "AND json_extract(payload,'$.setup_id')=? "
        "AND json_extract(payload,'$.event')='DECISION' ORDER BY id DESC LIMIT 1",
        (symbol, RISK_VERSION, p.get("setup_id"))).fetchone()
    if d:
        dp = json.loads(d[0])
        lines.append(f"  risk authority: {dp.get('decision')} "
                     f"{dp.get('reasons') or ''} risk_usd={dp.get('risk_usd')}")
    return "\n".join(lines)


def build_pack(con, symbol: str, tf: str, setup_id: str | None = None) -> str:
    """Everything the analyst may ground itself in, compact and labelled.

    Assembled fresh per conversation. Deliberately TEXT, not JSON: the reader
    is a language model, and labelled prose with numbers survives summarising
    far better than nested braces.
    """
    v = venues.venue_for(symbol)
    parts = [
        f"FACT PACK — {symbol} {tf}, assembled from the SniperSight fact store.",
        "",
        f"VENUE: {v.key} ({v.kind}); shorts {'allowed' if v.allow_shorts else 'not possible'}; "
        f"max leverage {v.max_leverage}x. ROUND-TRIP FEE: "
        f"{_fmt_pct(venues.round_trip_cost_rate(symbol))} of notional — the "
        f"house model, maker entry {_fmt_pct(v.maker_rate)} + taker exit "
        f"{_fmt_pct(v.taker_rate)}; quote THIS as the round trip, not taker x2 "
        f"(taker both sides would be {_fmt_pct(v.taker_rate * 2)}, the "
        f"worst case, and worth naming only as that). Funding "
        f"{v.funding_settlements_per_day}x/day accrues while a perp is held.",
        "",
        "REGIME BY TIMEFRAME: " + ("; ".join(_latest_regimes(con, symbol)) or "none recorded"),
        "",
        _setup_block(con, symbol, tf, setup_id),
    ]
    dr = draft_mod.for_symbol(con, symbol, tf)
    if dr:
        parts += ["", f"STRUCTURE DRAFT (not an engine setup — a starting point "
                      f"anchored to live structure): {dr['direction']} "
                      f"entry={dr['entry']} sl={dr['sl']} tp={dr['tp']} "
                      f"({dr['distance_atr']} ATR from price). Basis: "
                      + "; ".join(dr["basis"])]
    else:
        parts += ["", "STRUCTURE DRAFT: none — price is not within 3 ATR of any "
                      "live zone the engine recognises."]
    try:
        from .importer import TF_SECONDS
        open_pos = manual.status(con, symbol, tf, TF_SECONDS[tf])
        if open_pos:
            p0 = open_pos[0]
            parts += ["", f"OPERATOR'S OPEN TRADE HERE: {p0['direction']} "
                          f"state={p0['state']} entry={p0.get('fill_price', p0['entry'])} "
                          f"sl={p0.get('current_stop', p0['sl'])} tp={p0['tp']} "
                          f"unrealized={p0.get('unrealized_r', '—')}R "
                          f"(marked to last CLOSED bar)"]
    except Exception:
        pass
    b = manual.book(con)
    parts += ["", f"OPERATOR'S MANUAL BOOK: {b['n']} settled, "
                  f"{len(b['open_intents'])} open, total {b['total_r']}R, "
                  f"win rate {b['win_rate'] if b['win_rate'] is not None else '—'}%.",
              "",
              "EDGE STATE, and this frames everything: on the honest simulator "
              "NO strategy currently clears zero. REVERSAL sits near +0.15R "
              "with a 95% CI spanning zero; PULLBACK is negative; breakout "
              "measured indistinguishable from zero. Two earlier apparent "
              "edges were audit artifacts (fabricated fills, a tick-floor "
              "bug). Treat every setup as unproven-edge, costs-are-certain.",
              "",
              "The operator decides. You analyse."]
    return "\n".join(parts)


def _cli() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("the `claude` CLI is not on PATH — the copilot "
                           "needs the operator's Claude Code install")
    return exe


def build_diag_pack(con) -> str:
    """Everything a code-diagnosis turn may ground itself in.

    The chart pack answers "is this trade worth taking"; this one answers
    "why is the machine failing" — engine faults (current state), data gates,
    the latest quality verdict, and the tail of the engine log. Same format
    discipline as build_pack: labelled prose, because the reader is a model.
    """
    from pathlib import Path
    parts = ["DIAGNOSTIC PACK — assembled from the SniperSight fact store "
             "and runtime state.", ""]
    faults = con.execute(
        "SELECT symbol, tf, engine, error, first_seen, times FROM engine_faults "
        "ORDER BY last_seen DESC LIMIT 20").fetchall()
    parts.append("ENGINE FAULTS (current state; a clean run clears a row):")
    parts += [f"  {r[2]} on {r[0]} {r[1]} — {r[3]} (seen {r[5]}x)"
              for r in faults] or ["  none"]
    gates = con.execute(
        "SELECT symbol, tf, gate, detail FROM pipeline_gates "
        "ORDER BY measured_at LIMIT 20").fetchall()
    parts.append("")
    parts.append("DATA GATES (symbols the engines are not fully running on):")
    parts += [f"  {r[0]} {r[1]}: {r[2]} — {r[3]}" for r in gates] or ["  none"]
    q = con.execute("SELECT status, summary FROM quality_runs "
                    "ORDER BY observed_at DESC LIMIT 1").fetchone()
    parts.append("")
    parts.append(f"LATEST QUALITY AUDIT: {q[0]} — {q[1][:400]}" if q
                 else "LATEST QUALITY AUDIT: none recorded")
    log_path = Path(__file__).resolve().parent.parent / "data" / "engine.log"
    try:
        tail = log_path.read_text(encoding="utf-8", errors="replace")
        lines = [l for l in tail.splitlines() if l.strip()][-40:]
        parts += ["", "ENGINE LOG (last 40 lines):"] + [f"  {l}" for l in lines]
    except OSError:
        parts += ["", "ENGINE LOG: unavailable"]
    parts += ["", "The codebase lives in app/ — engines in app/engine/, one "
              "per module, run by pipeline.run_symbol. Answer as a debugging "
              "partner: name the likely failing module and the next check."]
    return chr(10).join(parts)


def ask(message: str, pack: str | None = None, session_id: str | None = None,
        model: str = DEFAULT_MODEL) -> dict:
    """One turn against the operator's Claude subscription via `claude -p`.

    First turn: PREAMBLE via --append-system-prompt, pack + question as the
    prompt. Resumed turns: the message alone — the session already holds the
    pack, so quota is spent once per conversation, not once per message.
    """
    if model not in ALLOWED_MODELS:
        model = DEFAULT_MODEL
    CWD.mkdir(parents=True, exist_ok=True)
    args = [_cli(), "-p", "--output-format", "json", "--model", model,
            "--disallowedTools", ",".join(DENY_TOOLS)]
    if session_id:
        args += ["--resume", session_id]
        prompt = message
    else:
        args += ["--append-system-prompt", PREAMBLE]
        prompt = (pack or "") + "\n\n---\nOPERATOR ASKS: " + message
    try:
        r = subprocess.run(args, input=prompt, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=TIMEOUT_S, cwd=str(CWD))
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"copilot timed out after {TIMEOUT_S}s"}
    if r.returncode != 0:
        return {"ok": False,
                "error": (r.stderr or r.stdout or "claude CLI failed").strip()[:500]}
    try:
        env = json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"ok": False, "error": "unparseable CLI output: " + r.stdout[:300]}
    if env.get("is_error"):
        return {"ok": False, "error": str(env.get("result"))[:500],
                "session_id": env.get("session_id")}
    return {"ok": True, "reply": env.get("result", ""),
            "session_id": env.get("session_id"),
            "model": model,
            "duration_ms": env.get("duration_ms")}
