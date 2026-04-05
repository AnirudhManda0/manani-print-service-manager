"""Main desktop shell for PrintX.

This window orchestrates:
- Dashboard metrics from API
- Print log table
- Service / Report / Settings panels
- Theme, clock, retention prompt, and scheduled backup checks

UI widgets never write directly to SQLite; all data flows through API client calls.
"""

import os
from datetime import datetime

from branding import APP_FULL_NAME, APP_NAME, APP_SUBTITLE, icon_path, logo_path
from ui.qt import (
    QAbstractItemView,
    QComboBox,
    Qt,
    QAction,
    QDateEdit,
    QDate,
    QHBoxLayout,
    QHeaderView,
    QIcon,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QMenu,
    QPixmap,
    QScrollArea,
    QSize,
    QSystemTrayIcon,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTimer,
    QVBoxLayout,
    QWidget,
)

from ui.dashboard import DashboardPanel
from ui.formatting import format_currency
from ui.catalog_panel import CatalogPanel
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

    def __init__(self, api_client, app_version: str = "1.0.0", start_hidden: bool = False):
        super().__init__()
        self.api = api_client
        self.app_version = app_version
        self.start_hidden = start_hidden
        self._tray_icon = None
        self._tray_hint_shown = False
        self._is_exiting = False
        self.background_supported = False
        self.theme_manager = ThemeManager()
        self.setWindowTitle(f"{APP_NAME} v{self.app_version}")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)
        app_icon_path = icon_path()
        if os.path.exists(app_icon_path):
            self.setWindowIcon(QIcon(app_icon_path))

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(18, 14, 18, 12)
        root.setSpacing(14)

        # Top ribbon: app title, dashboard date selector, theme toggle, and live clock.
        header = QHBoxLayout()
        header.setSpacing(12)
        logo_label = QLabel()
        logo = QPixmap(logo_path())
        if not logo.isNull():
            logo_label.setPixmap(logo.scaledToHeight(52, Qt.SmoothTransformation))
            header.addWidget(logo_label)
        title = QLabel(APP_NAME)
        title.setObjectName("appTitle")
        subtitle = QLabel(APP_SUBTITLE)
        subtitle.setObjectName("secondaryLabel")
        version_label = QLabel(f"v{self.app_version}")
        version_label.setObjectName("secondaryLabel")
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
        header.addSpacing(10)
        header.addWidget(subtitle)
        header.addSpacing(8)
        header.addWidget(version_label)
        header.addStretch()
        header.addWidget(dash_date_label)
        header.addWidget(self.dashboard_date)
        header.addWidget(self.dashboard_refresh_btn)
        header.addWidget(self.theme_toggle_btn)
        header.addWidget(self.clock_label)
        root.addLayout(header)

        self.dashboard = DashboardPanel()
        root.addWidget(self.dashboard, 0)
        root.addSpacing(48)

        # Main content area uses tabbed pages.
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setIconSize(QSize(16, 16))
        root.addWidget(self.tabs, 1)

        self.print_log_tab = self._build_print_log_tab()
        self.tabs.addTab(self.print_log_tab, self._icon("printer.svg"), "Print Log")

        self.services_panel = ServicesPanel(self.api)
        self.services_panel.service_recorded.connect(self.refresh_all)
        self.tabs.addTab(self.services_panel, self._icon("services.svg"), "Services")

        self.reports_panel = ReportsPanel(self.api)
        self.tabs.addTab(self._wrap_scroll(self.reports_panel), self._icon("reports.svg"), "Reports")

        self.settings_panel = SettingsPanel(self.api)
        self.settings_panel.settings_saved.connect(self.refresh_all)
        self.tabs.addTab(self._wrap_scroll(self.settings_panel), self._icon("settings.svg"), "Settings")

        self.catalog_panel = CatalogPanel(self.api)
        self.tabs.addTab(self._wrap_scroll(self.catalog_panel), self._icon("database.svg"), "Catalog")

        self.statusBar().showMessage("Ready")
        self.apply_theme()
        self._setup_tray()
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
        if self.start_hidden:
            QTimer.singleShot(250, lambda: self.hide_to_tray(notify=False))

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

        self.print_log_table = QTableWidget(0, 10)
        self.print_log_table.setHorizontalHeaderLabels(
            ["Time", "Operator", "Computer", "Printer", "Pages", "Document", "Print Type", "Paper", "Cost", "Delete"]
        )
        self.print_log_table.setAlternatingRowColors(True)
        self.print_log_table.setWordWrap(False)
        self.print_log_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.print_log_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.print_log_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.print_log_table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.print_log_table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.print_log_table.verticalHeader().setVisible(False)
        self.print_log_table.verticalHeader().setDefaultSectionSize(38)
        header = self.print_log_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        header.setSectionResizeMode(7, QHeaderView.Fixed)
        header.setSectionResizeMode(8, QHeaderView.Fixed)
        header.setSectionResizeMode(9, QHeaderView.Fixed)
        self.print_log_table.setColumnWidth(0, 152)
        self.print_log_table.setColumnWidth(1, 110)
        self.print_log_table.setColumnWidth(2, 132)
        self.print_log_table.setColumnWidth(3, 220)
        self.print_log_table.setColumnWidth(4, 72)
        self.print_log_table.setColumnWidth(6, 120)
        self.print_log_table.setColumnWidth(7, 90)
        self.print_log_table.setColumnWidth(8, 110)
        self.print_log_table.setColumnWidth(9, 84)
        self.print_log_table.cellDoubleClicked.connect(self._handle_print_log_double_click)
        layout.addWidget(self.print_log_table)
        return tab

    def _icon(self, filename: str) -> QIcon:
        icon_path = ui_resource_path(os.path.join("ui", "icons", filename))
        return QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.background_supported = True
        tray_icon = self.windowIcon()
        if tray_icon.isNull():
            tray_icon = self._icon("dashboard.svg")
        self._tray_icon = QSystemTrayIcon(tray_icon, self)
        self._tray_icon.setToolTip(APP_NAME)
        tray_menu = QMenu(self)
        open_action = tray_menu.addAction(f"Open {APP_NAME}")
        hide_action = tray_menu.addAction("Hide Window")
        tray_menu.addSeparator()
        exit_action = tray_menu.addAction("Exit Completely")
        open_action.triggered.connect(self.show_from_tray)
        hide_action.triggered.connect(self.hide_to_tray)
        exit_action.triggered.connect(self.exit_application)
        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason) -> None:
        if reason in {QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick}:
            if self.isVisible():
                self.hide_to_tray(notify=False)
            else:
                self.show_from_tray()

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def hide_to_tray(self, notify: bool = True) -> None:
        if self._tray_icon is None:
            return
        self.hide()
        if notify and not self._tray_hint_shown:
            self._tray_hint_shown = True
            self._tray_icon.showMessage(
                APP_NAME,
                "Print monitoring is still running in the background.",
                QSystemTrayIcon.Information,
                3000,
            )

    def exit_application(self) -> None:
        self._is_exiting = True
        if self._tray_icon is not None:
            self._tray_icon.hide()
        self.close()

    def apply_theme(self) -> None:
        self.setStyleSheet(self.theme_manager.stylesheet())
        self.theme_toggle_btn.setText(self.theme_manager.mode_label())
        self._repolish_widget_tree(self)

    def toggle_theme(self) -> None:
        self.theme_manager.toggle()
        self.apply_theme()

    def closeEvent(self, event) -> None:  # pragma: no cover - UI close behavior.
        if self._tray_icon is not None and not self._is_exiting:
            event.ignore()
            self.hide_to_tray(notify=True)
            return
        super().closeEvent(event)

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
        self.catalog_panel.refresh_data()

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
            job_id = int(item.get("id", 0))
            time_item = QTableWidgetItem(item.get("timestamp", ""))
            time_item.setData(Qt.UserRole, job_id)
            self.print_log_table.setItem(idx, 0, time_item)
            self.print_log_table.setItem(idx, 1, QTableWidgetItem(item.get("operator_id", "ADMIN")))
            self.print_log_table.setItem(idx, 2, QTableWidgetItem(item.get("computer_name", "")))
            self.print_log_table.setItem(idx, 3, QTableWidgetItem(item.get("printer_name", "")))
            self.print_log_table.setItem(idx, 4, QTableWidgetItem(str(item.get("pages", 0))))
            self.print_log_table.setItem(idx, 5, QTableWidgetItem(item.get("document_name", "")))
            self.print_log_table.setItem(idx, 6, QTableWidgetItem(str(item.get("print_type", "")).replace("_", " ")))
            self.print_log_table.setItem(idx, 7, QTableWidgetItem(item.get("paper_size", "Unknown")))
            self.print_log_table.setItem(idx, 8, QTableWidgetItem(format_currency(currency, item.get("total_cost", 0))))
            delete_btn = QPushButton("Delete")
            delete_btn.setObjectName("tableDeleteButton")
            delete_btn.setFixedSize(66, 26)
            delete_btn.clicked.connect(lambda _checked=False, j=job_id: self.delete_print_job(j))
            delete_container = QWidget()
            delete_layout = QHBoxLayout(delete_container)
            delete_layout.setContentsMargins(0, 0, 0, 0)
            delete_layout.setAlignment(Qt.AlignCenter)
            delete_layout.addWidget(delete_btn)
            self.print_log_table.setCellWidget(idx, 9, delete_container)

            for col in (0, 1, 2, 3, 4, 5, 6, 7, 8):
                cell = self.print_log_table.item(idx, col)
                if cell is not None:
                    cell.setToolTip(cell.text())
                    cell.setTextAlignment(Qt.AlignVCenter | (Qt.AlignCenter if col in {4, 8} else Qt.AlignLeft))

        self.statusBar().showMessage(f"Loaded {len(rows)} print jobs for {day}")

    def delete_print_job(self, job_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Delete Transaction",
            f"Delete print transaction ID {job_id}?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            self.api.delete_print_job(job_id)
            self.load_print_jobs()
            self.load_dashboard()
            self.statusBar().showMessage(f"Deleted print transaction ID {job_id}")
        except Exception as exc:
            QMessageBox.warning(self, "Delete Error", f"Unable to delete transaction.\n{exc}")

    def _handle_print_log_double_click(self, row: int, column: int) -> None:
        if column != 6:
            return
        type_cell = self.print_log_table.item(row, 6)
        timestamp_cell = self.print_log_table.item(row, 0)
        if type_cell is None:
            return
        current = str(type_cell.text()).strip().lower().replace(" ", "_")
        new_type = "color" if current == "black_and_white" else "black_and_white"
        job_id = timestamp_cell.data(Qt.UserRole) if timestamp_cell is not None else None
        timestamp = timestamp_cell.text() if timestamp_cell is not None else "selected job"
        response = QMessageBox.question(
            self,
            "Correct Print Type",
            f"Change print type for {timestamp} to '{new_type.replace('_', ' ')}'?\n\nThis will recalculate billing.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            return

        try:
            if not job_id:
                raise ValueError("Could not resolve the selected job for correction.")
            self.api.update_print_job_type(int(job_id), new_type)
            self.refresh_all()
            self.statusBar().showMessage(f"Corrected print type to {new_type.replace('_', ' ')}")
        except Exception as exc:
            QMessageBox.warning(self, "Correction Error", f"Unable to update print type.\n{exc}")

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
