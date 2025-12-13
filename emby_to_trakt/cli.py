"""CLI for emby-sync tool."""

import click
from rich.console import Console

from emby_to_trakt import __version__

console = Console()


@click.group()
@click.version_option(version=__version__)
def cli():
    """Emby to Trakt sync tool - Download watched history from Emby."""
    pass


@cli.command()
def setup():
    """Interactive setup wizard to configure Emby connection."""
    console.print("[yellow]Setup wizard not yet implemented[/yellow]")


@cli.command()
@click.option(
    "--mode",
    type=click.Choice(["full", "incremental"]),
    help="Sync mode (overrides config)",
)
@click.option(
    "--content",
    type=click.Choice(["movies", "episodes", "all"]),
    default="all",
    help="Content types to download",
)
@click.option("--verbose", is_flag=True, help="Show detailed progress")
@click.option("--debug", is_flag=True, help="Show API request/response details")
def download(mode, content, verbose, debug):
    """Download watched history from Emby server."""
    console.print("[yellow]Download not yet implemented[/yellow]")


@cli.command()
def status():
    """Show sync status and statistics."""
    console.print("[yellow]Status not yet implemented[/yellow]")


@cli.command()
def validate():
    """Validate configuration and test Emby connection."""
    console.print("[yellow]Validate not yet implemented[/yellow]")


if __name__ == "__main__":
    cli()
