#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_validate_skill.py —— github-upload 校验器自身的回归测试

正向:真实 skill 目录应通过。
反向:人为破坏(缺章节 / 悬空引用 / BOM 丢失 / 删掉关键实现)必须被抓出来。

用法:python tests/test_validate_skill.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(TESTS_DIR)
VALIDATOR = os.path.join(SKILL_DIR, "scripts", "validate_skill.py")

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def run_validator(path):
    proc = subprocess.run(
        [sys.executable, VALIDATOR, path],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout


class ValidateSkillTest(unittest.TestCase):
    def test_real_skill_passes(self):
        code, out = run_validator(SKILL_DIR)
        self.assertEqual(code, 0, "真实 skill 目录应通过校验:\n" + out)
        self.assertIn("PASS", out)

    def test_missing_section_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "github-upload")
            shutil.copytree(SKILL_DIR, dst)
            p = os.path.join(dst, "SKILL.md")
            with open(p, "r", encoding="utf-8-sig") as fh:
                body = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body.replace("## Invariants", "## 被删掉的章节"))
            code, out = run_validator(dst)
            self.assertEqual(code, 1)
            self.assertIn("## Invariants", out)

    def test_dangling_reference_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "github-upload")
            shutil.copytree(SKILL_DIR, dst)
            os.remove(os.path.join(dst, "references", "git-data-api.md"))
            code, out = run_validator(dst)
            self.assertEqual(code, 1)
            self.assertIn("git-data-api.md", out)

    def test_missing_bom_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "github-upload")
            shutil.copytree(SKILL_DIR, dst)
            p = os.path.join(dst, "scripts", "gh-upload.ps1")
            with open(p, "r", encoding="utf-8-sig") as fh:
                body = fh.read()
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            code, out = run_validator(dst)
            self.assertEqual(code, 1)
            self.assertIn("BOM", out)

    def test_missing_escaping_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = os.path.join(tmp, "github-upload")
            shutil.copytree(SKILL_DIR, dst)
            p = os.path.join(dst, "scripts", "gh-upload.ps1")
            with open(p, "r", encoding="utf-8-sig") as fh:
                body = fh.read()
            body = body.replace("Esc-Ascii", "Esc2")
            with open(p, "w", encoding="utf-8-sig") as fh:
                fh.write(body)
            code, out = run_validator(dst)
            self.assertEqual(code, 1)
            self.assertIn("Esc-Ascii", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
