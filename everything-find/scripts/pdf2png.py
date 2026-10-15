# -*- coding: utf-8 -*-
"""pdf2png.py —— 把矢量 PDF 光栅化成 PNG(给视觉模型判读用)

用法:python pdf2png.py <in.pdf> <out.png> [target_width_px] [page_index]
输出(ASCII):PDF2PNG_OK <w> <h> <page_count> <path> | PDF2PNG_ERR <reason>

要点:PDF 是矢量,按目标像素宽度反算缩放,所以"高清"只是这一个参数。
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def main():
    if len(sys.argv) < 3:
        print("USAGE: pdf2png.py <in.pdf> <out.png> [target_width_px] [page_index]")
        return 2
    try:
        import fitz  # PyMuPDF
    except Exception as exc:
        print("PDF2PNG_ERR no-pymupdf %s" % exc)
        return 1

    src, dst = sys.argv[1], sys.argv[2]
    target = int(sys.argv[3]) if len(sys.argv) > 3 else 2400
    page_index = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    try:
        doc = fitz.open(src)
        if doc.page_count == 0:
            print("PDF2PNG_ERR empty-pdf")
            return 1
        if page_index < 0 or page_index >= doc.page_count:
            page_index = 0
        page = doc[page_index]
        zoom = float(target) / float(page.rect.width or 1.0)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        pix.save(dst)
        print("PDF2PNG_OK %d %d %d %s" % (pix.width, pix.height, doc.page_count, dst))
        return 0
    except Exception as exc:
        print("PDF2PNG_ERR %s: %s" % (type(exc).__name__, exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
