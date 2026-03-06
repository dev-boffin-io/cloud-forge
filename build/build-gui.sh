#!/usr/bin/env bash
set -e

# ─── Resolve Project Root ───────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
GUI_DIR="$PROJECT_ROOT/gui"
BIN_DIR="$PROJECT_ROOT/bin"
SFTP_BIN="$BIN_DIR/rclone-sftp"
DIST_BIN="$GUI_DIR/dist/cloud-forge"
TARGET_BIN="$PROJECT_ROOT/cloud-forge"

echo "Building Cloud Forge GUI..."

# ─── Check Requirements ─────────────────────────────────────────────────
if ! command -v pyinstaller >/dev/null 2>&1; then
    echo "PyInstaller not found. Install with: pip install pyinstaller"
    exit 1
fi

if [ ! -f "$GUI_DIR/cloud_forge.py" ]; then
    echo "GUI file not found: $GUI_DIR/cloud_forge.py"
    exit 1
fi

# ─── Clean Previous Builds ──────────────────────────────────────────────
rm -rf "$GUI_DIR/build" \
       "$GUI_DIR/dist" \
       "$GUI_DIR/__pycache__" \
       "$GUI_DIR"/*.spec \
       "$TARGET_BIN"

# ─── Build Arguments ────────────────────────────────────────────────────
cd "$GUI_DIR"

PYINSTALLER_ARGS=(
    --onefile
    --windowed
    --name cloud-forge
    --clean
)

# rclone-sftp binary পাশে রাখি (bundle করি না, শুধু path hint দিই)
# PyInstaller-এ --add-binary দিলে _MEIPASS-এ যায়, exe-র পাশে নয়
# তাই আমরা exe-র পাশে bin/ ফোল্ডারে রাখব — post-build step-এ

pyinstaller "${PYINSTALLER_ARGS[@]}" cloud_forge.py

# ─── Move Binary To Project Root ────────────────────────────────────────
if [ ! -f "$DIST_BIN" ]; then
    echo "Build failed. Binary not found at: $DIST_BIN"
    exit 1
fi

mv "$DIST_BIN" "$TARGET_BIN"
chmod +x "$TARGET_BIN"

# ─── Place rclone-sftp next to the binary ───────────────────────────────
# cloud-forge binary খোঁজে: ./bin/rclone-sftp (exe-র পাশে)
RUNTIME_BIN_DIR="$PROJECT_ROOT/bin"

if [ -f "$SFTP_BIN" ]; then
    # bin/ already exists with rclone-sftp — nothing to do
    echo "rclone-sftp found at: $SFTP_BIN"
else
    echo "WARNING: $SFTP_BIN not found."
    echo "         cloud-forge will try PATH to find rclone-sftp."
fi

# ─── Cleanup ────────────────────────────────────────────────────────────
rm -rf "$GUI_DIR/build" \
       "$GUI_DIR/dist" \
       "$GUI_DIR/__pycache__" \
       "$GUI_DIR"/*.spec

echo ""
echo "Build complete!"
echo "Binary : $TARGET_BIN"
echo ""
echo "Expected layout:"
echo "  $PROJECT_ROOT/"
echo "  ├── cloud-forge        (this binary)"
echo "  └── bin/"
echo "      └── rclone-sftp   (sftp manager binary)"
