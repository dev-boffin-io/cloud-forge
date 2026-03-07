# cloud-forge

A suite of tools for managing **rclone cloud storage remotes** and **SFTP servers** — featuring a CLI binary (`rclone-sftp`) and a desktop GUI (`cloud-forge`).

---

## Overview

| Component | Language | Description |
|-----------|----------|-------------|
| `rclone-sftp` | Go | CLI tool — start, stop, and manage rclone SFTP servers |
| `cloud-forge` | Python / PyQt5 | Desktop GUI — wraps both `rclone` and `rclone-sftp` |

---

## Project Structure

```
cloud-forge/
├── bin/
│   └── rclone-sftp          # Compiled Go binary
├── build/
│   ├── build-bin.sh         # Build rclone-sftp (Go)
│   ├── build-gui.sh         # Build cloud-forge GUI (PyInstaller, no root required)
│   └── install-deps-gui.sh  # Install GUI system dependencies (requires sudo)
├── gui/
│   └── cloud_forge.py       # PyQt5 GUI source
├── src/
│   └── rclone-sftp/
│       ├── go.mod
│       └── main.go          # Go CLI source
├── cloud-forge              # Compiled GUI binary (after build)
├── cloud-forge.png          # Application icon (512×512)
└── install.sh               # Desktop entry installer
```

---

## Requirements

### Runtime
- [`rclone`](https://rclone.org/) — must be installed and in `PATH`
- Linux desktop environment with a file manager that supports `sftp://` URIs (Thunar, Nautilus, Dolphin, etc.)

### Build

| Tool | Purpose |
|------|---------|
| Go 1.21+ | Build `rclone-sftp` CLI |
| Python 3.9+ | Run or build the GUI |
| PyQt5 | GUI framework |
| PyInstaller | Build standalone GUI binary |

---

## Installation

### Quick install (binaries already built)

```bash
./install.sh
```

Installs a desktop entry to `~/.local/share/applications/cloud-forge.desktop`.

### Build from source, then install

```bash
./install.sh --build
```

Runs `build/build-bin.sh` → `build/build-gui.sh` → installs the desktop entry.

### Remove desktop entry

```bash
./install.sh --remove
```

---

## Building

### Step 1 — rclone-sftp (Go binary)

```bash
bash build/build-bin.sh
# Output: bin/rclone-sftp
```

### Step 2 — GUI system dependencies (ARM64 / PRoot only)

On ARM64 devices (e.g. Android PRoot, Raspberry Pi), PyQt5 pip wheels are not
available. System packages must be installed once before building:

```bash
sudo bash build/install-deps-gui.sh
```

Supported distributions: Debian/Ubuntu (`apt`), Fedora/RHEL (`dnf`/`yum`),
Arch (`pacman`), openSUSE (`zypper`), Alpine (`apk`).

On x86\_64 the build script handles everything automatically — this step can be skipped.

### Step 3 — cloud-forge GUI (standalone binary via PyInstaller)

```bash
bash build/build-gui.sh
# Output: cloud-forge
```

The build script:
- Detects the Python interpreter (`python3` or `python`)
- Creates an isolated virtual environment under `build/.venv-build/`
- On ARM64: uses `--system-site-packages` to access the system PyQt5, installs only PyInstaller into the venv
- On x86\_64: installs PyQt5 and PyInstaller from pip, fully isolated
- Resolves a PyInstaller version compatible with the running Python automatically (no hardcoded version pin)
- Cleans up the venv after a successful build

> **Note:** Do not run `build-gui.sh` as root. It will refuse to proceed.
> Run `install-deps-gui.sh` with sudo separately if system packages are needed.

### Both at once

```bash
./install.sh --build
```

---

## Running the GUI from source

```bash
pip install PyQt5
python3 gui/cloud_forge.py
```

---

## rclone-sftp CLI

The `rclone-sftp` binary wraps `rclone serve sftp` with persistent server
management: PID tracking, log rotation, metadata persistence across restarts,
and three performance profiles.

### Commands

```
rclone-sftp start   REMOTE [PORT|auto] USER [PASS] [--password-file FILE] [--profile PROFILE]
rclone-sftp stop    REMOTE PORT
rclone-sftp stop-all
rclone-sftp restart REMOTE PORT USER [PASS] [--profile PROFILE]
rclone-sftp status  [--json]
rclone-sftp logs    REMOTE PORT [LINES]
rclone-sftp check   REMOTE PORT
rclone-sftp ports
rclone-sftp health  [--json]
rclone-sftp config  [KEY=VALUE ...]
rclone-sftp profiles
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
```

---

## Performance Profiles

Three built-in profiles tune rclone flags for different workloads.

### Light
Small files, minimal memory usage.

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 16M |
| `--transfers` | 2 |
| `--checkers` | 4 |
| `--sftp-concurrency` | 2 |
| `--vfs-cache-mode` | off |
| `--timeout` | 30m |

### Balanced *(default)*
Medium files, good all-round performance.

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 32M |
| `--transfers` | 4 |
| `--checkers` | 8 |
| `--sftp-concurrency` | 4 |
| `--vfs-cache-mode` | writes |
| `--vfs-cache-max-size` | 50G |
| `--vfs-cache-max-age` | 72h |
| `--vfs-read-chunk-size` | 32M |
| `--vfs-read-ahead` | 64M |
| `--timeout` | 1h |
| `--low-level-retries` | 10 |

### Heavy
Large files (100 GB+), maximum throughput.

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 64M |
| `--transfers` | 8 |
| `--checkers` | 16 |
| `--sftp-concurrency` | 8 |
| `--vfs-cache-mode` | full |
| `--vfs-cache-max-size` | 200G |
| `--vfs-cache-max-age` | 168h |
| `--vfs-read-chunk-size` | 64M |
| `--vfs-read-ahead` | 128M |
| `--timeout` | 2h |
| `--low-level-retries` | 20 |
| `--max-connections` | 20 |

Profile values can be customised at runtime without editing any config files:

```bash
rclone-sftp config heavy.vfs_cache_max_size=500G
rclone-sftp config balanced.transfers=8
```

---

## Configuration

Configuration is stored at `~/.local/share/rclone-sftp/config.json` and is
created automatically on first run.

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
| `config_path` | _(empty)_ | Path to rclone config file (uses rclone default if unset) |

### Profile keys

Prefix any profile parameter with `light.`, `balanced.`, or `heavy.`:

```bash
rclone-sftp config heavy.buffer_size=128M
rclone-sftp config balanced.vfs_cache_max_size=100G
rclone-sftp config light.timeout=1h
```

---

## Runtime Data

All runtime data is stored under `~/.local/share/rclone-sftp/`:

```
~/.local/share/rclone-sftp/
├── config.json                    # Main configuration
├── <remote>_<port>.pid            # PID file per running server
├── meta/
│   └── <remote>_<port>.json       # Persistent server metadata
├── logs/
│   └── <remote>_<port>.log        # Server log (auto-rotated, gzip compressed)
├── cache/                         # rclone VFS cache
└── temp/                          # rclone temp files
```

Server metadata (profile, start time, user, PID) is persisted to disk so that
`status`, `check`, and uptime display correctly after a program restart — even
if the underlying rclone process was started in a previous session.

---

## cloud-forge GUI

The desktop GUI provides a graphical interface for all `rclone` and
`rclone-sftp` operations.

### Remote Manager tab

| Button | Command |
|--------|---------|
| Add Remote | Opens `rclone config` in a terminal emulator |
| Refresh | `rclone listremotes --long` |
| Browse | `rclone lsd <remote>:` |
| Rename | `rclone config rename <old> <new>` |
| Dump Config | `rclone config dump` |
| Delete | `rclone config delete <remote>` |

### SFTP Servers tab

| Button | Action |
|--------|--------|
| Start Server | Dialog → `rclone-sftp start` |
| Stop | `rclone-sftp stop <remote> <port>` |
| Stop All | `rclone-sftp stop-all` |
| Restart | Dialog → `rclone-sftp restart` |
| Logs | `rclone-sftp logs <remote> <port>` |
| Check | `rclone-sftp check <remote> <port>` |
| Ports | `rclone-sftp ports` |
| Health | `rclone-sftp health` |
| Profiles | `rclone-sftp profiles` |
| Open in Files | Opens `sftp://user@127.0.0.1:<port>/` in the system file manager |

The server table auto-refreshes every 5 seconds. Running servers are
highlighted in green, stopped servers in red.

### Config tab

Set the default profile and apply custom `key=value` configuration directly
from the GUI.

### Binary discovery

The GUI locates `rclone-sftp` in this order:

1. `./bin/rclone-sftp` (relative to the `cloud-forge` binary)
2. `../bin/rclone-sftp`
3. `/usr/local/bin/rclone-sftp`
4. `/usr/bin/rclone-sftp`
5. `PATH`

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `RCLONE_SFTP_PASS` | Server password (alternative to passing on the command line) |
| `RCLONE_BINARY` | Path to rclone binary (defaults to `rclone` in `PATH`) |
| `RCLONE_CONFIG` | Path to rclone config file |

---

## Signal Handling

`rclone-sftp` handles `SIGINT` and `SIGTERM` gracefully — on receipt it stops
all running servers before exiting.

---

## Credits

- [rclone](https://rclone.org/) — the underlying cloud storage engine powering all SFTP serving and remote management. This project is a management and GUI layer built on top of `rclone serve sftp`.
- [PyQt5](https://riverbankcomputing.com/software/pyqt/) — desktop GUI framework.
