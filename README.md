# Emby to Trakt

Sync watched history from Emby to Trakt.

## Installation

```bash
# Using uv (recommended)
uv pip install -e .

# Or run without installing
uv run emby-sync --help
```

## Quick Start

1. **Setup** - Configure your Emby connection:
   ```bash
   emby-sync setup
   ```
   You'll be prompted for:
   - Emby server URL (e.g., `https://emby.example.com`)
   - Username
   - Password

2. **Download** - Fetch your watched history:
   ```bash
   emby-sync download
   ```

3. **Check Status**:
   ```bash
   emby-sync status
   ```

## Commands

### `emby-sync setup`
Interactive wizard to configure Emby connection. Authenticates with your Emby server and stores the access token locally.

### `emby-sync download`
Downloads watched movies and TV shows from Emby.

Options:
- `--mode [full|incremental]` - Full re-download or incremental since last sync
- `--content [movies|episodes|all]` - What content to download
- `--verbose` - Show detailed progress
- `--debug` - Show API requests

### `emby-sync status`
Shows sync statistics: total items, movies, episodes, and last sync time.

### `emby-sync validate`
Tests your Emby connection to verify configuration is working.

## Data Storage

All data is stored in the `data/` directory:
- `config.yaml` - Emby credentials (access token, not password)
- `watched.yaml` - Downloaded watch history
- `emby-sync.log` - Log file

## Development

```bash
# Install with dev dependencies
uv pip install -e ".[dev]"

# Run tests
uv run pytest -v

# Run with coverage
uv run pytest --cov=emby_to_trakt
```

## Phase 2 (Coming Soon)

Phase 2 will add Trakt sync functionality to push your watched history to Trakt.
