# dialogs.py — AddRemoteDialog, RenameDialog, StartServerDialog

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QFrame,
    QGroupBox, QDialogButtonBox, QMessageBox,
)
from PyQt5.QtCore import Qt

from theme import DARK


# ─── Provider list ────────────────────────────────────────────────────────────
# (Display Name, rclone type, [(label, key, placeholder, is_password), ...])

PROVIDERS = [
    ("Google Drive",      "drive",       [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False),
                                          ("Client Secret (optional)", "client_secret",    "leave blank to use default",                 False)]),
    ("Google Photos",     "googlephotos",[]),
    ("OneDrive",          "onedrive",    [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False),
                                          ("Client Secret (optional)", "client_secret",    "leave blank to use default",                 False)]),
    ("Dropbox",           "dropbox",     [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False),
                                          ("Client Secret (optional)", "client_secret",    "leave blank to use default",                 False)]),
    ("Amazon S3",         "s3",          [("Access Key ID",            "access_key_id",    "AWS access key",                             False),
                                          ("Secret Access Key",        "secret_access_key","AWS secret key",                             True),
                                          ("Region",                   "region",           "e.g. us-east-1",                             False),
                                          ("Endpoint (optional)",      "endpoint",         "for S3-compatible services",                 False)]),
    ("Backblaze B2",      "b2",          [("Account ID",               "account",          "B2 account ID",                              False),
                                          ("Application Key",          "key",              "B2 application key",                         True)]),
    ("SFTP",              "sftp",        [("Host",                     "host",             "hostname or IP",                             False),
                                          ("Port",                     "port",             "22",                                         False),
                                          ("Username",                 "user",             "ssh username",                               False),
                                          ("Password",                 "pass",             "ssh password",                               True),
                                          ("Key File (optional)",      "key_file",         "path to private key",                        False)]),
    ("FTP",               "ftp",         [("Host",                     "host",             "hostname or IP",                             False),
                                          ("Port",                     "port",             "21",                                         False),
                                          ("Username",                 "user",             "ftp username",                               False),
                                          ("Password",                 "pass",             "ftp password",                               True)]),
    ("WebDAV",            "webdav",      [("URL",                      "url",              "https://example.com/dav",                    False),
                                          ("Vendor",                   "vendor",           "e.g. nextcloud, owncloud",                   False),
                                          ("Username",                 "user",             "webdav username",                            False),
                                          ("Password",                 "pass",             "webdav password",                            True)]),
    ("pCloud",            "pcloud",      [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False)]),
    ("Mega",              "mega",        [("Username",                 "user",             "mega email",                                 False),
                                          ("Password",                 "pass",             "mega password",                              True)]),
    ("Box",               "box",         [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False)]),
    ("Yandex Disk",       "yandex",      [("Client ID (optional)",     "client_id",        "leave blank to use default",                 False)]),
    ("iCloud Drive",      "iclouddrive", [("Apple ID",                 "apple_id",         "your Apple ID email",                        False),
                                          ("Password",                 "password",         "Apple ID password",                          True)]),
    ("Cloudflare R2",     "s3",          [("Access Key ID",            "access_key_id",    "R2 access key",                              False),
                                          ("Secret Access Key",        "secret_access_key","R2 secret key",                              True),
                                          ("Endpoint",                 "endpoint",         "https://<account>.r2.cloudflarestorage.com", False)]),
    ("Wasabi",            "s3",          [("Access Key ID",            "access_key_id",    "Wasabi access key",                          False),
                                          ("Secret Access Key",        "secret_access_key","Wasabi secret key",                          True),
                                          ("Endpoint",                 "endpoint",         "s3.wasabisys.com",                           False)]),
    ("HTTP (read-only)",  "http",        [("URL",                      "url",              "https://example.com",                        False)]),
    ("Local filesystem",  "local",       []),
]

PROVIDER_NAMES = [p[0] for p in PROVIDERS]

# OAuth providers that need browser authentication
OAUTH_TYPES = frozenset({
    "drive", "onedrive", "dropbox", "pcloud",
    "box", "yandex", "googlephotos", "iclouddrive",
})


# ─── Add Remote Dialog ────────────────────────────────────────────────────────

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

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Remote name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. gdrive, mybox, work-s3")
        name_row.addWidget(self.name_edit)
        root.addLayout(name_row)

        prov_row = QHBoxLayout()
        prov_row.addWidget(QLabel("Provider:     "))
        self.provider_combo = QComboBox()
        self.provider_combo.addItems(PROVIDER_NAMES)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_change)
        prov_row.addWidget(self.provider_combo)
        root.addLayout(prov_row)

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        self.fields_group = QGroupBox("Provider Settings")
        self.fields_layout = QFormLayout(self.fields_group)
        self.fields_layout.setSpacing(10)
        self.fields_layout.setContentsMargins(12, 14, 12, 10)
        root.addWidget(self.fields_group)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet(f"color: {DARK['text_dim']}; font-size: 26px;")
        root.addWidget(self.info_label)

        root.addStretch()

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
        while self.fields_layout.rowCount():
            self.fields_layout.removeRow(0)
        self._field_widgets.clear()

        _, rtype, fields = PROVIDERS[idx]

        if not fields:
            lbl = QLabel("No additional settings required.\nClick 'Add Remote' to continue.")
            lbl.setStyleSheet(f"color: {DARK['text_dim']};")
            self.fields_layout.addRow(lbl)
            if rtype in OAUTH_TYPES:
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

        # Sensitive values passed via env vars, not CLI args
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

        self._cmd        = cmd
        self._secret_env = secret_env
        self._name       = name
        self._rtype      = rtype
        self._needs_oauth = rtype in OAUTH_TYPES
        self.accept()

    def get_result(self):
        return {
            "cmd":         self._cmd,
            "secret_env":  self._secret_env,
            "name":        self._name,
            "rtype":       self._rtype,
            "needs_oauth": self._needs_oauth,
        }


# ─── Rename Dialog ────────────────────────────────────────────────────────────

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


# ─── Start Server Dialog ──────────────────────────────────────────────────────

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
