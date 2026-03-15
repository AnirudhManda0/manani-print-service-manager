from PySide6.QtCore import QEvent, QObject


class IgnoreWheelEventFilter(QObject):
    """Prevents accidental mouse-wheel edits on spin controls."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            return True
        return super().eventFilter(obj, event)


def disable_wheel_changes(widget) -> None:
    wheel_filter = IgnoreWheelEventFilter(widget)
    widget.installEventFilter(wheel_filter)
    widget._ignore_wheel_filter = wheel_filter
