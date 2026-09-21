"""Word 表格优化：分栏自适应 + 按内容动态算列宽 + 统一表格样式。

用法:
    python fit_tables.py --list-styles
    python fit_tables.py 输入.docx -o 输出.docx --style three-line
    python fit_tables.py 输入.docx -o 输出.docx --style zebra --font-size 10.5 --caption
    python fit_tables.py 输入.docx -o 输出.docx --style grid --clean-header --dry-run
"""
import argparse
import io
import os
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from docx import Document
from docx.oxml.ns import qn

import wtlib as L

EMPTY_HDR = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
             '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p/></w:hdr>')
EMPTY_FTR = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\r\n'
             '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p/></w:ftr>')


def list_styles():
    print('可用表格样式（黑白灰）：')
    print()
    for k, v in L.PRESETS.items():
        print('  %-14s %-10s %s' % (k, v['name'], v['desc']))


def clean_header_footer(path, work):
    """移除页眉/页脚引用并清空部件，返回是否改动。"""
    zin = zipfile.ZipFile(path)
    doc = zin.read('word/document.xml').decode('utf-8')
    if not re.search(r'<w:(header|footer)Reference', doc):
        zin.close()
        return False
    doc2 = re.sub(r'<w:(header|footer)Reference[^>]*/>', '', doc)
    zout = zipfile.ZipFile(work, 'w', zipfile.ZIP_DEFLATED)
    for n in zin.namelist():
        data = zin.read(n)
        if n == 'word/document.xml':
            data = doc2.encode('utf-8')
        elif n.startswith('word/header'):
            data = EMPTY_HDR.encode('utf-8')
        elif n.startswith('word/footer'):
            data = EMPTY_FTR.encode('utf-8')
        zout.writestr(n, data)
    zout.close()
    zin.close()
    return True


def strip_horizontal_rules(doc):
    """移除 pandoc 由 Markdown `---` 生成的 VML 水平线段落。

    pandoc 会把主题分隔线渲染成
      <w:p><w:r><w:pict><v:rect ... o:hr="t"/></w:pict></w:r></w:p>
    它既不是段落边框也不是表格边框，靠常规清理手段找不到。
    """
    VML = '{urn:schemas-microsoft-com:vml}rect'
    OFF = '{urn:schemas-microsoft-com:office:office}hr'
    body = doc.element.body
    removed = 0
    for el in list(body):
        if el.tag != qn('w:p'):
            continue
        for rect in el.iter(VML):
            if rect.get(OFF) == 't':
                body.remove(el)
                removed += 1
                break
    return removed


def add_captions(doc):
    body = doc.element.body
    last_heading = ''
    idx = 0
    for el in list(body):
        if el.tag == qn('w:p'):
            txt = ''.join(t.text or '' for t in el.iter(qn('w:t'))).strip()
            pPr = el.find(qn('w:pPr'))
            style = ''
            if pPr is not None:
                ps = pPr.find(qn('w:pStyle'))
                if ps is not None:
                    style = ps.get(qn('w:val')) or ''
            if txt and (style.startswith('Heading') or style in ('1', '2', '3', '4')):
                last_heading = txt
        elif el.tag == qn('w:tbl'):
            idx += 1
            if el.getprevious() is not None:
                prev = el.getprevious()
                if prev.tag == qn('w:p'):
                    ptxt = ''.join(t.text or '' for t in prev.iter(qn('w:t'))).strip()
                    if ptxt.startswith('表 '):
                        continue
            from docx.oxml import OxmlElement
            cap = OxmlElement('w:p')
            pPr = OxmlElement('w:pPr')
            jc = OxmlElement('w:jc')
            jc.set(qn('w:val'), 'center')
            pPr.append(jc)
            cap.append(pPr)
            r = OxmlElement('w:r')
            rPr = OxmlElement('w:rPr')
            for t in ('w:sz', 'w:szCs'):
                e = OxmlElement(t)
                e.set(qn('w:val'), '21')
                rPr.append(e)
            r.append(rPr)
            t = OxmlElement('w:t')
            t.text = '表 %d  %s' % (idx, last_heading or '说明')
            r.append(t)
            cap.append(r)
            el.addprevious(cap)


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('input', nargs='?')
    ap.add_argument('-o', '--output')
    ap.add_argument('--style', default=None)
    ap.add_argument('--font-size', type=float, default=L.DEFAULT_FONT_PT)
    ap.add_argument('--header-rows', type=int, default=1)
    ap.add_argument('--min-chars', type=float, default=4.0,
                    help='每列最小宽度（中文字数），默认 4')
    ap.add_argument('--no-fill', action='store_true',
                    help='不撑满栏宽，仅按内容最小宽（仍不超栏宽）')
    ap.add_argument('--caption', action='store_true', help='为表格添加「表 N 标题」题注')
    ap.add_argument('--clean-header', action='store_true', help='清空页眉页脚（去除模板图签残留）')
    ap.add_argument('--strip-hr', action='store_true', help='删除 pandoc 由 --- 生成的 VML 水平线')
    ap.add_argument('--dry-run', action='store_true', help='只测算不写文件')
    ap.add_argument('--list-styles', action='store_true')
    a = ap.parse_args()

    if a.list_styles:
        list_styles()
        return
    if not a.input or not a.output:
        ap.error('需要 input 与 -o output')
    if a.style not in L.PRESETS:
        print('未指定或未知样式。可用样式：')
        list_styles()
        sys.exit(1)

    work = a.input
    cleaned = False
    if a.clean_header:
        tmp = a.input + '.nohdr.docx'
        cleaned = clean_header_footer(a.input, tmp)
        if cleaned:
            work = tmp
            print('[页眉页脚] 已清空模板残留')

    doc = Document(work)
    tmap = L.table_section_map(doc)
    font_pt = a.font_size
    lr = 85
    min_w = int(a.min_chars * font_pt * L.TWIP_PER_PT) + 2 * lr

    print('[样式] %s (%s)' % (L.PRESETS[a.style]['name'], a.style))
    print('[字号] %.1fpt   最小列宽 %.1f 字' % (font_pt, a.min_chars))
    print()
    print('  %-4s %-4s %-9s %-9s %s' % ('表', '列数', '栏宽mm', '表宽mm', '列宽mm'))
    wraps = 0
    for i, tbl in enumerate(doc.tables):
        avail = tmap.get(i, (0, 1, 0))[0]
        if avail <= 0:
            continue
        desired = L.measure_table(tbl, font_pt, lr)
        target = avail
        if a.no_fill:
            target = min(sum(desired), avail)
        widths = L.allocate(desired, target, min_w)
        ncol = len(tbl.columns)
        for ri, row in enumerate(tbl.rows):
            tcs = row._tr.findall(qn('w:tc'))
            for ci in range(min(ncol, len(tcs))):
                L.set_cell_width(tcs[ci], widths[ci])
        L.set_grid(tbl, widths)
        L.set_table_width(tbl, sum(widths))
        L.format_cell_paragraphs(tbl)
        L.set_cell_margins(tbl, lr, 40)
        tbl.autofit = False
        L.apply_style(tbl, a.style, font_pt, a.header_rows)
        # 统计仍会折行的列
        for ci, d in enumerate(desired):
            if widths[ci] < d - 2:
                wraps += 1
        print('  %-4d %-4d %-9.1f %-9.1f %s'
              % (i + 1, ncol, avail / 56.6929, sum(widths) / 56.6929,
                 '/'.join('%.0f' % (w / 56.6929) for w in widths)))

    if a.strip_hr:
        n = strip_horizontal_rules(doc)
        print('\n[水平线] 已删除 %d 条 pandoc 生成的分隔线' % n)

    if a.caption:
        add_captions(doc)
        print('\n[题注] 已为 %d 张表添加「表 N 标题」' % len(doc.tables))

    print('\n仍会折行的列数: %d （列宽不足以单行容纳最宽单元格）' % wraps)
    if a.dry_run:
        print('[dry-run] 未写出文件')
        return
    doc.save(a.output)
    print('已保存:', a.output)
    if cleaned and os.path.exists(a.input + '.nohdr.docx'):
        os.remove(a.input + '.nohdr.docx')


if __name__ == '__main__':
    main()


