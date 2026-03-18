# tab_remote.py — Remote Manager tab

import os
import sys
import json
import time
import shlex
import subprocess
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog, QFrame,
    QGroupBox, QWidget, QSplitter, QAbstractItemView, QMessageBox,
    QSystemTrayIcon,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor

from theme import DARK
from workers import BaseRunner, CmdWorker, OutputBox
from dialogs import AddRemoteDialog, RenameDialog


class RemoteTab(BaseRunner):
    def __init__(self, rclone_bin, parent=None):
        super().__init__(parent)
        self.rclone = rclone_bin
        self._init_runner()
        self._build_ui()
        self.refresh_remotes()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        lbl = QLabel("CLOUD REMOTES")
        lbl.setObjectName("title")
        hdr.addWidget(lbl)
        hdr.addStretch()
        sub = QLabel("rclone remote management")
        sub.setObjectName("subtitle")
        hdr.addWidget(sub)
        root.addLayout(hdr)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        # ── Toolbar row 1: primary actions ───────────────────────────
        tb1 = QHBoxLayout()
        tb1.setSpacing(8)

        self.btn_add = QPushButton("＋  Add Remote")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.setToolTip("Add a new rclone remote")
        self.btn_add.clicked.connect(self.add_remote)
        tb1.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("↻  Refresh")
        self.btn_refresh.setToolTip("rclone listremotes --long")
        self.btn_refresh.clicked.connect(self.refresh_remotes)
        tb1.addWidget(self.btn_refresh)

        self.btn_browse = QPushButton("⊞  Browse")
        self.btn_browse.setToolTip("rclone lsd <remote>:")
        self.btn_browse.clicked.connect(self.browse_remote)
        tb1.addWidget(self.btn_browse)

        self.btn_delete = QPushButton("✕  Delete")
        self.btn_delete.setObjectName("btn_danger")
        self.btn_delete.setToolTip("rclone config delete <remote>")
        self.btn_delete.clicked.connect(self.delete_remote)
        tb1.addWidget(self.btn_delete)

        self.btn_fix_drive = QPushButton("🔧  Fix Drive")
        self.btn_fix_drive.setToolTip(
            "Fix OneDrive: set drive_id and drive_type after OAuth sign-in"
        )
        self.btn_fix_drive.clicked.connect(self.fix_drive)
        tb1.addWidget(self.btn_fix_drive)

        tb1.addStretch()
        root.addLayout(tb1)

        # ── Toolbar row 2: advanced actions (hidden by default) ──────
        tb2 = QHBoxLayout()
        tb2.setSpacing(8)

        self.btn_rename = QPushButton("✎  Rename")
        self.btn_rename.setToolTip("rclone config rename")
        self.btn_rename.clicked.connect(self.rename_remote)
        tb2.addWidget(self.btn_rename)

        self.btn_dump = QPushButton("⬇  Dump Config")
        self.btn_dump.setToolTip("rclone config dump")
        self.btn_dump.clicked.connect(self.dump_config)
        tb2.addWidget(self.btn_dump)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("rclone command (advanced)")
        self.cmd_input.setFixedWidth(380)
        tb2.addWidget(self.cmd_input)

        self.btn_run_cmd = QPushButton("▶ Run")
        self.btn_run_cmd.clicked.connect(self.run_custom_cmd)
        tb2.addWidget(self.btn_run_cmd)

        tb2.addStretch()

        self._adv_row = QWidget()
        self._adv_row.setLayout(tb2)
        root.addWidget(self._adv_row)

        # Splitter: table + output
        splitter = QSplitter(Qt.Vertical)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["REMOTE NAME", "TYPE"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
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

    def _selected_remote(self):
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        return item.text().rstrip(":") if item else None

    def _on_run_done(self, out, ok, label=""):
        if ok:
            self.output.append_ok(out or "[OK]")
        else:
            self.output.append_err(out or "[ERROR]")
        if label == "refresh":
            self._parse_remotes(out)

    def _notify(self, title, message):
        win = self.window()
        tray = getattr(win, "tray", None)
        if tray and QSystemTrayIcon.isSystemTrayAvailable():
            tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def set_advanced(self, enabled):
        self._adv_row.setVisible(enabled)

    def get_remote_names(self):
        names = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                names.append(item.text())
        return names

    # ── Remote list ──────────────────────────────────────────────────

    def refresh_remotes(self):
        if not shutil.which(self.rclone) and not Path(self.rclone).exists():
            self.output.append_err("[ERROR] rclone not found — install it or check your PATH")
            return
        self._run([self.rclone, "listremotes", "--long"], "refresh")

    def _parse_remotes(self, out):
        self.table.setRowCount(0)
        for line in out.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split(":", 1)
            name  = parts[0].strip()
            rtype = parts[1].strip() if len(parts) > 1 else ""
            if not name:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            t_item = QTableWidgetItem(rtype)
            t_item.setForeground(QColor(DARK['text_dim']))
            self.table.setItem(row, 1, t_item)

    # ── Add Remote ───────────────────────────────────────────────────

    def add_remote(self):
        dlg = AddRemoteDialog(self.rclone, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        r = dlg.get_result()
        if r["needs_oauth"]:
            self._do_oauth_add(r)
        else:
            self.output.append_cmd(" ".join(r["cmd"]))
            self._run(r["cmd"], on_done=self._after_add,
                      secret_env=r.get("secret_env"))

    def _do_oauth_add(self, r):
        name = r["name"]
        create_cmd = r["cmd"] + ["--non-interactive"]
        self.output.append_cmd(" ".join(create_cmd))
        self.output.append_line(
            f"[INFO] Creating remote entry '{name}'...", DARK['warning']
        )
        worker = CmdWorker(create_cmd, timeout=15, env=r.get("secret_env"),
                           registry=self._workers)
        worker.done.connect(
            lambda out, ok, n=name: self._after_create_then_auth(out, ok, n)
        )
        worker.start()

    def _after_create_then_auth(self, out, ok, name):
        self.output.append_ok(f"[OK] Remote entry '{name}' ready.")

        auth_cmd = [self.rclone, "config", "reconnect", f"{name}:"]
        self.output.append_cmd(" ".join(auth_cmd))
        self.output.append_line(
            "[INFO] Browser window opening for authentication.\n"
            "       Complete sign-in, then click Refresh.",
            DARK['warning']
        )
        try:
            env = os.environ.copy()
            if "DISPLAY" not in env and "WAYLAND_DISPLAY" not in env:
                env["DISPLAY"] = ":0"
            proc = subprocess.Popen(
                auth_cmd,
                stdin=subprocess.PIPE,
                env=env,
                start_new_session=True,
            )
            # Answer "y" to "Use web browser?" prompt
            try:
                if proc.stdin:
                    time.sleep(0.3)
                    proc.stdin.write(b"y\n")
                    proc.stdin.flush()
                    proc.stdin.close()
            except Exception:
                pass
        except Exception as e:
            self.output.append_err(f"[ERROR] Could not launch auth: {e}")
            return

        QTimer.singleShot(3000, self.refresh_remotes)

    def _after_add(self, out, ok):
        if ok:
            self.output.append_ok(out or "[OK] Remote added.")
            QTimer.singleShot(800, self.refresh_remotes)
            self._notify("Remote Added", "New cloud remote has been added.")
        else:
            self.output.append_err(out or "[ERROR] Failed to add remote.")

    # ── Remote actions ───────────────────────────────────────────────

    def browse_remote(self):
        name = self._selected_remote()
        if not name:
            self.output.append_err("[ERROR] Please select a remote first")
            return
        self._run([self.rclone, "lsd", f"{name}:"])

    def rename_remote(self):
        name = self._selected_remote()
        if not name:
            self.output.append_err("[ERROR] Please select a remote first")
            return
        dlg = RenameDialog(name, self)
        if dlg.exec_() == QDialog.Accepted:
            new_name = dlg.get_name()
            if not new_name:
                self.output.append_err("[ERROR] New name cannot be empty")
                return
            self._run([self.rclone, "config", "rename", name, new_name])
            QTimer.singleShot(1000, self.refresh_remotes)

    def dump_config(self):
        self._run([self.rclone, "config", "dump"])

    def delete_remote(self):
        name = self._selected_remote()
        if not name:
            self.output.append_err("[ERROR] Please select a remote first")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete remote '{name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._run([self.rclone, "config", "delete", name])
            QTimer.singleShot(800, self.refresh_remotes)

    def run_custom_cmd(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        try:
            cmd = shlex.split(text)
        except ValueError as e:
            self.output.append_err(f"[ERROR] Invalid command syntax: {e}")
            return
        self._run(cmd)

    # ── Fix OneDrive drive_id via Microsoft Graph API ─────────────────

    def fix_drive(self):
        """Fix OneDrive: get drive_id via Microsoft Graph API and update config."""
        name = self._selected_remote()
        if not name:
            self.output.append_err("[ERROR] Please select a remote first")
            return

        row = self.table.currentRow()
        type_item = self.table.item(row, 1)
        rtype = type_item.text().strip() if type_item else ""
        if rtype != "onedrive":
            self.output.append_err(
                f"[ERROR] '{name}' is type '{rtype}', not onedrive"
            )
            return

        self.output.append_line(f"[INFO] Reading token for '{name}'...", DARK['warning'])

        try:
            result = subprocess.run(
                [self.rclone, "config", "dump"],
                capture_output=True, text=True, timeout=10
            )
            cfg        = json.loads(result.stdout) if result.returncode == 0 else {}
            remote_cfg = cfg.get(name, {})
            token_data = json.loads(remote_cfg.get("token", "{}"))
            access_token = token_data.get("access_token", "")
        except Exception as e:
            self.output.append_err(f"[ERROR] Could not read token: {e}")
            return

        if not access_token:
            self.output.append_err(
                "[ERROR] No access token found — make sure OAuth sign-in completed."
            )
            return

        self.output.append_line(
            "[INFO] Querying Microsoft Graph for drive info...", DARK['warning']
        )

        graph_script = (
            "import urllib.request, json\n"
            "req = urllib.request.Request(\n"
            "    'https://graph.microsoft.com/v1.0/me/drive',\n"
            f"    headers={{'Authorization': 'Bearer {access_token}'}}\n"
            ")\n"
            "try:\n"
            "    with urllib.request.urlopen(req, timeout=15) as r:\n"
            "        print(r.read().decode())\n"
            "except Exception as e:\n"
            "    import json as _j; print(_j.dumps({'error': str(e)}))\n"
        )
        worker = CmdWorker(
            ["python3", "-c", graph_script],
            timeout=20, registry=self._workers
        )
        worker.done.connect(
            lambda out, ok, n=name: self._on_graph_drive_result(out, ok, n)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_graph_drive_result(self, out, ok, name):
        try:
            data = json.loads(out)
        except Exception:
            self.output.append_err(f"[ERROR] Unexpected response:\n{out[:200]}")
            return

        if "error" in data:
            err = data.get("error", {})
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            self.output.append_err(f"[ERROR] Graph API: {msg}")
            return

        drive_id   = data.get("id", "")
        drive_type = data.get("driveType", "personal")

        if not drive_id:
            self.output.append_err("[ERROR] drive_id not found in Graph response.")
            return

        update_cmd = [
            self.rclone, "config", "update", name,
            "drive_id",   drive_id,
            "drive_type", drive_type,
            "--non-interactive",
        ]
        self.output.append_cmd(" ".join(update_cmd))
        worker = CmdWorker(update_cmd, timeout=30, registry=self._workers)
        worker.done.connect(
            lambda out2, ok2, n=name, dt=drive_type, di=drive_id:
                self._on_fix_drive_done(out2, ok2, n, dt, di)
        )
        worker.finished.connect(worker.deleteLater)
        worker.start()

    def _on_fix_drive_done(self, out, ok, name, drive_type, drive_id):
        if ok:
            self.output.append_ok(
                f"[OK] '{name}' configured:\n"
                f"     drive_type = {drive_type}\n"
                f"     drive_id   = {drive_id[:20]}..."
            )
            QTimer.singleShot(500, self.refresh_remotes)
        else:
            self.output.append_err(out or "[ERROR] Failed to update config.")
