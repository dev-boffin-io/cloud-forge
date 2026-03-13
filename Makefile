# ─── cloud-forge Makefile ───────────────────────────────────────────────────

SHELL        := /usr/bin/env bash
PROJECT_ROOT := $(shell cd "$(dir $(abspath $(lastword $(MAKEFILE_LIST))))" && pwd)
BUILD_DIR    := $(PROJECT_ROOT)/build
INSTALL_SH   := $(PROJECT_ROOT)/install.sh

.PHONY: all build build-cli build-gui deps install install-only install-cli uninstall clean help

# ─── Default ────────────────────────────────────────────────────────────────

all: help

# ─── Dependencies ───────────────────────────────────────────────────────────

## deps         Install GUI system dependencies (requires sudo)
deps:
	@sudo bash "$(BUILD_DIR)/install-deps-gui.sh"

# ─── Build ──────────────────────────────────────────────────────────────────

## build        Build all binaries (rclone-sftp + rclone-engen + cloud-forge)
build:
	@bash "$(INSTALL_SH)" --build

## build-cli    Build CLI binaries only (rclone-sftp + rclone-engen)
build-cli:
	@bash "$(INSTALL_SH)" --build --cli

## build-gui    Build GUI binary only (cloud-forge)
build-gui:
	@bash "$(BUILD_DIR)/build-gui.sh"

# ─── Install ────────────────────────────────────────────────────────────────

## install      Build everything, then install (symlinks + desktop entry)
install:
	@bash "$(INSTALL_SH)" --build --install

## install-only Install pre-built binaries only (symlinks + desktop entry, no build)
install-only:
	@bash "$(INSTALL_SH)" --install

## install-cli  Build CLI only, then install symlinks (no desktop entry)
install-cli:
	@bash "$(INSTALL_SH)" --build --install --cli

# ─── Uninstall ──────────────────────────────────────────────────────────────

## uninstall    Remove symlinks and desktop entry
uninstall:
	@bash "$(INSTALL_SH)" --remove

# ─── Clean ──────────────────────────────────────────────────────────────────

## clean        Remove all build outputs (binaries + build artefacts)
clean:
	@echo "  [INFO]  Cleaning build outputs..."
	@rm -f  "$(PROJECT_ROOT)/cloud-forge"
	@rm -f  "$(PROJECT_ROOT)/rclone-engen"
	@rm -f  "$(PROJECT_ROOT)/bin/rclone-sftp"
	@rm -rf "$(BUILD_DIR)/.pyinstaller"
	@rm -rf "$(BUILD_DIR)/.venv-build"
	@echo "  [OK]    Clean done."

# ─── Help ───────────────────────────────────────────────────────────────────

## help         Show this help message
help:
	@echo ""
	@echo "  ╔══════════════════════════════════════╗"
	@echo "  ║          cloud-forge Makefile        ║"
	@echo "  ╚══════════════════════════════════════╝"
	@echo ""
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/^## /  make /' | column -t -s '@'
	@echo ""
