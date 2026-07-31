"""API credential storage — Windows DPAPI, write-only from the app's view.

Design constraints, stated because they are the whole point of this module:

  · Secrets are encrypted by **DPAPI** (`CryptProtectData`), which ties the
    ciphertext to the current Windows user account. Another account on the same
    machine cannot decrypt it, and the plaintext never touches disk.
  · Nothing here ever RETURNS a secret to a caller that could surface it. The
    read path exists only for a future signed-request layer; the API exposes
    `has_secret`, never the value.
  · Secrets never enter the fact store, the engine log, or git. The vault file
    lives beside the database in `data/` and is excluded from version control.
  · Claude never enters, reads, or transports the operator's keys. The operator
    types them into their own machine; this module encrypts what it is handed.

Live order submission remains locked regardless of whether a key is stored — a
credential existing is not permission to trade. That gate is `live_enabled` in
`/api/trade-config`, and it is earned by forward evidence, not by configuration.
"""
import ctypes
import ctypes.wintypes as wt
import json
import os
from pathlib import Path

from . import venues as _venues

VAULT = Path(__file__).resolve().parents[1] / "data" / "credentials.vault"
# Only these may be stored. An open-ended store invites secrets nobody audits.
FIELDS = ("api_key", "api_secret", "passphrase")
# DERIVED from `venues.ALL`, not typed here. This list was `("coinbase-spot",
# "phemex-perp")` while `venues.py` had already declared a third venue, so
# `/api/trade-config` offered kraken-perp and `store_secret` raised "unknown
# venue" for it — a venue the operator could select but could never hold keys
# for. `venues.py` says it plainly: "Adding a venue means adding a descriptor
# here plus an adapter module. Nothing else in the engine should branch on venue
# by name." A second hand-maintained list is exactly the branch it warns about,
# and deriving it means adding a venue can never again half-arrive.
VENUES = tuple(v.key for v in _venues.ALL)


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes) -> _Blob:
    buf = ctypes.create_string_buffer(data, len(data))
    return _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))


def _out_bytes(blob: _Blob) -> bytes:
    out = ctypes.string_at(blob.pbData, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return out


def available() -> bool:
    return os.name == "nt" and hasattr(ctypes, "windll")


def _protect(plaintext: str) -> bytes:
    out = _Blob()
    if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(_blob(plaintext.encode())), None, None, None, None, 0,
            ctypes.byref(out)):
        raise OSError("CryptProtectData failed")
    return _out_bytes(out)


def _unprotect(ciphertext: bytes) -> str:
    out = _Blob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(_blob(ciphertext)), None, None, None, None, 0,
            ctypes.byref(out)):
        raise OSError("CryptUnprotectData failed")
    return _out_bytes(out).decode()


def _load() -> dict:
    if not VAULT.exists():
        return {}
    try:
        return json.loads(VAULT.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    VAULT.write_text(json.dumps(data), encoding="utf-8")
    if os.name == "nt":                      # owner-only where the OS allows it
        try:
            os.chmod(VAULT, 0o600)
        except OSError:
            pass


def store_secret(venue: str, field: str, value: str) -> None:
    """Encrypt and persist one credential field. The value is never logged."""
    if venue not in VENUES:
        raise ValueError(f"unknown venue {venue!r}")
    if field not in FIELDS:
        raise ValueError(f"unknown field {field!r}")
    if not value or not value.strip():
        raise ValueError("empty value")
    if not available():
        raise OSError("DPAPI unavailable on this platform")
    data = _load()
    data.setdefault(venue, {})[field] = _protect(value).hex()
    _save(data)


def clear(venue: str, field: str | None = None) -> None:
    data = _load()
    if venue in data:
        if field is None:
            data.pop(venue)
        else:
            data[venue].pop(field, None)
        _save(data)


def status() -> dict:
    """What EXISTS, never what it is. This is the only shape the API may return."""
    data = _load()
    return {v: {f: bool(data.get(v, {}).get(f)) for f in FIELDS} for v in VENUES}


def read_secret(venue: str, field: str) -> str | None:
    """Decrypt for in-process use only.

    Deliberately NOT reachable from any HTTP route. A signed-request layer would
    call this directly; exposing it over the wire would defeat the vault.
    """
    enc = _load().get(venue, {}).get(field)
    if not enc:
        return None
    return _unprotect(bytes.fromhex(enc))
