"""LanWhodis GUI: Qt Quick (QML) front end over the Qt-free core.

The look follows steamos-fm (dark navy + accent, Fluent icons, boxed sections); the logic lives in
backend.py, QML only renders.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle

from .backend import Backend
from .iconprovider import IconProvider

QML_DIR = Path(__file__).parent / "qml"


def create_engine(backend: Backend) -> QQmlApplicationEngine:
    """Engine with the icon provider, the `backend` context property and Main.qml loaded."""
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML_DIR))
    engine.addImageProvider("lw", IconProvider())
    engine.rootContext().setContextProperty("backend", backend)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    return engine


def main(argv: list[str] | None = None) -> int:
    QQuickStyle.setStyle("Basic")            # our components draw themselves; avoid native-style interference
    app = QGuiApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("LanWhodis")
    app.setOrganizationName("LanWhodis")
    backend = Backend()
    engine = create_engine(backend)
    if not engine.rootObjects():
        return 1
    code = app.exec()
    backend.shutdown()
    return code


if __name__ == "__main__":
    sys.exit(main())
