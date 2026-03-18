# theme.py — Color palette and Qt stylesheet for cloud-forge GUI

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
