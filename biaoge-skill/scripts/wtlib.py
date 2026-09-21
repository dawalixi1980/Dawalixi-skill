"""word-table-skill 公共库：分栏识别、文字宽度测算、列宽分配、样式应用。"""

from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TWIP_PER_PT = 20
DEFAULT_FONT_PT = 10.5  # 五号

# ---------------- 灰度色板 ----------------
C = {
    'black': '000000', 'dgray': '595959', 'mgray': '808080',
    'lgray': 'BFBFBF', 'pale': 'D9D9D9',
    'hdr': 'F2F2F2', 'hdr_dark': '404040', 'zebra': 'F7F7F7', 'label': 'EDEDED',
}

# 表体一律沿用「不修改正文字号」的做法，字号由 CLI 传入
PRESETS = {
    'three-line': {
        'name': '三线表',
        'borders': {'top': (18, 'black'), 'bottom': (18, 'black'),
                    'left': None, 'right': None, 'insideH': None, 'insideV': None},
        'header_fill': None, 'header_color': 'black', 'header_bottom': (8, 'black'),
        'zebra': None, 'label_col': False,
        'desc': '仅顶线/表头下线/底线，无竖线，最简洁，适合正式文件',
    },
    'grid': {
        'name': '标准网格',
        'borders': {'top': (12, 'black'), 'bottom': (12, 'black'), 'left': (4, 'mgray'),
                    'right': (4, 'mgray'), 'insideH': (4, 'mgray'), 'insideV': (4, 'mgray')},
        'header_fill': 'hdr', 'header_color': 'black', 'header_bottom': None,
        'zebra': None, 'label_col': False,
        'desc': '全网格线，表头浅灰，通用性最强',
    },
    'zebra': {
        'name': '斑马隔行',
        'borders': {'top': (12, 'black'), 'bottom': (12, 'black'), 'left': None,
                    'right': None, 'insideH': (4, 'lgray'), 'insideV': None},
        'header_fill': 'hdr', 'header_color': 'black', 'header_bottom': None,
        'zebra': 'zebra', 'label_col': False,
        'desc': '表头浅灰 + 隔行浅灰底，无竖线，长表易读',
    },
    'dark-header': {
        'name': '深色表头',
        'borders': {'top': (12, 'black'), 'bottom': (12, 'black'), 'left': (4, 'mgray'),
                    'right': (4, 'mgray'), 'insideH': (4, 'mgray'), 'insideV': (4, 'mgray')},
        'header_fill': 'hdr_dark', 'header_color': 'FFFFFF', 'header_bottom': None,
        'zebra': None, 'label_col': False,
        'desc': '表头深灰反白，全网格，层次最强',
    },
    'label-col': {
        'name': '标签列强调',
        'borders': {'top': (12, 'black'), 'bottom': (12, 'black'), 'left': None,
                    'right': None, 'insideH': (4, 'lgray'), 'insideV': (4, 'lgray')},
        'header_fill': 'hdr', 'header_color': 'black', 'header_bottom': None,
        'zebra': None, 'label_col': True,
        'desc': '表头浅灰 + 首列浅灰底，适合「标签—内容」型表格',
    },
    'grid-plain': {
        'name': '全网格无底色',
        'borders': {'top': (8, 'black'), 'bottom': (8, 'black'), 'left': (8, 'black'),
                    'right': (8, 'black'), 'insideH': (4, 'black'), 'insideV': (4, 'black')},
        'header_fill': None, 'header_color': 'black', 'header_bottom': None,
        'zebra': None, 'label_col': False,
        'desc': '全网格线，外框 1pt / 内线 0.5pt，无任何底纹，仅表头加粗，最朴素干净',
    },
    'head-rule': {
        'name': '表头下线',
        'borders': {'top': None, 'bottom': None, 'left': None,
                    'right': None, 'insideH': None, 'insideV': None},
        'header_fill': None, 'header_color': 'black', 'header_bottom': (12, 'black'),
        'header_top': (12, 'black'),
        'zebra': None, 'label_col': False,
        'desc': '仅表头上下两条线，无其他框线，最轻量',
    },
}

ORDER = ['w:tblStyle', 'w:tblpPr', 'w:tblOverlap', 'w:bidiVisual',
         'w:tblStyleRowBandSize', 'w:tblStyleColBandSize', 'w:tblW', 'w:jc',
         'w:tblCellSpacing', 'w:tblInd', 'w:tblBorders', 'w:shd', 'w:tblLayout',
         'w:tblCellMar', 'w:tblLook', 'w:tblCaption', 'w:tblDescription']


# ---------------- 文字宽度测算 ----------------
def char_em(ch):
    o = ord(ch)
    if o < 0x20:
        return 0.0
    if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
        return 1.0
    if 0x3000 <= o <= 0x303F or 0xFF00 <= o <= 0xFFEF:
        return 1.0
    if 0x2010 <= o <= 0x201F:
        return 0.5
    if o == 0x20:
        return 0.28
    if 0x30 <= o <= 0x39:
        return 0.55
    if 0x41 <= o <= 0x5A:
        return 0.65
    if 0x61 <= o <= 0x7A:
        return 0.52
    return 0.5


def text_em(s):
    return sum(char_em(c) for c in s)


def text_twips(s, font_pt):
    return text_em(s) * font_pt * TWIP_PER_PT


# ---------------- 分栏与版心 ----------------
def section_avail(sectPr):
    """返回该节的可用宽度（twips）：多栏时返回单栏宽。"""
    pg = sectPr.find(qn('w:pgSz'))
    mar = sectPr.find(qn('w:pgMar'))
    w = int(pg.get(qn('w:w')))
    if pg.get(qn('w:orient')) == 'landscape' and pg.get(qn('w:w'), '').isdigit():
        pass
    left = int(mar.get(qn('w:left')))
    right = int(mar.get(qn('w:right')))
    content = w - left - right
    cols = sectPr.find(qn('w:cols'))
    num = 1
    space = 0
    ex = []
    if cols is not None:
        num = int(cols.get(qn('w:num')) or 1) or 1
        space = int(cols.get(qn('w:space')) or 0)
        ex = cols.findall(qn('w:col'))
    if num <= 1:
        return content, 1, content
    if ex and ex[0].get(qn('w:w')):
        cw = int(ex[0].get(qn('w:w')))
    else:
        cw = int((content - space * (num - 1)) / num)
    return cw, num, content


def body_sections(doc):
    """返回 [(start_idx, end_idx, sectPr), ...]，按 body 子元素顺序。"""
    body = doc.element.body
    children = list(body)
    out = []
    start = 0
    for i, el in enumerate(children):
        if el.tag == qn('w:p'):
            pPr = el.find(qn('w:pPr'))
            if pPr is not None:
                sp = pPr.find(qn('w:sectPr'))
                if sp is not None:
                    out.append((start, i, sp))
                    start = i + 1
    final = body.find(qn('w:sectPr'))
    if final is not None:
        out.append((start, len(children) - 1, final))
    return out


def table_section_map(doc):
    """返回 {表格序号(0基): (avail, num_cols, content)}。"""
    body = doc.element.body
    children = list(body)
    secs = body_sections(doc)
    idx = 0
    mapping = {}
    for i, el in enumerate(children):
        if el.tag != qn('w:tbl'):
            continue
        owner = None
        for s, e, sp in secs:
            if s <= i <= e:
                owner = sp
                break
        if owner is None and secs:
            owner = secs[-1][2]
        mapping[idx] = section_avail(owner) if owner is not None else (0, 1, 0)
        idx += 1
    return mapping


# ---------------- XML 工具 ----------------
def normalize_tblPr(tblPr):
    kids = {}
    for ch in list(tblPr):
        kids.setdefault(ch.tag, []).append(ch)
    for ch in list(tblPr):
        tblPr.remove(ch)
    for tag in ORDER:
        for ch in kids.get(qn(tag), []):
            tblPr.append(ch)
    known = {qn(t) for t in ORDER}
    for tag, items in kids.items():
        if tag not in known:
            for ch in items:
                tblPr.append(ch)


def format_cell_paragraphs(tbl):
    """清零表格内段落的缩进与段间距。

    中文 Word 模板常用「字符级」缩进（w:firstLineChars="200" 表示首行缩进 2 字符）。
    仅把 w:firstLine 设为 0 无效——Word 里 firstLineChars 优先级更高，
    会吃掉约 2 个字的可用宽度，使本可单行的文字折行。故必须一并清零。
    """
    from docx.text.paragraph import Paragraph
    CHAR_ATTRS = ('w:leftChars', 'w:rightChars', 'w:firstLineChars', 'w:hangingChars')
    for p_el in tbl._tbl.iter(qn('w:p')):
        try:
            pf = Paragraph(p_el, None).paragraph_format
            pf.left_indent = 0
            pf.right_indent = 0
            pf.first_line_indent = 0
            pf.space_before = 0
            pf.space_after = 0
            pf.line_spacing = 1.0
            pPr = p_el.find(qn('w:pPr'))
            ind = pPr.find(qn('w:ind')) if pPr is not None else None
            if ind is not None:
                for k in CHAR_ATTRS:
                    ind.set(qn(k), '0')
        except Exception:
            pass


def set_cell_margins(tbl, lr=85, tb=40):
    tblPr = tbl._tbl.tblPr
    for e in tblPr.findall(qn('w:tblCellMar')):
        tblPr.remove(e)
    mar = OxmlElement('w:tblCellMar')
    for side, val in (('top', tb), ('left', lr), ('bottom', tb), ('right', lr)):
        n = OxmlElement('w:' + side)
        n.set(qn('w:w'), str(val))
        n.set(qn('w:type'), 'dxa')
        mar.append(n)
    tblPr.append(mar)
    normalize_tblPr(tblPr)


def set_table_width(tbl, tw):
    tblPr = tbl._tbl.tblPr
    for tag in ('w:tblW', 'w:tblLayout', 'w:jc'):
        for e in tblPr.findall(qn(tag)):
            tblPr.remove(e)
    w = OxmlElement('w:tblW')
    w.set(qn('w:w'), str(int(tw)))
    w.set(qn('w:type'), 'dxa')
    tblPr.append(w)
    jc = OxmlElement('w:jc')
    jc.set(qn('w:val'), 'left')
    tblPr.append(jc)
    lay = OxmlElement('w:tblLayout')
    lay.set(qn('w:type'), 'fixed')
    tblPr.append(lay)
    normalize_tblPr(tblPr)


def set_grid(tbl, widths):
    grid = tbl._tbl.find(qn('w:tblGrid'))
    if grid is None:
        return
    gcs = grid.findall(qn('w:gridCol'))
    for gc, w in zip(gcs, widths):
        gc.set(qn('w:w'), str(int(w)))


def set_cell_width(tc, tw):
    tcPr = tc.find(qn('w:tcPr'))
    if tcPr is None:
        tcPr = OxmlElement('w:tcPr')
        tc.insert(0, tcPr)
    for e in tcPr.findall(qn('w:tcW')):
        tcPr.remove(e)
    cw = OxmlElement('w:tcW')
    cw.set(qn('w:w'), str(int(tw)))
    cw.set(qn('w:type'), 'dxa')
    tcPr.append(cw)


def set_vAlign(tc, val='center'):
    tcPr = tc.find(qn('w:tcPr'))
    if tcPr is None:
        tcPr = OxmlElement('w:tcPr')
        tc.insert(0, tcPr)
    for e in tcPr.findall(qn('w:vAlign')):
        tcPr.remove(e)
    v = OxmlElement('w:vAlign')
    v.set(qn('w:val'), val)
    tcPr.append(v)


def set_shd(tc, fill):
    tcPr = tc.find(qn('w:tcPr'))
    if tcPr is None:
        tcPr = OxmlElement('w:tcPr')
        tc.insert(0, tcPr)
    for e in tcPr.findall(qn('w:shd')):
        tcPr.remove(e)
    if fill:
        s = OxmlElement('w:shd')
        s.set(qn('w:val'), 'clear')
        s.set(qn('w:color'), 'auto')
        s.set(qn('w:fill'), fill)
        tcPr.append(s)


def set_cell_border(tc, edge, sz, color):
    tcPr = tc.find(qn('w:tcPr'))
    if tcPr is None:
        tcPr = OxmlElement('w:tcPr')
        tc.insert(0, tcPr)
    tb = tcPr.find(qn('w:tcBorders'))
    if tb is None:
        tb = OxmlElement('w:tcBorders')
        tcPr.append(tb)
    for e in tb.findall(qn('w:' + edge)):
        tb.remove(e)
    e = OxmlElement('w:' + edge)
    e.set(qn('w:val'), 'single')
    e.set(qn('w:sz'), str(sz))
    e.set(qn('w:space'), '0')
    e.set(qn('w:color'), color)
    tb.append(e)


def set_borders(tbl, spec):
    tblPr = tbl._tbl.tblPr
    for e in tblPr.findall(qn('w:tblBorders')):
        tblPr.remove(e)
    b = OxmlElement('w:tblBorders')
    for edge in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        e = OxmlElement('w:' + edge)
        v = spec.get(edge)
        if v:
            e.set(qn('w:val'), 'single')
            e.set(qn('w:sz'), str(v[0]))
            e.set(qn('w:space'), '0')
            e.set(qn('w:color'), C.get(v[1], v[1]))
        else:
            e.set(qn('w:val'), 'none')
            e.set(qn('w:sz'), '0')
            e.set(qn('w:space'), '0')
            e.set(qn('w:color'), 'auto')
        b.append(e)
    tblPr.append(b)
    normalize_tblPr(tblPr)


def set_run_font(tbl, font_pt, color=None, bold=None, rows=None):
    for ri, tr in enumerate(tbl._tbl.findall(qn('w:tr'))):
        if rows is not None and ri not in rows:
            continue
        for r in tr.iter(qn('w:r')):
            rPr = r.find(qn('w:rPr'))
            if rPr is None:
                rPr = OxmlElement('w:rPr')
                r.insert(0, rPr)
            for tag in ('w:sz', 'w:szCs'):
                for e in rPr.findall(qn(tag)):
                    rPr.remove(e)
                e = OxmlElement(tag)
                e.set(qn('w:val'), str(int(round(font_pt * 2))))
                rPr.append(e)
            if color:
                for e in rPr.findall(qn('w:color')):
                    rPr.remove(e)
                e = OxmlElement('w:color')
                e.set(qn('w:val'), color)
                rPr.append(e)
            if bold is not None:
                for tag in ('w:b', 'w:bCs'):
                    for e in rPr.findall(qn(tag)):
                        rPr.remove(e)
                if bold:
                    rPr.append(OxmlElement('w:b'))
                    rPr.append(OxmlElement('w:bCs'))


# ---------------- 列宽分配（注水法） ----------------
def allocate(desired, avail, min_w=0):
    n = len(desired)
    if n == 0:
        return []
    total = sum(desired)
    if total <= 0:
        out = [int(avail / n)] * n
        out[-1] = avail - sum(out[:-1])
        return out
    if total <= avail:
        out = [int(d * avail / total) for d in desired]
        out[-1] = avail - sum(out[:-1])
        return out
    lo, hi = 0.0, float(max(desired))
    for _ in range(80):
        mid = (lo + hi) / 2
        if sum(min(d, mid) for d in desired) < avail:
            lo = mid
        else:
            hi = mid
    cap = (lo + hi) / 2
    out = [int(min(d, cap)) for d in desired]
    for i in range(n):
        if out[i] < min_w:
            out[i] = int(min_w)
    guard = 0
    while sum(out) != avail and guard < 100000:
        diff = avail - sum(out)
        if diff > 0:
            idx = max(range(n), key=lambda i: desired[i] - out[i])
            if desired[idx] - out[idx] <= 0:
                idx = out.index(min(out))
            out[idx] += 1
        else:
            idx = max(range(n), key=lambda i: out[i])
            if out[idx] <= min_w:
                break
            out[idx] -= 1
        guard += 1
    return out


def measure_table(tbl, font_pt, lr_margin=85, header_bold=True):
    """返回每列单行所需宽度 twips（含单元格左右边距）。"""
    ncol = len(tbl.columns)
    desired = [0] * ncol
    for ri, row in enumerate(tbl.rows):
        cells = row.cells
        for ci in range(ncol):
            if ci >= len(cells):
                continue
            txt = cells[ci].text.replace('\n', ' ')
            w = text_twips(txt, font_pt)
            if ri == 0 and header_bold:
                w *= 1.05
            if w > desired[ci]:
                desired[ci] = w
    return [int(d) + 2 * lr_margin for d in desired]


def apply_style(tbl, style_key, font_pt, header_rows=1):
    st = PRESETS[style_key]
    set_borders(tbl, st['borders'])
    trs = tbl._tbl.findall(qn('w:tr'))
    for ri, tr in enumerate(trs):
        is_head = ri < header_rows
        for tc in tr.findall(qn('w:tc')):
            set_vAlign(tc, 'center')
            if is_head:
                set_shd(tc, C.get(st['header_fill']) if st['header_fill'] else None)
                if st.get('header_bottom'):
                    set_cell_border(tc, 'bottom', st['header_bottom'][0], C[st['header_bottom'][1]])
                if st.get('header_top'):
                    set_cell_border(tc, 'top', st['header_top'][0], C[st['header_top'][1]])
            else:
                set_shd(tc, C.get(st['zebra']) if (st['zebra'] and ri % 2 == 0) else None)
            if st['label_col'] and not is_head:
                pass
        if st['label_col'] and not is_head:
            tcs = tr.findall(qn('w:tc'))
            if tcs:
                set_shd(tcs[0], C['label'])
    set_run_font(tbl, font_pt)
    set_run_font(tbl, font_pt, color=C.get(st['header_color']),
                 bold=True, rows=set(range(header_rows)))
