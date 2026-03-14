from datetime import datetime

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class AddServiceDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Service")
        self.resize(320, 160)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_input = QLineEdit()
        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 100000)
        self.price_input.setDecimals(2)
        self.price_input.setValue(100.0)

        form.addRow("Service Name", self.name_input)
        form.addRow("Default Price", self.price_input)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def values(self):
        return self.name_input.text().strip(), float(self.price_input.value())


class ServicesPanel(QWidget):
    service_recorded = Signal()

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client
        self.services = []
        self.service_buttons = []
        self.currency = "INR"

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        top_bar = QHBoxLayout()
        title = QLabel("Services")
        title.setObjectName("sectionHeader")
        subtitle = QLabel("Tap a service button to record instantly")
        subtitle.setObjectName("secondaryLabel")
        self.add_btn = QPushButton("Add Service")
        self.add_btn.setMinimumHeight(54)
        self.add_btn.setMinimumWidth(180)
        self.add_btn.setProperty("variant", "primary")
        self.add_btn.clicked.connect(self.open_add_dialog)
        top_bar.addWidget(title)
        top_bar.addSpacing(14)
        top_bar.addWidget(subtitle)
        top_bar.addStretch()
        top_bar.addWidget(self.add_btn)
        root.addLayout(top_bar)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("secondaryLabel")
        root.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll_container = QWidget()
        self.grid = QGridLayout(self.scroll_container)
        self.grid.setSpacing(12)
        self.scroll.setWidget(self.scroll_container)
        root.addWidget(self.scroll)

        self.refresh_services()

    def refresh_services(self) -> None:
        try:
            self.services = self.api.list_services()
            settings = self.api.get_settings()
            self.currency = str(settings.get("currency", "INR"))
        except Exception as exc:
            QMessageBox.warning(self, "Service Error", f"Could not load services.\n{exc}")
            return

        for btn in self.service_buttons:
            btn.deleteLater()
        self.service_buttons.clear()

        for i, service in enumerate(self.services):
            btn = QPushButton(f"{service['service_name']}\n{self.currency} {service['default_price']:.2f}")
            btn.setMinimumHeight(96)
            btn.setMinimumWidth(210)
            btn.setObjectName("serviceActionButton")
            btn.setProperty("variant", "primary")
            btn.clicked.connect(lambda checked=False, s=service: self.record_service(s))
            row = i // 4
            col = i % 4
            self.grid.addWidget(btn, row, col)
            self.service_buttons.append(btn)
        if not self.services:
            self.status_label.setText("No services yet. Use Add Service to create your first service.")
        else:
            self.status_label.setText(f"{len(self.services)} services loaded")

    def open_add_dialog(self) -> None:
        dialog = AddServiceDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        name, price = dialog.values()
        if not name:
            QMessageBox.warning(self, "Validation", "Service name is required.")
            return
        try:
            self.api.add_service(name, price)
            self.refresh_services()
        except Exception as exc:
            QMessageBox.warning(self, "Add Service Error", str(exc))

    def record_service(self, service: dict) -> None:
        try:
            self.api.record_service(service_id=service["id"])
            self.status_label.setText(
                f"Recorded '{service['service_name']}' at {datetime.now().strftime('%H:%M:%S')}"
            )
            self.service_recorded.emit()
        except Exception as exc:
            QMessageBox.warning(self, "Record Error", str(exc))
