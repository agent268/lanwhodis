"""Render the app icon (gui/assets/app/lanwhodis.svg) to lanwhodis.png (256 px) and a multi-size lanwhodis.ico.

Run after editing the SVG:  python tools/build_icon.py
"""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

APP = Path(__file__).resolve().parent.parent / "lanwhodis" / "gui" / "assets" / "app"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def render(renderer: QSvgRenderer, size: int) -> QImage:
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(p)
    p.end()
    return img


def png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(ba)


def main() -> int:
    _app = QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(APP / "lanwhodis.svg"))
    if not renderer.isValid():
        return 1
    frames = [(s, png_bytes(render(renderer, s))) for s in SIZES]
    (APP / "lanwhodis.png").write_bytes(dict(frames)[256])
    head = struct.pack("<HHH", 0, 1, len(frames))
    offset = 6 + 16 * len(frames)
    entries, blobs = b"", b""
    for size, data in frames:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    (APP / "lanwhodis.ico").write_bytes(head + entries + blobs)
    print("wrote", APP / "lanwhodis.ico", [s for s, _ in frames])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
