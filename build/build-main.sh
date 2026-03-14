#!/usr/bin/env bash
# build/build-main.sh — Build rclone-engine binary from src/rclone_engine.py
# Output: <project-root>/rclone-engine

set -euo pipefail

# ─── Paths ───────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SRC_FILE="${PROJECT_ROOT}/src/rclone_engine.py"
OUTPUT_NAME="rclone-engine"
OUTPUT_BIN="${PROJECT_ROOT}/${OUTPUT_NAME}"
BUILD_WORK="${PROJECT_ROOT}/build/.pyinstaller"

# ─── Checks ──────────────────────────────────────────────────────────────────

echo "[INFO] Project root : ${PROJECT_ROOT}"
echo "[INFO] Source        : ${SRC_FILE}"
echo "[INFO] Output        : ${OUTPUT_BIN}"

if [[ ! -f "${SRC_FILE}" ]]; then
    echo "[ERROR] Source file not found: ${SRC_FILE}"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "[ERROR] python3 not found in PATH"
    exit 1
fi

# ─── Pre-build: remove old binary ────────────────────────────────────────────

if [[ -f "${OUTPUT_BIN}" ]]; then
    echo "[INFO] Removing old binary: ${OUTPUT_BIN}"
    rm -f "${OUTPUT_BIN}"
fi

# ─── Virtualenv ──────────────────────────────────────────────────────────────

VENV_DIR="${BUILD_WORK}/venv"

if [[ ! -d "${VENV_DIR}" ]]; then
    echo "[INFO] Creating virtual environment..."
    python3 -m venv "${VENV_DIR}" --system-site-packages
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# ─── Install PyInstaller ─────────────────────────────────────────────────────

echo "[INFO] Installing PyInstaller..."
"${VENV_DIR}/bin/pip" install --quiet --upgrade pyinstaller

# Locate pyinstaller inside venv
PYINSTALLER_BIN="${VENV_DIR}/bin/pyinstaller"
if [[ ! -f "${PYINSTALLER_BIN}" ]]; then
    # pip may have installed scripts to a different location — find it
    PYINSTALLER_BIN="$("${VENV_DIR}/bin/python3" -c \
        "import sysconfig; print(sysconfig.get_path('scripts'))")/pyinstaller"
fi
if [[ ! -f "${PYINSTALLER_BIN}" ]]; then
    echo "[ERROR] pyinstaller not found after install. Tried: ${PYINSTALLER_BIN}"
    echo "[DEBUG] venv bin contents:"
    ls "${VENV_DIR}/bin/" || true
    exit 1
fi
echo "[INFO] Using pyinstaller: ${PYINSTALLER_BIN}"

# ─── Build ───────────────────────────────────────────────────────────────────

echo "[INFO] Building ${OUTPUT_NAME}..."

"${PYINSTALLER_BIN}" \
    --onefile \
    --name       "${OUTPUT_NAME}" \
    --distpath   "${PROJECT_ROOT}" \
    --workpath   "${BUILD_WORK}/work" \
    --specpath   "${BUILD_WORK}/spec" \
    --clean \
    --noconfirm \
    "${SRC_FILE}"

deactivate

# ─── Post-build: clean temp files ────────────────────────────────────────────

echo "[INFO] Cleaning up build artifacts..."
rm -rf "${BUILD_WORK}"

# ─── Done ────────────────────────────────────────────────────────────────────

if [[ -f "${OUTPUT_BIN}" ]]; then
    chmod +x "${OUTPUT_BIN}"
    SIZE=$(du -sh "${OUTPUT_BIN}" | cut -f1)
    echo "[OK] Built: ${OUTPUT_BIN} (${SIZE})"
else
    echo "[ERROR] Build failed — binary not found at ${OUTPUT_BIN}"
    exit 1
fi
