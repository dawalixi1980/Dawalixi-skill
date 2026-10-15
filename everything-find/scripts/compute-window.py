# -*- coding: utf-8 -*-
"""compute-window.py —— 从 DXF 算出一块"只包住主体图形"的打印窗口

用法:python compute-window.py <in.dxf> [trim_ratio] [margin_ratio]
输出(ASCII):WINDOW <x1>,<y1>,<x2>,<y2>    ← 直接喂给 AutoCAD -PLOT 的窗口两点
            STATS entities=<n> kept=<m>

为什么需要:模型空间里常有游离的说明文字/图签,用"范围(Extents)"出图会把整张纸拉大、
主体缩得很小。这里做**迭代剔除离群实体**:反复丢掉落在当前包围盒边缘 4% 内的实体中心,
直到数量稳定,再留 3% 边距。
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def box_of(items):
    return (min(a for a, b, c, d in items), min(b for a, b, c, d in items),
            max(c for a, b, c, d in items), max(d for a, b, c, d in items))


def main():
    if len(sys.argv) < 2:
        print("USAGE: compute-window.py <in.dxf> [trim_ratio] [margin_ratio]")
        return 2
    src = sys.argv[1]
    trim = float(sys.argv[2]) if len(sys.argv) > 2 else 0.04
    margin = float(sys.argv[3]) if len(sys.argv) > 3 else 0.03
    try:
        import ezdxf
        from ezdxf import bbox as ezbbox
    except Exception as exc:
        print("WINDOW_ERR no-ezdxf %s" % exc)
        return 1

    try:
        doc = ezdxf.readfile(src)
    except Exception as exc:
        print("WINDOW_ERR read %s: %s" % (type(exc).__name__, exc))
        return 1

    boxes = []
    for e in doc.modelspace():
        try:
            b = ezbbox.extents([e])
            if b.has_data:
                boxes.append((float(b.extmin.x), float(b.extmin.y), float(b.extmax.x), float(b.extmax.y)))
        except Exception:
            pass
    if not boxes:
        print("WINDOW_ERR no-entities")
        return 1

    cur = boxes
    for _ in range(8):
        x1, y1, x2, y2 = box_of(cur)
        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            break
        nxt = [e for e in cur
               if x1 + trim * w <= (e[0] + e[2]) / 2 <= x2 - trim * w
               and y1 + trim * h <= (e[1] + e[3]) / 2 <= y2 - trim * h]
        if len(nxt) == len(cur) or len(nxt) < max(3, int(0.15 * len(boxes))):
            break
        cur = nxt

    x1, y1, x2, y2 = box_of(cur)
    mx = margin * (x2 - x1)
    my = margin * (y2 - y1)
    print("STATS entities=%d kept=%d" % (len(boxes), len(cur)))
    print("WINDOW %.4f,%.4f,%.4f,%.4f" % (x1 - mx, y1 - my, x2 + mx, y2 + my))
    return 0


if __name__ == "__main__":
    sys.exit(main())
