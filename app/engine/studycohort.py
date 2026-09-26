"""Start a forward study's next cohort without losing the one before it.

A forward study freezes the rules it was started under and pauses when an
input moves, because its record is evidence about those rules. Pausing is
correct for a drift nobody declared. A deliberate bump of the study's OWN
version is different: it is the declaration that a new cohort should start.
Until 2026-09-26 nothing honoured it. Activation was `INSERT OR IGNORE` into a
one-row config, so the breakout trial, the stop comparison and the zone
comparison all sat PAUSED on their 2026-09-15 configs after the exec-v0.30
fill-pricing change, and would have stayed there forever.

The old cohort is renamed, never deleted: `stop_study_events` becomes
`stop_study_events__stop_study_v0_1_draft`, rows and ids intact, and the new
config records where it went. Nothing reads the archive at runtime, so an
archived trade no longer pins its market's candles. That is intended: a
paused cohort was never going to settle again.
"""
import json
import re


def _archive_name(con, table, version):
    base = f"{table}__{re.sub(r'[^a-z0-9]+', '_', version.lower()).strip('_')}"
    name, n = base, 2
    while con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone():
        name, n = f"{base}_{n}", n+1
    return name


def stored_version(con, table):
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (table,)).fetchone():
        return None
    row = con.execute(f"SELECT payload FROM {table} WHERE id=1").fetchone()
    return json.loads(row[0]).get("version") if row else None


def archive_if_superseded(con, table, companions, version):
    """Caller holds the write transaction. Returns the archived cohort, or None.

    Only a different stored `version` starts a new cohort; dependency drift
    under the same version keeps pausing, which is the visible signal that
    someone moved an input without bumping the study.
    """
    old = stored_version(con, table)
    if old is None or old == version:
        return None
    config = json.loads(con.execute(f"SELECT payload FROM {table} WHERE id=1").fetchone()[0])
    archived = {}
    for name in (table, *companions):
        if con.execute("SELECT 1 FROM sqlite_master WHERE name=?", (name,)).fetchone():
            archived[name] = _archive_name(con, name, old)
            con.execute(f"ALTER TABLE {name} RENAME TO {archived[name]}")
    return {"version": old, "started_at": config.get("started_at"), "archived_as": archived}
