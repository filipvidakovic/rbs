"""
oblak/commands/invoke.py
─────────────────────────
`oblak invoke <hash>`  – poziva deployovanu funkciju
`oblak status <hash>`  – prikazuje metadata funkcije
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from oblak import audit
from oblak.auth import client

console = Console()

# SHA-256 hex string pattern (64 hex karaktera)
_HASH_REGEX = r"^[a-f0-9]{64}$"


@click.command()
@click.argument("url_hash")
def invoke(url_hash: str) -> None:
    """Pokreni deployovanu funkciju po njenom hash-u.

    \b
    Primer:
      oblak invoke abc123...
    """
    import re
    if not re.fullmatch(_HASH_REGEX, url_hash):
        raise click.ClickException(
            "Neispravan hash format. Hash mora biti 64-karakterni hex string."
        )

    audit.log(audit.Action.INVOKE, {"url_hash": url_hash})

    resp = client.post(f"/api/functions/{url_hash}/invoke")

    if resp.status_code == 404:
        audit.log(audit.Action.INVOKE_FAILURE, {"url_hash": url_hash, "reason": "not_found"}, outcome="failure")
        raise click.ClickException(f"Funkcija sa hashom '{url_hash[:16]}…' ne postoji.")

    if not resp.ok:
        audit.log(audit.Action.INVOKE_FAILURE, {"url_hash": url_hash, "reason": f"http_{resp.status_code}"}, outcome="failure")
        raise click.ClickException(f"Greška pri pokretanju (HTTP {resp.status_code}).")

    data = resp.json()
    status = data.get("status", "?")
    message = data.get("message", "")

    console.print(f"[green]✓[/green] Status: [bold]{status}[/bold]")
    if message:
        console.print(f"  {message}")


@click.command()
@click.argument("url_hash")
def status(url_hash: str) -> None:
    """Prikaži informacije o deployovanoj funkciji.

    \b
    Primer:
      oblak status abc123...
    """
    import re
    if not re.fullmatch(_HASH_REGEX, url_hash):
        raise click.ClickException(
            "Neispravan hash format. Hash mora biti 64-karakterni hex string."
        )

    audit.log(audit.Action.STATUS_CHECK, {"url_hash": url_hash})

    resp = client.get(f"/api/functions/{url_hash}")

    if resp.status_code == 404:
        raise click.ClickException(f"Funkcija sa hashom '{url_hash[:16]}…' ne postoji.")

    if not resp.ok:
        raise click.ClickException(f"Greška (HTTP {resp.status_code}).")

    data = resp.json()

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Polje", style="bold")
    table.add_column("Vrednost")

    table.add_row("Hash",     data.get("urlHash", "-"))
    table.add_row("Fajl",     data.get("originalFilename", "-"))
    table.add_row("Status",   data.get("status", "-"))
    table.add_row("Kreiran",  data.get("createdAt", "-"))
    table.add_row("Putanja",  data.get("storagePath", "-"))

    console.print(table)