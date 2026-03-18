# window.py — MainWindow (binary discovery, tray, advanced mode, settings)

import os
import sys
import subprocess
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QMessageBox,
    QSystemTrayIcon, QMenu, QAction, QApplication,
)
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QColor, QIcon, QPixmap

from theme import DARK
from tab_remote import RemoteTab
from tab_server import ServerTab
from tab_config import ConfigTab


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cloud-forge")
        self.setMinimumSize(1900, 800)
        self.resize(2048, 920)

        self.advanced_mode  = False
        self._settings      = QSettings("cloud-forge", "cloud-forge")

        self.rclone_bin    = self._find_bin("rclone")
        self.sftp_bin      = self._find_sftp_bin()
        self.cf_config_bin = self._find_cf_config_bin()

        self._build_ui()
        self._check_bins()
        self._restore_settings()
        self._setup_tray()   # called once here, never inside _build_ui

    # ── Binary discovery ─────────────────────────────────────────────

    def _find_bin(self, name):
        found = shutil.which(name)
        return found or name

    def _find_sftp_bin(self):
        exe_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        candidates = [
            exe_dir / "bin" / "rclone-sftp",
            exe_dir.parent / "bin" / "rclone-sftp",
            exe_dir / "rclone-sftp",
            Path("/usr/local/bin/rclone-sftp"),
            Path("/usr/bin/rclone-sftp"),
        ]
        for p in candidates:
            if p.exists() and os.access(p, os.X_OK):
                return str(p)
        return shutil.which("rclone-sftp") or "rclone-sftp"

    def _find_cf_config_bin(self):
        exe_dir = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        candidates = [
            exe_dir / "bin" / "cf-config-launcher",
            exe_dir.parent / "bin" / "cf-config-launcher",
            exe_dir / "cf-config-launcher",
            Path("/usr/local/bin/cf-config-launcher"),
            Path("/usr/bin/cf-config-launcher"),
        ]
        for p in candidates:
            if p.exists() and os.access(p, os.X_OK):
                return str(p)
        return shutil.which("cf-config-launcher") or "cf-config-launcher"

    # ── UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(
            f"background: {DARK['panel']}; border-bottom: 1px solid {DARK['border']};"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("☁  cloud-forge")
        logo.setStyleSheet(
            f"color: {DARK['accent']}; font-size: 38px; font-weight: bold; letter-spacing: 2px;"
        )
        hl.addWidget(logo)
        hl.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {DARK['text_dim']}; font-size: 26px;")
        hl.addWidget(self.status_label)

        self.btn_cf_config = QPushButton("🔧  CF Config")
        self.btn_cf_config.setToolTip("Launch cf-config-launcher (rclone config in terminal)")
        self.btn_cf_config.setObjectName("btn_primary")
        self.btn_cf_config.clicked.connect(self.launch_cf_config)
        hl.addWidget(self.btn_cf_config)

        self.btn_advanced = QPushButton("⚙ Advanced: OFF")
        self.btn_advanced.setCheckable(True)
        self.btn_advanced.setToolTip("Toggle advanced controls")
        self.btn_advanced.clicked.connect(self.toggle_advanced)
        hl.addWidget(self.btn_advanced)

        main_layout.addWidget(header)

        # Tabs
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)

        self.remote_tab = RemoteTab(self.rclone_bin)
        self.tabs.addTab(self.remote_tab, "  🌐  Remote Manager  ")

        self.server_tab = ServerTab(self.sftp_bin, self.remote_tab)
        self.tabs.addTab(self.server_tab, "  ⚡  SFTP Servers  ")

        self.config_tab = ConfigTab(self.sftp_bin)
        self.tabs.addTab(self.config_tab, "  ⚙  Config  ")

        main_layout.addWidget(self.tabs)

        self.statusBar().showMessage(
            f"  rclone: {self.rclone_bin}"
            f"   |   rclone-sftp: {self.sftp_bin}"
            f"   |   cf-config-launcher: {self.cf_config_bin}"
        )

        # Initial state: advanced OFF
        self.remote_tab.set_advanced(False)
        self.server_tab.set_advanced(False)
        self.tabs.setTabVisible(2, False)

    # ── Advanced mode ────────────────────────────────────────────────

    def toggle_advanced(self):
        self.advanced_mode = not self.advanced_mode
        label = "⚙ Advanced: ON" if self.advanced_mode else "⚙ Advanced: OFF"
        self.btn_advanced.setText(label)
        self.remote_tab.set_advanced(self.advanced_mode)
        self.server_tab.set_advanced(self.advanced_mode)
        self.tabs.setTabVisible(2, self.advanced_mode)

    # ── CF Config launcher ───────────────────────────────────────────

    def launch_cf_config(self):
        try:
            subprocess.Popen([self.cf_config_bin], start_new_session=True)
            self.statusBar().showMessage(f"  Launched: {self.cf_config_bin}", 4000)
        except Exception as e:
            QMessageBox.warning(
                self, "cf-config-launcher",
                f"Could not launch cf-config-launcher:\n{e}"
            )

    # ── Binary check ─────────────────────────────────────────────────

    def _check_bins(self):
        warnings = []
        if not shutil.which(self.rclone_bin) and not Path(self.rclone_bin).exists():
            warnings.append("rclone not found")
        if not Path(self.sftp_bin).exists() and not shutil.which(self.sftp_bin):
            warnings.append("rclone-sftp binary not found")
        if not Path(self.cf_config_bin).exists() and not shutil.which(self.cf_config_bin):
            warnings.append("cf-config-launcher not found")

        if warnings:
            self.status_label.setText("⚠  " + "  |  ".join(warnings))
            self.status_label.setStyleSheet(f"color: {DARK['warning']}; font-size: 26px;")
        else:
            self.status_label.setText("✓  All binaries found")
            self.status_label.setStyleSheet(f"color: {DARK['accent2']}; font-size: 26px;")

    # ── Settings persistence ─────────────────────────────────────────

    def _restore_settings(self):
        geom = self._settings.value("geometry")
        if geom:
            self.restoreGeometry(geom)

        last_tab = int(self._settings.value("last_tab", 0))
        self.tabs.setCurrentIndex(last_tab)

        adv = self._settings.value("advanced_mode", False)
        adv = adv if isinstance(adv, bool) else adv == "true"
        if adv:
            self.advanced_mode = True
            self.btn_advanced.setText("⚙ Advanced: ON")
            self.btn_advanced.setChecked(True)
            self.remote_tab.set_advanced(True)
            self.server_tab.set_advanced(True)
            self.tabs.setTabVisible(2, True)

    def _save_settings(self):
        self._settings.setValue("geometry",      self.saveGeometry())
        self._settings.setValue("last_tab",      self.tabs.currentIndex())
        self._settings.setValue("advanced_mode", self.advanced_mode)

    # ── System tray ──────────────────────────────────────────────────

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        if hasattr(self, "tray") and self.tray is not None:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None

        base = (
            Path(sys.executable).parent
            if getattr(sys, "frozen", False)
            else Path(__file__).parent
        )
        icon = None
        for p in [base / "cloud-forge.png",
                  base.parent / "cloud-forge.png",
                  base / "gui" / "cloud-forge.png"]:
            if p.exists():
                icon = QIcon(str(p))
                break
        if icon is None:
            pix = QPixmap(16, 16)
            pix.fill(QColor(DARK['accent']))
            icon = QIcon(pix)

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("cloud-forge")

        menu = QMenu()
        act_show = QAction("Show", self)
        act_show.triggered.connect(self.show)
        act_show.triggered.connect(self.activateWindow)
        act_quit = QAction("Quit", self)
        act_quit.triggered.connect(self._quit_app)
        menu.addAction(act_show)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    # ── Quit / close ─────────────────────────────────────────────────

    def _quit_app(self):
        self._save_settings()
        for proc in getattr(self.server_tab, "_procs", []):
            try:
                proc.terminate()
            except Exception:
                pass
        QApplication.quit()

    def closeEvent(self, event):
        """Minimize to tray if available; otherwise quit."""
        self._save_settings()
        if QSystemTrayIcon.isSystemTrayAvailable() and hasattr(self, "tray"):
            self.hide()
            self.tray.showMessage(
                "cloud-forge",
                "Running in background. Double-click tray icon to restore.",
                QSystemTrayIcon.Information, 2000
            )
            event.ignore()
        else:
            for proc in getattr(self.server_tab, "_procs", []):
                try:
                    proc.terminate()
                except Exception:
                    pass
            event.accept()
