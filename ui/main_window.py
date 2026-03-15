"""Main desktop shell for ManAni Print & Service Manager.

This window orchestrates:
- Dashboard metrics from API
- Print log table
- Service / Report / Settings panels
- Theme, clock, retention prompt, and scheduled backup checks

UI widgets never write directly to SQLite; all data flows through API client calls.
"""

import os
from datetime import datetime

from PySide6.QtCore import QDate, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.dashboard import DashboardPanel
from ui.formatting import format_currency
from ui.reports_panel import ReportsPanel
from ui.resources import ui_resource_path
from ui.services_panel import ServicesPanel
from ui.settings_panel import SettingsPanel
from ui.theme import ThemeManager


class MainWindow(QMainWindow):
    """Primary operator window.

    Data flow:
    - Pulls data from FastAPI via APIClient
    - Displays metrics/logs in widgets
    - Sends user actions (settings/services/retention/backup) back to API
    """

    def __init__(self, api_client):
        super().__init__()
        self.api = api_client
        self.theme_manager = ThemeManager()
        self.setWindowTitle("ManAni Print & Service Manager")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(12)

        # Top ribbon: app title, dashboard date selector, theme toggle, and live clock.
        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("ManAni Print & Service Manager")
        title.setObjectName("appTitle")
        subtitle = QLabel("POS Console")
        subtitle.setObjectName("secondaryLabel")
        dash_date_label = QLabel("Dashboard Date")
        dash_date_label.setObjectName("secondaryLabel")
        self.dashboard_date = QDateEdit()
        self.dashboard_date.setCalendarPopup(True)
        self.dashboard_date.setDate(QDate.currentDate())
        self.dashboard_date.dateChanged.connect(self.load_dashboard)
        self.dashboard_refresh_btn = QPushButton("Load")
        self.dashboard_refresh_btn.setProperty("variant", "primary")
        self.dashboard_refresh_btn.clicked.connect(self.load_dashboard)
        self.theme_toggle_btn = QPushButton(self.theme_manager.mode_label())
        self.theme_toggle_btn.clicked.connect(self.toggle_theme)
        self.clock_label = QLabel()
        self.clock_label.setObjectName("clockLabel")
        header.addWidget(title)
        header.addSpacing(8)
        header.addWidget(subtitle)
        header.addStretch()
        header.addWidget(dash_date_label)
        header.addWidget(self.dashboard_date)
        header.addWidget(self.dashboard_refresh_btn)
        header.addWidget(self.theme_toggle_btn)
        header.addWidget(self.clock_label)
        root.addLayout(header)

        # Dashboard cards are wrapped in a scroll area for smaller displays.
        self.dashboard = DashboardPanel()
        root.addWidget(self._wrap_scroll(self.dashboard), 0)

        # Main content area uses tabbed pages.
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.West)
        self.tabs.setIconSize(QSize(18, 18))
        root.addWidget(self.tabs, 1)

        self.print_log_tab = self._build_print_log_tab()
        self.tabs.addTab(self.print_log_tab, self._icon("printer.svg"), "Print Log")

        self.services_panel = ServicesPanel(self.api)
        self.services_panel.service_recorded.connect(self.refresh_all)
        self.tabs.addTab(self._wrap_scroll(self.services_panel), self._icon("services.svg"), "Services")

        self.reports_panel = ReportsPanel(self.api)
        self.tabs.addTab(self._wrap_scroll(self.reports_panel), self._icon("reports.svg"), "Reports")

        self.settings_panel = SettingsPanel(self.api)
        self.settings_panel.settings_saved.connect(self.refresh_all)
        self.tabs.addTab(self._wrap_scroll(self.settings_panel), self._icon("settings.svg"), "Settings")

        self.statusBar().showMessage("Ready")
        self.apply_theme()
        self.refresh_all()

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(10000)
        self.refresh_timer.timeout.connect(self.refresh_all)
        self.refresh_timer.start()
        self.retention_prompt_shown = False

        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()
        self.backup_timer = QTimer(self)
        self.backup_timer.setInterval(60 * 60 * 1000)
        self.backup_timer.timeout.connect(self.run_daily_backup)
        self.backup_timer.start()
        QTimer.singleShot(1200, self.run_daily_backup)
        QTimer.singleShot(1500, self.check_retention_notice)

    @staticmethod
    def _wrap_scroll(widget: QWidget) -> QScrollArea:
        """Wraps long content panels in a vertical scroll area."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_print_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Filter controls support both dropdown selection and manual text entry.
        controls = QHBoxLayout()
        label = QLabel("Date")
        self.log_date = QDateEdit()
        self.log_date.setCalendarPopup(True)
        self.log_date.setDate(QDate.currentDate())
        self.log_date.dateChanged.connect(self.load_print_jobs)

        print_type_label = QLabel("Print Type")
        self.print_type_filter = QComboBox()
        self.print_type_filter.setEditable(True)
        self.print_type_filter.addItems(["All", "black_and_white", "color"])
        self.print_type_filter.currentTextChanged.connect(self.load_print_jobs)

        paper_label = QLabel("Paper Size")
        self.paper_size_filter = QComboBox()
        self.paper_size_filter.setEditable(True)
        self.paper_size_filter.addItems(["All", "A4", "A3", "Letter", "Unknown"])
        self.paper_size_filter.currentTextChanged.connect(self.load_print_jobs)

        self.refresh_log_btn = QPushButton("Refresh")
        self.refresh_log_btn.setProperty("variant", "primary")
        self.refresh_log_btn.clicked.connect(self.load_print_jobs)

        controls.addWidget(label)
        controls.addWidget(self.log_date)
        controls.addWidget(print_type_label)
        controls.addWidget(self.print_type_filter)
        controls.addWidget(paper_label)
        controls.addWidget(self.paper_size_filter)
        controls.addWidget(self.refresh_log_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.print_log_table = QTableWidget(0, 7)
        self.print_log_table.setHorizontalHeaderLabels(
            ["Time", "Computer", "Printer", "Pages", "Print Type", "Paper", "Cost"]
        )
        self.print_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.print_log_table.verticalHeader().setDefaultSectionSize(34)
        self.print_log_table.setAlternatingRowColors(True)
        layout.addWidget(self.print_log_table)
        return tab

    def _icon(self, filename: str) -> QIcon:
        icon_path = ui_resource_path(os.path.join("ui", "icons", filename))
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def apply_theme(self) -> None:
        self.setStyleSheet(self.theme_manager.stylesheet())
        self.theme_toggle_btn.setText(self.theme_manager.mode_label())
        self._repolish_widget_tree(self)

    def toggle_theme(self) -> None:
        self.theme_manager.toggle()
        self.apply_theme()

    def _repolish_widget_tree(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        for child in widget.findChildren(QWidget):
            style.unpolish(child)
            style.polish(child)

    def refresh_all(self) -> None:
        self.load_dashboard()
        self.load_print_jobs()
        self.services_panel.refresh_services()

    def load_dashboard(self, *_args) -> None:
        day = self.dashboard_date.date().toString("yyyy-MM-dd")
        try:
            payload = self.api.get_dashboard(day=day)
            self.dashboard.update_metrics(payload)
            self.statusBar().showMessage(f"Dashboard loaded for {day}")
        except Exception as exc:
            self.statusBar().showMessage(f"Dashboard refresh failed: {exc}")

    def load_print_jobs(self, *_args) -> None:
        """Load print rows from API and apply local UI filters."""
        day = self.log_date.date().toString("yyyy-MM-dd")
        try:
            rows = self.api.get_print_jobs(day=day, limit=500)
        except Exception as exc:
            QMessageBox.warning(self, "Print Log Error", f"Unable to load print log.\n{exc}")
            return

        settings = {}
        try:
            settings = self.api.get_settings()
        except Exception:
            pass
        currency = settings.get("currency", "INR")

        selected_print_type = self.print_type_filter.currentText().strip().lower()
        selected_paper = self.paper_size_filter.currentText().strip().lower()
        if selected_print_type and selected_print_type != "all":
            rows = [r for r in rows if str(r.get("print_type", "")).strip().lower() == selected_print_type]
        if selected_paper and selected_paper != "all":
            rows = [r for r in rows if str(r.get("paper_size", "")).strip().lower() == selected_paper]

        self.print_log_table.setRowCount(len(rows))
        for idx, item in enumerate(rows):
            self.print_log_table.setItem(idx, 0, QTableWidgetItem(item.get("timestamp", "")))
            self.print_log_table.setItem(idx, 1, QTableWidgetItem(item.get("computer_name", "")))
            self.print_log_table.setItem(idx, 2, QTableWidgetItem(item.get("printer_name", "")))
            self.print_log_table.setItem(idx, 3, QTableWidgetItem(str(item.get("pages", 0))))
            self.print_log_table.setItem(idx, 4, QTableWidgetItem(item.get("print_type", "")))
            self.print_log_table.setItem(idx, 5, QTableWidgetItem(item.get("paper_size", "Unknown")))
            self.print_log_table.setItem(idx, 6, QTableWidgetItem(format_currency(currency, item.get("total_cost", 0))))

        self.statusBar().showMessage(f"Loaded {len(rows)} print jobs for {day}")

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def run_daily_backup(self) -> None:
        try:
            result = self.api.run_daily_backup(force=False)
            if result.get("status") == "created":
                self.statusBar().showMessage(f"Database backup created: {result.get('backup_path')}")
        except Exception as exc:
            self.statusBar().showMessage(f"Backup check failed: {exc}")

    def check_retention_notice(self) -> None:
        if self.retention_prompt_shown:
            return
        try:
            settings = self.api.get_settings()
            days = int(settings.get("retention_days", 30))
            status = self.api.get_retention_status(days=days)
        except Exception:
            return

        if not status.get("has_old_data"):
            return

        self.retention_prompt_shown = True
        message = "Data older than 30 days detected. Would you like to archive or delete older records?"
        box = QMessageBox(self)
        box.setWindowTitle("Data Retention")
        box.setText(message)
        archive_btn = box.addButton("Archive", QMessageBox.AcceptRole)
        delete_btn = box.addButton("Delete", QMessageBox.DestructiveRole)
        box.addButton("Later", QMessageBox.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked == archive_btn:
            mode = "archive_30_days"
        elif clicked == delete_btn:
            mode = "delete_30_days"
        else:
            return

        try:
            result = self.api.execute_retention(mode=mode, days=int(settings.get("retention_days", 30)))
            QMessageBox.information(self, "Retention Completed", str(result))
            self.refresh_all()
        except Exception as exc:
            QMessageBox.warning(self, "Retention Error", str(exc))
