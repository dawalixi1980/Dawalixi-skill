#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""probe.py - PDF 体检，零模型开销。

不看内容，只回答三件事：
  1. 这是什么（图纸 / 文档 / 扫描件）
  2. 有没有书签、有没有文本层（决定能不能零渲染建索引）
  3. 走哪条路要多少 token

用法:
    python probe.py <file.pdf> [--json] [--deep]

--deep 会调用 get_drawings() 统计矢量图元数，慢，仅在对单页有疑问时用。
"""
import argparse
import json
import os
import sys

import fitz

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 实测：图框（标题栏）在页面最底部、横贯全宽。取下部 15% 整幅宽。
TB_X0, TB_Y0 = 0.0, 0.85

# ISO 幅面（单位 pt，1pt = 1/72 inch）
PAPER = [
    ("A0", 2384, 3370),
    ("A1", 1684, 2384),
    ("A2", 1191, 1684),
    ("A3", 842, 1191),
    ("A4", 595, 842),
]

# 官方口径：图片输入按 token 计费，单张最高 384 tokens（DeepSeek V4.1-Flash）
IMG_TOKENS_MAX = 384
# 中文经验值：约 1.5 字符 / token（估算，非实测）
CHARS_PER_TOKEN = 1.5


def paper_name(w, h):
    short, long_ = min(w, h), max(w, h)
    best, best_err = None, 1e9
    for name, pw, ph in PAPER:
        err = abs(short - pw) / pw + abs(long_ - ph) / ph
        if err < best_err:
            best, best_err = name, err
    # 允许 12% 误差，否则算非标幅面
    return best if best_err < 0.24 else f"非标({round(short)}x{round(long_)})"


def page_probe(page, deep=False):
    rect = page.rect
    words = page.get_text("words")
    text = page.get_text()
    tb = [w for w in words if w[0] >= rect.width * TB_X0 and w[1] >= rect.height * TB_Y0]
    info = {
        "text_chars": len(text.strip()),
        "words": len(words),
        "tb_words": len(tb),
        "tb_text": "".join(w[4] for w in tb)[:240],
        "images": len(page.get_images(full=True)),
    }
    if deep:
        try:
            info["vector_ops"] = len(page.get_drawings())
        except Exception as e:  # 某些损坏页会炸
            info["vector_ops"] = f"err:{e}"
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--deep", action="store_true", help="统计矢量图元（慢）")
    args = ap.parse_args()

    path = args.pdf
    if not os.path.isfile(path):
        sys.exit(f"文件不存在: {path}")

    doc = fitz.open(path)
    n = len(doc)
    toc = doc.get_toc(simple=True)

    # 全量扫描页码信息（get_text 很快，180 页也是秒级）
    pages = [page_probe(doc[i], deep=args.deep and i < 3) for i in range(n)]

    chars = sum(p["text_chars"] for p in pages)
    tb_hit = sum(1 for p in pages if p["tb_words"] > 0)
    r0 = doc[0].rect
    size = paper_name(r0.width, r0.height)
    landscape = r0.width > r0.height
    mean_chars = chars / n if n else 0

    # 版式判定
    if mean_chars < 10:
        layout = "scanned"          # 几乎无文本层 → 扫描件/纯栅格
    elif landscape and max(r0.width, r0.height) >= 1000:
        layout = "drawing"          # A3 横及以上 + 有文字层 → 图纸
    else:
        layout = "document"

    # 路由建议
    if toc:
        index_route = "toc"
    elif layout == "scanned":
        index_route = "vision_titleblock"
    elif tb_hit >= max(1, n // 2):
        index_route = "text_titleblock"
    else:
        index_route = "catalog_or_manual"

    img_tok = n * IMG_TOKENS_MAX
    txt_tok = round(chars / CHARS_PER_TOKEN) if chars >= 10 else None

    doc.close()

    report = {
        "file": os.path.basename(path),
        "path": os.path.abspath(path),
        "mb": round(os.path.getsize(path) / 1048576, 1),
        "pages": n,
        "first_page_pt": [round(r0.width), round(r0.height)],
        "paper": size,
        "orientation": "横" if landscape else "竖",
        "layout": layout,
        "toc_entries": len(toc),
        "text_chars_total": chars,
        "text_chars_mean_per_page": round(mean_chars, 1),
        "pages_with_titleblock_text": tb_hit,
        "index_route": index_route,
        "est_tokens": {
            "all_pages_as_image": img_tok,
            "all_pages_as_text": txt_tok,
            "index_local_only": 0,
        },
        "sample_first_pages": [
            {"page": i + 1, "chars": p["text_chars"], "tb": p["tb_text"][:120]}
            for i, p in enumerate(pages[:3])
        ],
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    r = report
    print(f"文件      {r['file']}")
    print(f"大小/页数 {r['mb']} MB / {r['pages']} 页")
    print(f"幅面      {r['paper']} {r['orientation']}  ({r['first_page_pt'][0]}x{r['first_page_pt'][1]} pt)")
    print(f"类型      {r['layout']}")
    print(f"书签      {r['toc_entries']} 条" + ("  <- 可直接建索引" if r["toc_entries"] else ""))
    print(f"文本层    共 {r['text_chars_total']} 字符，均 {r['text_chars_mean_per_page']} 字/页")
    print(f"图框文字  {r['pages_with_titleblock_text']}/{r['pages']} 页命中")
    print(f"索引路线  {r['index_route']}")
    print("成本预估  "
          f"全图 {r['est_tokens']['all_pages_as_image']} tok | "
          f"全文 {r['est_tokens']['all_pages_as_text'] if r['est_tokens']['all_pages_as_text'] is not None else '—（无文本层）'} tok | "
          f"仅索引 {r['est_tokens']['index_local_only']} tok")
    print("首页摘要")
    for s in r["sample_first_pages"]:
        print(f"  p{s['page']}  {s['chars']:>5} 字  {s['tb']}")


if __name__ == "__main__":
    main()
