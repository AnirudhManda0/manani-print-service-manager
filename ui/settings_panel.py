"""Settings panel for pricing, retention, and backup behavior.

The UI reads settings from the FastAPI layer and writes updates back through APIClient.
This keeps business logic on the server/database side and keeps the panel focused on operator input.
"""

from ui.qt import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    Signal,
    QVBoxLayout,
    QWidget,
)

from ui.input_filters import disable_wheel_changes


class SettingsPanel(QWidget):
    """Operator-facing settings form.

    Data flow:
    UI widgets -> API client -> FastAPI endpoint -> database settings table.
    """

    settings_saved = Signal()

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client

        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        form = QFormLayout()
        self.server_ip = QLineEdit()
        self.server_port = QSpinBox()
        self.server_port.setRange(1, 65535)
        disable_wheel_changes(self.server_port)
        self.auto_discovery = QComboBox()
        self.auto_discovery.addItem("Enabled", True)
        self.auto_discovery.addItem("Disabled", False)
        self.discovery_port = QSpinBox()
        self.discovery_port.setRange(1, 65535)
        disable_wheel_changes(self.discovery_port)
        self.computer_name = QLineEdit()
        self.operator_id = QLineEdit()
        self.poll_interval = QDoubleSpinBox()
        self.poll_interval.setRange(0.1, 10.0)
        self.poll_interval.setDecimals(2)
        self.poll_interval.setSingleStep(0.1)
        disable_wheel_changes(self.poll_interval)

        # Pricing controls use spin boxes with wheel protection to avoid accidental billing edits.
        self.bw_price = QDoubleSpinBox()
        self.bw_price.setRange(0, 100000)
        self.bw_price.setDecimals(2)
        disable_wheel_changes(self.bw_price)
        self.color_price = QDoubleSpinBox()
        self.color_price.setRange(0, 100000)
        self.color_price.setDecimals(2)
        disable_wheel_changes(self.color_price)

        # Editable combo allows both selecting common currencies and manual custom codes.
        self.currency = QComboBox()
        self.currency.setEditable(True)
        self.currency.addItems(["INR", "USD", "EUR", "GBP"])
        self.currency.setInsertPolicy(QComboBox.NoInsert)

        self.retention_mode = QComboBox()
        self.retention_mode.addItem("Retain All Records", "retain_all")
        self.retention_mode.addItem("Archive Records Older Than 30 Days", "archive_30_days")
        self.retention_mode.addItem("Delete Records Older Than 30 Days", "delete_30_days")

        self.retention_days = QSpinBox()
        self.retention_days.setRange(1, 3650)
        self.retention_days.setValue(30)
        disable_wheel_changes(self.retention_days)

        self.backup_enabled = QComboBox()
        self.backup_enabled.addItem("Enabled", True)
        self.backup_enabled.addItem("Disabled", False)

        self.backup_folder = QLineEdit()
        self.backup_folder.setText("backup")

        form.addRow("Server IP", self.server_ip)
        form.addRow("Server Port", self.server_port)
        form.addRow("Auto Discover Server", self.auto_discovery)
        form.addRow("Discovery Port", self.discovery_port)
        form.addRow("Computer Name", self.computer_name)
        form.addRow("Operator ID", self.operator_id)
        form.addRow("Polling Interval (sec)", self.poll_interval)
        form.addRow("B&W Price Per Page", self.bw_price)
        form.addRow("Color Price Per Page", self.color_price)
        form.addRow("Currency", self.currency)
        form.addRow("Data Retention Mode", self.retention_mode)
        form.addRow("Retention Days", self.retention_days)
        form.addRow("Daily Backup", self.backup_enabled)
        form.addRow("Backup Folder", self.backup_folder)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.reload_btn = QPushButton("Reload")
        self.save_btn = QPushButton("Save")
        self.run_retention_btn = QPushButton("Run Retention Now")
        self.run_backup_btn = QPushButton("Run Backup Now")
        self.save_btn.setProperty("variant", "primary")
        self.reload_btn.clicked.connect(self.load_settings)
        self.save_btn.clicked.connect(self.save_settings)
        self.run_retention_btn.clicked.connect(self.run_retention)
        self.run_backup_btn.clicked.connect(self.run_backup_now)
        buttons.addWidget(self.reload_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.run_retention_btn)
        buttons.addWidget(self.run_backup_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()

        self.load_settings()

    def load_settings(self) -> None:
        """Pull current settings from API and populate the form."""
        try:
            system_data = self.api.get_system_config()
            data = self.api.get_settings()
            self.server_ip.setText(str(system_data.get("server_ip", "127.0.0.1")))
            self.server_port.setValue(int(system_data.get("server_port", 8787)))
            auto_discovery_enabled = bool(system_data.get("auto_discovery_enabled", True))
            auto_discovery_index = self.auto_discovery.findData(auto_discovery_enabled)
            self.auto_discovery.setCurrentIndex(auto_discovery_index if auto_discovery_index >= 0 else 0)
            self.discovery_port.setValue(int(system_data.get("discovery_port", 8788)))
            self.computer_name.setText(str(system_data.get("computer_name", "")))
            self.operator_id.setText(str(system_data.get("operator_id", "ADMIN")))
            self.poll_interval.setValue(float(system_data.get("poll_interval", 0.5)))
            self.bw_price.setValue(float(data.get("bw_price_per_page", 2.0)))
            self.color_price.setValue(float(data.get("color_price_per_page", 10.0)))
            currency = str(data.get("currency", "INR"))
            index = self.currency.findText(currency)
            if index >= 0:
                self.currency.setCurrentIndex(index)
            else:
                self.currency.setCurrentText(currency)
            mode = data.get("retention_mode", "retain_all")
            idx = self.retention_mode.findData(mode)
            self.retention_mode.setCurrentIndex(idx if idx >= 0 else 0)
            self.retention_days.setValue(int(data.get("retention_days", 30)))
            backup_flag = bool(data.get("backup_enabled", True))
            backup_index = self.backup_enabled.findData(backup_flag)
            self.backup_enabled.setCurrentIndex(backup_index if backup_index >= 0 else 0)
            self.backup_folder.setText(str(data.get("backup_folder", "backup")))
        except Exception as exc:
            QMessageBox.warning(self, "Settings Error", f"Unable to load settings.\n{exc}")

    def save_settings(self) -> None:
        """Submit settings edits to API and notify parent windows to refresh summaries."""
        try:
            previous = self.api.get_system_config()
            self.api.update_system_config(
                server_ip=self.server_ip.text().strip(),
                server_port=int(self.server_port.value()),
                auto_discovery_enabled=bool(self.auto_discovery.currentData()),
                discovery_port=int(self.discovery_port.value()),
                computer_name=self.computer_name.text().strip(),
                operator_id=self.operator_id.text().strip() or "ADMIN",
                poll_interval=float(self.poll_interval.value()),
                bw_price_per_page=float(self.bw_price.value()),
                color_price_per_page=float(self.color_price.value()),
            )
            self.api.update_settings(
                bw_price_per_page=float(self.bw_price.value()),
                color_price_per_page=float(self.color_price.value()),
                currency=self.currency.currentText().strip() or "INR",
                retention_mode=str(self.retention_mode.currentData()),
                retention_days=int(self.retention_days.value()),
                backup_enabled=bool(self.backup_enabled.currentData()),
                backup_folder=self.backup_folder.text().strip() or "backup",
            )
            restart_needed = (
                str(previous.get("server_ip", "")).strip() != self.server_ip.text().strip()
                or int(previous.get("server_port", 8787)) != int(self.server_port.value())
            )
            message = "Settings updated successfully."
            if restart_needed:
                message += "\nRestart the application to apply new server IP/port."
            QMessageBox.information(self, "Saved", message)
            self.settings_saved.emit()
        except Exception as exc:
            QMessageBox.warning(self, "Settings Error", f"Unable to save settings.\n{exc}")

    def run_retention(self) -> None:
        """Allow operators to run archive/delete logic immediately instead of waiting for prompts."""
        mode = str(self.retention_mode.currentData())
        days = int(self.retention_days.value())
        if mode == "retain_all":
            QMessageBox.information(
                self,
                "Retention",
                "Retention mode is set to 'Retain All Records'. No archive/delete action was executed.",
            )
            return

        action = "archive" if mode == "archive_30_days" else "delete"
        confirm = QMessageBox.question(
            self,
            "Confirm Retention Action",
            f"Do you want to {action} records older than {days} days now?",
        )
        if confirm != QMessageBox.Yes:
            return

        try:
            result = self.api.execute_retention(mode=mode, days=days)
            QMessageBox.information(self, "Retention Complete", str(result))
            self.settings_saved.emit()
        except Exception as exc:
            QMessageBox.warning(self, "Retention Error", f"Unable to run retention action.\n{exc}")

    def run_backup_now(self) -> None:
        """Force an immediate backup through API to verify backup configuration quickly."""
        try:
            result = self.api.run_daily_backup(force=True)
            QMessageBox.information(self, "Backup Complete", str(result))
        except Exception as exc:
            QMessageBox.warning(self, "Backup Error", f"Unable to run backup.\n{exc}")
