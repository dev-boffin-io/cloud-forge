#!/usr/bin/env bash
set -e

# ─── Resolve Paths ──────────────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

BIN_DIR="$PROJECT_ROOT/bin"
BUILD_DIR="$PROJECT_ROOT/build"
GUI_BIN="$PROJECT_ROOT/cloud-forge"
SFTP_BIN="$BIN_DIR/rclone-sftp"
ICON="$PROJECT_ROOT/cloud-forge.png"

DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/cloud-forge.desktop"

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
    echo "    ./install.sh           Install desktop entry only"
    echo "    ./install.sh --build   Build binaries, then install"
    echo "    ./install.sh --remove  Remove desktop entry"
    echo ""
}

# ─── Build ──────────────────────────────────────────────────────────────
do_build() {
    section "Building rclone-sftp (Go binary)"
    if [ ! -f "$BUILD_DIR/build-bin.sh" ]; then
        err "build-bin.sh not found at $BUILD_DIR/build-bin.sh"
        exit 1
    fi
    bash "$BUILD_DIR/build-bin.sh"

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
    ok "cloud-forge     : $GUI_BIN"

    if [ ! -f "$SFTP_BIN" ]; then
        err "rclone-sftp not found: $SFTP_BIN"
        err "Run './install.sh --build' to build first."
        exit 1
    fi
    ok "rclone-sftp     : $SFTP_BIN"

    if [ ! -f "$ICON" ]; then
        info "Icon not found: $ICON  (desktop entry will have no icon)"
        ICON=""
    else
        ok "Icon            : $ICON"
    fi
}

# ─── Desktop Entry ──────────────────────────────────────────────────────
do_desktop_entry() {
    section "Installing desktop entry"

    mkdir -p "$DESKTOP_DIR"

    cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=cloud-forge
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

    # Update desktop database if available
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi

    ok "Desktop entry installed: $DESKTOP_FILE"
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
}

# ─── Main ───────────────────────────────────────────────────────────────
echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║        cloud-forge installer         ║"
echo "  ╚══════════════════════════════════════╝"

case "${1:-}" in
    --build)
        do_build
        do_checks
        do_desktop_entry
        ;;
    --remove)
        do_remove
        ;;
    --help|-h)
        usage
        ;;
    "")
        do_checks
        do_desktop_entry
        ;;
    *)
        err "Unknown option: $1"
        usage
        exit 1
        ;;
esac

echo ""
ok "Done."
echo ""
