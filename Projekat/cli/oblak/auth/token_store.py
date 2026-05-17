"""
oblak/auth/token_store.py
──────────────────────────
Bezbedno čuvanje JWT tokena lokalno.

Primarno: OS keychain via `keyring` (Keychain na macOS,
          libsecret na Linux, Credential Manager na Windows).
Fallback:  ~/.oblak/credentials sa chmod 600.

Nikad se ne čuva plain token u bash historiji ili env varijablama
dostupnim svim procesima.
"""

import json
import os
import stat
from pathlib import Path

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    _KEYRING_AVAILABLE = False

# Konstante za keyring servis
_SERVICE_NAME = "oblak-cli"
_TOKEN_KEY = "jwt_token"
_REFRESH_KEY = "refresh_token"

# Fallback lokacija
_OBLAK_DIR = Path.home() / ".oblak"
_CREDS_FILE = _OBLAK_DIR / "credentials"


# ── Public API ────────────────────────────────────────────────────────────────

def save_tokens(token: str, refresh_token: str | None = None) -> None:
    """Čuva JWT (i refresh token ako postoji) bezbedno."""
    if _KEYRING_AVAILABLE:
        try:
            keyring.set_password(_SERVICE_NAME, _TOKEN_KEY, token)
            if refresh_token:
                keyring.set_password(_SERVICE_NAME, _REFRESH_KEY, refresh_token)
            return
        except Exception:
            pass  # Fallback na fajl

    _save_to_file(token, refresh_token)


def load_token() -> str:
    """
    Učitava JWT token.
    Baca RuntimeError ako korisnik nije ulogovan.
    """
    if _KEYRING_AVAILABLE:
        try:
            token = keyring.get_password(_SERVICE_NAME, _TOKEN_KEY)
            if token:
                return token
        except Exception:
            pass

    return _load_from_file()["token"]


def load_refresh_token() -> str | None:
    """Učitava refresh token, ili None ako ne postoji."""
    if _KEYRING_AVAILABLE:
        try:
            return keyring.get_password(_SERVICE_NAME, _REFRESH_KEY)
        except Exception:
            pass

    data = _load_from_file()
    return data.get("refresh_token")


def clear_tokens() -> None:
    """Briše sve tokene (logout)."""
    if _KEYRING_AVAILABLE:
        try:
            keyring.delete_password(_SERVICE_NAME, _TOKEN_KEY)
            keyring.delete_password(_SERVICE_NAME, _REFRESH_KEY)
        except Exception:
            pass

    if _CREDS_FILE.exists():
        # Overwrite pre brisanja (basic zeroization)
        _CREDS_FILE.write_text("{}")
        _CREDS_FILE.unlink()


def is_logged_in() -> bool:
    """Provera da li postoji sačuvan token (ne validira potpis)."""
    try:
        load_token()
        return True
    except RuntimeError:
        return False


# ── Private helpers ───────────────────────────────────────────────────────────

def _save_to_file(token: str, refresh_token: str | None) -> None:
    _OBLAK_DIR.mkdir(exist_ok=True)
    data = {"token": token}
    if refresh_token:
        data["refresh_token"] = refresh_token

    _CREDS_FILE.write_text(json.dumps(data))

    # chmod 600 – samo vlasnik može čitati/pisati
    os.chmod(_CREDS_FILE, stat.S_IRUSR | stat.S_IWUSR)


def _load_from_file() -> dict:
    if not _CREDS_FILE.exists():
        raise RuntimeError(
            "Nisi ulogovan. Pokreni: oblak login"
        )
    try:
        data = json.loads(_CREDS_FILE.read_text())
        if "token" not in data:
            raise ValueError
        return data
    except (json.JSONDecodeError, ValueError) as exc:
        raise RuntimeError(
            "Credentials fajl je oštećen. Pokreni: oblak login"
        ) from exc