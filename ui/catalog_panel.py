"""Catalog panel for PrintX service catalog and service activity."""

from ui.qt import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_currency


class CatalogStat(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("reportStat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)
        self.title = QLabel(title)
        self.title.setObjectName("reportStatTitle")
        self.value = QLabel("0")
        self.value.setObjectName("reportStatValue")
        layout.addWidget(self.title)
        layout.addWidget(self.value)

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class CatalogPanel(QWidget):
    """Dedicated catalog view for service list and recent service records."""

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client
        self.currency = "INR"

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Catalog")
        title.setObjectName("sectionHeader")
        subtitle = QLabel("Service catalog and recent service activity")
        subtitle.setObjectName("secondaryLabel")
        self.refresh_btn = QPushButton("Refresh Catalog")
        self.refresh_btn.setProperty("variant", "primary")
        self.refresh_btn.clicked.connect(self.refresh_data)
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(subtitle)
        header.addStretch()
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        self.stats = QGridLayout()
        self.stats.setSpacing(12)
        self.catalog_total = CatalogStat("Catalog Services")
        self.services_today = CatalogStat("Services Today")
        self.service_revenue = CatalogStat("Service Revenue Today")
        self.stats.addWidget(self.catalog_total, 0, 0)
        self.stats.addWidget(self.services_today, 0, 1)
        self.stats.addWidget(self.service_revenue, 0, 2)
        root.addLayout(self.stats)

        catalog_label = QLabel("Service Catalog")
        catalog_label.setObjectName("sectionHeader")
        root.addWidget(catalog_label)

        self.catalog_table = QTableWidget(0, 2)
        self.catalog_table.setHorizontalHeaderLabels(["Service Name", "Default Price"])
        self.catalog_table.setAlternatingRowColors(True)
        self.catalog_table.verticalHeader().setVisible(False)
        self.catalog_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.catalog_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.catalog_table.setMinimumHeight(220)
        root.addWidget(self.catalog_table)

        records_label = QLabel("Recent Service Records")
        records_label.setObjectName("sectionHeader")
        root.addWidget(records_label)

        self.records_table = QTableWidget(0, 4)
        self.records_table.setHorizontalHeaderLabels(["Time", "Service", "Price", "Record ID"])
        self.records_table.setAlternatingRowColors(True)
        self.records_table.verticalHeader().setVisible(False)
        self.records_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.records_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.records_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.records_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.records_table.setMinimumHeight(240)
        root.addWidget(self.records_table, 1)

        self.refresh_data()

    def refresh_data(self) -> None:
        try:
            services = self.api.list_services()
            settings = self.api.get_settings()
            report = self.api.get_report(period="daily")
            records = self.api.list_service_records(limit=250)
        except Exception as exc:
            QMessageBox.warning(self, "Catalog Error", f"Could not load catalog data.\n{exc}")
            return

        self.currency = settings.get("currency", "INR")
        self.catalog_total.set_value(str(len(services)))
        self.services_today.set_value(str(report.get("summary", {}).get("total_services", 0)))
        self.service_revenue.set_value(
            format_currency(self.currency, report.get("summary", {}).get("service_revenue", 0))
        )

        self.catalog_table.setRowCount(len(services))
        for row, service in enumerate(services):
            self.catalog_table.setItem(row, 0, QTableWidgetItem(str(service.get("service_name", ""))))
            self.catalog_table.setItem(
                row,
                1,
                QTableWidgetItem(format_currency(self.currency, float(service.get("default_price", 0.0)))),
            )

        self.records_table.setRowCount(len(records))
        for row, record in enumerate(records):
            self.records_table.setItem(row, 0, QTableWidgetItem(str(record.get("timestamp", ""))))
            self.records_table.setItem(row, 1, QTableWidgetItem(str(record.get("service_name", ""))))
            self.records_table.setItem(
                row,
                2,
                QTableWidgetItem(format_currency(self.currency, float(record.get("price", 0.0)))),
            )
            self.records_table.setItem(row, 3, QTableWidgetItem(str(record.get("id", ""))))
