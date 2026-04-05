"""Services panel for one-click service billing.

Operators manage a service catalog and record service sales.
All persistence is handled by API calls, not direct DB writes from UI.
"""

import ast
import math
import operator
from datetime import datetime

from ui.qt import (
    QDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    Signal,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_currency


def evaluate_price_expression(expression: str) -> float:
    """Safely evaluate +, -, *, / arithmetic expressions using AST."""
    if not expression or not expression.strip():
        raise ValueError("Expression is empty")

    allowed_binary = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
    }
    allowed_unary = {
        ast.UAdd: lambda x: x,
        ast.USub: lambda x: -x,
    }

    def _eval(node) -> float:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Num):  # pragma: no cover - for older AST variants.
            return float(node.n)
        if isinstance(node, ast.BinOp) and type(node.op) in allowed_binary:
            left = _eval(node.left)
            right = _eval(node.right)
            if isinstance(node.op, ast.Div) and abs(right) < 1e-12:
                raise ValueError("Division by zero")
            return float(allowed_binary[type(node.op)](left, right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in allowed_unary:
            return float(allowed_unary[type(node.op)](_eval(node.operand)))
        raise ValueError("Unsupported expression")

    try:
        parsed = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise ValueError("Invalid expression syntax") from exc

    result = _eval(parsed)
    if not math.isfinite(result):
        raise ValueError("Invalid numeric result")
    if result < 0:
        raise ValueError("Value cannot be negative")
    return round(result, 2)


class AddServiceDialog(QDialog):
    """Small form dialog to add a new service template to the catalog."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Service")
        self.resize(520, 230)
        self._calculated_value = 0.0

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.name_input = QLineEdit()
        self.name_input.setMinimumHeight(38)
        self.price_input = QLineEdit()
        self.price_input.setText("100")
        self.price_input.setMinimumHeight(46)
        self.price_input.setPlaceholderText("Type expression: 10 * 2, 5 + 5, 20 / 2")
        self.price_input.textChanged.connect(self._update_calculated_value)
        self.calculated_value_label = QLabel("Calculated Value: 100.00")
        self.calculated_value_label.setObjectName("secondaryLabel")

        form.addRow("Service Name", self.name_input)
        form.addRow("Price Expression", self.price_input)
        form.addRow("Result", self.calculated_value_label)
        layout.addLayout(form)

        buttons = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        cancel_btn = QPushButton("Cancel")
        self.save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(cancel_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        self._update_calculated_value()

    def _update_calculated_value(self) -> None:
        expr = self.price_input.text().strip()
        try:
            value = evaluate_price_expression(expr)
            self._calculated_value = value
            self.calculated_value_label.setText(f"Calculated Value: {value:.2f}")
            self.calculated_value_label.setStyleSheet("")
            self.save_btn.setEnabled(True)
        except ValueError as exc:
            self._calculated_value = -1.0
            self.calculated_value_label.setText(f"Invalid expression: {exc}")
            self.calculated_value_label.setStyleSheet("color: #c0392b;")
            self.save_btn.setEnabled(False)

    def values(self):
        return self.name_input.text().strip(), float(self._calculated_value)


class ServicesPanel(QWidget):
    """Renders service buttons and records service activity through API."""

    service_recorded = Signal()

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client
        self.services = []
        self.service_buttons = []
        self.currency = "INR"

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(14)

        top_bar = QHBoxLayout()
        title = QLabel("Services")
        title.setObjectName("sectionHeader")
        subtitle = QLabel("Tap a service button to record instantly")
        subtitle.setObjectName("secondaryLabel")
        self.add_btn = QPushButton("Add Service")
        self.add_btn.setMinimumHeight(44)
        self.add_btn.setMinimumWidth(170)
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
        self.scroll.setStyleSheet("border: none; background: transparent;")
        self.scroll_container = QWidget()
        self.grid = QGridLayout(self.scroll_container)
        self.grid.setContentsMargins(8, 8, 8, 8)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.scroll.setWidget(self.scroll_container)
        self.scroll.setMinimumHeight(150)
        self.scroll.setMaximumHeight(200)
        root.addWidget(self.scroll)

        self.refresh_services()

    def refresh_services(self) -> None:
        """Reload services and rebuild button grid from current catalog data."""
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
            btn = QPushButton(
                f"{service['service_name']}  |  {format_currency(self.currency, service['default_price'])}"
            )
            btn.setMinimumHeight(58)
            btn.setMaximumHeight(62)
            btn.setMinimumWidth(240)
            btn.setObjectName("serviceActionButton")
            btn.clicked.connect(lambda checked=False, s=service: self.record_service(s))
            row = i // 3
            col = i % 3
            self.grid.addWidget(btn, row, col)
            self.service_buttons.append(btn)
        for col in range(3):
            self.grid.setColumnStretch(col, 1)

        if not self.services:
            self.status_label.setText("No services yet. Use Add Service to create your first service.")
        else:
            self.status_label.setText(f"{len(self.services)} services loaded")

    def open_add_dialog(self) -> None:
        """Collect new service input and submit it to API."""
        dialog = AddServiceDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        name, price = dialog.values()
        if not name:
            QMessageBox.warning(self, "Validation", "Service name is required.")
            return
        if price < 0:
            QMessageBox.warning(self, "Validation", "Enter a valid price expression.")
            return
        try:
            self.api.add_service(name, price)
            self.refresh_services()
        except Exception as exc:
            QMessageBox.warning(self, "Add Service Error", str(exc))

    def record_service(self, service: dict) -> None:
        """Record one service action and notify parent dashboard to refresh totals."""
        service_name = str(service.get("service_name", "this service"))
        service_price = format_currency(self.currency, float(service.get("default_price", 0.0)))
        response = QMessageBox.question(
            self,
            "Confirm Service",
            f"Are you sure you want to apply '{service_name}'?\n\nDefault amount: {service_price}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if response != QMessageBox.Yes:
            self.status_label.setText(f"Cancelled '{service_name}'")
            return

        try:
            self.api.record_service(service_id=service["id"])
            self.status_label.setText(
                f"Recorded '{service['service_name']}' at {datetime.now().strftime('%H:%M:%S')}"
            )
            self.service_recorded.emit()
        except Exception as exc:
            QMessageBox.warning(self, "Record Error", str(exc))
