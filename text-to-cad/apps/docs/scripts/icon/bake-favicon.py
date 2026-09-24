"""Bake the /icon page's Blue PNG download into both docs favicons.

Usage: python apps/docs/scripts/icon/bake-favicon.py /path/to/icon-blue.png
Requires Pillow (only for this manual asset refresh, not the docs build).
"""
import argparse
from pathlib import Path

from PIL import Image

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("render", type=Path)
args = parser.parse_args()
public = Path(__file__).resolve().parents[2] / "public"
with Image.open(args.render) as source:
    icon = source.convert("RGBA")
if icon.size != (512, 512):
    parser.error("render must be 512 × 512")
if icon.getpixel((0, 0))[3] != 0 or not icon.getbbox():
    parser.error("render must contain geometry on a transparent background")
icon.save(public / "favicon.png", optimize=True)
icon.save(public / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
print("Wrote static blue favicon.png and multi-size favicon.ico.")
