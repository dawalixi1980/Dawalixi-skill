#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""index.py - 建立图纸索引，全程本地，零渲染、零 token。

实测要点（阳江/茂名一带的初设+施工图 PDF）：
  * 图框（标题栏）在页面最底部、横贯全宽；「图号」常单独落在一个右下小单元格里，
    坐标近似恒定（x≈0.86W, y≈0.91H）。
  * 图号形态：C04L001-7/11（册号-张号/总张数）、AD-01、DL-01-01、建施-05。
  * 页面下部其余文字是正文说明，不是图框 —— 所以不能对整条底带做正则，
    必须先按「单元格」再按「标签」，最后才退化成全带正则。
  * 「图名」常不在文本层里（是图框里的栅格图／外框图形），这类页需要渲染读图。

三级回退：
  1. toc             PDF 书签（get_toc）
  2. catalog_page    图纸目录／总目录页
  3. titleblock_text 逐页读图框文字（按坐标，不是 OCR）
  4. need_vision     整页无文本层（扫描件）→ 必须渲染后交给视觉模型

用法:
    python index.py <file.pdf> [-o index.json]
"""
import argparse
import json
import os
import re
import sys

import fitz

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# ---- 图框搜索区（均为页面宽高的比例）----
BAND_Y0 = 0.85        # 宽底带：用于找「图号/图名」标签
CELL_X0, CELL_Y0 = 0.78, 0.88   # 右下单元格：图号常驻位置
ROW_TOL = 6.0                   # 同一行的 y 容差（pt）

# 不要用裸的「名称」「编号」，否则误命中「工程名称」「设计号」
LABEL_NO = ("图号", "图 号", "图纸编号")
LABEL_TITLE = ("图名", "图 名", "图纸名称")

# 图号模式，从具体到宽泛，取第一个命中
SHEET_PATTERNS = [
    # C04L001-7/11   册号-张号/总张数（册号可含字母数字混排）
    (re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}[-－]\d{1,3}\s*/\s*\d{1,3}"), "volume_sheet"),
    # DL-01-01
    (re.compile(r"[A-Za-z]{1,4}[-－]\d{1,3}[-－]\d{1,3}"), "series_no"),
    # AD-01 / BJ-03a
    (re.compile(r"[A-Za-z]{1,4}[-－]\d{1,3}[A-Za-z]?"), "sheet_no"),
    # 建施-05
    (re.compile(r"[\u4e00-\u9fa5]{1,3}[-－]\d{1,3}[A-Za-z]?"), "cn_sheet_no"),
    # C04L001 仅册号（最后兜底）
    (re.compile(r"[A-Za-z][A-Za-z0-9]{0,7}\d"), "volume_only"),
]

# 图名后缀
RE_TITLE_TAIL = re.compile(
    r"([\u4e00-\u9fa5A-Za-z0-9（）()、\-]{2,24}?"
    r"(?:平面图|剖面图|立面图|断面图|详图|大样图|节点图|系统图|布置图|"
    r"设计说明|说明书|说明|一览表|示意图|纵断面|横断面|标准图|图册|图例|总图|表))"
)
CATALOG_HINTS = ("图纸目录", "图名", "图号", "目录", "总目录", "分册目录")

# CAD 导出书签常带的排版垃圾：Model (1) / Layout1 / 布局1 / (2) ...
RE_CAD_NOISE = re.compile(
    r"\s*(?:Model|Layout|布局|图纸空间|Paper\s*Space)\s*\d*\s*(?:\(\d+\))?\s*$",
    re.IGNORECASE,
)


def clean_title(t):
    if not t:
        return t
    s = t.strip()
    for _ in range(3):
        s2 = RE_CAD_NOISE.sub("", s).strip()
        if s2 == s:
            break
        s = s2
    return re.sub(r"\s*\(\d+\)\s*$", "", s).strip() or t.strip()


def band_words(page):
    r = page.rect
    return [w for w in page.get_text("words") if w[1] >= r.height * BAND_Y0]


def cell_words(page):
    r = page.rect
    return [w for w in page.get_text("words")
            if w[0] >= r.width * CELL_X0 and w[1] >= r.height * CELL_Y0]


def label_value(ws, labels):
    """在词列表里找标签（如「图号」），取其右侧或正下方最近的词作为值。"""
    for w in ws:
        if not any(lb in w[4] for lb in labels):
            continue
        yc = (w[1] + w[3]) / 2
        best, best_d = None, 1e9
        for v in ws:
            if v is w:
                continue
            vyc = (v[1] + v[3]) / 2
            same_row = abs(vyc - yc) <= ROW_TOL and v[0] > w[2] - 2
            below = v[1] >= w[3] - 2 and abs(v[0] - w[0]) < 40
            if not (same_row or below):
                continue
            d = (v[0] - w[2]) if same_row else (v[1] - w[3]) + 200
            if 0 <= d < best_d:
                best, best_d = v, d
        if best:
            return best[4]
    return None


def match_sheet(text):
    """按优先级匹配图号，返回 (no, kind)。"""
    if not text:
        return None, None
    for pat, kind in SHEET_PATTERNS:
        m = pat.search(text)
        if m:
            return m.group(0).replace(" ", ""), kind
    return None, None


def split_volume_sheet(no):
    """C04L001-7/11 -> (volume='C04L001', sheet=7, total=11)。"""
    m = re.match(r"^([A-Za-z]{1,4}\d{2,4})[-－](\d{1,3})\s*/\s*(\d{1,3})$", no or "")
    if not m:
        return None
    return {"volume": m.group(1), "sheet": int(m.group(2)), "total": int(m.group(3))}


def parse_titleblock(page):
    """返回 dict(no, kind, title, raw)。

    注意：底带里混着正文说明文字，所以「图名」只认显式标签，
    不做正则猜后缀 —— 否则会把「接地引入线分组接地示意图」这类正文当图名。
    """
    cw = cell_words(page)
    bw = band_words(page)

    no = label_value(bw, LABEL_NO)
    kind = "label" if no else None
    if not no:
        no, kind = match_sheet("".join(w[4] for w in cw))
    if not no:
        no, kind = match_sheet("".join(w[4] for w in bw))

    title = label_value(bw, LABEL_TITLE)

    raw = "".join(w[4] for w in cw)[:120] or "".join(w[4] for w in bw)[:120]
    return {"no": no, "kind": kind, "title": title, "raw": raw}


def norm_sheet(no):
    if not no:
        return None
    return no.strip().replace("－", "-").replace(" ", "").upper()


def norm_title(t):
    if not t:
        return None
    return re.sub(r"[\s　（）()、·\-_]", "", t)


def _find_catalog(doc, n):
    """找图纸目录页：要求「图纸目录/总目录」或同时出现「图名」「图号」。"""
    best, best_score = None, 0
    for i in range(n):
        t = doc[i].get_text()
        if len(t.strip()) < 20:
            continue
        score = 0
        if any(k in t for k in ("图纸目录", "总目录", "分册目录", "图册目录")):
            score += 3
        if "图名" in t:
            score += 2
        if "图号" in t:
            score += 2
        if score > best_score:
            best, best_score = i, score
    return best if best_score >= 4 else None


def _read_catalog(doc, page_idx, n):
    """读图纸目录页（含后 2 页）里的条目 -> [{no,title,src}]。"""
    entries = []
    for pi in range(page_idx, min(page_idx + 3, n)):
        for line in doc[pi].get_text().splitlines():
            line = line.strip()
            if len(line) < 4:
                continue
            no, _k = match_sheet(line)
            if not no:
                continue
            rest = line.replace(no, " ").strip()
            m = RE_TITLE_TAIL.search(rest)
            title = m.group(1) if m else re.sub(r"\s+", " ", rest)[:40]
            if title:
                entries.append({"no": no, "title": title, "src": "catalog_page"})
    return entries


def build(path):
    doc = fitz.open(path)
    n = len(doc)

    # ---------- A. 逐页读图框 ----------
    page_map, no_text = [], []
    for i in range(n):
        page = doc[i]
        if len(page.get_text().strip()) < 10:
            no_text.append(i + 1)
            continue
        info = parse_titleblock(page)
        if info["no"] or info["title"]:
            info["page"] = i + 1
            info.update(split_volume_sheet(info["no"]) or {})
            page_map.append(info)

    def finish(source, entries, extra=None):
        doc.close()
        out = {"file": os.path.basename(path), "pages": n,
               "source": source, "entries": entries,
               "pages_with_titleblock": len(page_map),
               "no_text_pages": no_text,
               "title_missing_pages": [p["page"] for p in page_map if not p["title"]]}
        if extra:
            out.update(extra)
        return out

    toc = doc.get_toc(simple=True)

    # ---------- B1. 书签 ----------
    if toc:
        entries = []
        for i, (l, t, p) in enumerate(toc):
            ok = isinstance(p, int) and 1 <= p <= n
            entries.append({"page": p if ok else None, "seq": i + 1,
                            "no": None, "title": clean_title(t),
                            "level": max(0, l - 1), "src": "toc"})
        valid = sum(1 for e in entries if e["page"])
        seen = [e["page"] for e in entries if e["page"]]
        dup = 1 - (len(set(seen)) / len(seen)) if seen else 1
        reliable = bool(valid >= len(entries) * 0.8 and dup < 0.25)
        # 书签没图号时，用逐页图框读数补上
        by_page = {p["page"]: p for p in page_map}
        for e in entries:
            info = by_page.get(e["page"])
            if info and not e["no"]:
                e["no"] = info["no"]
                e["kind"] = info["kind"]
                if info.get("sheet"):
                    e["sheet"], e["total"], e["volume"] = (
                        info["sheet"], info["total"], info["volume"])
        return finish("toc", entries, {
            "toc_pages_valid": valid,
            "toc_pages_reliable": reliable,
            "toc_warning": None if reliable else (
                "书签页码大量缺失或重复，不可直接定位；"
                "建议按 seq 顺序逐张渲染图框确认"),
        })

    # ---------- B2. 逐页图框读数（每页一张图，最贴合图纸集） ----------
    if len(page_map) >= max(3, n * 0.10):
        entries = [{"page": p["page"], "no": p["no"], "title": p["title"],
                    "kind": p.get("kind"), "sheet": p.get("sheet"),
                    "total": p.get("total"), "volume": p.get("volume"),
                    "src": "titleblock_text"} for p in page_map]
        # 有图纸目录页时，用目录里的图名补全缺失的图名
        cat = _find_catalog(doc, n)
        filled = 0
        if cat is not None:
            by_no = {norm_sheet(e["no"]): e["title"] for e in _read_catalog(doc, cat, n)
                     if e["no"] and e["title"]}
            for e in entries:
                if not e["title"] and e["no"]:
                    t = by_no.get(norm_sheet(e["no"]))
                    if t:
                        e["title"] = t
                        filled += 1
        return finish("titleblock_text", entries,
                      {"catalog_filled_titles": filled,
                       "catalog_page": (cat + 1) if cat is not None else None})

    # ---------- B3. 图纸目录页 ----------
    cat = _find_catalog(doc, n)
    if cat is not None:
        by_no = {norm_sheet(p["no"]): p["page"] for p in page_map if p["no"]}
        by_title = {norm_title(p["title"]): p["page"] for p in page_map if p["title"]}
        entries = []
        for e in _read_catalog(doc, cat, n):
            pg = by_no.get(norm_sheet(e["no"])) or by_title.get(norm_title(e["title"]))
            e["page"] = pg
            e["catalog_page"] = cat + 1
            entries.append(e)
        if entries:
            hit = sum(1 for e in entries if e["page"])
            return finish("catalog_page", entries,
                          {"catalog_page": cat + 1,
                           "catalog_resolved": hit, "catalog_total": len(entries)})

    # ---------- B4. 逐页图框读数（覆盖不足也给出） ----------
    if page_map:
        entries = [{"page": p["page"], "no": p["no"], "title": p["title"],
                    "kind": p.get("kind"), "sheet": p.get("sheet"),
                    "total": p.get("total"), "volume": p.get("volume"),
                    "src": "titleblock_text"} for p in page_map]
        return finish("titleblock_text", entries)

    # ---------- B5. 全无文本层 ----------
    return finish("need_vision", [], {"no_text_pages": no_text or list(range(1, n + 1))})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("-o", "--out", help="写出 JSON 到文件")
    args = ap.parse_args()

    idx = build(args.pdf)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=2)

    print(f"文件   {idx['file']}  ({idx['pages']} 页)")
    print(f"来源   {idx['source']}")
    if idx.get("catalog_page"):
        print(f"目录页 第 {idx['catalog_page']} 页；"
              f"图号已定位 {idx.get('catalog_resolved')}/{idx.get('catalog_total')}")
    if idx["source"] == "toc":
        print(f"书签页码 有效 {idx.get('toc_pages_valid')}/{len(idx['entries'])}"
              f"  可信: {'是' if idx.get('toc_pages_reliable') else '否'}")
        if idx.get("toc_warning"):
            print(f"警告   {idx['toc_warning']}")
    print(f"图框读数 {idx['pages_with_titleblock']} 页")
    print(f"条目   {len(idx['entries'])}")
    for e in idx["entries"][:80]:
        mark = " " * ((e.get("level") or 0) * 2)
        if e.get("page"):
            pg = f"p{e['page']}"
        elif e.get("catalog_page"):
            pg = f"目录p{e['catalog_page']}?"
        else:
            pg = f"序{e.get('seq')}(无页码)"
        sh = f" 张{e['sheet']}/{e['total']}" if e.get("sheet") else ""
        print(f"  {pg:>14}  {mark}{e.get('no') or '-':<16} {e.get('title') or ''}{sh}")
    if len(idx["entries"]) > 80:
        print(f"  ... 还有 {len(idx['entries']) - 80} 条，见 JSON")
    tm = idx.get("title_missing_pages") or []
    if tm:
        print(f"图名缺失 {len(tm)} 页（文本层无图名，需渲染图框读）: "
              f"{tm[:15]}{' ...' if len(tm) > 15 else ''}")
    if idx["no_text_pages"]:
        print(f"无文本层 {len(idx['no_text_pages'])} 页（要看内容必须渲染）: "
              f"{idx['no_text_pages'][:15]}{' ...' if len(idx['no_text_pages']) > 15 else ''}")
    print("\n本轮模型开销 0 tokens（全本地）")


if __name__ == "__main__":
    main()
