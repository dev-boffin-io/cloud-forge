#!/usr/bin/env python3

import os
import sys
import platform
import subprocess
import tempfile
import shutil
import zipfile
import urllib.request
import json

GITHUB_API = "https://api.github.com/repos/rclone/rclone/releases/latest"
FALLBACK_VERSION = "https://downloads.rclone.org/version.txt"

INSTALL_PATHS = [
    "/usr/local/bin/rclone",
    os.path.expanduser("~/.local/bin/rclone")
]


# -------------------------------------------------
# helpers
# -------------------------------------------------

def run(cmd):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def human_size(size):

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024

    return f"{size:.2f} PB"


# -------------------------------------------------
# architecture
# -------------------------------------------------

def get_arch():

    arch = platform.machine()

    if arch == "x86_64":
        return "amd64"
    elif arch == "aarch64":
        return "arm64"
    elif arch == "armv7l":
        return "arm-v7"
    else:
        print(f"Unsupported architecture: {arch}")
        sys.exit(1)


# -------------------------------------------------
# find rclone
# -------------------------------------------------

def find_rclone():

    for path in INSTALL_PATHS:
        if os.path.exists(path):
            return path

    result = run(["which", "rclone"])

    if result.returncode == 0:
        return result.stdout.strip()

    return None


# -------------------------------------------------
# version functions
# -------------------------------------------------

def get_installed_version():

    rclone = find_rclone()

    if not rclone:
        return None

    result = run([rclone, "version"])

    if result.returncode != 0:
        return None

    line = result.stdout.splitlines()[0]

    return line.split()[1]


def get_latest_version():

    # First try GitHub API
    try:
        with urllib.request.urlopen(GITHUB_API, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data["tag_name"]
    except Exception:
        print("GitHub API failed, using fallback source...")

    # Fallback source
    try:
        with urllib.request.urlopen(FALLBACK_VERSION, timeout=10) as resp:
            version = resp.read().decode().strip()
            if not version.startswith("v"):
                version = "v" + version
            return version
    except Exception:
        print("Failed to fetch latest version from all sources.")
        return None


# -------------------------------------------------
# download
# -------------------------------------------------

def download_rclone():

    arch = get_arch()

    url = f"https://downloads.rclone.org/rclone-current-linux-{arch}.zip"

    temp_dir = tempfile.mkdtemp()

    zip_path = os.path.join(temp_dir, "rclone.zip")

    print("Downloading latest rclone...\n")

    def progress(block_num, block_size, total_size):

        downloaded = block_num * block_size

        if downloaded > total_size:
            downloaded = total_size

        percent = downloaded * 100 / total_size if total_size > 0 else 0

        sys.stdout.write(
            f"\r{percent:6.2f}% | {human_size(downloaded)} / {human_size(total_size)}"
        )

        sys.stdout.flush()

    urllib.request.urlretrieve(url, zip_path, progress)

    print("\nDownload complete.\n")

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(temp_dir)

    for d in os.listdir(temp_dir):

        if d.startswith("rclone-"):

            bin_path = os.path.join(temp_dir, d, "rclone")

            return bin_path, temp_dir

    return None, temp_dir


# -------------------------------------------------
# install
# -------------------------------------------------

def install_rclone():

    rclone_path = find_rclone()

    if rclone_path:

        print("Rclone already installed.")

        update_check()

        return

    binary, temp = download_rclone()

    install_dir = "/usr/local/bin"

    if not os.access(install_dir, os.W_OK):

        install_dir = os.path.expanduser("~/.local/bin")

        os.makedirs(install_dir, exist_ok=True)

    dest = os.path.join(install_dir, "rclone")

    shutil.copy(binary, dest)

    os.chmod(dest, 0o755)

    shutil.rmtree(temp)

    print(f"Installed rclone → {dest}")


# -------------------------------------------------
# update check
# -------------------------------------------------

def update_check():

    installed = get_installed_version()

    latest = get_latest_version()

    if not installed:

        print("Rclone not installed.")

        return

    if not latest:

        print("Could not determine latest version.")
        return

    print(f"Installed version : {installed}")

    print(f"Latest version    : {latest}")

    if installed == latest:

        print("Already latest version.")

    else:

        print("Update available.")


# -------------------------------------------------
# upgrade
# -------------------------------------------------

def upgrade():

    installed = get_installed_version()

    latest = get_latest_version()

    if not installed:

        print("Rclone not installed. Running install.")

        install_rclone()

        return

    if not latest:

        print("Cannot check latest version.")
        return

    print(f"Installed : {installed}")

    print(f"Latest    : {latest}")

    if installed == latest:

        print("Already latest version.")

        return

    print("Upgrading rclone...\n")

    binary, temp = download_rclone()

    rclone_path = find_rclone()

    shutil.copy(binary, rclone_path)

    os.chmod(rclone_path, 0o755)

    shutil.rmtree(temp)

    print("\nUpgrade complete.")


# -------------------------------------------------
# uninstall
# -------------------------------------------------

def uninstall():

    rclone = find_rclone()

    if not rclone:

        print("Rclone not installed.")

        return

    os.remove(rclone)

    print(f"Removed {rclone}")


# -------------------------------------------------
# version
# -------------------------------------------------

def version():

    installed = get_installed_version()

    if not installed:

        print("Rclone not installed")

    else:

        print("Installed version:", installed)


# -------------------------------------------------
# CLI
# -------------------------------------------------

def main():

    if len(sys.argv) < 2:

        print("""
Usage:
  rclone_engine install
  rclone_engine update
  rclone_engine upgrade
  rclone_engine uninstall
  rclone_engine version
""")

        return

    cmd = sys.argv[1]

    if cmd == "install":

        install_rclone()

    elif cmd == "update":

        update_check()

    elif cmd == "upgrade":

        upgrade()

    elif cmd == "uninstall":

        uninstall()

    elif cmd == "version":

        version()

    else:

        print("Unknown command")


if __name__ == "__main__":

    main()
