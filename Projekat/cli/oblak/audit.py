"""
oblak/audit.py
───────────────
Revizijski (audit) log za sve akcije CLI-ja.

Format: JSON Lines (jedan JSON objekat po liniji) u ~/.oblak/audit.log
Svaki unos sadrži: timestamp (UTC), akciju, korisnika (iz tokena), 
detalje i rezultat (success/failure).

Ovaj log je read-only za ostale korisnike (chmod 600).
Server-side audit log je odvojen i upravljan od strane Člana 2.
"""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── Lokacija audit loga ───────────────────────────────────────────────────────
_OBLAK_DIR = Path.home() / ".oblak"
_AUDIT_FILE = _OBLAK_DIR / "audit.log"

# ── Poznate akcije (enumerišemo umesto slobodnog stringa) ─────────────────────
class Action:
    LOGIN_ATTEMPT   = "LOGIN_ATTEMPT"
    LOGIN_SUCCESS   = "LOGIN_SUCCESS"
    LOGIN_FAILURE   = "LOGIN_FAILURE"
    LOGOUT          = "LOGOUT"
    DEPLOY_START    = "DEPLOY_START"
    DEPLOY_SUCCESS  = "DEPLOY_SUCCESS"
    DEPLOY_FAILURE  = "DEPLOY_FAILURE"
    INVOKE          = "INVOKE"
    INVOKE_FAILURE  = "INVOKE_FAILURE"
    STATUS_CHECK    = "STATUS_CHECK"
    TOKEN_REFRESH   = "TOKEN_REFRESH"


# ── Public API ────────────────────────────────────────────────────────────────

def log(
    action: str,
    details: dict[str, Any] | None = None,
    outcome: str = "success",
    username: str | None = None,
) -> None:
    """
    Upisuje jedan audit unos u ~/.oblak/audit.log

    Parametri
    ---------
    action   : jedna od Action.* konstanti
    details  : opcioni rečnik sa kontekstom (nikad ne sadrži lozinku/token)
    outcome  : "success" | "failure" | "error"
    username : korisničko ime; ako nije prosleđeno, pokušava se čitanje iz tokena
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action":    action,
        "outcome":   outcome,
        "username":  username or _extract_username(),
        "details":   details or {},
    }

    _write(entry)


# ── Private helpers ───────────────────────────────────────────────────────────

def _extract_username() -> str:
    """
    Čita username iz lokalnog JWT tokena (bez verifikacije potpisa –
    ovo je samo za lokalni audit log).
    """
    try:
        from oblak.auth import token_store
        token = token_store.load_token()
        return _decode_jwt_payload(token).get("sub", "unknown")
    except Exception:
        return "unauthenticated"


def _decode_jwt_payload(token: str) -> dict:
    """
    Dekoduje payload deo JWT-a bez verifikacije potpisa.
    Koristi se SAMO za čitanje 'sub' (username) za audit svrhe.
    """
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        return {}

    # Base64url decode (dodaj padding ako treba)
    payload_b64 = parts[1] + "=="
    try:
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        return json.loads(payload_bytes)
    except Exception:
        return {}


def _write(entry: dict) -> None:
    """Atomično dodaje jedan JSON red u audit log fajl."""
    try:
        _OBLAK_DIR.mkdir(exist_ok=True)
        line = json.dumps(entry, ensure_ascii=False) + "\n"

        with open(_AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(line)

        # chmod 600 – samo vlasnik može čitati
        os.chmod(_AUDIT_FILE, stat.S_IRUSR | stat.S_IWUSR)

    except OSError:
        # Audit greška ne sme srušiti CLI operaciju
        pass