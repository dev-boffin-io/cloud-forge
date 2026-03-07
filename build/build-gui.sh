#!/usr/bin/env bash
# =============================================================
#  cloud-forge — GUI Build Script (no root required)
#  Usage: ./build/build-gui.sh
#
#  ARM64/PRoot: run sudo ./build/install-deps-gui.sh first
# =============================================================
set -euo pipefail

# ─── Resolve Project Root ───────────────────────────────────────────────
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"
GUI_DIR="$PROJECT_ROOT/gui"
BIN_DIR="$PROJECT_ROOT/bin"
SFTP_BIN="$BIN_DIR/rclone-sftp"
DIST_BIN="$GUI_DIR/dist/cloud-forge"
TARGET_BIN="$PROJECT_ROOT/cloud-forge"
VENV_DIR="$SCRIPT_DIR/.venv-build"
DEPS_SCRIPT="$SCRIPT_DIR/install-deps-gui.sh"

echo "Building Cloud Forge GUI..."

# ─── Must NOT run as root ────────────────────────────────────────────────
if [ "$(id -u)" -eq 0 ]; then
    echo "ERROR: Do not run this script as root."
    echo "       For system dependencies run: sudo $DEPS_SCRIPT"
    exit 1
fi

# ─── Detect Python binary ────────────────────────────────────────────────
PY_BIN=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        PY_BIN="$(command -v "$candidate")"
        break
    fi
done || true   # loop exit code irrelevant — we check PY_BIN below

if [ -z "$PY_BIN" ]; then
    echo "ERROR: No Python interpreter found."
    echo "       Install Python 3 and re-run this script."
    exit 1
fi

echo "Python : $PY_BIN ($($PY_BIN --version 2>&1))"

# ─── Check source file ───────────────────────────────────────────────────
if [ ! -f "$GUI_DIR/cloud_forge.py" ]; then
    echo "ERROR: GUI source not found: $GUI_DIR/cloud_forge.py"
    exit 1
fi

# ─── Detect architecture ─────────────────────────────────────────────────
IS_ARM64=0
[ "$(uname -m)" = "aarch64" ] && IS_ARM64=1

# ─── ARM64: verify system deps installed (no install, no sudo) ───────────
arm64_preflight() {
    echo ""
    echo "ARM64 detected — verifying system PyQt5..."

    MISSING=""

    if ! "$PY_BIN" -c "from PyQt5 import QtCore" 2>/dev/null; then
        MISSING="${MISSING} python3-pyqt5"
    fi

    # libGL — ctypes probe first, then dpkg/rpm fallback
    HAS_GL=0
    if "$PY_BIN" -c "import ctypes; ctypes.CDLL('libGL.so.1')" 2>/dev/null; then
        HAS_GL=1
    elif command -v dpkg >/dev/null 2>&1; then
        for pkg in libgl1-mesa-dev libgl1; do
            dpkg -s "$pkg" >/dev/null 2>&1 && HAS_GL=1 && break
        done
    elif command -v rpm >/dev/null 2>&1; then
        rpm -q mesa-libGL >/dev/null 2>&1 && HAS_GL=1
    fi
    [ "$HAS_GL" -eq 0 ] && MISSING="${MISSING} libgl1-mesa-dev"

    # libxcb-xinerama
    HAS_XCB=0
    if "$PY_BIN" -c "import ctypes; ctypes.CDLL('libxcb-xinerama.so.0')" 2>/dev/null; then
        HAS_XCB=1
    elif command -v dpkg >/dev/null 2>&1 && dpkg -s libxcb-xinerama0 >/dev/null 2>&1; then
        HAS_XCB=1
    elif command -v rpm >/dev/null 2>&1 && rpm -q libxcb >/dev/null 2>&1; then
        HAS_XCB=1
    fi
    [ "$HAS_XCB" -eq 0 ] && MISSING="${MISSING} libxcb-xinerama0"

    if [ -n "$MISSING" ]; then
        echo ""
        echo "ERROR: Missing system packages: $MISSING"
        echo ""
        echo "  Run the dependency installer first:"
        echo "    sudo $DEPS_SCRIPT"
        echo ""
        exit 1
    fi

    VER="$("$PY_BIN" -c 'from PyQt5 import QtCore; print(QtCore.PYQT_VERSION_STR)')"
    echo "System PyQt5 OK: $VER"
}

# ─── Resolve compatible PyInstaller version ──────────────────────────────
# pyinstaller==6.4.0 requires Python <3.13.
# No version pin — pip automatically picks the highest version
# compatible with the running Python interpreter.
install_pyinstaller() {
    local py_ver
    py_ver="$("$PY_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    echo "Python $py_ver detected — installing latest compatible PyInstaller..."
    pip install --quiet pyinstaller
    local installed
    installed="$(pip show pyinstaller 2>/dev/null | grep -i '^Version:' | awk '{print $2}')" || true
    echo "PyInstaller installed: ${installed:-unknown}"
}

# ─── Isolated Virtual Environment ────────────────────────────────────────
echo ""
echo "Setting up isolated build environment..."

rm -rf "$VENV_DIR"

if [ "$IS_ARM64" -eq 1 ]; then
    arm64_preflight

    # --system-site-packages makes system PyQt5 visible inside venv
    "$PY_BIN" -m venv --system-site-packages "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    pip install --quiet --upgrade pip setuptools wheel
    install_pyinstaller

else
    # x86_64 — fully isolated, pip wheels available
    "$PY_BIN" -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"

    pip install --quiet --upgrade pip setuptools wheel
    install_pyinstaller
    pip install --quiet --force-reinstall PyQt5==5.15.10
fi

echo "Build environment ready."

# ─── Clean Previous Builds ───────────────────────────────────────────────
rm -rf "$GUI_DIR/build" \
       "$GUI_DIR/dist" \
       "$GUI_DIR/__pycache__" \
       "$GUI_DIR"/*.spec \
       "$TARGET_BIN"

# ─── Build ───────────────────────────────────────────────────────────────
cd "$GUI_DIR"

pyinstaller \
    --onefile \
    --windowed \
    --name cloud-forge \
    --clean \
    cloud_forge.py

# ─── Move Binary To Project Root ─────────────────────────────────────────
if [ ! -f "$DIST_BIN" ]; then
    echo "Build failed. Binary not found at: $DIST_BIN"
    deactivate
    exit 1
fi

mv "$DIST_BIN" "$TARGET_BIN"
chmod +x "$TARGET_BIN"

# ─── Check rclone-sftp ───────────────────────────────────────────────────
if [ -f "$SFTP_BIN" ]; then
    echo "rclone-sftp found at: $SFTP_BIN"
else
    echo "WARNING: $SFTP_BIN not found."
    echo "         cloud-forge will try PATH to find rclone-sftp."
fi

# ─── Cleanup ─────────────────────────────────────────────────────────────
rm -rf "$GUI_DIR/build" \
       "$GUI_DIR/dist" \
       "$GUI_DIR/__pycache__" \
       "$GUI_DIR"/*.spec \
       "$VENV_DIR"

deactivate 2>/dev/null || true

echo ""
echo "Build complete!"
echo "Binary : $TARGET_BIN"
echo ""
echo "Expected layout:"
echo "  $PROJECT_ROOT/"
echo "  ├── cloud-forge        (this binary)"
echo "  └── bin/"
echo "      └── rclone-sftp   (sftp manager binary)"
