"""The Qt Quick UI loads cleanly: every QML file parses, every import/type resolves, delegates instantiate
with real data, and nothing logs a warning."""
import os

import pytest

pytest.importorskip("PySide6.QtQuick")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")      # no display needed (fonts are missing, layout is fine)

from PySide6.QtCore import QCoreApplication, QtMsgType, qInstallMessageHandler  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQuickControls2 import QQuickStyle  # noqa: E402

from lanwhodis import classify  # noqa: E402
from test_core import make  # noqa: E402


@pytest.fixture(scope="module")
def app():
    QQuickStyle.setStyle("Basic")
    return QGuiApplication.instance() or QGuiApplication([])


def pump(n=8):
    for _ in range(n):
        QCoreApplication.processEvents()


def sample_devices():
    cam = make("192.168.1.20", "aa:00:00:00:00:20", hostname="porch-cam")
    cam.vendor = "Hikvision"
    cam.open_ports |= {80, 554}
    cam.add_web_url("http://192.168.1.20/", "http", 3)
    tv = make("192.168.1.21", "aa:00:00:00:00:21")
    tv.vendor = "LG Electronics"
    tv.text.append("webOS TV")
    phone = make("192.168.1.22", "82:17:3f:57:9d:9b")
    phone.open_ports.add(62078)
    out = [classify.classify(d) for d in (cam, tv, phone)]
    cam.history = {"status": "new", "first_seen": 1_700_000_000, "seen_count": 1, "previous_ip": None}
    return out


def test_ui_loads_and_renders_populated_without_warnings(app, tmp_path, monkeypatch):
    monkeypatch.setenv("LANWHODIS_HOME", str(tmp_path))
    from lanwhodis import history
    from lanwhodis.gui.app import create_engine
    from lanwhodis.gui.backend import Backend, offline_snapshot

    messages = []
    qInstallMessageHandler(lambda mode, ctx, msg: messages.append((mode, msg)))
    try:
        backend = Backend()
        engine = create_engine(backend)
        assert engine.rootObjects(), "Main.qml failed to load: " + "; ".join(m for _, m in messages)
        win = engine.rootObjects()[0]

        devices = sample_devices()
        for d in devices:                                        # what a finished scan delivers
            backend._on_snapshot(d.to_dict())
        backend._devices = devices
        ghost = history.KnownDevice("aa:00:00:00:00:99", "aa:00:00:00:00:99", "Kitchen Sonos", "speaker",
                                    "Sonos, Inc.", None, "192.168.1.99", "192.168.1.0/24", 1.7e9, 1.7e9, 3, 2)
        backend._on_snapshot(offline_snapshot(ghost))
        pump()
        assert backend.devices.rowCount() == 4 and backend.hasDevices

        backend.select(devices[0].ip)                            # detail panel with every section type
        pump()
        cur = backend.current
        assert cur["name"] == "porch-cam" and cur["webUrl"] == "http://192.168.1.20/"
        assert [s["title"] for s in cur["sections"]][0] == "GENERAL" and cur["sections"][-1]["title"] == "WHY THIS TYPE"

        backend.select("offline:aa:00:00:00:00:99")              # offline variant
        pump()
        assert backend.current["offline"] and not backend.current["editable"]

        for mode in ("light", "deck", "dark"):                   # every theme + the list view + filters
            backend.theme = mode
            pump(2)
        backend.view = "list"
        backend.setCategory("Smart Home")
        backend.setSearch("cam")
        backend.setStatusFilter("new")
        backend.setSort("name")
        pump()
        backend.view, _ = "grid", backend.setCategory("")

        pump()

        problems = [m for mode, m in messages
                    if mode in (QtMsgType.QtWarningMsg, QtMsgType.QtCriticalMsg, QtMsgType.QtFatalMsg)
                    and not m.startswith("QFontDatabase")]       # offscreen platform ships no fonts
        assert problems == []
        win.deleteLater()
        backend.shutdown()
    finally:
        qInstallMessageHandler(None)
