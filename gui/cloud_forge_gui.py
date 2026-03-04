import sys
import subprocess
import os
import re
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QPushButton,
    QTabWidget, QMessageBox,
    QTextEdit, QHBoxLayout
)
from PyQt6.QtGui import QFont


# ───────── Auto Project Root Detection ─────────

PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

BIN_PATH = os.path.join(PROJECT_ROOT, "bin")


class CloudForgeGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("☁ Cloud Forge Manager")
        self.setMinimumSize(1100, 700)
        self.setStyleSheet(self.dark_theme())

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.init_remotes_tab()
        self.init_servers_tab()
        self.init_mount_tab()

    # ───────── Tabs ─────────

    def init_remotes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.make_xterm_button("➕ Manage Remotes", "cloud-config"))
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Remotes")

    def init_servers_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()

        layout.addWidget(self.make_xterm_button("🚀 Launch SFTP Server", "cloud-run"))

        btn_layout = QHBoxLayout()

        status_btn = QPushButton("🟢 Status All")
        start_btn = QPushButton("▶ Start All")
        stop_btn = QPushButton("⏹ Stop All")
        restart_btn = QPushButton("🔄 Restart All")

        status_btn.clicked.connect(lambda: self.run_ctl("status"))
        start_btn.clicked.connect(lambda: self.run_ctl("start"))
        stop_btn.clicked.connect(lambda: self.run_ctl("stop"))
        restart_btn.clicked.connect(lambda: self.run_ctl("restart"))

        btn_layout.addWidget(status_btn)
        btn_layout.addWidget(start_btn)
        btn_layout.addWidget(stop_btn)
        btn_layout.addWidget(restart_btn)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)

        layout.addLayout(btn_layout)
        layout.addWidget(self.output_box)

        tab.setLayout(layout)
        self.tabs.addTab(tab, "Servers")

    def init_mount_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        layout.addWidget(self.make_xterm_button("🌐 Open Running Servers", "cloud-mnt"))
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Mount")

    # ───────── Helpers ─────────

    def make_xterm_button(self, text, binary_name):
        btn = QPushButton(text)
        btn.clicked.connect(lambda: self.launch_xterm(binary_name))
        return btn

    def strip_ansi(self, text):
        ansi_escape = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')
        return ansi_escape.sub('', text)

    def run_ctl(self, action):
        binary_path = os.path.join(BIN_PATH, "cloud-ctl")

        if not os.path.exists(binary_path):
            self.output_box.setText(f"Binary not found:\n{binary_path}")
            return

        try:
            result = subprocess.run(
                [binary_path, action, "all"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True
            )

            output = result.stdout + result.stderr
            clean_output = self.strip_ansi(output)
            self.output_box.setText(clean_output)

        except Exception as e:
            self.output_box.setText(str(e))

    def launch_xterm(self, binary):
        binary_path = os.path.join(BIN_PATH, binary)

        if not os.path.exists(binary_path):
            QMessageBox.critical(
                self,
                "Error",
                f"Binary not found:\n{binary_path}"
            )
            return

        try:
            cmd = [
                "xterm",
                "-fa", "Monospace",
                "-fs", "18",
                "-bg", "#111111",
                "-fg", "#00ffcc",
                "-geometry", "90x24",
                "-hold",
                "-e",
                binary_path
            ]

            subprocess.Popen(cmd, cwd=PROJECT_ROOT)

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def dark_theme(self):
        return """
        QMainWindow {
            background-color: #0f111a;
        }
        QPushButton {
            background-color: #1e222d;
            border-radius: 12px;
            padding: 18px;
            font-size: 20px;
            color: white;
        }
        QPushButton:hover {
            background-color: #2b3245;
        }
        QTextEdit {
            background-color: #111827;
            color: #00ffcc;
            font-size: 18px;
            border-radius: 10px;
            padding: 10px;
        }
        QTabWidget::pane {
            border: 1px solid #2b3245;
        }
        """


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setFont(QFont("Segoe UI", 20))
    window = CloudForgeGUI()
    window.show()
    sys.exit(app.exec())
