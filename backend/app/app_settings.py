"""Settings an Admin changes in the app (Stage 9B), kept in the app_settings table as JSON.

  security     the sensitive-information scanner switches, extra classification words, sign-out after
               inactivity, lock after N wrong passwords (see policy() below)
  letterhead   office name and logo printed on every exported file (app/routes/branding.py)
  counters     how many "Is this real?" checks found genuine / changed / fake messages (numbers only)
  speed_test   the last AI speed test

Values are read often (every scan, every request's session check), so they are kept in memory and
read again only after a change.
"""

import copy
import threading

from app.db import AppSetting, SessionLocal, utc_now

_cache: dict[str, dict] = {}
_lock = threading.Lock()

# Which scanner checks can be switched off, and the kinds of finding each covers (scanner.KINDS).
# Attack indicators and the built-in classification words are always on.
SCANNER_SWITCHES = {
    "aadhaar": ("Aadhaar numbers", ["aadhaar"]),
    "pan": ("PAN numbers", ["pan"]),
    "phone": ("Phone numbers", ["phone"]),
    "email": ("Email addresses", ["email"]),
    "bank": ("Bank account and IFSC", ["bank_account", "ifsc"]),
    "passport": ("Passport numbers", ["passport"]),
    "vehicle": ("Vehicle numbers", ["vehicle"]),
    "gps": ("GPS locations", ["gps"]),
    "internal_ip": ("Internal IP addresses and hosts", ["private_ip", "internal_host"]),
    "secrets": ("Passwords and keys", ["password", "api_key", "token", "private_key"]),
}
IDLE_CHOICES = [15, 30, 60]       # minutes without activity before signing out
LOCK_CHOICES = [3, 5, 10]         # wrong passwords in a row before the account is locked
DEFAULTS = {
    "security": {"scanner": {key: True for key in SCANNER_SWITCHES}, "classification_words": [],
                 "idle_minutes": 30, "lock_after": 5},
    "letterhead": {"office_name": "", "has_logo": False},
    "counters": {"checks": 0, "genuine": 0, "changed": 0, "scam": 0, "withdrawn": 0, "not_found": 0},
    "speed_test": {},
    "public_page": {"last_export": None},
}


def get(key: str) -> dict:
    """The setting, with defaults for anything not saved yet (a copy: change it with put())."""
    with _lock:
        if key not in _cache:
            with SessionLocal() as db:
                row = db.get(AppSetting, key)
                saved = dict(row.value) if row is not None and row.value else {}
            _cache[key] = _merge(DEFAULTS.get(key, {}), saved)
        return copy.deepcopy(_cache[key])


def put(key: str, value: dict, by=None) -> dict:
    with _lock, SessionLocal() as db:
        row = db.get(AppSetting, key)
        if row is None:
            row = AppSetting(key=key)
            db.add(row)
        row.value, row.updated_at, row.updated_by = copy.deepcopy(value), utc_now(), getattr(by, "id", None)
        db.commit()
        _cache.pop(key, None)
    return get(key)


def bump(key: str, *names: str) -> None:
    """Add 1 to counters (e.g. bump("counters", "checks", "scam"))."""
    value = get(key)
    for name in names:
        value[name] = int(value.get(name, 0)) + 1
    put(key, value)


def forget_cache() -> None:
    """For tests that change the table directly."""
    with _lock:
        _cache.clear()


def _merge(defaults: dict, saved: dict) -> dict:
    merged = copy.deepcopy(defaults)
    for name, value in saved.items():
        if isinstance(value, dict) and isinstance(merged.get(name), dict):
            merged[name] = _merge(merged[name], value)
        else:
            merged[name] = value
    return merged


# ---- the security policy, as the rest of the app reads it -------------------------------------------


def policy() -> dict:
    return get("security")


def disabled_kinds() -> set[str]:
    switches = policy()["scanner"]
    return {kind for key, (_, kinds) in SCANNER_SWITCHES.items() if not switches.get(key, True) for kind in kinds}


def idle_minutes() -> int:
    return int(policy()["idle_minutes"])


def lock_after() -> int:
    return int(policy()["lock_after"])
