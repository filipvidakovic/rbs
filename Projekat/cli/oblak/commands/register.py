# oblak/commands/register.py
import click
import requests
from rich.console import Console

from oblak import audit
from oblak.auth import token_store
from oblak.config import get_server_url, save_server_url

console = Console()


@click.command()
@click.option("--server", default=None, help="URL servera.")
@click.option("--username", prompt="Korisničko ime")
@click.password_option("--password", prompt="Lozinka", confirmation_prompt=True)
def register(server: str | None, username: str, password: str) -> None:
    """Registracija novog Oblak korisnika."""

    if server:
        save_server_url(server)

    base_url = get_server_url()

    try:
        resp = requests.post(
            f"{base_url}/api/auth/register",
            json={"username": username, "password": password},
            timeout=(5, 10),
        )
    except requests.ConnectionError:
        raise click.ClickException(f"Ne mogu da se povežem sa {base_url}.")
    except requests.Timeout:
        raise click.ClickException("Server ne odgovara (timeout).")

    if resp.status_code == 409:
        raise click.ClickException("Korisnik sa tim username-om već postoji.")

    if resp.status_code == 400:
        err = resp.json().get("error", "Validacijska greška.")
        raise click.ClickException(err)

    if not resp.ok:
        raise click.ClickException(f"Greška servera: {resp.status_code}")

    data = resp.json()
    token = data.get("token") or data.get("accessToken")
    refresh = data.get("refreshToken")

    token_store.save_tokens(token, refresh)
    audit.log(audit.Action.LOGIN_SUCCESS, {"server": base_url}, username=username)

    console.print(f"[green]✓[/green] Registrovan i ulogovan kao [bold]{username}[/bold]")