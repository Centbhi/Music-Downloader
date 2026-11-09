"""Regenerate the app icon (assets/app.ico).

Green rounded square (#1db954, matches style.ACCENT) with the white
music_note glyph from icons.py. Run:  python tools/make_icon.py
Requires PyQt5 (already a runtime dep). No Pillow needed.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import QColor, QImage, QPainter, QPainterPath
from PyQt5.QtSvg import QSvgRenderer
from PyQt5.QtWidgets import QApplication

ACCENT = "#1db954"
VIEWBOX = "0 -960 960 960"
# Same path as icons._ICONS['music_note']
NOTE_PATH = ("M400-120q-66 0-113-47t-47-113q0-66 47-113t113-47q23 0 "
             "42.5 5.5T480-418v-422h240v160H560v400q0 66-47 113t-113 47Z")
SIZE = 256


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(repo_root, "assets")
    os.makedirs(out_dir, exist_ok=True)
    ico_path = os.path.join(out_dir, "app.ico")
    png_path = os.path.join(out_dir, "app.png")

    app = QApplication(sys.argv)
    img = QImage(SIZE, SIZE, QImage.Format_ARGB32)
    img.fill(Qt.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    bg = QPainterPath()
    radius = SIZE * 0.22
    bg.addRoundedRect(0, 0, SIZE, SIZE, radius, radius)
    p.fillPath(bg, QColor(ACCENT))

    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256' "
        f"viewBox='{VIEWBOX}' fill='#ffffff'><path d='{NOTE_PATH}'/></svg>"
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    margin = SIZE * 0.20
    renderer.render(p, QRectF(margin, margin, SIZE - 2 * margin, SIZE - 2 * margin))
    p.end()

    if not img.save(png_path, "PNG"):
        raise SystemExit("failed to write " + png_path)
    # Single 256px image ICO; Windows scales it down for taskbar/explorer.
    if not img.save(ico_path, "ICO"):
        raise SystemExit("failed to write " + ico_path)
    print("wrote", png_path)
    print("wrote", ico_path)


if __name__ == "__main__":
    main()
