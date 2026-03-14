#!/usr/bin/env bash
set -euo pipefail

# ─── Resolve Paths ──────────────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

BIN_DIR="$PROJECT_ROOT/bin"
BUILD_DIR="$PROJECT_ROOT/build"
GUI_BIN="$PROJECT_ROOT/cloud-forge"
SFTP_BIN="$BIN_DIR/rclone-sftp"
ENGEN_BIN="$PROJECT_ROOT/rclone-engine"
ICON="$PROJECT_ROOT/cloud-forge.png"

DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/cloud-forge.desktop"

SYMLINK_DIRS=("$HOME/.local/bin" "/usr/local/bin")

# ─── Helper ─────────────────────────────────────────────────────────────
info()    { echo "  [INFO]  $*"; }
ok()      { echo "  [OK]    $*"; }
err()     { echo "  [ERROR] $*" >&2; }
section() { echo ""; echo "── $* ──────────────────────────────────────────"; }

# ─── Usage ──────────────────────────────────────────────────────────────
usage() {
    echo ""
    echo "  cloud-forge installer"
    echo ""
    echo "  Usage:"
    echo "    ./install.sh --build              Build all binaries (CLI + GUI)"
    echo "    ./install.sh --build --cli        Build CLI binaries only (rclone-sftp + rclone-engine)"
    echo "    ./install.sh --install            Install symlinks + desktop entry"
    echo "    ./install.sh --build --install    Build everything, then install"
    echo "    ./install.sh --remove             Remove symlinks and desktop entry"
    echo ""
}

# ─── Build CLI ──────────────────────────────────────────────────────────
build_cli() {
    section "Building rclone-sftp (Go binary)"
    if [ ! -f "$BUILD_DIR/build-bin.sh" ]; then
        err "build-bin.sh not found at $BUILD_DIR/build-bin.sh"
        exit 1
    fi
    bash "$BUILD_DIR/build-bin.sh"

    section "Building rclone-engine (Python binary)"
    if [ ! -f "$BUILD_DIR/build-main.sh" ]; then
        err "build-main.sh not found at $BUILD_DIR/build-main.sh"
        exit 1
    fi
    bash "$BUILD_DIR/build-main.sh"
}

# ─── Build GUI ──────────────────────────────────────────────────────────
build_gui() {
    section "Building cloud-forge GUI (PyInstaller)"
    if [ ! -f "$BUILD_DIR/build-gui.sh" ]; then
        err "build-gui.sh not found at $BUILD_DIR/build-gui.sh"
        exit 1
    fi
    bash "$BUILD_DIR/build-gui.sh"
}

# ─── Checks ─────────────────────────────────────────────────────────────
do_checks() {
    section "Checking binaries"

    if [ ! -f "$GUI_BIN" ]; then
        err "GUI binary not found: $GUI_BIN"
        err "Run './install.sh --build' to build first."
        exit 1
    fi
    ok "cloud-forge  : $GUI_BIN"

    if [ ! -f "$SFTP_BIN" ]; then
        err "rclone-sftp not found: $SFTP_BIN"
        err "Run './install.sh --build' to build first."
        exit 1
    fi
    ok "rclone-sftp  : $SFTP_BIN"

    if [ ! -f "$ENGEN_BIN" ]; then
        err "rclone-engine not found: $ENGEN_BIN"
        err "Run './install.sh --build' to build first."
        exit 1
    fi
    ok "rclone-engine : $ENGEN_BIN"

    if [ ! -f "$ICON" ]; then
        info "Icon not found: $ICON  (desktop entry will have no icon)"
        ICON=""
    else
        ok "Icon         : $ICON"
    fi
}

# ─── Symlink helper ─────────────────────────────────────────────────────
_make_symlink() {
    local binary="$1"
    local name="$2"
    local target=""

    for dir in "${SYMLINK_DIRS[@]}"; do
        if [ -d "$dir" ] && [ -w "$dir" ]; then
            target="$dir/$name"
            break
        fi
    done

    if [ -z "$target" ]; then
        mkdir -p "$HOME/.local/bin"
        target="$HOME/.local/bin/$name"
    fi

    if [ -L "$target" ] || [ -f "$target" ]; then
        rm -f "$target"
        info "Removed old: $target"
    fi

    ln -s "$binary" "$target"
    ok "Symlink: $target → $binary"

    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$(dirname "$target")"; then
        info "Note: $(dirname "$target") is not in PATH."
        info "Add to ~/.bashrc:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
}

# ─── Symlinks ────────────────────────────────────────────────────────────
do_symlinks() {
    section "Installing symlinks"
    _make_symlink "$SFTP_BIN"  "rclone-sftp"
    _make_symlink "$ENGEN_BIN" "rclone-engine"
}

# ─── Remove symlinks ─────────────────────────────────────────────────────
remove_symlinks() {
    section "Removing symlinks"
    for name in rclone-sftp rclone-engine; do
        for dir in "${SYMLINK_DIRS[@]}"; do
            target="$dir/$name"
            if [ -L "$target" ] || [ -f "$target" ]; then
                rm -f "$target"
                ok "Removed: $target"
            fi
        done
    done
}

# ─── Desktop Entry ──────────────────────────────────────────────────────
do_desktop_entry() {
    section "Installing desktop entry"

    mkdir -p "$DESKTOP_DIR"

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Cloud Forge
Comment=rclone Cloud Storage & SFTP Server Manager
Exec=$GUI_BIN
Icon=$ICON
Terminal=false
Categories=Network;FileTransfer;Utility;
Keywords=rclone;sftp;cloud;storage;gdrive;
StartupNotify=true
StartupWMClass=cloud-forge
EOF

    chmod +x "$DESKTOP_FILE"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi

    ok "Desktop entry: $DESKTOP_FILE"
    info "You can now launch cloud-forge from your application menu."
}

# ─── Remove ─────────────────────────────────────────────────────────────
do_remove() {
    section "Removing desktop entry"
    if [ -f "$DESKTOP_FILE" ]; then
        rm -f "$DESKTOP_FILE"
        if command -v update-desktop-database >/dev/null 2>&1; then
            update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
        fi
        ok "Removed: $DESKTOP_FILE"
    else
        info "Desktop entry not found, nothing to remove."
    fi
    remove_symlinks
}

# ─── Main ───────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        cloud-forge installer         ║"
echo "  ╚══════════════════════════════════════╝"

if [ $# -eq 0 ]; then
    usage
    exit 0
fi

DO_BUILD=false
DO_INSTALL=false
CLI_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --build)   DO_BUILD=true ;;
        --install) DO_INSTALL=true ;;
        --cli)     CLI_ONLY=true ;;
        --remove)
            do_remove
            echo ""
            ok "Done."
            echo ""
            exit 0
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            err "Unknown option: $arg"
            usage
            exit 1
            ;;
    esac
done

if ! $DO_BUILD && ! $DO_INSTALL; then
    err "Specify at least --build or --install."
    usage
    exit 1
fi

if $DO_BUILD; then
    build_cli
    if ! $CLI_ONLY; then
        build_gui
    fi
fi

if $DO_INSTALL; then
    do_checks
    do_symlinks
    if ! $CLI_ONLY; then
        do_desktop_entry
    fi
fi

echo ""
ok "Done."
echo ""
