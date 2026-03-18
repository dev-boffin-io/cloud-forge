#!/usr/bin/env python3
"""
cloud-forge GUI
rclone remote management + rclone-sftp server management
"""

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QLineEdit, QTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QDialog, QFormLayout, QDialogButtonBox,
    QMessageBox, QSplitter, QGroupBox, QComboBox, QSpinBox, QFrame,
    QSizePolicy, QAbstractItemView, QStatusBar, QSystemTrayIcon, QMenu, QAction
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QProcess, QSettings
)
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon, QPixmap

# ==================== Colors & Theme ====================

DARK = {
    "bg":        "#1a1b1e",
    "panel":     "#25262b",
    "border":    "#2c2e33",
    "accent":    "#4dabf7",
    "accent2":   "#69db7c",
    "danger":    "#ff6b6b",
    "warning":   "#ffa94d",
    "text":      "#c9d1d9",
    "text_dim":  "#6e7681",
    "btn":       "#2c2e33",
    "btn_hover": "#373a40",
    "running":   "#69db7c",
    "stopped":   "#ff6b6b",
}

STYLESHEET = f"""
QMainWindow, QWidget {{
    background-color: {DARK['bg']};
    color: {DARK['text']};
    font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace;
    font-size: 30px;
}}
QTabWidget::pane {{
    border: 1px solid {DARK['border']};
    background: {DARK['panel']};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: {DARK['bg']};
    color: {DARK['text_dim']};
    padding: 12px 28px;
    border: 1px solid {DARK['border']};
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
    min-width: 160px;
    font-size: 28px;
}}
QTabBar::tab:selected {{
    background: {DARK['panel']};
    color: {DARK['accent']};
    border-bottom: 2px solid {DARK['accent']};
}}
QTabBar::tab:hover:!selected {{
    background: {DARK['btn_hover']};
    color: {DARK['text']};
}}
QPushButton {{
    background: {DARK['btn']};
    color: {DARK['text']};
    border: 1px solid {DARK['border']};
    border-radius: 6px;
    padding: 10px 20px;
    font-size: 27px;
    min-height: 38px;
}}
QPushButton:hover {{
    background: {DARK['btn_hover']};
    border-color: {DARK['accent']};
    color: {DARK['accent']};
}}
QPushButton:pressed {{
    background: {DARK['accent']};
    color: {DARK['bg']};
}}
QPushButton#btn_primary {{
    background: {DARK['accent']};
    color: {DARK['bg']};
    border: none;
    font-weight: bold;
    font-size: 27px;
}}
QPushButton#btn_primary:hover {{
    background: #74c0fc;
    color: {DARK['bg']};
}}
QPushButton#btn_danger {{
    background: {DARK['danger']};
    color: white;
    border: none;
    font-size: 27px;
}}
QPushButton#btn_danger:hover {{
    background: #ff8787;
}}
QPushButton#btn_success {{
    background: {DARK['accent2']};
    color: {DARK['bg']};
    border: none;
    font-weight: bold;
    font-size: 27px;
}}
QPushButton#btn_success:hover {{
    background: #8ce99a;
}}
QLineEdit, QTextEdit, QComboBox, QSpinBox {{
    background: {DARK['bg']};
    color: {DARK['text']};
    border: 1px solid {DARK['border']};
    border-radius: 4px;
    padding: 8px 12px;
    font-size: 28px;
    selection-background-color: {DARK['accent']};
}}
QLineEdit:focus, QTextEdit:focus {{
    border-color: {DARK['accent']};
}}
QTableWidget {{
    background: {DARK['bg']};
    color: {DARK['text']};
    border: 1px solid {DARK['border']};
    gridline-color: {DARK['border']};
    border-radius: 4px;
    outline: none;
    font-size: 28px;
}}
QTableWidget::item {{
    padding: 10px 14px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {DARK['btn_hover']};
    color: {DARK['accent']};
}}
QHeaderView::section {{
    background: {DARK['panel']};
    color: {DARK['text_dim']};
    padding: 10px 14px;
    border: none;
    border-bottom: 1px solid {DARK['border']};
    font-size: 26px;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QGroupBox {{
    color: {DARK['text_dim']};
    border: 1px solid {DARK['border']};
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 12px;
    font-size: 26px;
    letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {DARK['accent']};
}}
QScrollBar:vertical {{
    background: {DARK['bg']};
    width: 10px;
    border-radius: 5px;
}}
QScrollBar::handle:vertical {{
    background: {DARK['border']};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {DARK['text_dim']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QStatusBar {{
    background: {DARK['panel']};
    color: {DARK['text_dim']};
    border-top: 1px solid {DARK['border']};
    font-size: 24px;
}}
QDialog {{
    background: {DARK['panel']};
}}
QLabel#title {{
    color: {DARK['accent']};
    font-size: 36px;
    font-weight: bold;
    letter-spacing: 2px;
}}
QLabel#subtitle {{
    color: {DARK['text_dim']};
    font-size: 26px;
    letter-spacing: 1px;
}}
QFrame#divider {{
    background: {DARK['border']};
    max-height: 1px;
}}
"""

# ==================== Background Command Runner ====================

class CmdWorker(QThread):
    done = pyqtSignal(str, bool)  # output, success

    def __init__(self, cmd, parent=None, timeout=None, env=None, registry=None):
        super().__init__(parent)
        self.cmd = cmd
        self.timeout = timeout
        self.env = env
        self._registry = registry  # owning set — prevents GC, enables cleanup
        if self._registry is not None:
            self._registry.add(self)
        self.finished.connect(self._cleanup)
        self.destroyed.connect(self._cleanup)

    def _cleanup(self):
        if self._registry is not None:
            self._registry.discard(self)

    def run(self):
        try:
            run_env = None
            if self.env:
                run_env = os.environ.copy()
                run_env.update(self.env)
            result = subprocess.run(
                self.cmd, capture_output=True, text=True,
                timeout=self.timeout if self.timeout else None,
                env=run_env,
            )
            out = result.stdout + result.stderr
            self.done.emit(out.strip(), result.returncode == 0)
        except subprocess.TimeoutExpired:
            self.done.emit("[ERROR] Command timed out", False)
        except Exception as e:
            self.done.emit(f"[ERROR] {e}", False)


# ==================== Output Terminal Widget ====================

class OutputBox(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono", 16))
        self.setMinimumHeight(160)

    def append_line(self, text, color=None):
        import html as _html
        color = color or DARK['text']
        safe = _html.escape(str(text))
        self.append(f'<span style="color:{color};">{safe}</span>')
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def append_cmd(self, cmd_str):
        self.append_line(f"$ {cmd_str}", DARK['accent'])

    def append_ok(self, text):
        self.append_line(text, DARK['accent2'])

    def append_err(self, text):
        self.append_line(text, DARK['danger'])

    def clear_output(self):
        self.clear()


# ==================== Add Remote Dialog ====================

# Provider list: (Display Name, rclone type, fields)
# fields: list of (label, key, placeholder, is_password)
PROVIDERS = [
    ("Google Drive",         "drive",     [("Client ID (optional)",     "client_id",     "leave blank to use default", False),
                                            ("Client Secret (optional)", "client_secret", "leave blank to use default", False)]),
    ("Google Photos",        "googlephotos",[]),
    ("OneDrive",             "onedrive",  [("Client ID (optional)",     "client_id",     "leave blank to use default", False),
                                            ("Client Secret (optional)", "client_secret", "leave blank to use default", False)]),
    ("Dropbox",              "dropbox",   [("Client ID (optional)",     "client_id",     "leave blank to use default", False),
                                            ("Client Secret (optional)", "client_secret", "leave blank to use default", False)]),
    ("Amazon S3",            "s3",        [("Access Key ID",            "access_key_id", "AWS access key",              False),
                                            ("Secret Access Key",        "secret_access_key","AWS secret key",           True),
                                            ("Region",                   "region",        "e.g. us-east-1",              False),
                                            ("Endpoint (optional)",      "endpoint",      "for S3-compatible services",  False)]),
    ("Backblaze B2",         "b2",        [("Account ID",               "account",       "B2 account ID",               False),
                                            ("Application Key",          "key",           "B2 application key",          True)]),
    ("SFTP",                 "sftp",      [("Host",                     "host",          "hostname or IP",              False),
                                            ("Port",                     "port",          "22",                          False),
                                            ("Username",                 "user",          "ssh username",                False),
                                            ("Password",                 "pass",          "ssh password",                True),
                                            ("Key File (optional)",      "key_file",      "path to private key",         False)]),
    ("FTP",                  "ftp",       [("Host",                     "host",          "hostname or IP",              False),
                                            ("Port",                     "port",          "21",                          False),
                                            ("Username",                 "user",          "ftp username",                False),
                                            ("Password",                 "pass",          "ftp password",                True)]),
    ("WebDAV",               "webdav",    [("URL",                      "url",           "https://example.com/dav",     False),
                                            ("Vendor",                   "vendor",        "e.g. nextcloud, owncloud",    False),
                                            ("Username",                 "user",          "webdav username",             False),
                                            ("Password",                 "pass",          "webdav password",             True)]),
    ("pCloud",               "pcloud",    [("Client ID (optional)",     "client_id",     "leave blank to use default",  False)]),
    ("Mega",                 "mega",      [("Username",                 "user",          "mega email",                  False),
                                            ("Password",                 "pass",          "mega password",               True)]),
    ("Box",                  "box",       [("Client ID (optional)",     "client_id",     "leave blank to use default",  False)]),
    ("Yandex Disk",          "yandex",    [("Client ID (optional)",     "client_id",     "leave blank to use default",  False)]),
    ("iCloud Drive",         "iclouddrive",[("Apple ID",                "apple_id",      "your Apple ID email",         False),
                                            ("Password",                 "password",      "Apple ID password",           True)]),
    ("Cloudflare R2",        "s3",        [("Access Key ID",            "access_key_id", "R2 access key",               False),
                                            ("Secret Access Key",        "secret_access_key","R2 secret key",            True),
                                            ("Endpoint",                 "endpoint",      "https://<account>.r2.cloudflarestorage.com", False)]),
    ("Wasabi",               "s3",        [("Access Key ID",            "access_key_id", "Wasabi access key",           False),
                                            ("Secret Access Key",        "secret_access_key","Wasabi secret key",        True),
                                            ("Endpoint",                 "endpoint",      "s3.wasabisys.com",            False)]),
    ("HTTP (read-only)",     "http",      [("URL",                      "url",           "https://example.com",         False)]),
    ("Local filesystem",     "local",     []),
]

PROVIDER_NAMES = [p[0] for p in PROVIDERS]


class AddRemoteDialog(QDialog):
    def __init__(self, rclone_bin, parent=None):
        super().__init__(parent)
        self.rclone_bin = rclone_bin
        self.setWindowTitle("Add New Remote")
        self.setMinimumSize(560, 460)
        self._field_widgets = {}
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Remote name
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Remote name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. gdrive, mybox, work-s3")
        name_row.addWidget(self.name_edit)
        root.addLayout(name_row)

        # Provider dropdown
        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Provider:     "))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDER_NAMES)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        prov_row.addWidget(self.provider_combo)
        root.addLayout(prov_row)

        # Divider
        div = QFrame(); div.setObjectName("divider")
        root.addWidget(div)

        # Dynamic fields area
        self.fields_group = QGroupBox("Provider Settings")
        self.fields_layout = QFormLayout(self.fields_group)
        self.fields_layout.setSpacing(10)
        self.fields_layout.setContentsMargins(12, 14, 12, 10)
        root.addWidget(self.fields_group)

        # Info label
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {DARK['text_dim']}; font-size: 26px;")
        root.addWidget(self.info_label)

        root.addStretch()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_cancel)
        self.btn_add = QPushButton("Add Remote")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.clicked.connect(self._do_add)
        btn_row.addWidget(self.btn_add)
        root.addLayout(btn_row)

        self._on_provider_change(0)

    def _on_provider_change(self, idx):
        # Clear existing fields
        while self.fields_layout.rowCount():
            self.fields_layout.removeRow(0)
        self._field_widgets.clear()

        _, rtype, fields = PROVIDERS[idx]

        if not fields:
            lbl = QLabel("No additional settings required.\nClick 'Add Remote' to continue.")
            lbl.setStyleSheet(f"color: {DARK['text_dim']};")
            self.fields_layout.addRow(lbl)
            if rtype in ("drive", "onedrive", "dropbox", "pcloud", "box", "yandex", "googlephotos"):
                self.info_label.setText(
                    "A browser window will open for OAuth authentication after clicking Add Remote."
                )
            else:
                self.info_label.setText("")
        else:
            self.info_label.setText("")
            for label, key, placeholder, is_pass in fields:
                widget = QLineEdit()
                widget.setPlaceholderText(placeholder)
                if is_pass:
                    widget.setEchoMode(QLineEdit.Password)
                self.fields_layout.addRow(label + ":", widget)
                self._field_widgets[key] = widget

    def _do_add(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Please enter a remote name.")
            return
        if not name.replace("-", "").replace("_", "").isalnum():
            QMessageBox.warning(self, "Invalid name",
                "Remote name can only contain letters, numbers, hyphens, and underscores.")
            return

        idx = self.provider_combo.currentIndex()
        _, rtype, fields = PROVIDERS[idx]

        # Build rclone config create command
        # Sensitive values (passwords/keys) passed via env vars, not CLI args
        cmd = [self.rclone_bin, "config", "create", name, rtype]
        secret_env = {}
        for label, key, placeholder, is_pass in fields:
            widget = self._field_widgets.get(key)
            if widget:
                val = widget.text().strip()
                if val:
                    if is_pass:
                        env_key = f"RCLONE_CONFIG_{name.upper()}_{key.upper()}"
                        secret_env[env_key] = val
                    else:
                        cmd += [key, val]

        self._cmd = cmd
        self._secret_env = secret_env
        self._name = name
        self._rtype = rtype
        self._needs_oauth = rtype in (
            "drive", "onedrive", "dropbox", "pcloud",
            "box", "yandex", "googlephotos", "iclouddrive"
        )
        self.accept()

    def get_result(self):
        return {
            "cmd":         self._cmd,
            "secret_env":  self._secret_env,
            "name":        self._name,
            "rtype":       self._rtype,
            "needs_oauth": self._needs_oauth,
        }


# ==================== Rename Dialog ====================

class RenameDialog(QDialog):
    def __init__(self, old_name, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Rename Remote")
        self.setFixedSize(480, 180)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.old_label = QLabel(old_name)
        self.old_label.setStyleSheet(f"color: {DARK['warning']};")
        layout.addRow("Current name:", self.old_label)

        self.new_name = QLineEdit()
        self.new_name.setPlaceholderText("Enter new name...")
        layout.addRow("New name:", self.new_name)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_name(self):
        return self.new_name.text().strip()


# ==================== Start Server Dialog ====================

class StartServerDialog(QDialog):
    def __init__(self, remotes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New SFTP Server")
        self.setFixedSize(560, 360)
        layout = QFormLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        self.remote = QComboBox()
        self.remote.addItems(remotes if remotes else ["(no remotes found)"])
        layout.addRow("Remote:", self.remote)

        self.port = QLineEdit("auto")
        self.port.setPlaceholderText("auto or port number")
        layout.addRow("Port:", self.port)

        self.user = QLineEdit()
        self.user.setPlaceholderText("username")
        layout.addRow("User:", self.user)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.Password)
        self.password.setPlaceholderText("password")
        layout.addRow("Password:", self.password)

        self.profile = QComboBox()
        self.profile.addItems(["balanced", "light", "heavy"])
        layout.addRow("Profile:", self.profile)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Start")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self):
        return {
            "remote":   self.remote.currentText().strip(),
            "port":     self.port.text().strip() or "auto",
            "user":     self.user.text().strip(),
            "password": self.password.text(),
            "profile":  self.profile.currentText(),
        }


# ==================== Base Command Runner Mixin ====================

class BaseRunner(QWidget):
    """Shared _run/_busy/output logic for all tabs."""

    def _init_runner(self):
        self.worker  = None
        self._busy   = False
        self._workers: set = set()  # per-instance GC anchor + lifecycle tracking

    def _run(self, cmd, label="", on_done=None, secret_env=None):
        if self._busy:
            self.output.append_err("[BUSY] Wait for current task to finish...")
            return
        self._busy = True
        self.output.append_cmd(" ".join(cmd))
        self.worker = CmdWorker(cmd, env=secret_env, registry=self._workers)

        def _wrap(out, ok, _cb=on_done, _lbl=label):
            self._busy = False
            if _cb:
                _cb(out, ok)
            else:
                self._on_run_done(out, ok, _lbl)

        self.worker.done.connect(_wrap)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _on_run_done(self, out, ok, label=""):
        """Override in subclass for custom post-run logic."""
        if ok:
            self.output.append_ok(out or "[OK]")
        else:
            self.output.append_err(out or "[ERROR]")


# ==================== Remote Management Tab ====================

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

        div = QFrame(); div.setObjectName("divider")
        root.addWidget(div)

        # ── Toolbar row 1: primary actions ──────────────────────────
        tb1 = QHBoxLayout()
        tb1.setSpacing(8)

        self.btn_add = QPushButton("＋  Add Remote")
        self.btn_add.setObjectName("btn_primary")
        self.btn_add.setToolTip("rclone config — add a new remote")
        self.btn_add.clicked.connect(self.add_remote)
        tb1.addWidget(self.btn_add)

        self.btn_refresh = QPushButton("↻  Refresh")
        self.btn_refresh.setToolTip("rclone listremotes")
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

        tb1.addStretch()
        root.addLayout(tb1)

        # ── Toolbar row 2: advanced actions (hidden by default) ──────
        tb2 = QHBoxLayout()
        tb2.setSpacing(8)

        self.btn_rename = QPushButton("✎  Rename")
        self.btn_rename.setToolTip("rclone config rename")
        self.btn_rename.clicked.connect(self.rename_remote)
        self.btn_rename.setProperty("advanced", True)
        tb2.addWidget(self.btn_rename)

        self.btn_dump = QPushButton("⬇  Dump Config")
        self.btn_dump.setToolTip("rclone config dump — view as JSON")
        self.btn_dump.clicked.connect(self.dump_config)
        self.btn_dump.setProperty("advanced", True)
        tb2.addWidget(self.btn_dump)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("rclone command (advanced)")
        self.cmd_input.setProperty("advanced", True)
        self.cmd_input.setFixedWidth(380)
        tb2.addWidget(self.cmd_input)

        self.btn_run_cmd = QPushButton("▶ Run")
        self.btn_run_cmd.setProperty("advanced", True)
        self.btn_run_cmd.clicked.connect(self.run_custom_cmd)
        tb2.addWidget(self.btn_run_cmd)

        tb2.addStretch()

        # Container widget — lets us hide the entire row cleanly
        self._adv_row = QWidget()
        self._adv_row.setLayout(tb2)
        root.addWidget(self._adv_row)

        # Splitter: table + output
        splitter = QSplitter(Qt.Vertical)

        # Remote table
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["REMOTE NAME", "TYPE"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        splitter.addWidget(self.table)

        # Output box
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
            name = parts[0].strip()
            rtype = parts[1].strip() if len(parts) > 1 else ""
            if not name:
                continue
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(name))
            t_item = QTableWidgetItem(rtype)
            t_item.setForeground(QColor(DARK['text_dim']))
            self.table.setItem(row, 1, t_item)

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
        name  = r["name"]
        rtype = r["rtype"]

        # Step 1: create bare entry (non-interactive, no browser)
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

        # Step 2: reconnect — pipe "y\n" to stdin so it auto-opens browser
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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )
            # Brief pause so process stdin is ready before writing
            # Answer "y" to "Use web browser?" prompt
            try:
                if proc.stdin:
                    import time
                    time.sleep(0.2)
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

    def _notify(self, title, message):
        """Send a tray notification if tray is available."""
        win = self.window()
        tray = getattr(win, "tray", None)
        if tray and QSystemTrayIcon.isSystemTrayAvailable():
            tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

    def _find_terminal(self):
        for t in ["xterm", "xfce4-terminal", "gnome-terminal", "konsole", "lxterminal"]:
            if shutil.which(t):
                return t
        return None

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

    def set_advanced(self, enabled):
        self._adv_row.setVisible(enabled)

    def run_custom_cmd(self):
        text = self.cmd_input.text().strip()
        if not text:
            return
        try:
            import shlex
            cmd = shlex.split(text)
        except ValueError as e:
            self.output.append_err(f"[ERROR] Invalid command syntax: {e}")
            return
        self._run(cmd)

    def get_remote_names(self):
        names = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                names.append(item.text())
        return names


# ==================== Server Management Tab ====================

class ServerTab(BaseRunner):
    def __init__(self, sftp_bin, remote_tab, parent=None):
        super().__init__(parent)
        self.sftp = sftp_bin
        self.remote_tab = remote_tab
        self._init_runner()
        self._server_data = []
        self._procs = []  # track Popen processes for cleanup
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

        div = QFrame(); div.setObjectName("divider")
        root.addWidget(div)

        # ── Toolbar row 1: primary server actions ────────────────────
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
        self.btn_refresh.setToolTip("Status refresh")
        self.btn_refresh.clicked.connect(self.refresh_status)
        tb1.addWidget(self.btn_refresh)

        root.addLayout(tb1)

        # ── Toolbar row 2: advanced actions (hidden by default) ──────
        tb2 = QHBoxLayout()
        tb2.setSpacing(8)

        self.btn_logs = QPushButton("≡  Logs")
        self.btn_logs.clicked.connect(self.show_logs)
        self.btn_logs.setProperty("advanced", True)
        tb2.addWidget(self.btn_logs)

        self.btn_ports = QPushButton("⊡  Ports")
        self.btn_ports.clicked.connect(self.show_ports)
        self.btn_ports.setProperty("advanced", True)
        tb2.addWidget(self.btn_ports)

        self.btn_health = QPushButton("♥  Health")
        self.btn_health.clicked.connect(self.health_check)
        self.btn_health.setProperty("advanced", True)
        tb2.addWidget(self.btn_health)

        self.btn_profiles = QPushButton("⚙  Profiles")
        self.btn_profiles.clicked.connect(self.show_profiles)
        self.btn_profiles.setProperty("advanced", True)
        tb2.addWidget(self.btn_profiles)

        tb2.addStretch()

        # Container widget — lets us hide the entire row cleanly
        self._adv_row = QWidget()
        self._adv_row.setLayout(tb2)
        root.addWidget(self._adv_row)

        # Splitter
        splitter = QSplitter(Qt.Vertical)

        # Server table
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

        # Output
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

    def set_advanced(self, enabled):
        self._adv_row.setVisible(enabled)

    def _selected_row(self):
        row = self.table.currentRow()
        if row < 0:
            return None, None
        remote = self.table.item(row, 0)
        port = self.table.item(row, 1)
        if remote and port:
            return remote.text(), port.text()
        return None, None

    def _on_run_done(self, out, ok, label=""):
        if ok:
            self.output.append_ok(out or "[OK]")
        else:
            self.output.append_err(out or "[ERROR]")

    def refresh_status(self):
        if self._busy:
            return
        self.worker = CmdWorker([self.sftp, "status", "--json"],
                                registry=self._workers)
        self.worker.done.connect(self._parse_status)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _parse_status(self, out, ok):
        # status --json: returns "null" or empty when no servers are running
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

        self._server_data = servers  # keep full data for file manager
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
                if col == 4:  # status
                    color = DARK['running'] if val == "running" else DARK['stopped']
                    item.setForeground(QColor(color))
                self.table.setItem(row, col, item)

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

    def _notify(self, title, message):
        """Send a tray notification if tray is available."""
        win = self.window()
        tray = getattr(win, "tray", None)
        if tray and QSystemTrayIcon.isSystemTrayAvailable():
            tray.showMessage(title, message, QSystemTrayIcon.Information, 3000)

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

        # Check if server is running
        row = self.table.currentRow()
        status_item = self.table.item(row, 4)
        if not status_item or status_item.text() != "running":
            self.output.append_err("[ERROR] Server is not running")
            return

        # Read user from meta file on disk
        # ~/.local/share/rclone-sftp/meta/<remote>_<port>.json
        user = self._get_user_from_meta(remote, port)

        # Build sftp:// URL
        url = f"sftp://{user}@127.0.0.1:{port}/"
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
                os.startfile(url)  # safer than Popen on Windows
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

    def _get_user_from_meta(self, remote, port):
        """Read user from rclone-sftp meta JSON file."""
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
        # fallback: _server_data cache
        for s in self._server_data:
            if str(s.get("port", "")) == port:
                u = s.get("user", "").strip()
                if u:
                    return u
        return "user"


    def clear_cache(self):
        remote, port = self._selected_row()

        if remote and port:
            # Specific server selected
            reply = QMessageBox.question(
                self, "Clear Cache",
                f"Clear VFS cache for {remote}:{port}?\n\nThis will free disk space but may slow down the next access.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._run([self.sftp, "clear-cache", remote, port],
                          on_done=self._after_clear_cache)
        else:
            # No server selected — clear all
            reply = QMessageBox.question(
                self, "Clear All Cache",
                "Clear ALL VFS cache?\n\nThis will free disk space but may slow down the next access.",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self._run([self.sftp, "clear-cache"],
                          on_done=self._after_clear_cache)

    def _after_clear_cache(self, out, ok):
        self._on_run_done(out, ok)
        # Update cache column in table
        QTimer.singleShot(1000, self.refresh_status)


# ==================== Config Tab ====================

class ConfigTab(BaseRunner):
    def __init__(self, sftp_bin, parent=None):
        super().__init__(parent)
        self.sftp = sftp_bin
        self._init_runner()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        lbl = QLabel("SFTP CONFIG")
        lbl.setObjectName("title")
        root.addWidget(lbl)

        div = QFrame(); div.setObjectName("divider")
        root.addWidget(div)

        # Profile selection
        pg = QGroupBox("DEFAULT PROFILE")
        pl = QHBoxLayout(pg)
        pl.setSpacing(10)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["balanced", "light", "heavy"])
        self.profile_combo.setFixedWidth(140)
        btn_set_profile = QPushButton("Set Default")
        btn_set_profile.setObjectName("btn_primary")
        btn_set_profile.clicked.connect(self.set_profile)
        pl.addWidget(QLabel("Profile:"))
        pl.addWidget(self.profile_combo)
        pl.addWidget(btn_set_profile)
        pl.addStretch()
        root.addWidget(pg)

        # Custom config
        cg = QGroupBox("CUSTOM CONFIG  (key=value format)")
        cl = QVBoxLayout(cg)
        cl.setSpacing(8)
        eg = QLabel(
            "Example:  heavy.buffer_size=128M    "
            "balanced.transfers=8    "
            "max_disk_mb=2048"
        )
        eg.setStyleSheet(f"color: {DARK['text_dim']}; font-size: 26px;")
        cl.addWidget(eg)
        inp_row = QHBoxLayout()
        self.config_input = QLineEdit()
        self.config_input.setPlaceholderText("key=value  (separate multiple entries with spaces)")
        btn_apply = QPushButton("Apply")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self.apply_config)
        inp_row.addWidget(self.config_input)
        inp_row.addWidget(btn_apply)
        cl.addLayout(inp_row)
        root.addWidget(cg)

        # Show config actions
        act_row = QHBoxLayout()
        btn_show = QPushButton("Show Full Config")
        btn_show.clicked.connect(self.show_config)
        btn_show_profiles = QPushButton("Show Profiles")
        btn_show_profiles.clicked.connect(self.show_profiles)
        act_row.addWidget(btn_show)
        act_row.addWidget(btn_show_profiles)
        act_row.addStretch()
        root.addLayout(act_row)

        # Output
        out_grp = QGroupBox("OUTPUT")
        out_l = QVBoxLayout(out_grp)
        out_l.setContentsMargins(8, 8, 8, 8)
        self.output = OutputBox()
        out_l.addWidget(self.output)
        root.addWidget(out_grp)

    def set_advanced(self, enabled):
        # Visibility is controlled at the tab level by MainWindow
        pass

    def set_profile(self):
        profile = self.profile_combo.currentText()
        self._run([self.sftp, "config", profile])

    def apply_config(self):
        import shlex
        text = self.config_input.text().strip()
        if not text:
            return
        try:
            parts = shlex.split(text)
        except ValueError as e:
            self.output.append_err(f"[ERROR] Invalid syntax: {e}")
            return
        self._run([self.sftp, "config"] + parts)

    def show_config(self):
        self._run([self.sftp, "config"])

    def show_profiles(self):
        self._run([self.sftp, "profiles"])


# ==================== Main Window ====================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("cloud-forge")
        self.setMinimumSize(1900, 800)
        self.resize(2048, 920)

        self.advanced_mode = False
        self._settings = QSettings("cloud-forge", "cloud-forge")

        self.rclone_bin     = self._find_bin("rclone")
        self.sftp_bin       = self._find_sftp_bin()
        self.cf_config_bin  = self._find_cf_config_bin()

        self._build_ui()
        self._check_bins()
        self._restore_settings()
        self._setup_tray()  # called once here, never inside _build_ui

    def _find_bin(self, name):
        found = shutil.which(name)
        return found or name

    def _find_sftp_bin(self):
        # PyInstaller frozen binary: sys.executable is the built binary itself
        # so we look relative to it
        import sys
        if getattr(sys, 'frozen', False):
            # Running as PyInstaller bundle — binary sits next to cloud-forge
            exe_dir = Path(sys.executable).parent
        else:
            # Running as plain .py script
            exe_dir = Path(__file__).parent

        candidates = [
            exe_dir / "bin" / "rclone-sftp",          # ./bin/rclone-sftp
            exe_dir.parent / "bin" / "rclone-sftp",   # ../bin/rclone-sftp
            exe_dir / "rclone-sftp",                   # same dir
            Path("/usr/local/bin/rclone-sftp"),
            Path("/usr/bin/rclone-sftp"),
        ]
        for p in candidates:
            if p.exists() and os.access(p, os.X_OK):
                return str(p)
        # Fall back to PATH
        found = shutil.which("rclone-sftp")
        return found or "rclone-sftp"

    def _find_cf_config_bin(self):
        import sys
        if getattr(sys, 'frozen', False):
            exe_dir = Path(sys.executable).parent
        else:
            exe_dir = Path(__file__).parent

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
        found = shutil.which("cf-config-launcher")
        return found or "cf-config-launcher"

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header bar
        header = QWidget()
        header.setFixedHeight(72)
        header.setStyleSheet(f"background: {DARK['panel']}; border-bottom: 1px solid {DARK['border']};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 0, 20, 0)

        logo = QLabel("☁  cloud-forge")
        logo.setStyleSheet(f"color: {DARK['accent']}; font-size: 38px; font-weight: bold; letter-spacing: 2px;")
        hl.addWidget(logo)
        hl.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet(f"color: {DARK['text_dim']}; font-size: 26px;")
        hl.addWidget(self.status_label)

        # cf-config-launcher button
        self.btn_cf_config = QPushButton("🔧  CF Config")
        self.btn_cf_config.setToolTip("Launch cf-config-launcher")
        self.btn_cf_config.setObjectName("btn_primary")
        self.btn_cf_config.clicked.connect(self.launch_cf_config)
        hl.addWidget(self.btn_cf_config)

        # Advanced mode toggle
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

        # Status bar
        self.statusBar().showMessage(
            f"  rclone: {self.rclone_bin}   |   rclone-sftp: {self.sftp_bin}   |   cf-config-launcher: {self.cf_config_bin}"
        )

        # Apply initial advanced=False state
        self.remote_tab.set_advanced(False)
        self.server_tab.set_advanced(False)
        self.tabs.setTabVisible(2, False)  # Config tab hidden until Advanced ON

    def toggle_advanced(self):
        self.advanced_mode = not self.advanced_mode
        if self.advanced_mode:
            self.btn_advanced.setText("⚙ Advanced: ON")
        else:
            self.btn_advanced.setText("⚙ Advanced: OFF")
        self.remote_tab.set_advanced(self.advanced_mode)
        self.server_tab.set_advanced(self.advanced_mode)
        # Config tab is shown/hidden as a whole tab — no floating widgets
        self.tabs.setTabVisible(2, self.advanced_mode)

    def launch_cf_config(self):
        try:
            subprocess.Popen(
                [self.cf_config_bin],
                start_new_session=True,
            )
            self.statusBar().showMessage(f"  Launched: {self.cf_config_bin}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "cf-config-launcher",
                                f"Could not launch cf-config-launcher:\n{e}")

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

    def _restore_settings(self):
        """Restore window geometry, last tab, and advanced mode from QSettings."""
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
        """Persist window geometry, last tab, and advanced mode."""
        self._settings.setValue("geometry",      self.saveGeometry())
        self._settings.setValue("last_tab",      self.tabs.currentIndex())
        self._settings.setValue("advanced_mode", self.advanced_mode)

    def _setup_tray(self):
        """System tray icon — one instance only, uses cloud-forge.png."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        # Destroy any stale tray before creating
        if hasattr(self, "tray") and self.tray is not None:
            self.tray.hide()
            self.tray.deleteLater()
            self.tray = None

        # Find cloud-forge.png relative to script or frozen binary
        if getattr(sys, 'frozen', False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).parent

        icon_candidates = [
            base / "cloud-forge.png",
            base.parent / "cloud-forge.png",
            base / "gui" / "cloud-forge.png",
        ]
        icon = None
        for p in icon_candidates:
            if p.exists():
                icon = QIcon(str(p))
                break
        if icon is None:
            # Fallback: coloured square
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

    def _quit_app(self):
        self._save_settings()
        for proc in getattr(self.server_tab, "_procs", []):
            try:
                proc.terminate()
            except Exception:
                pass
        QApplication.quit()

    def closeEvent(self, event):
        """Minimize to tray if available; otherwise save settings and quit."""
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


# ==================== Entrypoint ====================

_INSTANCE_KEY = "cloud-forge-single-instance"

def main():
    import traceback

    def _excepthook(exc_type, exc_value, exc_tb):
        msg = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        print(f"[UNHANDLED ERROR]\n{msg}", file=sys.stderr)
        QMessageBox.critical(None, "Unexpected Error",
                             f"{exc_type.__name__}: {exc_value}\n\nSee terminal for full traceback.")

    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("cloud-forge")
    app.setStyle("Fusion")
    app.setFont(QFont("JetBrains Mono", 16))

    # ── Single-instance check ────────────────────────────────────────
    # Try to connect to an already-running instance first
    socket = QLocalSocket()
    socket.connectToServer(_INSTANCE_KEY)
    if socket.waitForConnected(300):
        # Another instance is running — send "raise" signal and exit
        socket.write(b"raise\n")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        sys.exit(0)
    socket.deleteLater()

    # No existing instance — start the local server to claim the slot
    local_server = QLocalServer()
    QLocalServer.removeServer(_INSTANCE_KEY)   # clean up stale socket file
    local_server.listen(_INSTANCE_KEY)

    # Dark palette
    palette = QPalette()
    palette.setColor(QPalette.Window,       QColor(DARK['bg']))
    palette.setColor(QPalette.WindowText,   QColor(DARK['text']))
    palette.setColor(QPalette.Base,         QColor(DARK['bg']))
    palette.setColor(QPalette.AlternateBase,QColor(DARK['panel']))
    palette.setColor(QPalette.Text,         QColor(DARK['text']))
    palette.setColor(QPalette.Button,       QColor(DARK['btn']))
    palette.setColor(QPalette.ButtonText,   QColor(DARK['text']))
    palette.setColor(QPalette.Highlight,    QColor(DARK['accent']))
    palette.setColor(QPalette.HighlightedText, QColor(DARK['bg']))
    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)

    win = MainWindow()
    win.show()

    def _on_new_connection():
        """A second instance tried to launch — bring this window to front."""
        conn = local_server.nextPendingConnection()
        if conn:
            conn.waitForReadyRead(200)
            conn.deleteLater()
        win.show()
        win.raise_()
        win.activateWindow()

    local_server.newConnection.connect(_on_new_connection)

    ret = app.exec_()
    local_server.close()
    QLocalServer.removeServer(_INSTANCE_KEY)
    sys.exit(ret)


if __name__ == "__main__":
    main()
