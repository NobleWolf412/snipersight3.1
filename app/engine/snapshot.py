"""Consistent point-in-time copies of the fact store.

Every measurement in this project is taken against a COPY, so that a replay
cannot write into the live store and a running scanner cannot move the ground
underneath a comparison. The copies were being made with `shutil.copy` after a
`PRAGMA wal_checkpoint(FULL)`, and that is wrong in a way that stays invisible
until it isn't:

  · the checkpoint is a point in time, the copy takes seconds, and the live
    scanner writes throughout — so the destination can contain pages from
    several inconsistent moments;
  · SQLite in WAL mode keeps recent commits in `-wal`, and a plain file copy
    of `.db` alone can miss or half-take them.

Observed 2026-07-30 on a 1.4 GB store: a copy taken this way failed
`PRAGMA quick_check` with hundreds of "Rowid out of order" errors on the facts
B-tree, and every engine run against it raised `database disk image is
malformed`. **The live store was `ok` on a full `integrity_check`** — the
corruption existed only in the copy, which is the failure mode that matters:
a measurement can be taken from a broken snapshot and look like a result.

`sqlite3.Connection.backup()` is the supported answer. It holds a read
transaction for the duration, copies pages under it, and restarts if a writer
changes something mid-copy — so the destination is a transactionally consistent
snapshot rather than a smear of several.

Cost: a few seconds more than a raw file copy, and worth every one of them.
"""
import sqlite3
from pathlib import Path


def snapshot(src, dst, *, verify: bool = True) -> Path:
    """Copy the store at `src` to `dst` as of one consistent instant.

    `verify` runs `quick_check` on the result and raises if it fails. It is on
    by default because the entire point of this module is that a bad copy must
    not be able to masquerade as data — silently returning a corrupt snapshot
    would be strictly worse than the `shutil.copy` it replaces, which at least
    failed loudly on first use.
    """
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    source = sqlite3.connect(str(src))
    try:
        target = sqlite3.connect(str(dst))
        try:
            # Pages are copied under a read transaction that the backup API
            # restarts if a writer intervenes, which is the whole guarantee.
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()

    if verify:
        con = sqlite3.connect(str(dst))
        try:
            result = con.execute("PRAGMA quick_check").fetchone()[0]
        finally:
            con.close()
        if result != "ok":
            raise RuntimeError(
                f"snapshot of {src} failed integrity check: {result[:200]}. "
                f"The copy is unusable — do NOT measure against it.")
    return dst
