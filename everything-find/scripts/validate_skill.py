#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_skill.py —— everything-find 的契约校验器

校验 SKILL.md 的 frontmatter、必需章节、固定输出表格列、枚举值、引用文件是否存在,
以及脚本层的硬性约定(UTF-8 BOM、每个查询词独立成参数)。

用法:
    python scripts/validate_skill.py [skill_dir]
退出码:0 = 全部通过, 1 = 有问题(逐条列出)
"""
import os
import re
import sys

REQUIRED_SECTIONS = [
    "## Invariants",
    "## 状态机",
    "## 输入契约",
    "## 查询构造",
    "## 搜索命令",
    "## 判定与收窄",
    "## 删词阶梯",
    "## 评分与选 5",
    "## 出图判读",
    "## 输出契约",
    "## 错误码",
    "## 宿主能力与降级",
    "## 不做的事",
]

TABLE_COLUMNS = ["序号", "文件名", "完整路径", "大小 / 修改时间", "匹配度", "匹配理由"]

ERROR_CODES = ["NONE", "NO_MATCH", "AMBIGUOUS", "TOOL_UNAVAILABLE", "BAD_ARGS", "QUERY_TIMEOUT"]

RANKING_TIERS = ["精确", "高", "中", "低"]

REQUIRED_REFERENCES = [
    "references/everything-syntax.md",
    "references/ranking-rubric.md",
    "references/fallback-ladder.md",
    "references/host-capabilities.md",
    "references/dwg-shot.md",
    "scripts/ev-search.ps1",
    "scripts/dwg-shot.ps1",
    "scripts/pdf2png.py",
    "scripts/png-check.py",
    "scripts/compute-window.py",
    "scripts/dxf-text.py",
    "tests/test_ev_search.ps1",
    "tests/test_dwg_shot.ps1",
]

BOM_REQUIRED = [
    "scripts/ev-search.ps1",
    "scripts/dwg-shot.ps1",
    "tests/test_ev_search.ps1",
    "tests/test_dwg_shot.ps1",
    "install.ps1",
]

SHOT_PARAMS = ["$Path", "$Mode", "$Width", "$Text", "$OutDir", "$Paper", "$Window", "$AcadDir"]

SHOT_TOKENS = [
    ("accoreconsole", "必须调用无头 AutoCAD 引擎 accoreconsole"),
    ("'-PLOT'", "必须走 -PLOT 出图链"),
    ("-Encoding Default", "生成 .scr 必须按 ANSI(GBK)写,否则纸名/布局名里的中文会丢"),
    ("manifest.json", "必须产出 manifest.json 供 LLM 读真实路径"),
]

SCRIPT_PARAMS = ["$Query", "$Count", "$Ext", "$Path", "$Regex", "$Ladder", "$Transport", "$EsPath", "$HttpBase", "$OutDir"]

PLACEHOLDERS = ["TODO", "FIXME", "XXX", "待补", "TBD"]


def read_text(path, errors, label=None):
    if not os.path.isfile(path):
        errors.append("缺少文件:%s" % (label or path))
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def check_frontmatter(text, skill_name, errors):
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        errors.append("SKILL.md 缺少 YAML frontmatter(--- ... ---)")
        return
    fm = m.group(1)
    name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M | re.S)
    if not name:
        errors.append("frontmatter 缺少 name 字段")
    elif name.group(1) != skill_name:
        errors.append("frontmatter name(%s)与目录名(%s)不一致" % (name.group(1), skill_name))
    if not desc:
        errors.append("frontmatter 缺少 description 字段")
    elif len(desc.group(1)) < 40:
        errors.append("description 太短,无法承担路由职责(<40 字符)")


def check_bom(path, errors):
    if not os.path.isfile(path):
        return
    with open(path, "rb") as fh:
        head = fh.read(3)
    if head != b"\xef\xbb\xbf":
        errors.append("%s 没有 UTF-8 BOM —— Windows PowerShell 5.1 会按 ANSI 读取并语法崩" % path)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    skill_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(here)
    skill_name = os.path.basename(os.path.normpath(skill_dir))
    errors = []

    skill_md = os.path.join(skill_dir, "SKILL.md")
    text = read_text(skill_md, errors)
    if text is None:
        report(errors)
        return 1

    check_frontmatter(text, skill_name, errors)

    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            errors.append("SKILL.md 缺少必需章节:%s" % sec)

    # 固定输出表格的 6 列必须齐全且同现
    for col in TABLE_COLUMNS:
        if col not in text:
            errors.append("SKILL.md 输出表格缺少列:%s" % col)

    for code in ERROR_CODES:
        if code not in text:
            errors.append("SKILL.md 错误码表缺少:%s" % code)

    for tier in RANKING_TIERS:
        if tier not in text:
            errors.append("SKILL.md 评分档位缺少:%s" % tier)

    # SKILL.md 里出现的所有 references/ 与 scripts/ 引用必须真实存在
    for ref in sorted(set(re.findall(r"(?:references|scripts|tests)/[A-Za-z0-9_.\-\u4e00-\u9fff]+", text))):
        if not os.path.exists(os.path.join(skill_dir, ref.replace("/", os.sep))):
            errors.append("SKILL.md 引用了不存在的文件:%s" % ref)

    for ref in REQUIRED_REFERENCES:
        if not os.path.exists(os.path.join(skill_dir, ref.replace("/", os.sep))):
            errors.append("缺少必需文件:%s" % ref)

    # 脚本层硬约定
    script = os.path.join(skill_dir, "scripts", "ev-search.ps1")
    check_bom(script, errors)
    for rel in BOM_REQUIRED:
        check_bom(os.path.join(skill_dir, rel.replace("/", os.sep)), errors)
    script_text = read_text(script, errors)
    if script_text:
        for prm in SCRIPT_PARAMS:
            if prm not in script_text:
                errors.append("ev-search.ps1 缺少参数:%s" % prm)
        if "foreach ($t in @($Terms)) { $esArgs += $t }" not in script_text:
            errors.append("ev-search.ps1 必须把每个查询词作为独立参数传递(es.exe 多词单参数会 0 命中)")
        if "-export-csv" not in script_text or "-utf8-bom" not in script_text:
            errors.append("ev-search.ps1 必须用 -export-csv + -utf8-bom 落盘以避开控制台编码")
        if "'NO_MATCH'" not in script_text:
            errors.append("ev-search.ps1 未实现 NO_MATCH 错误码")

    # 出图能力(dwg-shot)的硬约定
    shot = os.path.join(skill_dir, "scripts", "dwg-shot.ps1")
    shot_text = read_text(shot, errors)
    if shot_text:
        for prm in SHOT_PARAMS:
            if prm not in shot_text:
                errors.append("dwg-shot.ps1 缺少参数:%s" % prm)
        for token, why in SHOT_TOKENS:
            if token not in shot_text:
                errors.append("dwg-shot.ps1 缺少关键实现 %s(%s)" % (token, why))
        if "Copy-Item" not in shot_text:
            errors.append("dwg-shot.ps1 必须先把 dwg 复制到 ASCII 路径(中文路径会让 accoreconsole 挂死)")

    # 删词阶梯:references 与脚本都要有 R1..R4
    ladder = read_text(os.path.join(skill_dir, "references", "fallback-ladder.md"), errors)
    if ladder:
        for rnd in ["R1", "R2", "R3", "R4"]:
            if rnd not in ladder:
                errors.append("fallback-ladder.md 缺少轮次:%s" % rnd)
    if script_text:
        for rnd in ["R1-", "R2-", "R3-", "R4-"]:
            if rnd not in script_text:
                errors.append("ev-search.ps1 未实现阶梯轮次:%s" % rnd)

    # 遗留占位符
    for path in [skill_md, script] + [os.path.join(skill_dir, r.replace("/", os.sep)) for r in REQUIRED_REFERENCES if r.endswith(".md")]:
        body = read_text(path, [])
        if not body:
            continue
        for ph in PLACEHOLDERS:
            if ph in body:
                errors.append("%s 残留占位符:%s" % (os.path.relpath(path, skill_dir), ph))

    report(errors)
    return 1 if errors else 0


def report(errors):
    if errors:
        print("FAIL 契约校验未通过,共 %d 个问题:" % len(errors))
        for e in errors:
            print("  - " + e)
    else:
        print("PASS 契约校验通过")


if __name__ == "__main__":
    sys.exit(main())
