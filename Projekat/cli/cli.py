"""
oblak/cli.py
─────────────
Glavni entry point za CDK CLI.

Korišćenje:
  oblak login [--server URL]
  oblak logout
  oblak deploy <script.py> [--requirements req.txt]
  oblak invoke <hash>
  oblak status <hash>
"""

import click
from rich.console import Console

from oblak.commands.login import login, logout
from oblak.commands.deploy import deploy
from oblak.commands.invoke import invoke, status
from oblak.commands.register import register

console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="oblak")
def cli() -> None:
    """
    Oblak CDK – Cloud Development Kit CLI

    \b
    Platforma za izvršavanje Python koda u oblaku.
    Slično AWS Lambda ili Google Cloud Functions.
    """
    pass


# ── Registracija komandi ──────────────────────────────────────────────────────
cli.add_command(login)
cli.add_command(logout)
cli.add_command(deploy)
cli.add_command(invoke)
cli.add_command(status)
cli.add_command(register)


if __name__ == "__main__":
    cli()