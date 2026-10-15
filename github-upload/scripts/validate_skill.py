#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_skill.py —— github-upload 的契约校验器

校验:frontmatter、必需章节、引用文件存在性、.ps1 的 UTF-8 BOM、
      gh-upload.ps1 的关键实现(凭据发现/四步 API/编码转义/密钥自查/回读校验)、
      错误码枚举、遗留占位符。

用法:python scripts/validate_skill.py [skill_dir]
退出码:0 = 通过, 1 = 有问题
"""
import os
import re
import sys

REQUIRED_SECTIONS = [
    "## Invariants",
    "## 状态机",
    "## 用法",
    "## 通道选择",
    "## 上传前必做",
    "## 错误码",
    "## 不做的事",
]

ERROR_CODES = ["BAD_ARGS", "NO_CREDENTIAL", "API_ERROR", "VERIFY_FAILED", "SECRET_SUSPECTED"]

REQUIRED_FILES = [
    "references/credential-transport.md",
    "references/git-data-api.md",
    "scripts/gh-upload.ps1",
    "tests/test_gh_upload.ps1",
    "tests/test_validate_skill.py",
    "README.md",
    "TARGET.md",
    "STATUS.md",
    "AGENTS.md",
]

SCRIPT_PARAMS = ["$Repo", "$Source", "$Prefix", "$Message", "$Branch", "$Exclude", "$Force", "$DryRun", "$AllowSecrets"]

SCRIPT_TOKENS = [
    ("git credential fill", "必须能发现 git 凭据管理器里的凭据"),
    ("gh auth token", "必须支持 gh CLI 凭据回退"),
    ("/git/blobs", "必须走 Git Data API 建 blob"),
    ("/git/trees", "必须走 Git Data API 建 tree"),
    ("/git/commits", "必须走 Git Data API 建 commit"),
    ("/git/refs/heads/", "必须走 Git Data API 移动分支"),
    ("Esc-Ascii", "必须把非 ASCII 转义成 \\uXXXX,否则中文提交信息变 ?"),
    ("SECRET_SUSPECTED", "必须有上传前密钥自查"),
    ("VERIFY_FAILED", "必须有提交后回读校验"),
    ("Authorization", "必须以请求头方式携带凭据"),
]

FORBIDDEN = [
    ("Write-Output $token", "禁止把 token 打到输出"),
    ("echo $token", "禁止把 token 打到输出"),
    ("ConvertTo-SecureString", "本 skill 不需要把凭据落盘/加密存储"),
]

PLACEHOLDERS = ["TODO", "FIXME", "待补", "TBD"]


def read_text(path, errors):
    if not os.path.isfile(path):
        errors.append("缺少文件:%s" % path)
        return None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def check_bom(path, errors):
    if not os.path.isfile(path):
        return
    with open(path, "rb") as fh:
        head = fh.read(3)
    if head != b"\xef\xbb\xbf":
        errors.append("%s 没有 UTF-8 BOM —— PowerShell 5.1 会按 ANSI 读取并语法崩" % path)


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

    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        errors.append("SKILL.md 缺少 YAML frontmatter")
    else:
        fm = m.group(1)
        name = re.search(r"^name:\s*(\S+)\s*$", fm, re.M)
        desc = re.search(r"^description:\s*(.+)$", fm, re.M | re.S)
        if not name:
            errors.append("frontmatter 缺少 name")
        elif name.group(1) != skill_name:
            errors.append("frontmatter name(%s) 与目录名(%s) 不一致" % (name.group(1), skill_name))
        if not desc:
            errors.append("frontmatter 缺少 description")
        elif len(desc.group(1)) < 40:
            errors.append("description 太短,无法承担路由职责")

    for sec in REQUIRED_SECTIONS:
        if sec not in text:
            errors.append("SKILL.md 缺少必需章节:%s" % sec)

    for code in ERROR_CODES:
        if code not in text:
            errors.append("SKILL.md 错误码表缺少:%s" % code)

    for ref in sorted(set(re.findall(r"(?:references|scripts|tests)/[A-Za-z0-9_.\-\u4e00-\u9fff]+", text))):
        if not os.path.exists(os.path.join(skill_dir, ref.replace("/", os.sep))):
            errors.append("SKILL.md 引用了不存在的文件:%s" % ref)

    for ref in REQUIRED_FILES:
        if not os.path.exists(os.path.join(skill_dir, ref.replace("/", os.sep))):
            errors.append("缺少必需文件:%s" % ref)

    script = os.path.join(skill_dir, "scripts", "gh-upload.ps1")
    check_bom(script, errors)
    for rel in ["tests/test_gh_upload.ps1"]:
        check_bom(os.path.join(skill_dir, rel.replace("/", os.sep)), errors)
    script_text = read_text(script, errors)
    if script_text:
        for prm in SCRIPT_PARAMS:
            if prm not in script_text:
                errors.append("gh-upload.ps1 缺少参数:%s" % prm)
        for token, why in SCRIPT_TOKENS:
            if token not in script_text:
                errors.append("gh-upload.ps1 缺少关键实现 %s(%s)" % (token, why))
        for bad, why in FORBIDDEN:
            if bad in script_text:
                errors.append("gh-upload.ps1 命中禁止写法 %s(%s)" % (bad, why))
        if "-DryRun" not in script_text or "DryRun" not in script_text:
            errors.append("gh-upload.ps1 必须支持 -DryRun 干跑")

    for path in [skill_md, script]:
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
