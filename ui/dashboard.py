from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from ui.formatting import format_currency


class StatCard(QFrame):
    def __init__(self, title: str, value: str = "0", accent: str = "blue") -> None:
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setObjectName("statCard")
        self.setProperty("accent", accent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("statTitle")
        self.value_label = QLabel(value)
        self.value_label.setObjectName("statValue")
        self.value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        layout.addWidget(self.title_label)
        layout.addWidget(self.value_label)
        layout.addStretch()

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class DashboardPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.total_prints = StatCard("Total Prints Today", accent="blue")
        self.bw_pages = StatCard("B&W Pages", accent="cyan")
        self.color_pages = StatCard("Color Pages", accent="orange")
        self.total_services = StatCard("Total Services Today", accent="green")
        self.total_revenue = StatCard("Total Revenue Today", accent="gold")

        layout.addWidget(self.total_prints, 0, 0)
        layout.addWidget(self.bw_pages, 0, 1)
        layout.addWidget(self.color_pages, 0, 2)
        layout.addWidget(self.total_services, 0, 3)
        layout.addWidget(self.total_revenue, 1, 0, 1, 4)

    def update_metrics(self, payload: dict) -> None:
        currency = payload.get("currency", "INR")
        self.total_prints.set_value(str(payload.get("total_print_jobs", 0)))
        self.bw_pages.set_value(str(payload.get("bw_pages", 0)))
        self.color_pages.set_value(str(payload.get("color_pages", 0)))
        self.total_services.set_value(str(payload.get("total_services", 0)))
        self.total_revenue.set_value(format_currency(currency, payload.get("total_revenue", 0)))
