# Emby to Trakt

Sync watched history from Emby to Trakt.

## Installation

### Run directly without installing (recommended)

Use `uvx` to run directly from GitHub:

```bash
uvx --from git+https://github.com/swack-tools/emby-to-trakt.git emby-sync --help
```

For convenience, create an alias:

```bash
alias emby-sync='uvx --from git+https://github.com/swack-tools/emby-to-trakt.git emby-sync'
```

### Install from GitHub

```bash
uv pip install git+https://github.com/swack-tools/emby-to-trakt.git
```

### Install from source

```bash
git clone https://github.com/swack-tools/emby-to-trakt.git
cd emby-to-trakt
uv pip install -e .
```

## Quick Start

> **Note:** Examples below use `emby-sync` directly. If you didn't create an alias, replace `emby-sync` with `uvx --from git+https://github.com/swack-tools/emby-to-trakt.git emby-sync` or `uv run emby-sync` (if running from source).

1. **Setup Emby** - Configure your Emby connection:
   ```bash
   emby-sync setup
   ```
   You'll be prompted for:
   - Emby server URL (e.g., `https://emby.example.com`)
   - Username
   - Password

2. **Setup Trakt** - Connect your Trakt account:
   ```bash
   emby-sync trakt-setup
   ```
   This will guide you through:
   - Creating a Trakt API application at https://trakt.tv/oauth/applications
   - Entering your Client ID and Client Secret
   - Authorizing via device code at https://trakt.tv/activate

3. **Download & Push** - Sync your full watch history:
   ```bash
   emby-sync download --mode full --push
   ```

4. **Check Status**:
   ```bash
   emby-sync status
   ```

## Common Workflows

### First-time full sync to Trakt
Download everything from Emby and push to Trakt:
```bash
emby-sync download --mode full --push
```

### Fresh sync (replace Trakt history)
Clear Trakt first, then do a full sync:
```bash
emby-sync trakt-clear
emby-sync download --mode full --push
```

### Incremental sync (daily updates)
Only sync items changed since last sync:
```bash
emby-sync download --push
```

### Download and push separately
```bash
emby-sync download --mode full
emby-sync push
```

### Preview what would be synced
```bash
emby-sync push --dry-run
```

## Commands

### `emby-sync setup`
Interactive wizard to configure Emby connection. Authenticates with your Emby server and stores the access token locally.

### `emby-sync trakt-setup`
Interactive wizard to connect to Trakt:
1. Guides you to create a Trakt API application
2. Prompts for your Client ID and Client Secret
3. Uses device code authorization to link your account

### `emby-sync download`
Downloads watched movies and TV shows from Emby.

Options:
- `--mode full` - Download ALL watched items (use for first sync)
- `--mode incremental` - Only items changed since last sync (default)
- `--content [movies|episodes|all]` - What content to download (default: all)
- `--push` - Push to Trakt immediately after downloading
- `--verbose` - Show detailed progress
- `--debug` - Show API requests

**Note:** Use `--mode full` for your first sync or when you want to re-download everything. Without this flag, only items modified since the last sync are downloaded.

### `emby-sync push`
Push downloaded watch history to Trakt.

Options:
- `--mode [skip|overwrite|merge]` - Conflict resolution (default: skip)
- `--content [movies|episodes|all]` - What content to push
- `--dry-run` - Preview changes without syncing
- `--verbose` - Show detailed progress

### `emby-sync status`
Shows sync statistics: total items, movies, episodes, last sync time, Trakt connection status, and unmatched item count.

### `emby-sync validate`
Tests both Emby and Trakt connections to verify configuration is working.

### `emby-sync trakt-clear`
Clears ALL watch history from Trakt. Use before a fresh push if you want to replace your Trakt history entirely.

Options:
- `--yes, -y` - Skip confirmation prompt

**Warning:** This permanently deletes all your Trakt watch history!

## Data Storage

All data is stored in the `data/` directory:
- `config.yaml` - Emby and Trakt credentials (access tokens, not passwords)
- `watched.yaml` - Downloaded watch history
- `unmatched.yaml` - Items that couldn't be matched on Trakt
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
