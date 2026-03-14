from datetime import datetime

from PySide6.QtCore import QDate, QTimer
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ui.dashboard import DashboardPanel
from ui.reports_panel import ReportsPanel
from ui.services_panel import ServicesPanel
from ui.settings_panel import SettingsPanel
from ui.theme import ThemeManager


class MainWindow(QMainWindow):
    def __init__(self, api_client):
        super().__init__()
        self.api = api_client
        self.theme_manager = ThemeManager()
        self.setWindowTitle("CyberCafe Print & Service Manager")
        self.resize(1280, 820)

        container = QWidget()
        self.setCentralWidget(container)
        root = QVBoxLayout(container)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        header = QHBoxLayout()
        header.setSpacing(10)
        title = QLabel("CyberCafe Print & Service Manager")
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

        self.dashboard = DashboardPanel()
        root.addWidget(self.dashboard)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.West)
        root.addWidget(self.tabs)

        self.print_log_tab = self._build_print_log_tab()
        self.tabs.addTab(self.print_log_tab, "Print Log")

        self.services_panel = ServicesPanel(self.api)
        self.services_panel.service_recorded.connect(self.refresh_all)
        self.tabs.addTab(self.services_panel, "Services")

        self.reports_panel = ReportsPanel(self.api)
        self.tabs.addTab(self.reports_panel, "Reports")

        self.settings_panel = SettingsPanel(self.api)
        self.settings_panel.settings_saved.connect(self.refresh_all)
        self.tabs.addTab(self.settings_panel, "Settings")

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
        QTimer.singleShot(1500, self.check_retention_notice)

    def _build_print_log_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        label = QLabel("Date")
        self.log_date = QDateEdit()
        self.log_date.setCalendarPopup(True)
        self.log_date.setDate(QDate.currentDate())
        self.log_date.dateChanged.connect(self.load_print_jobs)

        self.refresh_log_btn = QPushButton("Refresh")
        self.refresh_log_btn.setProperty("variant", "primary")
        self.refresh_log_btn.clicked.connect(self.load_print_jobs)

        controls.addWidget(label)
        controls.addWidget(self.log_date)
        controls.addWidget(self.refresh_log_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.print_log_table = QTableWidget(0, 6)
        self.print_log_table.setHorizontalHeaderLabels(["Time", "Computer", "Printer", "Pages", "Print Type", "Cost"])
        self.print_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.print_log_table.verticalHeader().setDefaultSectionSize(34)
        self.print_log_table.setAlternatingRowColors(True)
        layout.addWidget(self.print_log_table)
        return tab

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

        self.print_log_table.setRowCount(len(rows))
        for idx, item in enumerate(rows):
            self.print_log_table.setItem(idx, 0, QTableWidgetItem(item.get("timestamp", "")))
            self.print_log_table.setItem(idx, 1, QTableWidgetItem(item.get("computer_name", "")))
            self.print_log_table.setItem(idx, 2, QTableWidgetItem(item.get("printer_name", "")))
            self.print_log_table.setItem(idx, 3, QTableWidgetItem(str(item.get("pages", 0))))
            self.print_log_table.setItem(idx, 4, QTableWidgetItem(item.get("print_type", "")))
            self.print_log_table.setItem(idx, 5, QTableWidgetItem(f"{currency} {item.get('total_cost', 0):.2f}"))

        self.statusBar().showMessage(f"Loaded {len(rows)} print jobs for {day}")

    def _update_clock(self) -> None:
        self.clock_label.setText(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

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
