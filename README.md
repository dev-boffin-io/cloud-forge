# cloud-forge

A suite of tools for managing **rclone cloud storage remotes** and **SFTP servers** on Linux — featuring a Go CLI (`rclone-sftp`), a Python rclone manager (`rclone-engine`), a cross-platform terminal launcher (`cf-config-launcher`), and a full-featured PyQt5 desktop GUI (`cloud-forge`).

The project is designed to be **self-contained**, **portable**, and **offline-first** — all binaries are statically compiled or bundled, and no internet connection is required to run the SFTP servers after initial setup.

---

## Overview

| Component | Language | Binary | Description |
|-----------|----------|--------|-------------|
| `rclone-sftp` | Go | `bin/rclone-sftp` | CLI — start, stop, and manage rclone SFTP servers with profiles, log rotation, and metadata persistence |
| `rclone-engine` | Python | `rclone-engine` | CLI — install, update, upgrade, and uninstall the rclone binary itself |
| `cf-config-launcher` | Go | `bin/cf-config-launcher` | Helper binary — opens `rclone config` (or any rclone subcommand) in the correct terminal emulator |
| `cloud-forge` | Python / PyQt5 | `cloud-forge` | Desktop GUI — graphical frontend for all of the above |

---

## How It Works

```
cloud-forge (GUI)
    │
    ├── rclone              ← manages cloud storage remotes (OAuth, config)
    │
    ├── rclone-sftp         ← wraps "rclone serve sftp" with process management
    │       │
    │       └── exposes remotes as local SFTP servers on 127.0.0.1:<port>
    │
    ├── rclone-engine       ← installs / upgrades rclone itself
    │
    └── cf-config-launcher  ← opens rclone config in a terminal (for OAuth)
```

Any SFTP-capable client (file manager, `sftp`, `scp`, `rsync`) can connect to
the local server once it is running.

---

## Project Structure

```
cloud-forge/
├── bin/
│   ├── rclone-sftp              # Compiled Go binary — SFTP server manager
│   └── cf-config-launcher       # Compiled Go binary — terminal launcher
│
├── build/
│   ├── build-bin.sh             # Build Go binaries (rclone-sftp + cf-config-launcher)
│   ├── build-main.sh            # Build rclone-engine (PyInstaller single-file)
│   ├── build-gui.sh             # Build cloud-forge GUI (PyInstaller single-file)
│   └── install-deps-gui.sh      # Install PyQt5 system packages (ARM64 / PRoot)
│
├── gui/
│   ├── cloud_forge.py           # Entry point — main() + single-instance guard
│   ├── theme.py                 # DARK color palette + Qt stylesheet
│   ├── workers.py               # CmdWorker (QThread), OutputBox, BaseRunner mixin
│   ├── dialogs.py               # AddRemoteDialog (18 providers), RenameDialog, StartServerDialog
│   ├── tab_remote.py            # Remote Manager tab + OneDrive Fix Drive (Graph API)
│   ├── tab_server.py            # SFTP Servers tab
│   ├── tab_config.py            # Config tab
│   └── window.py                # MainWindow — binary discovery, tray, advanced mode, QSettings
│
├── src/
│   ├── rclone_engine.py         # rclone installer/updater source (Python)
│   ├── cf-config-launcher/
│   │   ├── go.mod
│   │   └── main.go              # Terminal launcher source
│   └── rclone-sftp/
│       ├── go.mod
│       └── main.go              # SFTP server manager source
│
├── cloud-forge                  # Compiled GUI binary (produced by build-gui.sh)
├── rclone-engine                # Compiled rclone manager binary (produced by build-main.sh)
├── cloud-forge.png              # Application icon (512×512)
├── Makefile                     # Unified build and install targets
├── install.sh                   # Installer — builds, symlinks, desktop entry
└── README.md
```

---

## Requirements

### Runtime

- **[rclone](https://rclone.org/)** — the underlying cloud storage engine.
  Must be installed and available in `PATH`. Use `rclone-engine install` to
  install it automatically if not already present.
- **Linux desktop environment** with a file manager that supports `sftp://` URIs
  (Thunar, Nautilus, Dolphin, Nemo, etc.) — only required for the
  "Open in Files" feature. The CLI tools work on any Linux system.

### Build

| Tool | Version | Purpose |
|------|---------|---------|
| Go | 1.21+ | Compile `rclone-sftp` and `cf-config-launcher` |
| Python | 3.9+ | Build `rclone-engine` and `cloud-forge` via PyInstaller |
| PyQt5 | any | GUI framework (system package on ARM64, pip on x86_64) |
| PyInstaller | any | Bundle Python scripts into standalone binaries |

---

## Quick Start

### Standard Linux (x86_64)

```bash
# Clone the repository
git clone https://github.com/dev-boffin-io/cloud-forge
cd cloud-forge

# Build everything and install
make install
```

This builds all four binaries, places symlinks in `~/.local/bin/` (or
`/usr/local/bin/` if writable), and installs a `.desktop` entry so
`cloud-forge` appears in the application menu.

### ARM64 / PRoot (Android Termux, Raspberry Pi, etc.)

PyQt5 pip wheels are not published for ARM64. System packages must be
installed once before building the GUI:

```bash
make deps      # runs install-deps-gui.sh with sudo — installs python3-pyqt5
make install
```

`make deps` auto-detects the package manager (`apt`, `dnf`, `pacman`,
`zypper`, `apk`) and installs the correct packages for the distribution.

### CLI only (no GUI)

If you only need the server manager and rclone installer:

```bash
make install-cli
# Installs: rclone-sftp, rclone-engine, cf-config-launcher symlinks
# Does not build or install the cloud-forge GUI
```

---

## Makefile Targets

| Target | Description |
|--------|-------------|
| `make deps` | Install GUI system dependencies via package manager (requires sudo) |
| `make build` | Build all binaries — `rclone-sftp`, `cf-config-launcher`, `rclone-engine`, `cloud-forge` |
| `make build-cli` | Build CLI binaries only — `rclone-sftp`, `cf-config-launcher`, `rclone-engine` |
| `make build-gui` | Build GUI binary only — `cloud-forge` |
| `make install` | Build everything, then install symlinks + desktop entry |
| `make install-only` | Install pre-built binaries — symlinks + desktop entry, no build |
| `make install-cli` | Build CLI only, then install symlinks (no desktop entry) |
| `make uninstall` | Remove all symlinks and the desktop entry |
| `make clean` | Remove all compiled binaries and build artefacts |
| `make help` | Print a summary of all available targets |

Run `make` with no arguments to show the help message.

---

## install.sh

The installer script is called by `make` targets but can also be used
directly for more control.

```bash
# Build all binaries (no install)
./install.sh --build

# Build CLI binaries only
./install.sh --build --cli

# Install pre-built binaries (symlinks + desktop entry)
./install.sh --install

# Build everything then install in one step
./install.sh --build --install

# CLI build + CLI symlinks only (no desktop entry)
./install.sh --build --install --cli

# Remove everything that was installed
./install.sh --remove
```

### What `--install` does

1. Checks that `cloud-forge`, `bin/rclone-sftp`, `bin/cf-config-launcher`,
   and `rclone-engine` binaries exist.
2. Creates symlinks in `~/.local/bin/` (falls back to `/usr/local/bin/` if
   writable) for `rclone-sftp`, `cf-config-launcher`, and `rclone-engine`.
3. Installs `~/.local/share/applications/cloud-forge.desktop` and runs
   `update-desktop-database` if available.

---

## Building Individually

### Go binaries (rclone-sftp + cf-config-launcher)

```bash
bash build/build-bin.sh
# Output: bin/rclone-sftp
#         bin/cf-config-launcher
```

Each binary lives in its own Go module under `src/`. The build script:
- Cleans the Go build cache before each build (`go clean -cache`)
- Removes `go.mod` and `go.sum` for a fully reproducible fresh build
- Runs `go mod init` and `go mod tidy` automatically
- Builds with `CGO_ENABLED=0 -trimpath -ldflags="-s -w"` for a small,
  portable, statically linked binary
- Supports cross-compilation via `GOOS` / `GOARCH` environment variables

### rclone-engine (Python binary)

```bash
bash build/build-main.sh
# Output: rclone-engine
```

The build script:
- Creates an isolated virtualenv under `build/.pyinstaller/venv/`
- Installs PyInstaller into the venv
- Builds a single-file binary with `--onefile`
- Removes the venv and all PyInstaller artefacts on completion

### cloud-forge GUI

```bash
bash build/build-gui.sh
# Output: cloud-forge
```

On ARM64 the build uses `--system-site-packages` so PyInstaller can access
the system-installed PyQt5. On x86_64 PyQt5 is installed from pip into the
build venv. The venv and artefacts are removed after a successful build.

---

## rclone-engine

`rclone-engine` manages the `rclone` binary itself — download, install,
upgrade, and remove — without visiting the rclone website manually.
Architecture is detected automatically (amd64, arm64, arm-v7).

### Commands

| Command | Description |
|---------|-------------|
| `install` | Download and install the latest rclone. Skips if already installed. |
| `update` | Check if a newer version is available and report. |
| `upgrade` | Download and replace the existing rclone with the latest version. |
| `uninstall` | Remove the installed rclone binary. |
| `version` | Print the currently installed rclone version string. |

### How install works

1. Tries GitHub API (`/repos/rclone/rclone/releases/latest`) first.
2. Falls back to `https://downloads.rclone.org/version.txt` if GitHub is
   unavailable.
3. Downloads `rclone-current-linux-<arch>.zip` with a live progress bar.
4. Extracts the binary and copies it to the first writable location:
   `/usr/local/bin/rclone` → `~/.local/bin/rclone`.

### Examples

```bash
# Install rclone for the first time
rclone-engine install

# Check for a newer version
rclone-engine update
# Installed version : v1.68.0
# Latest version    : v1.69.1
# Update available.

# Upgrade to the latest version
rclone-engine upgrade

# Show what is currently installed
rclone-engine version
# Installed version: v1.69.1

# Remove rclone
rclone-engine uninstall
# Removed /usr/local/bin/rclone
```

---

## cf-config-launcher

A small Go binary that opens `rclone config` (or any rclone subcommand) in
the appropriate terminal emulator on the current platform. It is used
internally by the GUI to handle OAuth authentication flows, but can also be
called directly.

### Usage

```bash
# Open rclone config in a terminal (equivalent to running rclone config manually)
cf-config-launcher

# Open rclone config reconnect for a specific remote
cf-config-launcher reconnect myremote

# Pass arbitrary rclone arguments
cf-config-launcher config dump
```

### Terminal detection (Linux)

The launcher tries terminals in this order and uses the first one found:

1. `x-terminal-emulator` (Debian/Ubuntu alternatives system)
2. `gnome-terminal`
3. `konsole`
4. `xfce4-terminal`
5. `mate-terminal`
6. `lxterminal`
7. `alacritty`
8. `kitty`
9. `xterm`

If no terminal is found, the command is run directly in the current terminal
with stdin/stdout attached (useful in PRoot environments).

### Platform support

| Platform | Method |
|----------|--------|
| Linux | Detected terminal emulator (see above) |
| macOS | `Terminal.app` via AppleScript |
| Windows | PowerShell (preferred) or CMD |

---

## rclone-sftp CLI

`rclone-sftp` wraps `rclone serve sftp` with a full process management layer:
PID tracking, automatic log rotation with gzip compression, metadata
persistence that survives restarts, VFS cache management, auto-port assignment,
disk space checks, and three tunable performance profiles.

Once a server is started, any SSH/SFTP client can connect to it at
`127.0.0.1:<port>` using the username and password you provided.

### Commands

| Command | Description |
|---------|-------------|
| `start REMOTE [PORT\|auto] USER [PASS]` | Start an SFTP server for a remote |
| `stop REMOTE PORT` | Stop a specific server |
| `stop-all` | Stop all running servers |
| `restart REMOTE PORT USER [PASS]` | Stop and restart a server |
| `status [--json]` | Show all running servers (plain text or JSON) |
| `logs REMOTE PORT [LINES]` | Show the last N lines of a server's log (default 50) |
| `check REMOTE PORT` | Check port status, PID, profile, uptime, and cache size |
| `ports` | List all active ports from PID files |
| `health [--json]` | System health report — rclone, disk space, active servers |
| `config [KEY=VALUE ...]` | Show or update configuration |
| `profiles` | Show all performance profiles and their current values |
| `clear-cache [REMOTE PORT]` | Clear VFS cache — all servers or one specific server |
| `connect [REMOTE PORT]` | Print ready-to-use SSH/SFTP/SCP/rsync connection commands |

### Optional flags for start / restart

| Flag | Description |
|------|-------------|
| `--profile PROFILE` | Use a specific profile: `light`, `balanced`, `heavy` (default: config value) |
| `--password-file FILE` | Read password from a file instead of the command line |

Password can also be provided via the `RCLONE_SFTP_PASS` environment variable
to avoid it appearing in shell history.

### Examples

```bash
# Start gdrive on an auto-assigned port with the heavy profile
rclone-sftp start gdrive auto sumit mypassword --profile heavy
# [INFO] Auto-assigned port: 8023
# [OK] Server started: gdrive:8023 (PID: 12345)

# Start with password from file (password never visible in shell history)
rclone-sftp start gdrive auto sumit --password-file ~/.sftp-pass

# Start with password from environment variable
RCLONE_SFTP_PASS=mypassword rclone-sftp start gdrive 8888 sumit

# Check status (table output)
rclone-sftp status
# REMOTE  PORT  PID    PROFILE   STATUS   UPTIME     CACHE  SPEED
# gdrive  8888  12345  heavy     running  1h23m45s   2.1 GB  --

# Check status as JSON (useful for scripts)
rclone-sftp status --json

# Print connection commands for all running servers
rclone-sftp connect
# ── gdrive (port 8888) ─────────────────────────────────
#   SSH  :  ssh  -p 8888 sumit@127.0.0.1
#   SFTP :  sftp -P 8888 sumit@127.0.0.1
#   SCP  :  scp  -P 8888 <file> sumit@127.0.0.1:/
#   rsync:  rsync -avz -e "ssh -p 8888" <src> sumit@127.0.0.1:<dst>

# Show last 100 log lines
rclone-sftp logs gdrive 8888 100

# Detailed check for one server
rclone-sftp check gdrive 8888

# System health report
rclone-sftp health

# Set default profile to heavy for all new servers
rclone-sftp config heavy

# Override a single profile parameter without touching anything else
rclone-sftp config heavy.vfs_cache_max_size=500G heavy.transfers=16

# Clear all VFS cache (frees disk space)
rclone-sftp clear-cache

# Clear cache only for a specific server
rclone-sftp clear-cache gdrive 8888

# Gracefully stop a server
rclone-sftp stop gdrive 8888

# Stop all running servers at once
rclone-sftp stop-all
```

---

## Performance Profiles

Three built-in profiles tune the underlying rclone flags for different
workloads. The default profile is `balanced`. Switch the default globally with
`rclone-sftp config <profile>` or per-server with `--profile` at start time.

### Light — small files, low memory footprint

Suitable for browsing, small file transfers, or memory-constrained devices.

| Parameter | Value |
|-----------|-------|
| `--buffer-size` | 16M |
| `--transfers` | 2 |
| `--checkers` | 4 |
| `--sftp-concurrency` | 2 |
| `--vfs-cache-mode` | off |
| `--timeout` | 30m |

### Balanced *(default)* — medium files, good all-round performance

The recommended starting point for most users.

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
| `--contimeout` | 2m |
| `--low-level-retries` | 10 |

### Heavy — large files 100GB+, maximum throughput

For large media libraries, backups, or sustained high-bandwidth transfers.

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
| `--contimeout` | 5m |
| `--low-level-retries` | 20 |
| `--max-connections` | 20 |

### Customising profiles at runtime

Any profile parameter can be overridden without editing files. Changes are
persisted to `config.json` immediately.

```bash
# Increase cache size for the heavy profile
rclone-sftp config heavy.vfs_cache_max_size=500G

# Increase transfers for balanced
rclone-sftp config balanced.transfers=8

# Reduce cache age to reclaim disk faster
rclone-sftp config heavy.vfs_cache_max_age=24h
rclone-sftp config balanced.vfs_cache_max_age=12h

# See all current profile values
rclone-sftp profiles
```

---

## Configuration

All configuration is stored at `~/.local/share/rclone-sftp/config.json` and
is created with defaults on first run. Use `rclone-sftp config` to view or
modify it without editing JSON directly.

### Global keys

| Key | Default | Description |
|-----|---------|-------------|
| `profile` | `balanced` | Default profile applied to new servers |
| `cache_dir` | `~/.local/share/rclone-sftp/cache` | VFS cache root directory |
| `temp_dir` | `~/.local/share/rclone-sftp/temp` | Rclone temp file directory |
| `log_dir` | `~/.local/share/rclone-sftp/logs` | Log file directory |
| `log_size` | `50` (MB) | Log file size before rotation |
| `max_log_files` | `5` | Number of gzip-compressed rotated log files to keep |
| `max_disk_mb` | `1024` | Minimum free disk space (MB) required to start a server |
| `port_range_from` | `8022` | Start of the auto-assignment port range |
| `port_range_to` | `9000` | End of the auto-assignment port range |
| `verbose` | `false` | Enable rclone `-vv` verbose logging |
| `config_path` | _(empty)_ | Explicit path to rclone config file (uses rclone default if empty) |

### Profile-specific keys

Prefix any profile parameter with `light.`, `balanced.`, or `heavy.`:

```bash
rclone-sftp config light.buffer_size=32M
rclone-sftp config balanced.vfs_cache_max_size=100G
rclone-sftp config heavy.buffer_size=128M heavy.transfers=16
```

### Viewing the full config

```bash
rclone-sftp config
# Prints the full config.json to stdout
```

---

## Runtime Data

All runtime state is stored under `~/.local/share/rclone-sftp/`:

```
~/.local/share/rclone-sftp/
├── config.json                    # Global + profile configuration
├── <remote>_<port>.pid            # PID file — one per running server
├── meta/
│   └── <remote>_<port>.json       # Persisted server metadata:
│                                  #   remote, port, user, profile, start_time, pid
├── logs/
│   ├── <remote>_<port>.log        # Active log file (tailed by `logs` command)
│   └── <remote>_<port>.log.<ts>.gz  # Rotated + gzip-compressed archives
├── cache/                         # rclone VFS cache (can grow large on heavy profile)
└── temp/                          # rclone temporary files
```

**Metadata persistence** means that `rclone-sftp status` and `rclone-sftp
check` correctly report uptime, profile, and username even after the
`rclone-sftp` process itself has exited and been restarted — as long as the
underlying rclone serve process is still running.

**Log rotation** runs automatically every 5 minutes in the background.
When a log file exceeds `log_size`, it is renamed with a timestamp, compressed
to gzip, and the oldest files beyond `max_log_files` are pruned.

---

## cloud-forge GUI

The desktop GUI provides a graphical interface for all cloud storage and SFTP
server management operations.

### Window layout

The window has a fixed **header bar** at the top containing the app logo,
binary status indicator, **🔧 CF Config** button, and **⚙ Advanced** toggle.
Below the header are three tabs.

### Advanced mode

Click **⚙ Advanced: OFF** to reveal power-user controls that are hidden by
default to keep the interface clean for everyday use:

- **Remote Manager tab**: Rename, Dump Config, and a free-form rclone
  command input field with a Run button
- **SFTP Servers tab**: Logs, Ports, Health, and Profiles buttons
- **Config tab**: appears as a full tab (hidden in normal mode)

Window geometry, the last active tab, and the advanced mode state are all
saved between sessions via `QSettings`.

### System tray

When the window is closed, `cloud-forge` minimises to the system tray instead
of quitting. Double-click the tray icon to restore the window. Right-click for
Show / Quit options. A notification is shown when the window is first minimised.

### Single instance

Only one instance of `cloud-forge` can run at a time. If a second instance is
launched, it signals the running instance to raise its window and then exits
immediately.

---

### Remote Manager tab

Manages rclone remotes — the cloud storage accounts and connections that rclone
knows about.

| Button | Action | Notes |
|--------|--------|-------|
| **＋ Add Remote** | Opens the Add Remote wizard | Supports 18 providers |
| **↻ Refresh** | `rclone listremotes --long` | Updates the remote list |
| **⊞ Browse** | `rclone lsd <remote>:` | Lists top-level directories |
| **✕ Delete** | `rclone config delete <remote>` | Asks for confirmation |
| **🔧 Fix Drive** | Sets `drive_id` + `drive_type` for OneDrive | Uses Microsoft Graph API |
| **✎ Rename** | `rclone config rename` | Advanced mode only |
| **⬇ Dump Config** | `rclone config dump` | Shows full config JSON — Advanced mode only |
| **▶ Run** | Execute a free-form rclone command | Advanced mode only |

#### Add Remote wizard

The wizard supports **18 providers**:

| Provider | Auth type |
|----------|-----------|
| Google Drive | OAuth (browser) |
| Google Photos | OAuth (browser) |
| OneDrive | OAuth (browser) + Fix Drive required |
| Dropbox | OAuth (browser) |
| Amazon S3 | Access key + secret |
| Backblaze B2 | Account ID + application key |
| SFTP | Host / user / password or key file |
| FTP | Host / user / password |
| WebDAV | URL / vendor / user / password |
| pCloud | OAuth (browser) |
| Mega | Username + password |
| Box | OAuth (browser) |
| Yandex Disk | OAuth (browser) |
| iCloud Drive | Apple ID + password |
| Cloudflare R2 | Access key + secret + endpoint |
| Wasabi | Access key + secret + endpoint |
| HTTP (read-only) | URL only |
| Local filesystem | No credentials |

Sensitive values (passwords, secret keys) are passed via environment variables
rather than CLI arguments so they never appear in the process list.

#### OAuth flow

For OAuth providers the wizard:
1. Creates the rclone config entry with `--non-interactive` (no browser yet)
2. Runs `rclone config reconnect <name>:` via `cf-config-launcher`, which
   opens a terminal and answers `y` to the "Use web browser?" prompt
3. Your default browser opens the provider's sign-in page
4. After signing in, click **Refresh** to reload the remote list

#### OneDrive — Fix Drive

OneDrive requires `drive_id` and `drive_type` to be set after OAuth. After
signing in:

1. Select the `onedrive` remote in the table
2. Click **🔧 Fix Drive**
3. The GUI reads the access token from `rclone config dump`, calls
   `https://graph.microsoft.com/v1.0/me/drive`, and writes `drive_id` +
   `drive_type` back with `rclone config update --non-interactive`

---

### SFTP Servers tab

Manages running rclone SFTP servers. The table auto-refreshes every 5 seconds.
Running servers are highlighted green, stopped servers red.

| Button | Action | Notes |
|--------|--------|-------|
| **▶ Start Server** | Opens dialog → `rclone-sftp start` | Choose remote, port, user, password, profile |
| **■ Stop** | `rclone-sftp stop <remote> <port>` | Select a row first |
| **⬛ Stop All** | `rclone-sftp stop-all` | Asks for confirmation |
| **↺ Restart** | Opens restart dialog → `rclone-sftp restart` | Pre-fills remote and port |
| **✓ Check** | `rclone-sftp check <remote> <port>` | Shows port, PID, profile, uptime, cache |
| **📂 Open in Files** | `xdg-open sftp://user@127.0.0.1:<port>/` | Server must be running |
| **🔗 Copy URL** | Copies `sftp://user@127.0.0.1:<port>/` to clipboard | — |
| **🗑 Clear Cache** | `rclone-sftp clear-cache [remote port]` | Clears selected server or all |
| **≡ Logs** | `rclone-sftp logs <remote> <port> 80` | Advanced mode only |
| **⊡ Ports** | `rclone-sftp ports` | Advanced mode only |
| **♥ Health** | `rclone-sftp health` | Advanced mode only |
| **⚙ Profiles** | `rclone-sftp profiles` | Advanced mode only |

The username for the file manager URL and Copy URL is read from the metadata
file at `~/.local/share/rclone-sftp/meta/<remote>_<port>.json` — this means
it is correct even after a GUI restart.

---

### Config tab *(Advanced mode only)*

| Control | Action |
|---------|--------|
| Profile dropdown + **Set Default** | `rclone-sftp config <profile>` |
| Key=value input + **Apply** | `rclone-sftp config key=value ...` |
| **Show Full Config** | `rclone-sftp config` (prints full JSON) |
| **Show Profiles** | `rclone-sftp profiles` |

---

### CF Config button

The **🔧 CF Config** button in the header bar launches `cf-config-launcher`
with no arguments, which opens `rclone config` in a terminal. This is the
escape hatch for anything the GUI wizard does not support — manually editing
remotes, adding obscure providers, troubleshooting.

---

### Binary discovery

`window.py` locates each binary by checking candidates in order:

```
<exe_dir>/bin/<binary>         (./bin/ relative to cloud-forge binary)
<exe_dir>/../bin/<binary>      (../bin/)
<exe_dir>/<binary>             (same directory)
/usr/local/bin/<binary>
/usr/bin/<binary>
PATH (shutil.which)
```

`<exe_dir>` is `sys.executable.parent` when running as a PyInstaller bundle,
or `__file__.parent` when running from source.

---

## Connecting via CLI

The `rclone-sftp connect` command prints ready-to-use connection strings for
all running servers (or one specific server):

```bash
rclone-sftp connect

# ── gdrive (port 8888) ──────────────────────────────────────
#   SSH  :  ssh  -p 8888 sumit@127.0.0.1
#   SFTP :  sftp -P 8888 sumit@127.0.0.1
#   SCP  :  scp  -P 8888 <file> sumit@127.0.0.1:/
#   rsync:  rsync -avz -e "ssh -p 8888" <src> sumit@127.0.0.1:<dst>
```

### SSH

```bash
ssh -p 8888 sumit@127.0.0.1
```

### SFTP (interactive session)

```bash
sftp -P 8888 sumit@127.0.0.1

# Common SFTP commands inside the session:
sftp> ls                         # list remote files
sftp> cd /some/dir               # change remote directory
sftp> put /local/file.txt        # upload a file
sftp> get /remote/file.txt       # download a file
sftp> bye                        # exit
```

### SCP

```bash
# Upload
scp -P 8888 /path/to/file.txt sumit@127.0.0.1:/remote/path/

# Download
scp -P 8888 sumit@127.0.0.1:/remote/path/file.txt /local/path/
```

### rsync

```bash
# Sync local directory → remote
rsync -avz -e "ssh -p 8888" /local/dir/ sumit@127.0.0.1:/remote/path/

# Sync remote → local
rsync -avz -e "ssh -p 8888" sumit@127.0.0.1:/remote/path/ /local/dir/
```

> **Note:** SSH port flag is lowercase `-p`; SFTP and SCP use uppercase `-P`.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RCLONE_SFTP_PASS` | _(empty)_ | Server password — avoids passing on the command line |
| `RCLONE_BINARY` | `rclone` | Full path to the rclone binary |
| `RCLONE_CONFIG` | _(rclone default)_ | Full path to the rclone config file |

---

## Signal Handling

`rclone-sftp` installs handlers for `SIGINT` (Ctrl+C) and `SIGTERM`. On
receipt, it sends `SIGTERM` to all managed rclone serve processes, waits up
to 10 seconds for each to exit, then sends `SIGKILL` if necessary, before
cleaning up PID files and metadata and exiting cleanly.

---

## Credits

- **[rclone](https://rclone.org/)** — the underlying cloud storage engine that
  powers all remote management and SFTP serving. `cloud-forge` is a management
  and GUI layer built on top of `rclone serve sftp`.
- **[PyQt5](https://riverbankcomputing.com/software/pyqt/)** — Qt5 bindings
  for Python, used for the desktop GUI.
