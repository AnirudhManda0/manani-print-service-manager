from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QAbstractScrollArea


class IgnoreWheelEventFilter(QObject):
    """Prevents accidental mouse-wheel edits on spin controls."""

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            # Block wheel edits on numeric controls but keep parent panel scrolling usable.
            parent = obj.parent()
            while parent is not None and not isinstance(parent, QAbstractScrollArea):
                parent = parent.parent()
            if isinstance(parent, QAbstractScrollArea):
                bar = parent.verticalScrollBar()
                if bar is not None:
                    bar.setValue(bar.value() - event.angleDelta().y())
            return True
        return super().eventFilter(obj, event)


def disable_wheel_changes(widget) -> None:
    wheel_filter = IgnoreWheelEventFilter(widget)
    widget.installEventFilter(wheel_filter)
    widget._ignore_wheel_filter = wheel_filter
