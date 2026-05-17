"""
oblak/commands/login.py
────────────────────────
`oblak login`  – autentikacija ka serveru, čuvanje JWT tokena
`oblak logout` – brisanje tokena
"""

import click
import requests
from rich.console import Console

from oblak import audit
from oblak.auth import token_store
from oblak.config import get_server_url, save_server_url

console = Console()


@click.command()
@click.option(
    "--server",
    default=None,
    help="URL servera (npr. https://oblak.example.com). "
         "Ako nije navedeno, koristi OBLAK_SERVER env ili poslednji sačuvan.",
)
@click.option("--username", prompt="Korisničko ime", help="Oblak korisničko ime.")
@click.password_option(
    "--password",
    prompt="Lozinka",
    confirmation_prompt=False,
    help="Lozinka (unosi se interaktivno – ne kao argument).",
)
def login(server: str | None, username: str, password: str) -> None:
    """Prijava na Oblak server i čuvanje JWT tokena."""

    if server:
        save_server_url(server)

    base_url = get_server_url()

    audit.log(audit.Action.LOGIN_ATTEMPT, {"username": username, "server": base_url})

    try:
        resp = requests.post(
            f"{base_url}/api/auth/login",
            json={"username": username, "password": password},
            timeout=(5, 10),
        )
    except requests.ConnectionError:
        audit.log(audit.Action.LOGIN_FAILURE, {"reason": "connection_error"}, outcome="failure", username=username)
        raise click.ClickException(
            f"Ne mogu da se povežem sa {base_url}. Proveri adresu servera."
        )
    except requests.Timeout:
        audit.log(audit.Action.LOGIN_FAILURE, {"reason": "timeout"}, outcome="failure", username=username)
        raise click.ClickException("Server ne odgovara (timeout).")

    if resp.status_code == 401:
        audit.log(audit.Action.LOGIN_FAILURE, {"reason": "bad_credentials"}, outcome="failure", username=username)
        raise click.ClickException("Pogrešno korisničko ime ili lozinka.")

    if not resp.ok:
        audit.log(audit.Action.LOGIN_FAILURE, {"reason": f"http_{resp.status_code}"}, outcome="failure", username=username)
        raise click.ClickException(f"Greška servera: {resp.status_code}")

    data = resp.json()

    # Server može vratiti "token" ili "accessToken" – podržavamo oba
    token = data.get("token") or data.get("accessToken")
    refresh = data.get("refreshToken")

    if not token:
        audit.log(audit.Action.LOGIN_FAILURE, {"reason": "no_token_in_response"}, outcome="failure", username=username)
        raise click.ClickException("Server nije vratio token. Kontaktiraj administratora.")

    token_store.save_tokens(token, refresh)

    audit.log(audit.Action.LOGIN_SUCCESS, {"server": base_url}, username=username)
    console.print(f"[green]✓[/green] Uspešno ulogovan kao [bold]{username}[/bold] na {base_url}")


@click.command()
def logout() -> None:
    """Odjava – briše lokalno sačuvan token."""
    if not token_store.is_logged_in():
        console.print("[yellow]Već si odjavljen.[/yellow]")
        return

    token_store.clear_tokens()
    audit.log(audit.Action.LOGOUT)
    console.print("[green]✓[/green] Uspešno odjavljen.")