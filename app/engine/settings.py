"""Operator settings — editable at runtime, audited, and honest about cost.

The tension this module resolves: the whole system is built on versioned,
deterministic engine behaviour (§4/§7), but the operator legitimately wants to
change things without editing code. Those two only coexist if a change is
RECORDED and its effect on the forward record is stated rather than hidden.

Two classes of setting, and the distinction is the whole point:

  · PREFERENCE — changes what the operator sees or does on one trade. No engine
    behaviour changes, no fact differs. Free to change. (per-trade risk override
    lives in the ticket, not here.)

  · OPERATIONAL — pauses or resumes activity without changing how anything is
    evaluated. Audited, but it must NOT reset the baseline: halting is something
    you do to stay safe, and a halt that destroyed your forward evidence would
    punish exactly the caution it exists to allow.

  · BEHAVIOURAL — changes what the engines produce or what the risk authority
    decides. Changing one mid-window would mix two configurations inside a
    single forward record, which makes the record unreadable: you could not say
    which config produced which result. So a behavioural change AUTOMATICALLY
    starts a new baseline, and says so before you confirm.

That is the same reasoning that made a global risk-per-trade edit unsafe — and
why per-trade override was built instead. This module never silently rewrites
history; the old baseline and every fact under it are retained.
"""
import json
import time

SETTINGS_VERSION = "settings-v0.1-draft"

# name -> (class, type, default, description)
SPEC = {
    "enable_perps": ("BEHAVIOURAL", bool, True,
                     "Rank Phemex perps alongside Coinbase spot. Off = spot only, "
                     "which means longs only and ~1% round-trip fees."),
    "top_n": ("BEHAVIOURAL", int, 20,
              "How many symbols the universe admits, by 24h volume."),
    "min_volume_usd": ("BEHAVIOURAL", int, 3_000_000,
                       "Liquidity floor. Structural stops do not fill on thin books."),
    "strategy_pullback": ("BEHAVIOURAL", bool, True, "Trade PULLBACK setups."),
    "strategy_reversal": ("BEHAVIOURAL", bool, True, "Trade REVERSAL setups."),
    "strategy_scale_in": ("BEHAVIOURAL", bool, True, "Allow SCALE_IN adds."),
    # OPERATIONAL, deliberately: halting stops new entries but changes no rule.
    # Classing it BEHAVIOURAL reset the forward baseline on every halt/resume,
    # which would have made the safety control destroy the evidence it protects.
    # Safety gates are OPERATIONAL for the same reason `halted` is: they change
    # WHEN trading stops, not what counts as a valid trade. Classing them
    # BEHAVIOURAL would reset the forward record every time the operator
    # tightened a guardrail — penalising caution.
    "max_drawdown_pct": ("OPERATIONAL", float, 20.0,
                         "Halt all new entries if equity falls this far below "
                         "its peak. The guardrail that outlives a bad streak."),
    "halt_on_data_blocked": ("OPERATIONAL", bool, True,
                             "Refuse new entries while the pipeline audit is "
                             "BLOCKED. Trading on data known to be broken "
                             "produces a record that proves nothing."),
    "halted": ("OPERATIONAL", bool, False,
               "Operator halt. No new entries are sized while set. Open "
               "positions still settle — refusing to close is not safety."),
}

BEHAVIOURAL = {k for k, v in SPEC.items() if v[0] == "BEHAVIOURAL"}
OPERATIONAL = {k for k, v in SPEC.items() if v[0] == "OPERATIONAL"}


def _ensure(con):
    con.execute("""CREATE TABLE IF NOT EXISTS settings (
        name TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at INTEGER NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS settings_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, old_value TEXT, new_value TEXT NOT NULL,
        changed_at INTEGER NOT NULL, baseline_id INTEGER, note TEXT)""")


def defaults() -> dict:
    return {k: v[2] for k, v in SPEC.items()}


def _coerce(name, raw):
    typ = SPEC[name][1]
    if typ is bool:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    return typ(raw)


def all_settings(con) -> dict:
    """Current values, defaults filled in for anything never set."""
    _ensure(con)
    out = defaults()
    for name, value in con.execute("SELECT name, value FROM settings").fetchall():
        if name in SPEC:
            try:
                out[name] = _coerce(name, json.loads(value))
            except Exception:
                pass                      # a corrupt row falls back to default
    return out


def get(con, name):
    return all_settings(con)[name]


def describe() -> list[dict]:
    return [{"name": k, "class": v[0], "type": v[1].__name__,
             "default": v[2], "description": v[3]} for k, v in SPEC.items()]


def set_many(con, changes: dict, note: str = "") -> dict:
    """Apply settings. Returns what changed and whether a new baseline started.

    A BEHAVIOURAL change starts a new forward baseline, because a record that
    spans two configurations cannot tell you which one produced which result.
    Nothing is deleted — the previous baseline and all its facts are retained.
    """
    from . import store
    _ensure(con)
    unknown = [k for k in changes if k not in SPEC]
    if unknown:
        raise ValueError(f"unknown setting(s): {unknown}")

    current = all_settings(con)
    applied, behavioural = {}, []
    now = int(time.time())
    for name, raw in changes.items():
        value = _coerce(name, raw)
        if value == current[name]:
            continue                      # no-op: never log a change that isn't one
        con.execute(
            "INSERT INTO settings (name, value, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(name) DO UPDATE SET value=excluded.value, "
            "updated_at=excluded.updated_at",
            (name, json.dumps(value), now))
        con.execute(
            "INSERT INTO settings_log (name, old_value, new_value, changed_at, note) "
            "VALUES (?,?,?,?,?)",
            (name, json.dumps(current[name]), json.dumps(value), now, note))
        applied[name] = {"from": current[name], "to": value}
        if name in BEHAVIOURAL:
            behavioural.append(name)

    baseline = None
    if behavioural:
        from . import setups, execsim, risk
        baseline = store.start_baseline(
            con,
            label=f"config change: {', '.join(sorted(behavioural))}",
            strategy_version=setups.SETUP_VERSION,
            execution_version=execsim.EXEC_VERSION,
            risk_version=risk.RISK_VERSION)
        con.execute("UPDATE settings_log SET baseline_id=? WHERE changed_at=?",
                    (baseline["id"], now))
    con.commit()
    return {"applied": applied, "behavioural": behavioural, "baseline": baseline}


def history(con, limit: int = 50) -> list[dict]:
    _ensure(con)
    rows = con.execute(
        "SELECT name, old_value, new_value, changed_at, baseline_id, note "
        "FROM settings_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [{"name": r[0], "from": json.loads(r[1]) if r[1] else None,
             "to": json.loads(r[2]), "at": r[3], "baseline_id": r[4],
             "note": r[5]} for r in rows]
