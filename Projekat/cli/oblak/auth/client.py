"""
oblak/auth/client.py
─────────────────────
HTTP klijent koji automatski dodaje Authorization header
i radi refresh tokena kad istekne (401).

Sve greške mreže/auth se pretvaraju u click.ClickException
kako bi CLI štampao čistu poruku korisniku bez traceback-a.
"""

from __future__ import annotations

import click
import requests
from requests import Response

from oblak.auth import token_store
from oblak.config import get_server_url

# Timeout za sve HTTP pozive (connect, read) u sekundama
_TIMEOUT = (5, 30)


def get(path: str, **kwargs) -> Response:
    return _request("GET", path, **kwargs)


def post(path: str, **kwargs) -> Response:
    return _request("POST", path, **kwargs)


def _request(method: str, path: str, authenticated: bool = True, **kwargs) -> Response:
    """
    Šalje HTTP zahtev ka Oblak serveru.

    authenticated=True → dodaje Bearer token u header.
    Ako server vrati 401, pokušava refresh pa ponovi jednom.
    """
    url = get_server_url() + path

    if authenticated:
        try:
            token = token_store.load_token()
        except RuntimeError as exc:
            raise click.ClickException(str(exc))
        kwargs.setdefault("headers", {})
        kwargs["headers"]["Authorization"] = f"Bearer {token}"

    kwargs.setdefault("timeout", _TIMEOUT)

    try:
        resp = _do_request(method, url, **kwargs)
    except requests.ConnectionError:
        raise click.ClickException(
            f"Ne mogu da se povežem sa serverom ({get_server_url()}). "
            "Proveri da li je server pokrenut i OBLAK_SERVER env varijablu."
        )
    except requests.Timeout:
        raise click.ClickException("Zahtev ka serveru je istekao (timeout).")

    # Pokušaj refresh tokena pri 401
    if resp.status_code == 401 and authenticated:
        resp = _try_refresh_and_retry(method, url, kwargs)

    return resp


def _do_request(method: str, url: str, **kwargs) -> Response:
    return requests.request(method, url, **kwargs)


def _try_refresh_and_retry(method: str, url: str, kwargs: dict) -> Response:
    """
    Ako postoji refresh token, pokušava da dobije novi JWT,
    pa ponavlja originalni zahtev sa novim tokenom.
    """
    refresh = token_store.load_refresh_token()
    if not refresh:
        raise click.ClickException(
            "Sesija je istekla. Pokreni: oblak login"
        )

    server = get_server_url()
    try:
        r = requests.post(
            f"{server}/api/auth/refresh",
            json={"refreshToken": refresh},
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        raise click.ClickException("Nije moguće osvežiti sesiju. Pokreni: oblak login")

    if not r.ok:
        token_store.clear_tokens()
        raise click.ClickException(
            "Refresh token je nevažeći ili istekao. Pokreni: oblak login"
        )

    data = r.json()
    new_token = data.get("token") or data.get("accessToken")
    new_refresh = data.get("refreshToken")

    if not new_token:
        raise click.ClickException("Server nije vratio novi token. Pokreni: oblak login")

    token_store.save_tokens(new_token, new_refresh)

    # Ponovi originalni zahtev sa novim tokenom
    kwargs["headers"]["Authorization"] = f"Bearer {new_token}"
    return _do_request(method, url, **kwargs)