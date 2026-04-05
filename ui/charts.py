"""Reusable dashboard/report charts for PrintX."""

from ui.qt import (
    Qt,
    QBrush,
    QColor,
    QFrame,
    QLabel,
    QPainter,
    QPen,
    QVBoxLayout,
    QWidget,
)

from ui.formatting import format_currency


class ChartCard(QFrame):
    """Simple titled card wrapper for custom-painted charts."""

    def __init__(self, title: str, chart_widget: QWidget) -> None:
        super().__init__()
        self.setObjectName("reportStat")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("reportStatTitle")
        layout.addWidget(title_label)
        layout.addWidget(chart_widget, 1)


class RevenueTrendChart(QWidget):
    """Lightweight line chart showing total revenue over time."""

    def __init__(self) -> None:
        super().__init__()
        self.points = []
        self.currency = "INR"
        self.setMinimumHeight(220)

    def set_data(self, points: list, currency: str) -> None:
        self.points = points or []
        self.currency = currency or "INR"
        self.update()

    def paintEvent(self, _event) -> None:  # pragma: no cover - UI paint path.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(16, 12, -16, -24)
        painter.fillRect(rect, QBrush(QColor("#F8FAFC")))

        if not self.points:
            painter.setPen(QColor("#64748B"))
            painter.drawText(rect, Qt.AlignCenter, "No revenue data yet")
            return

        values = [float(item.get("total_revenue", 0.0)) for item in self.points]
        max_value = max(values) if max(values) > 0 else 1.0
        left = rect.left() + 22
        right = rect.right() - 10
        top = rect.top() + 10
        bottom = rect.bottom() - 34

        axis_pen = QPen(QColor("#CBD5E1"), 1)
        painter.setPen(axis_pen)
        painter.drawLine(left, bottom, right, bottom)
        painter.drawLine(left, top, left, bottom)

        step_x = (right - left) / max(1, len(self.points) - 1)
        chart_points = []
        for index, item in enumerate(self.points):
            x = left + (step_x * index)
            value = float(item.get("total_revenue", 0.0))
            y = bottom - ((value / max_value) * max(1, bottom - top))
            chart_points.append((x, y, item))

        line_pen = QPen(QColor("#2563EB"), 3)
        painter.setPen(line_pen)
        for index in range(len(chart_points) - 1):
            painter.drawLine(
                int(chart_points[index][0]),
                int(chart_points[index][1]),
                int(chart_points[index + 1][0]),
                int(chart_points[index + 1][1]),
            )

        point_brush = QBrush(QColor("#1D4ED8"))
        painter.setBrush(point_brush)
        painter.setPen(Qt.NoPen)
        for x, y, _item in chart_points:
            painter.drawEllipse(int(x - 4), int(y - 4), 8, 8)

        label_pen = QPen(QColor("#475569"))
        painter.setPen(label_pen)
        painter.setBrush(Qt.NoBrush)
        for x, _y, item in chart_points:
            painter.drawText(int(x - 28), bottom + 18, 56, 18, Qt.AlignCenter, str(item.get("label", "")))

        painter.drawText(left - 8, top - 2, 110, 18, Qt.AlignLeft, format_currency(self.currency, max_value))
        painter.drawText(left - 8, bottom - 18, 110, 18, Qt.AlignLeft, format_currency(self.currency, 0))


class ContributionChart(QWidget):
    """Bar chart comparing print and service contribution."""

    def __init__(self) -> None:
        super().__init__()
        self.printing_revenue = 0.0
        self.service_revenue = 0.0
        self.currency = "INR"
        self.setMinimumHeight(220)

    def set_data(self, printing_revenue: float, service_revenue: float, currency: str) -> None:
        self.printing_revenue = float(printing_revenue or 0.0)
        self.service_revenue = float(service_revenue or 0.0)
        self.currency = currency or "INR"
        self.update()

    def paintEvent(self, _event) -> None:  # pragma: no cover - UI paint path.
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = self.rect().adjusted(20, 20, -20, -20)
        painter.fillRect(rect, QBrush(QColor("#F8FAFC")))

        total = max(self.printing_revenue, self.service_revenue, 1.0)
        items = [
            ("Printing", self.printing_revenue, QColor("#2563EB")),
            ("Services", self.service_revenue, QColor("#10B981")),
        ]
        row_height = 56
        start_y = rect.top() + 24
        text_pen = QPen(QColor("#334155"))
        painter.setPen(text_pen)

        for index, (label, value, color) in enumerate(items):
            y = start_y + (index * row_height)
            painter.drawText(rect.left(), y, 110, 18, Qt.AlignLeft | Qt.AlignVCenter, label)
            painter.setPen(QPen(QColor("#E2E8F0"), 1))
            painter.setBrush(QBrush(QColor("#E2E8F0")))
            painter.drawRoundedRect(rect.left(), y + 22, rect.width() - 20, 14, 7, 7)
            painter.setBrush(QBrush(color))
            bar_width = int((rect.width() - 20) * (value / total))
            painter.drawRoundedRect(rect.left(), y + 22, max(8, bar_width), 14, 7, 7)
            painter.setPen(text_pen)
            painter.drawText(
                rect.left(),
                y + 38,
                rect.width() - 20,
                18,
                Qt.AlignRight | Qt.AlignVCenter,
                format_currency(self.currency, value),
            )
