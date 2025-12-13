"""CLI for emby-sync tool."""

import os
import time
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from emby_to_trakt import __version__
from emby_to_trakt.config import Config, ConfigError
from emby_to_trakt.emby_client import EmbyClient, EmbyAuthError, EmbyConnectionError
from emby_to_trakt.storage import DataStore
from emby_to_trakt.trakt_auth import TraktAuth, TraktAuthError
from emby_to_trakt.trakt_client import TraktClient, TraktError
from emby_to_trakt.unmatched import UnmatchedLogger

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


@cli.command("trakt-setup")
def trakt_setup():
    """Connect to Trakt via device code authorization."""
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Load existing config if present
    existing_client_id = None
    existing_client_secret = None
    if config.exists():
        try:
            config.load()
            existing_client_id = config.trakt_client_id
            existing_client_secret = config.trakt_client_secret
            if config.trakt_configured:
                console.print(
                    "[yellow]Trakt already configured.[/yellow]"
                )
                if not click.confirm("Reconfigure?"):
                    return
        except ConfigError:
            pass

    console.print("\n[bold]Trakt Setup[/bold]\n")

    # Check if we need API credentials
    if not existing_client_id:
        console.print("[bold]Step 1: Create a Trakt API Application[/bold]\n")
        console.print("You need to create a Trakt API application to get your credentials.\n")
        console.print("1. Go to: [bold cyan]https://trakt.tv/oauth/applications[/bold cyan]")
        console.print("2. Click [bold]New Application[/bold]")
        console.print("3. Fill in:")
        console.print("   - Name: [dim]emby-to-trakt[/dim] (or any name)")
        console.print("   - Redirect URI: [dim]urn:ietf:wg:oauth:2.0:oob[/dim]")
        console.print("4. Click [bold]Save App[/bold]")
        console.print("5. Copy your [bold]Client ID[/bold] and [bold]Client Secret[/bold]\n")

        if not click.confirm("Ready to continue?"):
            console.print("[dim]Setup cancelled.[/dim]")
            return

        console.print()
        client_id = click.prompt("Enter your Trakt Client ID", type=str).strip()
        client_secret = click.prompt("Enter your Trakt Client Secret", type=str).strip()
    else:
        console.print(f"[dim]Using existing Trakt API credentials[/dim]\n")
        client_id = existing_client_id
        client_secret = existing_client_secret

    console.print("\n[bold]Step 2: Authorize Your Account[/bold]\n")

    auth = TraktAuth(client_id=client_id, client_secret=client_secret)

    try:
        # Request device code
        device_data = auth.request_device_code()

        console.print(f"Visit: [bold cyan]{device_data['verification_url']}[/bold cyan]")
        console.print(f"Enter code: [bold green]{device_data['user_code']}[/bold green]")
        console.print("\n[dim]Waiting for authorization...[/dim]")

        # Poll for token
        interval = device_data.get("interval", 5)
        expires_in = device_data.get("expires_in", 600)
        device_code = device_data["device_code"]

        start_time = time.time()
        tokens = None

        while time.time() - start_time < expires_in:
            time.sleep(interval)
            tokens = auth.poll_for_token(device_code)
            if tokens:
                break

        if not tokens:
            console.print("[red]Authorization timed out.[/red]")
            raise SystemExit(2)

        # Calculate expiry
        expires_at = datetime.fromtimestamp(
            tokens["created_at"] + tokens["expires_in"]
        ).isoformat()

        # Save to config
        config.set_trakt_credentials(
            client_id=client_id,
            client_secret=client_secret,
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            expires_at=expires_at,
        )
        config.save()

        console.print("\n[green]✓ Trakt connected![/green]")
        console.print("Run [bold]emby-sync push[/bold] to sync your watch history.")

    except TraktAuthError as e:
        console.print(f"[red]Authorization failed:[/red] {e}")
        raise SystemExit(2)


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
@click.option("--push", is_flag=True, help="Push to Trakt after download")
def download(mode, content, verbose, debug, push):
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

    # Push to Trakt if requested
    if push:
        if not config.trakt_configured:
            console.print("\n[yellow]Cannot push: Trakt not configured.[/yellow]")
            console.print("Run [bold]emby-sync trakt-setup[/bold] first.")
            return

        # Separate items with and without provider IDs
        syncable = []
        unmatched_logger = UnmatchedLogger(data_dir=data_dir)

        for item in all_items:
            if item.imdb_id or item.tmdb_id or item.tvdb_id:
                syncable.append(item)
            else:
                unmatched_logger.log(item, reason="No provider IDs")

        if not syncable:
            console.print("\n[yellow]No items with provider IDs to push.[/yellow]")
            unmatched_logger.save()
            return

        # Create Trakt client and sync
        client = TraktClient(
            client_id=config.trakt_client_id,
            access_token=config.trakt_access_token,
        )

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Pushing to Trakt...", total=None)

                result = client.sync_history(syncable)

                progress.update(task, description="Push complete")

            # Save unmatched items
            unmatched_logger.save()

            added_movies = result.get("added", {}).get("movies", 0)
            added_episodes = result.get("added", {}).get("episodes", 0)

            console.print(f"\n[green]✓ Pushed to Trakt[/green]")
            console.print(f"  Movies: {added_movies}")
            console.print(f"  Episodes: {added_episodes}")

            if unmatched_logger.count() > 0:
                console.print(f"  Unmatched: {unmatched_logger.count()} (see data/unmatched.yaml)")

        except TraktError as e:
            console.print(f"\n[red]Push failed:[/red] {e}")
            raise SystemExit(3)


@cli.command()
def status():
    """Show sync status and statistics."""
    data_dir = get_data_dir()
    store = DataStore(data_dir=data_dir)
    config = Config(data_dir=data_dir)

    # Load watched items
    items = store.load_watched_items()

    if not items:
        console.print("[yellow]No watched data found.[/yellow]")
        console.print("Run [bold]emby-sync download[/bold] to sync.")
        return

    # Count by type
    movies = [i for i in items if i.item_type == "movie"]
    episodes = [i for i in items if i.item_type == "episode"]
    partial = [i for i in items if not i.is_fully_watched]

    # Create table
    table = Table(title="Sync Status")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total Items", str(len(items)))
    table.add_row("Movies", str(len(movies)))
    table.add_row("Episodes", str(len(episodes)))
    table.add_row("Partial Watches", str(len(partial)))

    # Last sync time
    last_sync = store.get_last_sync_time()
    if last_sync:
        table.add_row("Last Sync", last_sync.strftime("%Y-%m-%d %H:%M:%S"))

    # Unmatched count
    unmatched_path = data_dir / "unmatched.yaml"
    if unmatched_path.exists():
        import yaml
        try:
            with open(unmatched_path) as f:
                unmatched_data = yaml.safe_load(f)
                if unmatched_data:
                    table.add_row("Unmatched Items", str(len(unmatched_data)))
        except Exception:
            pass

    console.print(table)

    # Config status
    if config.exists():
        try:
            config.load()
            console.print(f"\n[dim]Server: {config.server_url}[/dim]")
            console.print(f"[dim]Sync mode: {config.sync_mode}[/dim]")

            # Trakt status
            if config.trakt_configured:
                console.print(f"[dim]Trakt: Connected[/dim]")
            else:
                console.print(f"[dim]Trakt: Not configured[/dim]")
        except ConfigError:
            pass


@cli.command()
@click.option(
    "--mode",
    type=click.Choice(["skip", "overwrite", "merge"]),
    default="skip",
    help="Conflict resolution mode",
)
@click.option(
    "--content",
    type=click.Choice(["movies", "episodes", "all"]),
    default="all",
    help="Content to sync",
)
@click.option("--dry-run", is_flag=True, help="Preview without syncing")
@click.option("--verbose", is_flag=True, help="Show detailed progress")
def push(mode, content, dry_run, verbose):
    """Push watched history to Trakt."""
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Load config
    try:
        config.load()
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    if not config.trakt_configured:
        console.print("[red]Trakt not configured.[/red]")
        console.print("Run [bold]emby-sync trakt-setup[/bold] first.")
        raise SystemExit(1)

    # Load watched items
    store = DataStore(data_dir=data_dir)
    items = store.load_watched_items()

    if not items:
        console.print("[yellow]No watched items to sync.[/yellow]")
        console.print("Run [bold]emby-sync download[/bold] first.")
        return

    # Filter by content type
    if content == "movies":
        items = [i for i in items if i.item_type == "movie"]
    elif content == "episodes":
        items = [i for i in items if i.item_type == "episode"]

    # Separate items with and without provider IDs
    syncable = []
    unmatched_logger = UnmatchedLogger(data_dir=data_dir)

    for item in items:
        if item.imdb_id or item.tmdb_id or item.tvdb_id:
            syncable.append(item)
        else:
            unmatched_logger.log(item, reason="No provider IDs")

    movies = [i for i in syncable if i.item_type == "movie"]
    episodes = [i for i in syncable if i.item_type == "episode"]

    # Dry run output
    if dry_run:
        console.print("[bold]Dry run - no changes will be made[/bold]\n")
        console.print(f"Would sync to Trakt:")
        console.print(f"  Movies: {len(movies)}")
        console.print(f"  Episodes: {len(episodes)}")
        console.print(f"  Unmatched: {unmatched_logger.count()}")
        return

    # Create Trakt client
    client = TraktClient(
        client_id=config.trakt_client_id,
        access_token=config.trakt_access_token,
    )

    # Sync history
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Syncing to Trakt...", total=None)

            result = client.sync_history(syncable)

            progress.update(task, description="Sync complete")

        # Save unmatched items
        unmatched_logger.save()

        added_movies = result.get("added", {}).get("movies", 0)
        added_episodes = result.get("added", {}).get("episodes", 0)

        console.print(f"\n[green]✓ Pushed to Trakt[/green]")
        console.print(f"  Movies: {added_movies}")
        console.print(f"  Episodes: {added_episodes}")

        if unmatched_logger.count() > 0:
            console.print(f"  Unmatched: {unmatched_logger.count()} (see data/unmatched.yaml)")

    except TraktError as e:
        console.print(f"[red]Sync failed:[/red] {e}")
        raise SystemExit(3)


@cli.command("trakt-clear")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def trakt_clear(yes):
    """Clear ALL watch history from Trakt.

    This is a destructive operation that removes all watched movies and shows
    from your Trakt account. Use with caution.
    """
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Load config
    try:
        config.load()
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    if not config.trakt_configured:
        console.print("[red]Trakt not configured.[/red]")
        console.print("Run [bold]emby-sync trakt-setup[/bold] first.")
        raise SystemExit(1)

    # Warning and confirmation
    console.print("\n[bold red]WARNING: This will delete ALL watch history from Trakt![/bold red]")
    console.print("This includes all watched movies and TV episodes.\n")

    if not yes:
        if not click.confirm("Are you sure you want to continue?", default=False):
            console.print("[dim]Operation cancelled.[/dim]")
            return

    # Create Trakt client
    client = TraktClient(
        client_id=config.trakt_client_id,
        access_token=config.trakt_access_token,
    )

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Fetching current watch history...", total=None)

            # Get counts before clearing
            movies = client.get_watched_movies()
            shows = client.get_watched_shows()

            progress.update(task, description=f"Found {len(movies)} movies, {len(shows)} shows")

            if not movies and not shows:
                console.print("\n[yellow]No watch history to clear.[/yellow]")
                return

            progress.update(task, description="Clearing watch history...")

            result = client.clear_all_history()

            progress.update(task, description="Clear complete")

        deleted_movies = result.get("deleted", {}).get("movies", 0)
        deleted_episodes = result.get("deleted", {}).get("episodes", 0)

        console.print(f"\n[green]✓ Trakt history cleared[/green]")
        console.print(f"  Deleted movies: {deleted_movies}")
        console.print(f"  Deleted episodes: {deleted_episodes}")

    except TraktError as e:
        console.print(f"[red]Failed to clear history:[/red] {e}")
        raise SystemExit(3)


@cli.command()
def validate():
    """Validate configuration and test Emby and Trakt connections."""
    data_dir = get_data_dir()
    config = Config(data_dir=data_dir)

    # Check config exists
    if not config.exists():
        console.print("[red]Configuration not found.[/red]")
        console.print("Run [bold]emby-sync setup[/bold] to configure.")
        raise SystemExit(1)

    # Load config
    try:
        config.load()
    except ConfigError as e:
        console.print(f"[red]Invalid configuration:[/red] {e}")
        raise SystemExit(1)

    console.print(f"[dim]Server URL:[/dim] {config.server_url}")
    console.print(f"[dim]User ID:[/dim] {config.user_id}")

    # Test Emby connection
    console.print("\n[dim]Testing Emby connection...[/dim]")

    emby_client = EmbyClient(
        server_url=config.server_url,
        access_token=config.access_token,
        user_id=config.user_id,
        device_id=config.device_id,
    )

    if emby_client.test_connection():
        console.print("[green]✓ Emby connection valid![/green]")
    else:
        console.print("[red]✗ Emby connection failed.[/red]")
        console.print("Your token may have expired. Run [bold]emby-sync setup[/bold] to re-authenticate.")
        raise SystemExit(2)

    # Test Trakt connection if configured
    if config.trakt_configured:
        console.print("\n[dim]Testing Trakt connection...[/dim]")

        trakt_client = TraktClient(
            client_id=config.trakt_client_id,
            access_token=config.trakt_access_token,
        )

        if trakt_client.test_connection():
            console.print("[green]✓ Trakt connection valid![/green]")
        else:
            console.print("[red]✗ Trakt connection failed.[/red]")
            console.print("Your token may have expired. Run [bold]emby-sync trakt-setup[/bold] to re-authenticate.")
            raise SystemExit(2)
    else:
        console.print("\n[dim]Trakt: Not configured[/dim]")


if __name__ == "__main__":
    cli()
