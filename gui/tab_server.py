# tab_server.py — SFTP Server Management tab

import os
import sys
import json
import subprocess
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFrame,
    QGroupBox, QWidget, QSplitter, QAbstractItemView, QMessageBox,
    QSystemTrayIcon,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from theme import DARK
from workers import BaseRunner, CmdWorker, OutputBox
from dialogs import StartServerDialog


class ServerTab(BaseRunner):
    def __init__(self, sftp_bin, remote_tab, parent=None):
        super().__init__(parent)
        self.sftp       = sftp_bin
        self.remote_tab = remote_tab
        self._init_runner()
        self._server_data = []
        self._procs = []          # track Popen processes for cleanup
        self._build_ui()

        # Auto-refresh every 5 seconds
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_status)
        self.timer.start(5000)
        self.refresh_status()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("SFTP SERVERS")
        lbl.setObjectName("title")
        hdr.addWidget(lbl)
        hdr.addStretch()
        sub = QLabel("rclone-sftp server management")
        sub.setObjectName("subtitle")
        hdr.addWidget(sub)
        root.addLayout(hdr)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        # ── Toolbar row 1: primary actions ───────────────────────────
        tb1 = QHBoxLayout()
        tb1.setSpacing(8)

        self.btn_start = QPushButton("▶  Start Server")
        self.btn_start.setObjectName("btn_success")
        self.btn_start.clicked.connect(self.start_server)
        tb1.addWidget(self.btn_start)

        self.btn_stop = QPushButton("■  Stop")
        self.btn_stop.setObjectName("btn_danger")
        self.btn_stop.clicked.connect(self.stop_server)
        tb1.addWidget(self.btn_stop)

        self.btn_stop_all = QPushButton("⬛  Stop All")
        self.btn_stop_all.setObjectName("btn_danger")
        self.btn_stop_all.clicked.connect(self.stop_all)
        tb1.addWidget(self.btn_stop_all)

        self.btn_restart = QPushButton("↺  Restart")
        self.btn_restart.clicked.connect(self.restart_server)
        tb1.addWidget(self.btn_restart)

        self.btn_check = QPushButton("✓  Check")
        self.btn_check.clicked.connect(self.check_server)
        tb1.addWidget(self.btn_check)

        self.btn_open_fm = QPushButton("📂  Open in Files")
        self.btn_open_fm.setObjectName("btn_primary")
        self.btn_open_fm.setToolTip("Open selected server in file manager")
        self.btn_open_fm.clicked.connect(self.open_in_filemanager)
        tb1.addWidget(self.btn_open_fm)

        self.btn_copy_url = QPushButton("🔗  Copy URL")
        self.btn_copy_url.setToolTip("Copy sftp:// URL to clipboard")
        self.btn_copy_url.clicked.connect(self.copy_sftp_url)
        tb1.addWidget(self.btn_copy_url)

        self.btn_clear_cache = QPushButton("🗑  Clear Cache")
        self.btn_clear_cache.setObjectName("btn_danger")
        self.btn_clear_cache.setToolTip("Clear rclone VFS cache")
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        tb1.addWidget(self.btn_clear_cache)

        tb1.addStretch()

        self.btn_refresh = QPushButton("↻")
        self.btn_refresh.setFixedWidth(38)
        self.btn_refresh.setToolTip("Refresh status")
        self.btn_refresh.clicked.connect(self.refresh_status)
        tb1.addWidget(self.btn_refresh)

        root.addLayout(tb1)

        # ── Toolbar row 2: advanced actions (hidden by default) ──────
        tb2 = QHBoxLayout()
        tb2.setSpacing(8)

        self.btn_logs = QPushButton("≡  Logs")
        self.btn_logs.clicked.connect(self.show_logs)
        tb2.addWidget(self.btn_logs)

        self.btn_ports = QPushButton("⊡  Ports")
        self.btn_ports.clicked.connect(self.show_ports)
        tb2.addWidget(self.btn_ports)

        self.btn_health = QPushButton("♥  Health")
        self.btn_health.clicked.connect(self.health_check)
        tb2.addWidget(self.btn_health)

        self.btn_profiles = QPushButton("⚙  Profiles")
        self.btn_profiles.clicked.connect(self.show_profiles)
        tb2.addWidget(self.btn_profiles)

        tb2.addStretch()

        self._adv_row = QWidget()
        self._adv_row.setLayout(tb2)
        root.addWidget(self._adv_row)

        # Splitter
        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "REMOTE", "PORT", "PID", "PROFILE", "STATUS", "UPTIME", "SPEED"
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            hh.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        splitter.addWidget(self.table)

        out_grp = QGroupBox("OUTPUT")
        out_layout = QVBoxLayout(out_grp)
        out_layout.setContentsMargins(8, 8, 8, 8)
        self.output = OutputBox()
        btn_clear = QPushButton("Clear")
        btn_clear.setFixedWidth(70)
        btn_clear.clicked.connect(self.output.clear_output)
        out_layout.addWidget(self.output)
        out_hdr = QHBoxLayout()
        out_hdr.addStretch()
        out_hdr.addWidget(btn_clear)
        out_layout.addLayout(out_hdr)
        splitter.addWidget(out_grp)

        splitter.setSizes([300, 220])
        root.addWidget(splitter)

    # ── Helpers ──────────────────────────────────────────────────────

    def set_advanced(self, enabled):
        self._adv_row.setVisible(enabled)

    def _selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None
        remote = self.table.item(row, 0)
        port   = self.table.item(row, 1)
        if remote and port:
            return remote.text(), port.text()
        return None, None

    def _on_run_done(self, out, ok, label=""):
        if ok:
            self.output.append_ok(out or "[OK]")
        else:
            self.output.append_err(out or "[ERROR]")

    def _notify(self, title, message):
        win  = self.window()
        tray = getattr(win, "tray", None)
        if tray and QSystemTrayIcon.isSystemTrayAvailable():
            tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def _get_user_from_meta(self, remote, port):
        """Read username from rclone-sftp meta JSON file on disk."""
        meta_path = (
            Path.home() / ".local" / "share" / "rclone-sftp"
            / "meta" / f"{remote}_{port}.json"
        )
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            user = data.get("user", "").strip()
            if user:
                return user
        except Exception:
            pass
        # Fallback: in-memory server data cache
        for s in self._server_data:
            if str(s.get("port", "")) == port:
                u = s.get("user", "").strip()
                if u:
                    return u
        return "user"

    # ── Status ───────────────────────────────────────────────────────

    def refresh_status(self):
        if self._busy:
            return
        self.worker = CmdWorker([self.sftp, "status", "--json"],
                                registry=self._workers)
        self.worker.done.connect(self._parse_status)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _parse_status(self, out, ok):
        out = out.strip()
        if not out or out == "null":
            self.table.setRowCount(0)
            self._server_data = []
            return
        try:
            servers = json.loads(out)
        except Exception as e:
            self.output.append_err(f"[ERROR] Invalid JSON from status: {e}")
            return

        if not isinstance(servers, list):
            self.table.setRowCount(0)
            self._server_data = []
            return

        self._server_data = servers
        self.table.setRowCount(0)
        for s in servers:
            row = self.table.rowCount()
            self.table.insertRow(row)
            items = [
                s.get("remote", ""),
                str(s.get("port", "")),
                str(s.get("pid", "")),
                s.get("profile", ""),
                s.get("status", ""),
                s.get("uptime", ""),
                s.get("transfer_speed", ""),
            ]
            for col, val in enumerate(items):
                item = QTableWidgetItem(val)
                if col == 4:
                    color = DARK['running'] if val == "running" else DARK['stopped']
                    item.setForeground(QColor(color))
                self.table.setItem(row, col, item)

    # ── Server lifecycle ─────────────────────────────────────────────

    def start_server(self):
        remotes = self.remote_tab.get_remote_names()
        dlg = StartServerDialog(remotes, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        v = dlg.get_values()
        if not v["user"] or not v["password"]:
            self.output.append_err("[ERROR] User and Password are required")
            return
        cmd = [
            self.sftp, "start",
            v["remote"], v["port"], v["user"], v["password"],
            "--profile", v["profile"]
        ]
        self._run(cmd, on_done=self._after_start)

    def _after_start(self, out, ok):
        self._on_run_done(out, ok)
        QTimer.singleShot(1500, self.refresh_status)
        if ok:
            self._notify("Server Started", "SFTP server is now running.")

    def stop_server(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        self._run([self.sftp, "stop", remote, port], on_done=self._after_stop)

    def _after_stop(self, out, ok):
        self._on_run_done(out, ok)
        QTimer.singleShot(1000, self.refresh_status)
        if ok:
            self._notify("Server Stopped", "SFTP server has been stopped.")

    def stop_all(self):
        reply = QMessageBox.question(
            self, "Confirm", "Stop all servers?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._run([self.sftp, "stop-all"], on_done=self._after_stop_all)

    def _after_stop_all(self, out, ok):
        self._on_run_done(out, ok)
        QTimer.singleShot(1500, self.refresh_status)
        if ok:
            self._notify("All Servers Stopped", "All SFTP servers have been stopped.")

    def restart_server(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        remotes = self.remote_tab.get_remote_names()
        dlg = StartServerDialog(remotes, self)
        idx = dlg.remote.findText(remote)
        if idx >= 0:
            dlg.remote.setCurrentIndex(idx)
        dlg.port.setText(port)
        dlg.setWindowTitle("Restart SFTP Server")
        if dlg.exec_() != QDialog.Accepted:
            return
        v = dlg.get_values()
        cmd = [
            self.sftp, "restart",
            remote, port, v["user"], v["password"],
            "--profile", v["profile"]
        ]
        self._run(cmd, on_done=self._after_restart)

    def _after_restart(self, out, ok):
        self._on_run_done(out, ok)
        QTimer.singleShot(2000, self.refresh_status)

    # ── Info commands ────────────────────────────────────────────────

    def show_logs(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        self._run([self.sftp, "logs", remote, port, "80"])

    def check_server(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        self._run([self.sftp, "check", remote, port])

    def show_ports(self):
        self._run([self.sftp, "ports"])

    def health_check(self):
        self._run([self.sftp, "health"])

    def show_profiles(self):
        self._run([self.sftp, "profiles"])

    # ── File manager / URL ───────────────────────────────────────────

    def copy_sftp_url(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        user = self._get_user_from_meta(remote, port)
        url  = f"sftp://{user}@127.0.0.1:{port}/"
        QApplication.clipboard().setText(url)
        self.output.append_ok(f"[OK] Copied to clipboard: {url}")
        self._notify("URL Copied", url)

    def open_in_filemanager(self):
        remote, port = self._selected_row()
        if not remote:
            self.output.append_err("[ERROR] Please select a server first")
            return
        row = self.table.currentRow()
        status_item = self.table.item(row, 4)
        if not status_item or status_item.text() != "running":
            self.output.append_err("[ERROR] Server is not running")
            return
        user = self._get_user_from_meta(remote, port)
        url  = f"sftp://{user}@127.0.0.1:{port}/"
        self.output.append_cmd(f"open {url}")
        try:
            if sys.platform.startswith("linux"):
                proc = subprocess.Popen(["xdg-open", url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._procs.append(proc)
            elif sys.platform == "darwin":
                proc = subprocess.Popen(["open", url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._procs.append(proc)
            elif sys.platform == "win32":
                os.startfile(url)
            else:
                proc = subprocess.Popen(["xdg-open", url],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self._procs.append(proc)
            self.output.append_ok(f"[OK] Opening file manager: {url}")
            self.output.append_line(
                "      Tip: if prompted for password, use the server password.",
                DARK['text_dim']
            )
        except Exception as e:
            self.output.append_err(f"[ERROR] Failed to open file manager: {e}")

    # ── Cache ────────────────────────────────────────────────────────

    def clear_cache(self):
        remote, port = self._selected_row()
        if remote and port:
            reply = QMessageBox.question(
                self, "Clear Cache",
                f"Clear VFS cache for {remote}:{port}?\n\n"
                "This will free disk space but may slow down the next access.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._run([self.sftp, "clear-cache", remote, port],
                          on_done=self._after_clear_cache)
        else:
            reply = QMessageBox.question(
                self, "Clear All Cache",
                "Clear ALL VFS cache?\n\n"
                "This will free disk space but may slow down the next access.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._run([self.sftp, "clear-cache"],
                          on_done=self._after_clear_cache)

    def _after_clear_cache(self, out, ok):
        self._on_run_done(out, ok)
        QTimer.singleShot(1000, self.refresh_status)
