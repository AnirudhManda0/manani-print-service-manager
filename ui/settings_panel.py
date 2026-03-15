from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ui.input_filters import disable_wheel_changes


class SettingsPanel(QWidget):
    settings_saved = Signal()

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client

        layout = QVBoxLayout(self)
        title = QLabel("Settings")
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        form = QFormLayout()
        self.bw_price = QDoubleSpinBox()
        self.bw_price.setRange(0, 100000)
        self.bw_price.setDecimals(2)
        disable_wheel_changes(self.bw_price)
        self.color_price = QDoubleSpinBox()
        self.color_price.setRange(0, 100000)
        self.color_price.setDecimals(2)
        disable_wheel_changes(self.color_price)
        self.currency = QLineEdit()
        self.currency.setMaxLength(8)

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
        try:
            data = self.api.get_settings()
            self.bw_price.setValue(float(data.get("bw_price_per_page", 2.0)))
            self.color_price.setValue(float(data.get("color_price_per_page", 10.0)))
            self.currency.setText(str(data.get("currency", "INR")))
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
        try:
            self.api.update_settings(
                bw_price_per_page=float(self.bw_price.value()),
                color_price_per_page=float(self.color_price.value()),
                currency=self.currency.text().strip() or "INR",
                retention_mode=str(self.retention_mode.currentData()),
                retention_days=int(self.retention_days.value()),
                backup_enabled=bool(self.backup_enabled.currentData()),
                backup_folder=self.backup_folder.text().strip() or "backup",
            )
            QMessageBox.information(self, "Saved", "Settings updated successfully.")
            self.settings_saved.emit()
        except Exception as exc:
            QMessageBox.warning(self, "Settings Error", f"Unable to save settings.\n{exc}")

    def run_retention(self) -> None:
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
        try:
            result = self.api.run_daily_backup(force=True)
            QMessageBox.information(self, "Backup Complete", str(result))
        except Exception as exc:
            QMessageBox.warning(self, "Backup Error", f"Unable to run backup.\n{exc}")
