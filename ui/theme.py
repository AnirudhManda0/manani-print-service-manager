from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    background: str
    card_background: str
    primary_text: str
    secondary_text: str
    accent: str
    border: str
    table_alt: str
    hover: str


LIGHT_THEME = Theme(
    name="light",
    background="#FFFFFF",
    card_background="#F5F7FA",
    primary_text="#1A1A1A",
    secondary_text="#555555",
    accent="#2E86DE",
    border="#E1E5EA",
    table_alt="#EEF2F6",
    hover="#EAF3FC",
)

DARK_THEME = Theme(
    name="dark",
    background="#121212",
    card_background="#1E1E1E",
    primary_text="#FFFFFF",
    secondary_text="#BBBBBB",
    accent="#4AA3FF",
    border="#333333",
    table_alt="#242424",
    hover="#2B2B2B",
)


class ThemeManager:
    def __init__(self) -> None:
        self._theme = LIGHT_THEME

    @property
    def theme(self) -> Theme:
        return self._theme

    def toggle(self) -> Theme:
        self._theme = DARK_THEME if self._theme.name == "light" else LIGHT_THEME
        return self._theme

    def set_theme(self, name: str) -> Theme:
        self._theme = DARK_THEME if name == "dark" else LIGHT_THEME
        return self._theme

    def mode_label(self) -> str:
        return "Light Mode / Dark Mode"

    def stylesheet(self) -> str:
        t = self._theme
        return f"""
        QMainWindow, QWidget {{
            background: {t.background};
            color: {t.primary_text};
            font-family: "Segoe UI", "Inter";
            font-size: 13px;
        }}

        QLabel {{
            color: {t.primary_text};
            font-size: 13px;
        }}
        QLabel#appTitle {{
            font-size: 22px;
            font-weight: 700;
            color: {t.primary_text};
        }}
        QLabel#sectionHeader {{
            font-size: 16px;
            font-weight: 700;
            color: {t.primary_text};
        }}
        QLabel#secondaryLabel {{
            color: {t.secondary_text};
            font-size: 13px;
        }}
        QLabel#clockLabel {{
            color: {t.secondary_text};
            font-size: 13px;
            font-weight: 600;
        }}
        QLabel#statTitle {{
            font-size: 13px;
            color: {t.secondary_text};
            font-weight: 600;
        }}
        QLabel#statValue {{
            font-size: 26px;
            font-weight: 700;
            color: {t.primary_text};
        }}
        QLabel#reportStatTitle {{
            color: {t.secondary_text};
            font-size: 13px;
            font-weight: 600;
        }}
        QLabel#reportStatValue {{
            font-size: 26px;
            font-weight: 700;
            color: {t.primary_text};
        }}

        QFrame#statCard, QFrame#reportStat {{
            background: {t.card_background};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}

        QFrame#statCard[accent="blue"], QFrame#statCard[accent="cyan"],
        QFrame#statCard[accent="orange"], QFrame#statCard[accent="green"],
        QFrame#statCard[accent="gold"] {{
            border-left: 5px solid {t.accent};
        }}

        QPushButton {{
            min-height: 38px;
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid {t.accent};
            background: transparent;
            color: {t.accent};
            font-size: 13px;
            font-weight: 600;
        }}
        QPushButton:hover {{
            background: {t.hover};
        }}
        QPushButton[variant="primary"] {{
            background: {t.accent};
            color: #FFFFFF;
            border: 1px solid {t.accent};
        }}
        QPushButton[variant="primary"]:hover {{
            background: {t.accent};
        }}
        QPushButton#serviceActionButton {{
            min-height: 90px;
            font-size: 13px;
            font-weight: 700;
            padding: 10px;
        }}

        QLineEdit, QSpinBox, QDoubleSpinBox, QDateEdit, QComboBox, QTextEdit {{
            background: {t.card_background};
            color: {t.primary_text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 6px 8px;
            selection-background-color: {t.accent};
            selection-color: #FFFFFF;
        }}
        QAbstractSpinBox::up-button, QAbstractSpinBox::down-button {{
            background: {t.card_background};
            border: none;
        }}
        QComboBox QAbstractItemView {{
            background: {t.card_background};
            color: {t.primary_text};
            border: 1px solid {t.border};
        }}

        QTableWidget {{
            background: {t.card_background};
            color: {t.primary_text};
            gridline-color: {t.border};
            border: 1px solid {t.border};
            border-radius: 8px;
            alternate-background-color: {t.table_alt};
        }}
        QHeaderView::section {{
            background: {t.card_background};
            color: {t.primary_text};
            border: 1px solid {t.border};
            padding: 6px;
            font-size: 13px;
            font-weight: 700;
        }}

        QScrollArea {{
            border: 1px solid {t.border};
            border-radius: 8px;
        }}

        QTabWidget::pane {{
            border: 1px solid {t.border};
            border-radius: 8px;
            margin-left: 8px;
        }}
        QTabBar::tab {{
            min-width: 130px;
            min-height: 48px;
            margin: 4px;
            padding: 10px;
            color: {t.primary_text};
            background: transparent;
            border: 1px solid {t.border};
            border-radius: 8px;
            font-size: 13px;
            font-weight: 600;
        }}
        QTabBar::tab:hover {{
            background: {t.hover};
        }}
        QTabBar::tab:selected {{
            background: {t.accent};
            color: #FFFFFF;
            border: 1px solid {t.accent};
        }}

        QStatusBar {{
            background: {t.card_background};
            color: {t.secondary_text};
            border-top: 1px solid {t.border};
        }}
        """
