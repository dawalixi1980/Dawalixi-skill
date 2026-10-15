# -*- coding: utf-8 -*-
"""dxf-text.py —— 从 DXF 里抽出全部文字内容(图纸内容检索的基础)

用法:python dxf-text.py <in.dxf> <out.txt> [keyword]
输出(ASCII):TEXT_OK <count> <path> | HIT <keyword> <n> | TEXT_ERR <reason>

抽取范围:TEXT / MTEXT / INSERT 块属性 / 块定义内文字 / 图层名 / 标注文字。
要点:不需要渲染,SHX 字体不影响抽取 —— CAD 图纸里的图名、图号、说明、表格都是数据。
"""
import sys
import pathlib

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def collect(doc):
    out = []

    def add(tag, value):
        v = (value or "").strip()
        if v:
            out.append((tag, v))

    for e in doc.modelspace():
        kind = e.dxftype()
        try:
            if kind == "TEXT":
                add("TEXT", e.dxf.text)
            elif kind == "MTEXT":
                add("MTEXT", e.text)
            elif kind == "INSERT":
                add("BLOCK", e.dxf.name)
                for a in e.attribs:
                    add("ATTR", a.dxf.text)
            elif kind == "DIMENSION":
                add("DIM", getattr(e.dxf, "text", ""))
        except Exception:
            pass

    for blk in doc.blocks:
        for e in blk:
            try:
                if e.dxftype() == "TEXT":
                    add("BLK_TEXT", e.dxf.text)
                elif e.dxftype() == "MTEXT":
                    add("BLK_MTEXT", e.text)
                elif e.dxftype() == "ATTDEF":
                    add("ATTDEF", e.dxf.text)
            except Exception:
                pass

    for layer in doc.layers:
        add("LAYER", layer.dxf.name)
    return out


def main():
    if len(sys.argv) < 3:
        print("USAGE: dxf-text.py <in.dxf> <out.txt> [keyword]")
        return 2
    src, dst = sys.argv[1], sys.argv[2]
    keyword = sys.argv[3] if len(sys.argv) > 3 else None
    try:
        import ezdxf
        doc = ezdxf.readfile(src)
    except Exception as exc:
        print("TEXT_ERR %s: %s" % (type(exc).__name__, exc))
        return 1

    items = collect(doc)
    pathlib.Path(dst).write_text("\n".join("%s\t%s" % (t, v) for t, v in items), encoding="utf-8")
    print("TEXT_OK %d %s" % (len(items), dst))
    if keyword:
        hits = [v for _, v in items if keyword in v]
        print("HIT %s %d" % (keyword, len(hits)))
        for h in hits[:10]:
            print("  " + h.replace("\n", " ")[:160])
    return 0


if __name__ == "__main__":
    sys.exit(main())
