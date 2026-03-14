# cloud-forge

A suite of tools for managing **rclone cloud storage remotes** and **SFTP servers** — featuring a CLI binary (`rclone-sftp`), a rclone installer/updater (`rclone-engine`), and a desktop GUI (`cloud-forge`).

---

## Overview

| Component | Language | Description |
|-----------|----------|-------------|
| `rclone-sftp` | Go | CLI tool — start, stop, and manage rclone SFTP servers |
| `rclone-engine` | Python | CLI tool — install, update, upgrade, and uninstall rclone |
| `cloud-forge` | Python / PyQt5 | Desktop GUI — wraps both `rclone` and `rclone-sftp` |

---

## Project Structure

```
cloud-forge/
├── bin/
│   └── rclone-sftp          # Compiled Go binary
├── build/
│   ├── build-bin.sh         # Build rclone-sftp (Go)
│   ├── build-main.sh        # Build rclone-engen (PyInstaller)
│   ├── build-gui.sh         # Build cloud-forge GUI (PyInstaller)
│   └── install-deps-gui.sh  # Install GUI system dependencies (requires sudo)
├── gui/
│   └── cloud_forge.py       # PyQt5 GUI source
├── src/
│   ├── rclone_engine.py      # rclone installer/updater source
│   └── rclone-sftp/
│       ├── go.mod
│       └── main.go          # Go CLI source
├── cloud-forge              # Compiled GUI binary (after build)
├── rclone-engine             # Compiled rclone manager binary (after build)
├── cloud-forge.png          # Application icon
├── Makefile                 # Build and install targets
└── install.sh               # Installer script
```

---

## Requirements

### Runtime
- [`rclone`](https://rclone.org/) — must be installed and in `PATH`
  (use `rclone-engine install` to install automatically)
- Linux desktop environment with a file manager that supports `sftp://` URIs
  (Thunar, Nautilus, Dolphin, etc.)

### Build

| Tool | Purpose |
|------|---------|
| Go 1.21+ | Build `rclone-sftp` |
| Python 3.9+ | Build `rclone-engine` and `cloud-forge` |
| PyQt5 | GUI framework |
| PyInstaller | Build standalone binaries |

---

## Quick Start

### Standard Linux (x86_64)

```bash
# Build everything and install
make install
```

### ARM64 / PRoot (e.g. Android Termux, Raspberry Pi)

PyQt5 pip wheels are not available on ARM64 — system packages must be
installed first:

```bash
# Step 1 — install system packages (once)
make deps

# Step 2 — build and install
make install
```

---

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make deps` | Install GUI system dependencies via package manager (requires sudo) |
| `make build` | Build all binaries — `rclone-sftp`, `rclone-engine`, `cloud-forge` |
| `make build-cli` | Build CLI binaries only — `rclone-sftp` + `rclone-engine` |
| `make build-gui` | Build GUI binary only — `cloud-forge` |
| `make install` | Build everything, then install symlinks + desktop entry |
| `make install-only` | Install pre-built binaries only — symlinks + desktop entry, no build |
| `make install-cli` | Build CLI only, then install symlinks (no desktop entry) |
| `make uninstall` | Remove symlinks and desktop entry |
| `make clean` | Remove all build outputs and artefacts |
| `make help` | Show all available targets |

---

## install.sh

The installer script is called by `make` targets but can also be used directly.

```bash
./install.sh --build              # Build all binaries
./install.sh --build --cli        # Build CLI binaries only
./install.sh --install            # Install pre-built binaries (symlinks + desktop entry)
./install.sh --build --install    # Build everything, then install
./install.sh --remove             # Remove symlinks and desktop entry
```

`--install` places symlinks in `~/.local/bin/` (or `/usr/local/bin/` if
writable) for both `rclone-sftp` and `rclone-engen`, and installs a desktop
entry for the GUI at `~/.local/share/applications/cloud-forge.desktop`.

---

## Building Individually

### rclone-sftp (Go binary)

```bash
bash build/build-bin.sh
# Output: bin/rclone-sftp
```

### rclone-engen (Python binary)

```bash
bash build/build-main.sh
# Output: rclone-engine
```

Builds a single-file binary via PyInstaller, then removes all build artefacts
including the temporary venv.

### cloud-forge GUI

```bash
bash build/build-gui.sh
# Output: cloud-forge
```

---

## rclone-engen

Manages the `rclone` binary — install, update, upgrade, and uninstall without
visiting the rclone website manually. Auto-detects architecture (amd64, arm64,
arm-v7).

### Commands

```
rclone-engine install     Install the latest rclone
rclone-engine update      Check if a newer version is available
rclone-engine upgrade     Download and replace rclone with the latest version
rclone-engine uninstall   Remove the installed rclone binary
rclone-engine version     Show the currently installed rclone version
```

### Examples

```bash
# Install rclone
rclone-engine install

# Check for updates
rclone-engine update
# Installed version : v1.68.0
# Latest version    : v1.69.1
# Update available.

# Upgrade to latest
rclone-engine upgrade

# Show installed version
rclone-engine version
```

Install locations (first writable wins):

1. `/usr/local/bin/rclone`
2. `~/.local/bin/rclone`

---

## rclone-sftp CLI

Wraps `rclone serve sftp` with persistent server management: PID tracking,
log rotation, metadata persistence across restarts, VFS cache management,
and three performance profiles.

### Commands

```
rclone-sftp start       REMOTE [PORT|auto] USER [PASS] [--password-file FILE] [--profile PROFILE]
rclone-sftp stop        REMOTE PORT
rclone-sftp stop-all
rclone-sftp restart     REMOTE PORT USER [PASS] [--profile PROFILE]
rclone-sftp status      [--json]
rclone-sftp logs        REMOTE PORT [LINES]
rclone-sftp check       REMOTE PORT
rclone-sftp ports
rclone-sftp health      [--json]
rclone-sftp config      [KEY=VALUE ...]
rclone-sftp profiles
rclone-sftp clear-cache [REMOTE PORT]
```

### Examples

```bash
# Start gdrive on port 8888 with heavy profile
rclone-sftp start gdrive 8888 sumit mypassword --profile heavy

# Auto-assign a free port
rclone-sftp start gdrive auto sumit mypassword

# Use password from file
rclone-sftp start gdrive auto sumit --password-file ~/.sftp-pass

# Use environment variable for password
RCLONE_SFTP_PASS=mypassword rclone-sftp start gdrive 8888 sumit

# Stop a specific server
rclone-sftp stop gdrive 8888

# Show running servers as JSON
rclone-sftp status --json

# Show last 100 log lines
rclone-sftp logs gdrive 8888 100

# Set default profile
rclone-sftp config heavy

# Tune a specific profile value
rclone-sftp config heavy.buffer_size=128M heavy.transfers=16

# Check server and system health
rclone-sftp health

# Clear all VFS cache
rclone-sftp clear-cache

# Clear cache for a specific server
rclone-sftp clear-cache gdrive 8888
```

---

## Performance Profiles

### Light — small files, minimal memory

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 16M |
| `--transfers` | 2 |
| `--checkers` | 4 |
| `--vfs-cache-mode` | off |
| `--timeout` | 30m |

### Balanced *(default)* — medium files, good all-round performance

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 32M |
| `--transfers` | 4 |
| `--checkers` | 8 |
| `--vfs-cache-mode` | writes |
| `--vfs-cache-max-size` | 50G |
| `--vfs-cache-max-age` | 72h |
| `--vfs-read-chunk-size` | 32M |
| `--vfs-read-ahead` | 64M |
| `--timeout` | 1h |
| `--low-level-retries` | 10 |

### Heavy — large files 100GB+, maximum throughput

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 64M |
| `--transfers` | 8 |
| `--checkers` | 16 |
| `--vfs-cache-mode` | full |
| `--vfs-cache-max-size` | 200G |
| `--vfs-cache-max-age` | 168h |
| `--vfs-read-chunk-size` | 64M |
| `--vfs-read-ahead` | 128M |
| `--timeout` | 2h |
| `--low-level-retries` | 20 |
| `--max-connections` | 20 |

Profile values can be customised at runtime:

```bash
rclone-sftp config heavy.vfs_cache_max_size=500G
rclone-sftp config balanced.transfers=8
```

---

## Configuration

Stored at `~/.local/share/rclone-sftp/config.json`, created automatically on
first run.

### Global keys

| Key | Default | Description |
|-----|---------|-------------|
| `profile` | `balanced` | Default profile for new servers |
| `cache_dir` | `~/.local/share/rclone-sftp/cache` | VFS cache directory |
| `temp_dir` | `~/.local/share/rclone-sftp/temp` | Temp directory |
| `log_dir` | `~/.local/share/rclone-sftp/logs` | Log directory |
| `log_size` | `50` (MB) | Rotate log when it exceeds this size |
| `max_log_files` | `5` | Number of rotated log archives to keep |
| `max_disk_mb` | `1024` | Minimum free disk space required to start a server |
| `port_range_from` | `8022` | Start of auto-assign port range |
| `port_range_to` | `9000` | End of auto-assign port range |
| `verbose` | `false` | Enable rclone `-vv` verbose logging |
| `config_path` | _(empty)_ | Path to rclone config file |

### Profile keys

```bash
rclone-sftp config heavy.buffer_size=128M
rclone-sftp config balanced.vfs_cache_max_size=100G
rclone-sftp config light.timeout=1h
```

---

## Runtime Data

```
~/.local/share/rclone-sftp/
├── config.json                  # Main configuration
├── <remote>_<port>.pid          # PID file per running server
├── meta/
│   └── <remote>_<port>.json     # Persistent server metadata
├── logs/
│   └── <remote>_<port>.log      # Server log (auto-rotated, gzip compressed)
├── cache/                       # rclone VFS cache
└── temp/                        # rclone temp files
```

---

## cloud-forge GUI

### Remote Manager tab

| Button | Action |
|--------|--------|
| Add Remote | GUI wizard — select provider, fill credentials, OAuth browser auth |
| Refresh | `rclone listremotes --long` |
| Browse | `rclone lsd <remote>:` |
| Rename | `rclone config rename` |
| Dump Config | `rclone config dump` |
| Delete | `rclone config delete` |

Supported providers in the Add Remote wizard: Google Drive, Google Photos,
OneDrive, Dropbox, Amazon S3, Backblaze B2, SFTP, FTP, WebDAV, pCloud, Mega,
Box, Yandex Disk, iCloud Drive, Cloudflare R2, Wasabi, HTTP, Local filesystem.

### SFTP Servers tab

| Button | Action |
|--------|--------|
| Start Server | Dialog → `rclone-sftp start` |
| Stop | `rclone-sftp stop` |
| Stop All | `rclone-sftp stop-all` |
| Restart | `rclone-sftp restart` |
| Logs | `rclone-sftp logs` |
| Check | `rclone-sftp check` |
| Ports | `rclone-sftp ports` |
| Health | `rclone-sftp health` |
| Profiles | `rclone-sftp profiles` |
| Open in Files | Opens `sftp://user@127.0.0.1:<port>/` in the system file manager |
| Clear Cache | `rclone-sftp clear-cache` — frees VFS cache disk space |

The server table auto-refreshes every 5 seconds. Running servers are
highlighted in green, stopped servers in red.

### Config tab

Set the default profile and apply custom `key=value` configuration from
the GUI.

### Binary discovery

The GUI locates `rclone-sftp` in this order:

1. `./bin/rclone-sftp` (relative to the `cloud-forge` binary)
2. `../bin/rclone-sftp`
3. `/usr/local/bin/rclone-sftp`
4. `/usr/bin/rclone-sftp`
5. `PATH`

---

## Connecting via CLI

```bash
# Start a server
rclone-sftp start gdrive 8888 sumit mypassword

# Connect interactively
sftp -P 8888 sumit@127.0.0.1

# Upload a file
scp -P 8888 /path/to/file.txt sumit@127.0.0.1:/

# Download a file
scp -P 8888 sumit@127.0.0.1:/file.txt /path/to/local/

# Sync a directory
rsync -avz -e "ssh -p 8888" /path/to/dir/ sumit@127.0.0.1:/backup/
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RCLONE_SFTP_PASS` | Server password (alternative to CLI argument) |
| `RCLONE_BINARY` | Path to rclone binary (defaults to `rclone` in `PATH`) |
| `RCLONE_CONFIG` | Path to rclone config file |

---

## Signal Handling

`rclone-sftp` handles `SIGINT` and `SIGTERM` gracefully — stops all running
servers before exiting.

---

## Credits

- [rclone](https://rclone.org/) — the underlying cloud storage engine. This
  project is a management and GUI layer built on top of `rclone serve sftp`.
- [PyQt5](https://riverbankcomputing.com/software/pyqt/) — desktop GUI framework.
