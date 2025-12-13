"""CLI for emby-sync tool."""

import os
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from emby_to_trakt import __version__
from emby_to_trakt.config import Config, ConfigError
from emby_to_trakt.emby_client import EmbyClient, EmbyAuthError, EmbyConnectionError
from emby_to_trakt.storage import DataStore

console = Console()


def get_data_dir() -> Path:
    """Get data directory from env or default."""
    env_dir = os.environ.get("EMBY_SYNC_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd() / "data"


@click.group()
@click.version_option(version=__version__)
def cli():
    """Emby to Trakt sync tool - Download watched history from Emby."""
    pass


@cli.command()
def setup():
    """Interactive setup wizard to configure Emby connection."""
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Warn if config exists
    if config.exists():
        console.print(
            "[yellow]Configuration already exists at:[/yellow] "
            f"{config.config_path}"
        )
        if not click.confirm("Overwrite existing configuration?"):
            console.print("[dim]Setup cancelled.[/dim]")
            return

    console.print("\n[bold]Emby Sync Setup[/bold]\n")

    # Get server URL
    server_url = click.prompt("Emby server URL", type=str)
    server_url = server_url.rstrip("/")

    # Get credentials
    username = click.prompt("Username", type=str)
    password = click.prompt("Password", hide_input=True, type=str)

    # Authenticate
    console.print("\n[dim]Authenticating with Emby server...[/dim]")

    try:
        client = EmbyClient(server_url=server_url)
        result = client.authenticate(username, password)
    except EmbyAuthError as e:
        console.print(f"[red]Authentication failed:[/red] {e}")
        raise SystemExit(1)
    except EmbyConnectionError as e:
        console.print(f"[red]Connection failed:[/red] {e}")
        raise SystemExit(1)

    # Save config
    config.set_emby_credentials(
        server_url=server_url,
        user_id=result["user_id"],
        access_token=result["access_token"],
        device_id=result["device_id"],
    )
    config.save()

    console.print("\n[green]✓ Setup complete![/green]")
    console.print(f"  Config saved to: {config.config_path}")
    console.print("\nRun [bold]emby-sync download[/bold] to sync watched history.")


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
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Load config
    try:
        config.load()
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        console.print("Run [bold]emby-sync setup[/bold] to configure.")
        raise SystemExit(1)

    # Determine sync mode
    sync_mode = mode or config.sync_mode

    # Create client
    client = EmbyClient(
        server_url=config.server_url,
        access_token=config.access_token,
        user_id=config.user_id,
        device_id=config.device_id,
    )

    # Determine content types to fetch
    content_types = []
    if content in ("movies", "all"):
        content_types.append("movies")
    if content in ("episodes", "all"):
        content_types.append("episodes")

    # Get since date for incremental sync
    since = None
    if sync_mode == "incremental":
        store = DataStore(data_dir=data_dir)
        since = store.get_last_sync_time()
        if since and verbose:
            console.print(f"[dim]Incremental sync since: {since}[/dim]")

    all_items = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        for content_type in content_types:
            task = progress.add_task(
                f"Fetching {content_type}...",
                total=None,
            )

            try:
                items = client.get_watched_items(
                    content_type=content_type,
                    since=since,
                    include_partial=True,
                )
                all_items.extend(items)
                progress.update(task, description=f"Fetched {len(items)} {content_type}")
            except (EmbyAuthError, EmbyConnectionError) as e:
                console.print(f"[red]Error:[/red] {e}")
                raise SystemExit(2)

            progress.remove_task(task)

    # Save items
    store = DataStore(data_dir=data_dir)
    store.save_watched_items(all_items)

    # Update last sync time
    config.set_last_sync(datetime.now())
    config.save()

    # Summary
    movies = sum(1 for i in all_items if i.item_type == "movie")
    episodes = sum(1 for i in all_items if i.item_type == "episode")

    console.print(
        f"\n[green]✓ Downloaded {len(all_items)} items[/green] "
        f"({movies} movies, {episodes} episodes)"
    )
    console.print(f"  Saved to: {store.watched_path}")


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
