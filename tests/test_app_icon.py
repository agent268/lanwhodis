"""The app ships a real icon: valid multi-size .ico, a PNG, and it is declared as package data."""
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "lanwhodis" / "gui" / "assets" / "app"


def test_ico_has_all_sizes_and_png_frames():
    data = (APP / "lanwhodis.ico").read_bytes()
    reserved, kind, count = struct.unpack_from("<HHH", data)
    assert (reserved, kind) == (0, 1)
    sizes = []
    for i in range(count):
        w, h, _, _, _, _, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
        assert data[offset:offset + 8] == b"\x89PNG\r\n\x1a\n"
        sizes.append(w or 256)
    assert sizes == [16, 24, 32, 48, 64, 128, 256]


def test_png_and_svg_exist_and_icon_is_package_data():
    assert (APP / "lanwhodis.png").read_bytes()[:4] == b"\x89PNG"
    assert (APP / "lanwhodis.svg").read_text(encoding="utf-8").startswith("<svg")
    assert "gui/assets/app/*" in (ROOT / "pyproject.toml").read_text(encoding="utf-8")
