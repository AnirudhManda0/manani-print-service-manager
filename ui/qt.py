"""Qt compatibility layer: prefer PySide2 (Windows 7), fallback to PySide6."""

try:  # pragma: no cover - import resolution depends on target runtime.
    from PySide2.QtCore import QDate, QEvent, QObject, QSize, QTimer, Qt, Signal
    from PySide2.QtGui import QIcon
    from PySide2.QtWidgets import (
        QAbstractScrollArea,
        QApplication,
        QComboBox,
        QDateEdit,
        QDialog,
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError:  # pragma: no cover - fallback for older runtime stacks.
    from PySide6.QtCore import QDate, QEvent, QObject, QSize, QTimer, Qt, Signal
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QAbstractScrollArea,
        QApplication,
        QComboBox,
        QDateEdit,
        QDialog,
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QGridLayout,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSpinBox,
        QTableWidget,
        QTableWidgetItem,
        QTabWidget,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
