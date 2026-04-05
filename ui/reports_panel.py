"""Reporting panel for daily/weekly/monthly business summaries.

Report payloads are retrieved from `/api/reports/{period}` and rendered for operators.
"""

from ui.qt import (
    QComboBox,
    QDate,
    QDateEdit,
    QFrame,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ui.charts import ChartCard, ContributionChart, RevenueTrendChart
from ui.formatting import format_currency


class ReportStat(QFrame):
    """Compact stat tile used in report summary header."""

    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("reportStat")
        self.setMinimumHeight(88)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        self.title = QLabel(title)
        self.title.setObjectName("reportStatTitle")
        self.value = QLabel("0")
        self.value.setObjectName("reportStatValue")
        layout.addWidget(self.title)
        layout.addWidget(self.value)
        layout.addStretch()

    def set_value(self, text: str) -> None:
        self.value.setText(text)


class ReportsPanel(QWidget):
    """Shows report filters, summary metrics, and service revenue table."""

    def __init__(self, api_client) -> None:
        super().__init__()
        self.api = api_client
        self.current_report = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        title = QLabel("Reports")
        title.setObjectName("sectionHeader")
        layout.addWidget(title)

        controls = QHBoxLayout()
        form = QFormLayout()
        self.period_combo = QComboBox()
        self.period_combo.addItems(["daily", "weekly", "monthly"])
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Period", self.period_combo)
        form.addRow("Anchor Date", self.date_edit)
        controls.addLayout(form)

        self.generate_btn = QPushButton("Generate Report")
        self.generate_btn.setMinimumHeight(54)
        self.generate_btn.setMinimumWidth(180)
        self.generate_btn.setProperty("variant", "primary")
        self.generate_btn.clicked.connect(self.load_report)
        controls.addWidget(self.generate_btn)
        controls.addStretch()
        layout.addLayout(controls)

        self.stat_grid = QGridLayout()
        self.stat_grid.setSpacing(10)
        self.stat_print_jobs = ReportStat("Print Jobs")
        self.stat_total_pages = ReportStat("Total Pages")
        self.stat_bw = ReportStat("B&W Pages")
        self.stat_color = ReportStat("Color Pages")
        self.stat_a4 = ReportStat("A4 Prints")
        self.stat_a3 = ReportStat("A3 Prints")
        self.stat_services = ReportStat("Services")
        self.stat_print_rev = ReportStat("Printing Revenue")
        self.stat_total_rev = ReportStat("Total Revenue")
        self.stat_grid.addWidget(self.stat_print_jobs, 0, 0)
        self.stat_grid.addWidget(self.stat_total_pages, 0, 1)
        self.stat_grid.addWidget(self.stat_bw, 0, 2)
        self.stat_grid.addWidget(self.stat_color, 0, 3)
        self.stat_grid.addWidget(self.stat_a4, 1, 0)
        self.stat_grid.addWidget(self.stat_a3, 1, 1)
        self.stat_grid.addWidget(self.stat_services, 1, 2)
        self.stat_grid.addWidget(self.stat_print_rev, 1, 3)
        self.stat_grid.addWidget(self.stat_total_rev, 2, 0, 1, 2)
        layout.addLayout(self.stat_grid)

        self.chart_grid = QGridLayout()
        self.chart_grid.setSpacing(12)
        self.chart_grid.setColumnStretch(0, 1)
        self.chart_grid.setColumnStretch(1, 1)
        self.revenue_chart = RevenueTrendChart()
        self.contribution_chart = ContributionChart()
        self.chart_grid.addWidget(ChartCard("Revenue Trend", self.revenue_chart), 0, 0)
        self.chart_grid.addWidget(ChartCard("Print vs Service Contribution", self.contribution_chart), 0, 1)
        layout.addLayout(self.chart_grid)

        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setMinimumHeight(120)
        layout.addWidget(self.summary_box)

        self.service_table = QTableWidget(0, 3)
        self.service_table.setHorizontalHeaderLabels(["Service Name", "Count", "Revenue"])
        self.service_table.setAlternatingRowColors(True)
        self.service_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.service_table)

        self.load_report()

    def load_report(self) -> None:
        """Fetch selected period report from API and render it."""
        period = self.period_combo.currentText()
        day = self.date_edit.date().toString("yyyy-MM-dd")
        try:
            report = self.api.get_report(period=period, day=day)
            self.current_report = report
            self._render_report(report)
        except Exception as exc:
            QMessageBox.warning(self, "Report Error", f"Could not generate report.\n{exc}")

    def _render_report(self, report: dict) -> None:
        """Convert report response into user-facing text, cards, and breakdown rows."""
        summary = report["summary"]
        currency = report.get("currency", "INR")

        text = "\n".join(
            [
                f"Date/Range: {report.get('label', '')}",
                f"Total Pages Printed: {summary.get('total_pages', 0)}",
                f"A4 Prints: {summary.get('a4_print_jobs', 0)}",
                f"A3 Prints: {summary.get('a3_print_jobs', 0)}",
                f"Total Services: {summary.get('total_services', 0)}",
                f"Total Revenue: {format_currency(currency, summary.get('total_revenue', 0))}",
                f"Service Revenue: {format_currency(currency, summary.get('service_revenue', 0))}",
                "Service Breakdown:",
            ]
        )
        self.summary_box.setText(text)
        self.stat_print_jobs.set_value(str(summary.get("total_print_jobs", 0)))
        self.stat_total_pages.set_value(str(summary.get("total_pages", 0)))
        self.stat_bw.set_value(str(summary.get("bw_pages", 0)))
        self.stat_color.set_value(str(summary.get("color_pages", 0)))
        self.stat_a4.set_value(str(summary.get("a4_print_jobs", 0)))
        self.stat_a3.set_value(str(summary.get("a3_print_jobs", 0)))
        self.stat_services.set_value(str(summary.get("total_services", 0)))
        self.stat_print_rev.set_value(format_currency(currency, summary.get("printing_revenue", 0)))
        self.stat_total_rev.set_value(format_currency(currency, summary.get("total_revenue", 0)))
        self.revenue_chart.set_data(report.get("trend_points", []), currency)
        contribution = report.get("contribution", {})
        self.contribution_chart.set_data(
            contribution.get("printing_revenue", 0.0),
            contribution.get("service_revenue", 0.0),
            currency,
        )

        items = report.get("services_breakdown", [])
        self.service_table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.service_table.setItem(row, 0, QTableWidgetItem(str(item.get("service_name", ""))))
            self.service_table.setItem(row, 1, QTableWidgetItem(str(item.get("count", 0))))
            self.service_table.setItem(row, 2, QTableWidgetItem(format_currency(currency, item.get("revenue", 0))))
