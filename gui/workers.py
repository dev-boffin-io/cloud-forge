# workers.py — CmdWorker, OutputBox, BaseRunner

import os
import html as _html
import subprocess

from PyQt5.QtWidgets import QWidget, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtGui import QFont

from theme import DARK


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


class OutputBox(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("JetBrains Mono", 16))
        self.setMinimumHeight(160)

    def append_line(self, text, color=None):
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
