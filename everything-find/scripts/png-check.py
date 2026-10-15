# -*- coding: utf-8 -*-
"""png-check.py —— 量一张 PNG 的尺寸与"墨量"(用于判断是否空白页)

用法:python png-check.py <a.png> [b.png ...]
输出(ASCII,每行一张):IMG_OK <name> <w>x<h> ink=<pct>%
                      IMG_ERR <name> <reason>

墨量定义:灰度 < 200 的像素占比。整页空白(<0.2%)说明布局里没有内容,
        应回退到模型空间出图 —— dwg-shot.ps1 的 auto 模式就是靠它判定的。
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def ink_percent(path):
    from PIL import Image
    im = Image.open(path).convert("L")
    hist = im.histogram()
    ink = sum(hist[:200])
    total = float(im.size[0] * im.size[1]) or 1.0
    return im.size[0], im.size[1], 100.0 * ink / total


def main():
    if len(sys.argv) < 2:
        print("USAGE: png-check.py <a.png> [b.png ...]")
        return 2
    for path in sys.argv[1:]:
        name = path.replace("\\", "/").split("/")[-1]
        try:
            w, h, pct = ink_percent(path)
            print("IMG_OK %s %dx%d ink=%.3f%%" % (name, w, h, pct))
        except Exception as exc:
            print("IMG_ERR %s %s: %s" % (name, type(exc).__name__, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
