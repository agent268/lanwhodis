"""QML image provider for the bundled Fluent icons, recoloured on the fly.

QML usage:  Image { source: "image://lw/" + encodeURIComponent("device_camera,#4a9eff") }
The icon SVGs carry Fluent's default #212121 fill; the provider swaps it for the requested colour and
rasterises at the requested size, so one icon serves every theme (same idea as steamos-fm's ActionIconProvider).
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtQuick import QQuickImageProvider
from PySide6.QtSvg import QSvgRenderer

ICON_DIR = Path(__file__).parent / "assets" / "icons"
_FLUENT_FILL = "#212121"


class IconProvider(QQuickImageProvider):
    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Pixmap)
        self._svg: dict[str, str] = {}
        self._cache: dict[tuple[str, str, int], QPixmap] = {}

    def _source(self, name: str) -> str | None:
        if name not in self._svg:
            path = ICON_DIR / f"{name}.svg"
            self._svg[name] = path.read_text(encoding="utf-8") if path.is_file() else ""
        return self._svg[name] or None

    def requestPixmap(self, id: str, size: QSize, requestedSize: QSize) -> QPixmap:  # noqa: N802 (Qt API)
        name, _, color = unquote(id).partition(",")
        qc = QColor(color)
        color = qc.name() if qc.isValid() else "#ffffff"      # opaque #rrggbb: alpha isn't valid in an SVG fill
        px = max(requestedSize.width(), requestedSize.height(), 16) if requestedSize.isValid() else 48
        key = (name, color, px)
        if key not in self._cache:
            pm = QPixmap(px, px)
            pm.fill(Qt.GlobalColor.transparent)
            svg = self._source(name)
            if svg:
                renderer = QSvgRenderer(svg.replace(_FLUENT_FILL, color).encode("utf-8"))
                p = QPainter(pm)
                p.setRenderHint(QPainter.RenderHint.Antialiasing)
                renderer.render(p)
                p.end()
            self._cache[key] = pm
        return self._cache[key]
