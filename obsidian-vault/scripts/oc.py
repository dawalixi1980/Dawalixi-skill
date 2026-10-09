#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oc - 用 OpenCode 桌面版打开一个本地文件夹（作为该项目的执行目录）

原理：桌面版注册了 opencode:// 协议，深链格式为
      opencode://open-project?directory=<URL 编码的绝对路径>
      已运行时由 second-instance 接收，未运行时冷启动。

用法:
  oc                 打开当前文件夹
  oc <文件夹>        打开指定文件夹
  oc --dry-run       只打印深链，不打开
"""

import ctypes
import os
import sys
import time
import urllib.parse
from pathlib import Path


def eprint(*a):
    print(*a, file=sys.stderr)


def focus_app(title="OpenCode"):
    """把 OpenCode 桌面版窗口拉到前台（深链需窗口处于激活态才会被处理）。"""
    try:
        u = ctypes.windll.user32
        hwnd = u.FindWindowW(None, title)
        if not hwnd:
            # 退一步：按标题包含 OpenCode 枚举
            found = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            def enum_cb(h, _):
                n = u.GetWindowTextLengthW(h)
                if n:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    u.GetWindowTextW(h, buf, n + 1)
                    t = buf.value
                    if "OpenCode" in t and u.IsWindowVisible(h):
                        found.append(h)
                return True

            u.EnumWindows(enum_cb, 0)
            hwnd = found[0] if found else 0
        if not hwnd:
            return False
        u.ShowWindow(hwnd, 9)  # SW_RESTORE
        u.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def resolve(args):
    for a in args:
        if not a.startswith("-"):
            p = Path(a).expanduser()
            if p.is_dir():
                return p.resolve()
    return Path.cwd().resolve()


def build_uri(root: Path) -> str:
    return "opencode://open-project?directory=" + urllib.parse.quote(str(root), safe="")


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return 0
    dry = "--dry-run" in args
    root = resolve(args)
    if not root.is_dir():
        eprint(f"路径不存在或不是文件夹: {root}")
        return 1
    uri = build_uri(root)
    if dry:
        print(f"[dry-run] 文件夹: {root}")
        print(f"[dry-run] 深链  : {uri}")
        return 0
    try:
        focus_app()            # 先聚焦，桌面版前端才处理深链
        time.sleep(0.4)
        os.startfile(uri)      # Windows 把协议派发给 OpenCode.exe
        time.sleep(0.8)
        os.startfile(uri)      # 补发一次，稳妥
        print(f"已用 OpenCode 桌面版打开: {root}")
        return 0
    except OSError as e:
        eprint(f"打开失败: {e}")
        eprint("请确认已安装 OpenCode 桌面版，并注册了 opencode:// 协议。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
