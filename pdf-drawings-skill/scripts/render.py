#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render.py - 按需渲染 / 裁剪，带缓存。只在「真要看图」时才用。

设计原则：
  * 默认低 DPI 通读，确认后再对局部高 DPI 复核（省 token、省时间）
  * 只渲染点名的页/区域，绝不整本转图
  * 结果按 (文件指纹, 页, DPI, 区域) 缓存，重复提问不重渲染

用法:
    # 列出可用区域预设
    python render.py --boxes

    # 通读：整页 150 DPI
    python render.py a.pdf --pages 12,15 --dpi 150

    # 读图框（拿图号图名用；若文本层可读则不必渲染）
    python render.py a.pdf --page 12 --box titleblock --dpi 150

    # 细看某处（百分比裁剪，左,上,右,下）
    python render.py a.pdf --page 12 --crop 0.05,0.08,0.45,0.40 --dpi 400
"""
import argparse
import hashlib
import io
import json
import os
import sys

import fitz

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

IMG_TOKENS_MAX = 384          # 官方口径：单张图片最高 384 tokens
MAX_PX = 6000                 # 单边像素护栏，超了自动降 DPI

BOXES = {
    "full":         (0.00, 0.00, 1.00, 1.00),
    # 实测：图框（标题栏）在页面最底部、横贯全宽，图号/图名在右半区
    "titleblock":   (0.45, 0.90, 1.00, 1.00),   # 图号+图名（最常用）
    "titleblock_l": (0.00, 0.90, 1.00, 1.00),   # 含工程名称的整条图框
    "notes":        (0.00, 0.00, 1.00, 0.50),   # 施工图说明常在上半页
    "topleft":      (0.00, 0.00, 0.50, 0.50),
    "left":         (0.00, 0.00, 0.50, 1.00),
    "center":       (0.20, 0.15, 0.80, 0.85),   # 图面主体
}

# 用于 auto 定位的标签词
LABELS = ("图号", "图 号", "图名", "图 名", "图纸编号", "比例")
AUTO_FALLBACK = "titleblock"


def auto_box(page):
    """按「图号/图名」文字的真实坐标算出图框裁剪框（0~1 分数）。

    返回 (frac, how)；文本层里找不到标签时返回 (None, reason)。
    """
    r = page.rect
    ws = [w for w in page.get_text("words")
          if any(lb in w[4] for lb in LABELS)]
    if not ws:
        return None, "无图号/图名标签（可能是扫描件）"
    x0 = min(w[0] for w in ws)
    y0 = min(w[1] for w in ws)
    x1 = max(w[2] for w in ws)
    y1 = max(w[3] for w in ws)
    # 向左留出名称列，向上留一行，向右向下贴边
    fx0 = max(0.0, (x0 - r.width * 0.10) / r.width)
    fy0 = max(0.0, (y0 - (y1 - y0) * 1.2) / r.height)
    return (fx0, fy0, 1.0, 1.0), "auto"


def render_one(page, frac, dpi, fmt, out):
    r = page.rect
    clip = fitz.Rect(r.x0 + frac[0] * r.width, r.y0 + frac[1] * r.height,
                     r.x0 + frac[2] * r.width, r.y0 + frac[3] * r.height)
    if clip.is_empty:
        return None
    px_w = clip.width / 72.0 * dpi
    px_h = clip.height / 72.0 * dpi
    scale = 1.0
    if max(px_w, px_h) > MAX_PX:
        scale = MAX_PX / max(px_w, px_h)
        dpi = int(dpi * scale)
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0),
                          clip=clip, alpha=False)
    if out:
        if fmt == "jpg":
            pix.save(out, jpg_quality=88)
        else:
            pix.save(out)
    return pix, dpi


def make_sheet(doc, pages, frac, dpi, cols, out, tile_w=860, gap=6, label_h=34):
    """把多页的同一区域拼成一张大图（接触印相表）。

    token 是按「张」封顶的，拼 40 个图框进一张图 = 384 tokens，
    而不是 40 x 384 = 15360。这是本 skill 最关键的省 token 手段。
    """
    if not HAS_PIL:
        sys.exit("--sheet 需要 Pillow：pip install pillow")
    tiles = []
    for pno in pages:
        if not (1 <= pno <= len(doc)):
            continue
        res = render_one(doc[pno - 1], frac, dpi, "png", None)
        if not res:
            continue
        pix, _ = res
        img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        w, h = img.size
        nh = max(1, int(h * tile_w / w))
        tiles.append((pno, img.resize((tile_w, nh), Image.LANCZOS)))
    if not tiles:
        sys.exit("没有可拼的页")

    tile_h = max(t[1].height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    cell_h = tile_h + label_h
    W = cols * tile_w + (cols + 1) * gap
    H = rows * cell_h + (rows + 1) * gap
    canvas = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default(size=26)
    except TypeError:
        font = ImageFont.load_default()

    for i, (pno, img) in enumerate(tiles):
        r_, c_ = divmod(i, cols)
        x = gap + c_ * (tile_w + gap)
        y = gap + r_ * (cell_h + gap)
        draw.rectangle([x - 1, y - 1, x + tile_w, y + cell_h], outline="#b0b0b0")
        draw.text((x + 6, y + 4), f"p{pno}", fill="#111111", font=font)
        canvas.paste(img, (x, y + label_h))

    canvas.save(out)
    return {"path": out, "cols": cols, "rows": rows,
            "tiles": [t[0] for t in tiles], "px": [W, H],
            "kb": round(os.path.getsize(out) / 1024, 1),
            "est_tokens": IMG_TOKENS_MAX}


def file_fingerprint(path):
    st = os.stat(path)
    h = hashlib.sha1()
    h.update(os.path.abspath(path).encode("utf-8", "ignore"))
    h.update(str(st.st_size).encode())
    h.update(str(int(st.st_mtime)).encode())
    return h.hexdigest()[:16]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--pages", help="页码，1 起，可逗号/区间，如 3,5,8-11")
    ap.add_argument("--page", type=int, help="单页")
    ap.add_argument("--box", default="full", help="区域预设，见 --boxes")
    ap.add_argument("--crop", help="百分比裁剪 左,上,右,下，如 0.0,0.0,0.5,0.5")
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--format", default="png", choices=["png", "jpg"])
    ap.add_argument("--outdir", help="输出目录（默认 <pdf目录>/.pdfdraw/<指纹>/）")
    ap.add_argument("--sheet", action="store_true",
                    help="拼图模式：把多页的同一区域拼成一张大图（省 token 的关键）")
    ap.add_argument("--cols", type=int, default=4, help="拼图列数（默认 4）")
    ap.add_argument("--sheet-width", type=int, default=860, help="拼图每格宽度 px")
    ap.add_argument("--boxes", action="store_true", help="列出区域预设后退出")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.boxes:
        for k, v in BOXES.items():
            print(f"  {k:<12} {v}")
        return

    if not args.pdf:
        ap.error("需要指定 pdf（或用 --boxes）")
    if not os.path.isfile(args.pdf):
        sys.exit(f"文件不存在: {args.pdf}")

    # 页码解析
    pages = []
    if args.page:
        pages = [args.page]
    elif args.pages:
        for part in args.pages.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                pages += list(range(int(a), int(b) + 1))
            else:
                pages.append(int(part))
    else:
        ap.error("需要 --page 或 --pages")

    # 区域解析
    auto_note = None
    if args.crop:
        try:
            frac = tuple(float(x) for x in args.crop.split(","))
            assert len(frac) == 4
        except Exception:
            sys.exit("--crop 需要 4 个 0~1 的数：左,上,右,下")
    elif args.box == "auto":
        frac = None                      # 逐页解析；拼图模式下回退 AUTO_FALLBACK
    else:
        if args.box not in BOXES:
            sys.exit(f"未知区域 {args.box}；可用：auto, {', '.join(BOXES)}")
        frac = BOXES[args.box]

    if args.sheet:
        if frac is None:
            frac = BOXES[AUTO_FALLBACK]
        doc = fitz.open(args.pdf)
        out = args.outdir or (os.path.join(
            os.path.dirname(os.path.abspath(args.pdf)),
            ".pdfdraw", file_fingerprint(args.pdf)))
        os.makedirs(out, exist_ok=True)
        fmt = args.format
        dst = os.path.join(out, f"sheet_{len(pages)}p_{args.box}_{args.dpi}.{fmt}")
        info = make_sheet(doc, pages, frac, args.dpi, args.cols, dst,
                          tile_w=args.sheet_width)
        doc.close()
        if fmt == "jpg":
            Image.open(dst).convert("RGB").save(dst, quality=88)
        if args.json:
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            print(f"拼图   {info['cols']}列 x {info['rows']}行  共 {len(info['tiles'])} 张图框")
            print(f"尺寸   {info['px'][0]}x{info['px'][1]}px  {info['kb']} KB")
            print(f"路径   {info['path']}")
            print(f"页序   行优先，左上起；格内已标 p<页码>")
            print(f"预估输入 {info['est_tokens']} tokens"
                  f"（若逐张渲染需 {len(info['tiles']) * IMG_TOKENS_MAX}）")
            print("下一步：用 Read 工具读上面这张图")
        return

    doc = fitz.open(args.pdf)
    n = len(doc)

    fp = file_fingerprint(args.pdf)
    outdir = args.outdir or os.path.join(os.path.dirname(os.path.abspath(args.pdf)),
                                         ".pdfdraw", fp)
    os.makedirs(outdir, exist_ok=True)

    results = []
    for pno in pages:
        if not (1 <= pno <= n):
            print(f"  p{pno} 超出范围（共 {n} 页），跳过")
            continue
        page = doc[pno - 1]
        r = page.rect

        use_frac, how = frac, args.box
        if frac is None:                       # --box auto
            ab, reason = auto_box(page)
            if ab is None:
                use_frac, how = BOXES[AUTO_FALLBACK], f"{AUTO_FALLBACK}(auto失败:{reason})"
                auto_note = reason
            else:
                use_frac, how = ab, "auto"
        frac_t = use_frac
        clip = fitz.Rect(r.x0 + frac_t[0] * r.width, r.y0 + frac_t[1] * r.height,
                         r.x0 + frac_t[2] * r.width, r.y0 + frac_t[3] * r.height)
        if clip.is_empty:
            print(f"  p{pno} 区域为空，跳过")
            continue

        # DPI 护栏：单边不超过 MAX_PX
        dpi = args.dpi
        px_w = clip.width / 72.0 * dpi
        px_h = clip.height / 72.0 * dpi
        scale = 1.0
        if max(px_w, px_h) > MAX_PX:
            scale = MAX_PX / max(px_w, px_h)
            dpi = int(dpi * scale)
            px_w, px_h = px_w * scale, px_h * scale

        key = (f"p{pno}_dpi{dpi}_"
               f"{frac_t[0]:.3f}{frac_t[1]:.3f}{frac_t[2]:.3f}{frac_t[3]:.3f}.{args.format}")
        out = os.path.join(outdir, key)
        cached = os.path.exists(out)
        if not cached:
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72.0, dpi / 72.0),
                                  clip=clip, alpha=False)
            if args.format == "jpg":
                pix.save(out, jpg_quality=88)
            else:
                pix.save(out)
        size = os.path.getsize(out)
        results.append({
            "page": pno, "path": out, "box": how,
            "crop": [round(v, 3) for v in frac_t], "dpi": dpi,
            "px": [round(px_w), round(px_h)],
            "kb": round(size / 1024, 1),
            "est_tokens": IMG_TOKENS_MAX,
            "cached": cached,
            "downscaled": bool(scale < 1.0),
        })

    doc.close()

    if args.json:
        print(json.dumps({"outdir": outdir, "images": results},
                         ensure_ascii=False, indent=2))
        return

    print(f"输出目录 {outdir}")
    if args.box == "auto":
        ok = sum(1 for x in results if x["box"] == "auto")
        print(f"auto 定位成功 {ok}/{len(results)}"
              + (f"；其余回退 {AUTO_FALLBACK}（{auto_note}）" if auto_note else ""))
    tot = 0
    for x in results:
        flag = " [缓存]" if x["cached"] else ""
        warn = " [已降DPI]" if x["downscaled"] else ""
        tot += x["est_tokens"]
        print(f"  p{x['page']:<4} {x['px'][0]}x{x['px'][1]}px  {x['kb']:>7.1f}KB  "
              f"crop={x['crop']}  {x['path']}{flag}{warn}")
    print(f"共 {len(results)} 张，预估输入 {tot} tokens（每张封顶 {IMG_TOKENS_MAX}）")
    print("下一步：用 Read 工具直接读上面这些图片路径")


if __name__ == "__main__":
    main()
