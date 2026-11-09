BG = "#121212"
SURFACE = "#181818"
SURFACE2 = "#212121"
SURFACE3 = "#2a2a2a"
BORDER = "#2e2e2e"
TEXT = "#ffffff"
MUTED = "#b3b3b3"
FAINT = "#7a7a7a"
ACCENT = "#1db954"
ACCENT_HOVER = "#1ed760"
ACCENT_DARK = "#169c46"
DANGER = "#e74c3c"
DANGER_HOVER = "#f05a4a"

QSS = f"""
* {{ outline: none; }}
QMainWindow, QWidget {{
    background-color: {BG}; color: {TEXT}; font-family: "Segoe UI"; font-size: 13px;
}}
QLabel {{ background-color: transparent; border: 0; }}
QLabel#brand {{ font-size: 16px; font-weight: 700; letter-spacing: 1px; }}
QLabel#navheader, QLabel#section {{ color: {MUTED}; font-size: 11px; font-weight: 600; letter-spacing: 1px; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 12px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#brandicon {{
    background-color: {ACCENT}; color: {BG}; border-radius: 16px;
    font-size: 18px; font-weight: 800;
}}
#titlebar {{ background-color: {BG}; border-bottom: 1px solid {BORDER}; }}
QToolButton#winbtn {{
    border: none; background-color: transparent; border-radius: 0;
    padding: 0;
}}
QToolButton#winbtn:hover {{ background-color: {SURFACE3}; border: none; }}
QToolButton#winclose {{
    border: none; background-color: transparent; border-radius: 0;
    padding: 0;
}}
QToolButton#winclose:hover {{ background-color: #e81123; border: none; }}
QLabel#cover {{ border-radius: 6px; background-color: {SURFACE2}; }}
QLabel#tracktitle {{ font-size: 13px; font-weight: 600; }}
QLabel#trackartist {{ color: {MUTED}; font-size: 12px; }}
QLabel#playermeta {{ color: {TEXT}; }}
#playerbar {{ background-color: {SURFACE}; }}
#playerLeft, #playerCenter, #playerRight {{ background-color: transparent; }}

QLineEdit, QTextEdit, QComboBox {{
    background-color: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 6px;
    padding: 8px 10px; color: {TEXT}; selection-background-color: {ACCENT}; selection-color: #000;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QLineEdit::placeholder {{ color: {FAINT}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox::down-arrow {{
    image: none; border-left: 5px solid transparent; border-right: 5px solid transparent;
    border-top: 6px solid {MUTED}; margin-right: 8px;
}}
QComboBox QAbstractItemView {{
    background-color: {SURFACE2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; color: {TEXT};
}}

QPushButton {{
    background-color: {SURFACE2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 0 18px; min-height: 34px; color: {TEXT}; font-weight: 600;
}}
QPushButton:hover {{ background-color: {SURFACE3}; border-color: #6a6a6a; }}
QPushButton:pressed {{
    background-color: {SURFACE3}; border-color: {ACCENT}; padding-top: 1px;
}}
QPushButton:disabled {{
    color: {FAINT}; border-color: {BORDER}; background-color: {SURFACE2};
}}
QPushButton[accent="true"] {{
    background-color: {ACCENT}; color: #000; border: none;
    padding: 0 24px; min-height: 34px; font-weight: 700;
}}
QPushButton[accent="true"]:hover {{ background-color: #25e065; border: 2px solid rgba(255,255,255,0.15); }}
QPushButton[accent="true"]:pressed {{ background-color: {ACCENT_DARK}; padding-top: 1px; }}
QPushButton[accent="true"]:disabled {{ background-color: {SURFACE3}; color: {FAINT}; }}
QPushButton[danger="true"] {{ background-color: {DANGER}; color: #fff; border: none; }}
QPushButton[danger="true"]:hover {{ background-color: #ff6b5a; border: 2px solid rgba(255,255,255,0.15); }}
QPushButton[danger="true"]:pressed {{ background-color: #c0392b; padding-top: 1px; }}
QPushButton[danger="true"]:disabled {{ background-color: {SURFACE3}; color: {FAINT}; }}
QToolButton#iconbtn {{
    border: none; background-color: transparent;
    padding: 4px; border-radius: 17px; min-height: 0; max-height: 16777215;
}}
QToolButton#iconbtn:hover {{ background-color: #3a3a3a; border: 1px solid #505050; border-radius: 17px; }}
QToolButton#iconbtn:pressed {{ background-color: {SURFACE2}; border: 1px solid transparent; border-radius: 17px; }}
QToolButton#iconbtn[play="true"] {{ border-radius: 20px; }}
QToolButton#iconbtn[play="true"]:hover {{ border-radius: 20px; background-color: #3a3a3a; border: 1px solid #505050; }}
QToolButton#iconbtn[play="true"]:pressed {{ border-radius: 20px; background-color: {SURFACE2}; border: 1px solid transparent; }}

QListWidget {{
    background: transparent; border: none; color: {MUTED};
}}
QListWidget::item {{
    padding: 8px 12px; border-radius: 6px; margin: 1px 0;
}}
QListWidget::item:hover {{ background-color: {SURFACE2}; color: {TEXT}; }}
QListWidget::item:selected {{ background-color: {SURFACE3}; color: {TEXT}; }}
QListWidget#sidebar {{
    background-color: {BG}; font-size: 14px; font-weight: 600;
}}
QListWidget#sidebar::item {{ padding: 10px 14px; border-radius: 6px; color: {MUTED}; }}
QListWidget#sidebar::item:hover {{ color: {TEXT}; background-color: {SURFACE}; }}
QListWidget#sidebar::item:selected {{ background-color: {SURFACE2}; color: {TEXT}; }}

QTableWidget {{
    background: transparent; border: none; color: {TEXT};
    selection-background-color: {SURFACE3}; selection-color: {TEXT};
}}
QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableWidget::item:selected {{ background-color: {SURFACE3}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background-color: {BG}; color: {MUTED}; border: none;
    border-right: 1px solid {BORDER}; border-bottom: 1px solid {BORDER};
    padding: 6px 8px; font-weight: 600;
}}
QHeaderView::section:hover {{ color: {TEXT}; }}
QTableCornerButton::section {{ background-color: {BG}; border: none; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent; width: 10px; margin: 0;
}}
QScrollBar::handle:vertical {{ background: #555; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #777; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QProgressBar {{
    background-color: {SURFACE2}; border: none; border-radius: 3px; height: 6px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background-color: {ACCENT}; border-radius: 3px; }}

QSlider {{ background-color: transparent; border: 0; }}
QSlider::groove:horizontal {{
    height: 3px; background: {BORDER}; border-radius: 1px;
}}
QSlider::sub-page:horizontal {{ background: {MUTED}; border-radius: 1px; }}
QSlider::handle:horizontal {{
    width: 0; height: 0; margin: 0; border: none; background: transparent;
}}
QSlider::groove:vertical {{
    width: 3px; background: {BORDER}; border-radius: 1px;
}}
QSlider::sub-page:vertical {{ background: {MUTED}; border-radius: 1px; }}
QSlider::handle:vertical {{
    width: 0; height: 0; margin: 0; border: none; background: transparent;
}}

QSplitter::handle {{ background-color: #2b2b2b; }}
QSplitter::handle:horizontal {{ width: 8px; }}
QSplitter::handle:vertical {{ height: 8px; }}
QSplitter::handle:hover {{ background-color: #555555; }}

QMenu {{ background-color: {SURFACE2}; border: 1px solid {BORDER}; color: {TEXT}; }}
QMenu::item {{ padding: 6px 24px; }}
QMenu::item:selected {{ background-color: {ACCENT}; color: #000; }}

QMessageBox {{ background-color: {SURFACE}; }}
"""
