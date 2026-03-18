# tab_config.py — SFTP Config tab

import shlex

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QFrame, QGroupBox,
)

from theme import DARK
from workers import BaseRunner, OutputBox


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

        div = QFrame()
        div.setObjectName("divider")
        root.addWidget(div)

        # Default profile
        from PyQt5.QtWidgets import QComboBox, QGroupBox
        pg = QGroupBox("DEFAULT PROFILE")
        pl = QHBoxLayout(pg)
        pl.setSpacing(10)
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["balanced", "light", "heavy"])
        self.profile_combo.setFixedWidth(140)
        btn_set = QPushButton("Set Default")
        btn_set.setObjectName("btn_primary")
        btn_set.clicked.connect(self.set_profile)
        pl.addWidget(QLabel("Profile:"))
        pl.addWidget(self.profile_combo)
        pl.addWidget(btn_set)
        pl.addStretch()
        root.addWidget(pg)

        # Custom config key=value
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
        self.config_input.setPlaceholderText("key=value  (separate multiple with spaces)")
        btn_apply = QPushButton("Apply")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self.apply_config)
        inp_row.addWidget(self.config_input)
        inp_row.addWidget(btn_apply)
        cl.addLayout(inp_row)
        root.addWidget(cg)

        # Action buttons
        act_row = QHBoxLayout()
        btn_show = QPushButton("Show Full Config")
        btn_show.clicked.connect(self.show_config)
        btn_profiles = QPushButton("Show Profiles")
        btn_profiles.clicked.connect(self.show_profiles)
        act_row.addWidget(btn_show)
        act_row.addWidget(btn_profiles)
        act_row.addStretch()
        root.addLayout(act_row)

        # Output
        from PyQt5.QtWidgets import QGroupBox as QGB
        out_grp = QGB("OUTPUT")
        out_l = QVBoxLayout(out_grp)
        out_l.setContentsMargins(8, 8, 8, 8)
        self.output = OutputBox()
        out_l.addWidget(self.output)
        root.addWidget(out_grp)

    def set_advanced(self, enabled):
        # Config tab visibility is controlled at the tab level by MainWindow
        pass

    def set_profile(self):
        self._run([self.sftp, "config", self.profile_combo.currentText()])

    def apply_config(self):
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
