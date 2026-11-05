"""
Pachul — ui_qt/qt.py
One import point for the Qt binding.

PySide6 (LGPL) is preferred; PyQt6 (GPLv3) works as a fallback so that an
existing install keeps running. Everything else in ui_qt imports Qt names
from *here* (``from .qt import QWidget, Qt, Signal``), never from a binding
directly, so switching bindings never touches the rest of the code.

Only fully scoped enums are used (``Qt.AlignmentFlag.AlignLeft``), which
both bindings accept.
"""

try:
    from PySide6 import QtCore, QtGui, QtWidgets, QtSvg
    from PySide6.QtCore import Signal, Slot, Property
    BINDING = "PySide6"
except ImportError:                                    # pragma: no cover
    from PyQt6 import QtCore, QtGui, QtWidgets, QtSvg
    from PyQt6.QtCore import pyqtSignal as Signal, pyqtSlot as Slot, \
        pyqtProperty as Property
    BINDING = "PyQt6"

# Re-export every Q* class (QWidget, QColor, QPainter, Qt, QSvgRenderer, …)
for _mod in (QtCore, QtGui, QtWidgets, QtSvg):
    globals().update({k: v for k, v in vars(_mod).items() if k.startswith("Q")})
del _mod
