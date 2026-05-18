"""
oblak/commands/deploy.py
─────────────────────────
`oblak deploy <file.py>` – upload Python skripte na Oblak server.

Podržava:
- Upload jednog .py fajla
- Opcioni --requirements za requirements.txt
- Auto-detekcija requirements.txt u istom folderu
- Provera veličine fajla pre uploada
- SHA-256 checksum verifikacija (klijentska strana)
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from oblak import audit
from oblak.auth import client

console = Console()

# Maksimalna veličina Python fajla: 1 MB
_MAX_PY_SIZE = 1 * 1024 * 1024

# Maksimalna veličina requirements.txt: 100 KB
_MAX_REQ_SIZE = 100 * 1024


@click.command()
@click.argument("script", type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option(
    "--requirements", "-r",
    type=click.Path(exists=True, dir_okay=False, readable=True),
    default=None,
    help="Putanja do requirements.txt. Ako nije navedeno, traži se u istom folderu.",
)
@click.option(
    "--no-auto-req",
    is_flag=True,
    default=False,
    help="Ne učitavaj requirements.txt automatski.",
)
def deploy(script: str, requirements: str | None, no_auto_req: bool) -> None:
    """Upload Python skripte na Oblak server.

    SCRIPT je putanja do .py fajla koji se deploye.

    \b
    Primeri:
      oblak deploy handler.py
      oblak deploy handler.py --requirements requirements.txt
    """
    script_path = Path(script)

    # ── Validacija na klijentskoj strani ──────────────────────────────────────
    if script_path.suffix != ".py":
        raise click.ClickException(
            f"Fajl mora biti Python (.py). Dobijeno: {script_path.name}"
        )

    if script_path.stat().st_size == 0:
        raise click.ClickException("Fajl je prazan.")

    if script_path.stat().st_size > _MAX_PY_SIZE:
        raise click.ClickException(
            f"Fajl je prevelik (max {_MAX_PY_SIZE // 1024} KB)."
        )

    # ── Auto-detekcija requirements.txt ───────────────────────────────────────
    req_path: Path | None = None

    if requirements:
        req_path = Path(requirements)
    elif not no_auto_req:
        candidate = script_path.parent / "requirements.txt"
        if candidate.exists():
            console.print(
                f"[dim]ℹ Auto-detektovan: {candidate.name}[/dim]"
            )
            req_path = candidate

    if req_path and req_path.stat().st_size > _MAX_REQ_SIZE:
        raise click.ClickException(
            f"requirements.txt je prevelik (max {_MAX_REQ_SIZE // 1024} KB)."
        )

    # ── SHA-256 pre uploada (za audit) ────────────────────────────────────────
    local_hash = _sha256(script_path)

    audit.log(
        audit.Action.DEPLOY_START,
        {
            "script": script_path.name,
            "local_sha256": local_hash,
            "has_requirements": req_path is not None,
        },
    )

    # ── Upload ────────────────────────────────────────────────────────────────
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task(f"Uploading {script_path.name}…", total=None)

        files: dict = {
            "file": (script_path.name, script_path.read_bytes(), "text/x-python"),
        }
        if req_path:
            files["requirements"] = (
                "requirements.txt",
                req_path.read_bytes(),
                "text/plain",
            )

        resp = client.post("/api/functions/upload", files=files)

    # ── Odgovor ───────────────────────────────────────────────────────────────
    if resp.status_code == 422:
        # Code Verifier je odbio kod
        err = resp.json().get("error", "Kod nije prošao verifikaciju.")
        audit.log(
            audit.Action.DEPLOY_FAILURE,
            {"reason": "verification_failed", "script": script_path.name},
            outcome="failure",
        )
        raise click.ClickException(f"[Verifikacija neuspešna] {err}")

    if not resp.ok:
        audit.log(
            audit.Action.DEPLOY_FAILURE,
            {"reason": f"http_{resp.status_code}", "script": script_path.name},
            outcome="failure",
        )
        raise click.ClickException(
            f"Upload neuspešan (HTTP {resp.status_code}): {resp.text[:200]}"
        )

    data = resp.json()
    url_hash = data.get("urlHash")
    invoke_url = data.get("invokeUrl")

    audit.log(
        audit.Action.DEPLOY_SUCCESS,
        {
            "script": script_path.name,
            "local_sha256": local_hash,
            "url_hash": url_hash,
        },
    )

    console.print(f"\n[green]✓ Deploy uspešan![/green]")
    console.print(f"  [bold]Hash:[/bold]       {url_hash}")
    console.print(f"  [bold]Invoke URL:[/bold] {invoke_url}")
    console.print(
        f"\n[dim]Pokreni sa:[/dim] oblak invoke {url_hash}"
    )


# ── Helper ────────────────────────────────────────────────────────────────────

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()