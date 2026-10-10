#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ob - 用 Obsidian 打开一个本地文件夹作为仓库（自适应、可移植、零第三方依赖）

打开策略:
  1. 官方 Obsidian CLI：obsidian eval + vault-open（热开任意文件夹，包括新建，不重启）
     关键：CLI 的 stdout/stderr 必须送 DEVNULL（不要 capture）——否则命令结束后
     管道断开，Obsidian 主进程再写一次就 EPIPE 崩溃弹窗。
  2. 兜底：登记 + obsidian://open?vault=<id>（必要时重启 Obsidian）。

用法:
  ob                  打开【本启动器所在文件夹】（默认仓库）
  ob <文件夹>         打开指定文件夹
  ob --dry-run        只显示识别与将要执行的命令，不打开
  ob -h/--help        帮助
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import uuid
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", "")) / "obsidian"
OBSIDIAN_JSON = APP_DIR / "obsidian.json"

CORE_PLUGINS = [
    "file-explorer", "global-search", "switcher", "graph", "backlink",
    "outgoing-link", "tag-pane", "page-preview", "daily-notes", "templates",
    "note-composer", "command-palette", "slash-command", "editor-status",
    "bookmarks", "outline", "word-count", "workspaces", "file-recovery",
    "canvas", "properties",
]

KNOWN_EXE = [
    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Obsidian" / "Obsidian.exe"),
    str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.exe"),
    str(Path(os.environ.get("ProgramFiles", "")) / "Obsidian" / "Obsidian.exe"),
    str(Path(os.environ.get("ProgramFiles(x86)", "")) / "Obsidian" / "Obsidian.exe"),
]

NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def eprint(*a):
    print(*a, file=sys.stderr)


# ---------- 仓库定位 ----------

def resolve_vault(args):
    """要打开的仓库：命令行参数 > 当前目录（在哪个文件夹敲 ob 就开哪个）。"""
    for a in args:
        if not a.startswith("-"):
            p = Path(a).expanduser()
            if p.is_dir():
                return p.resolve()
    return Path.cwd().resolve()


def ensure_vault(root: Path) -> bool:
    od = root / ".obsidian"
    if od.exists():
        return False
    od.mkdir(parents=True, exist_ok=True)
    (od / "app.json").write_text("{}", encoding="utf-8")
    (od / "appearance.json").write_text("{}", encoding="utf-8")
    (od / "core-plugins.json").write_text(
        json.dumps(CORE_PLUGINS, ensure_ascii=False, indent=2), encoding="utf-8")
    (od / "community-plugins.json").write_text("[]", encoding="utf-8")
    return True


# ---------- 环境探测 ----------

def find_cli():
    """官方 Obsidian CLI：先看 PATH，再看 Obsidian 安装目录里的 Obsidian.com 重定向器。"""
    p = shutil.which("obsidian")
    if p:
        return p
    exe = find_obsidian_exe()
    if exe:
        com = Path(exe).with_name("Obsidian.com")
        if com.exists():
            return str(com)
    return None


def cli_enabled(cli):
    """CLI 是否真的启用（跑 version，看是否为 not enabled）。"""
    try:
        r = subprocess.run([cli, "version"], capture_output=True, text=True,
                           timeout=20, creationflags=NOWIN)
        out = (r.stdout or "") + (r.stderr or "")
        return "not enabled" not in out.lower(), out.strip()
    except Exception as e:
        return False, str(e)


def find_obsidian_exe():
    try:
        import winreg
        roots = [
            (winreg.HKEY_CLASSES_ROOT, r"obsidian\shell\open\command"),
            (winreg.HKEY_CURRENT_USER, r"Software\Classes\obsidian\shell\open\command"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes\obsidian\shell\open\command"),
        ]
        for hive, sub in roots:
            try:
                with winreg.OpenKey(hive, sub) as k:
                    cmd = winreg.QueryValueEx(k, "")[0]
            except OSError:
                continue
            m = re.match(r'\s*"([^"]+\.exe)"', cmd) or re.match(r'\s*(\S+\.exe)', cmd)
            if m and Path(m.group(1)).exists():
                return m.group(1)
    except OSError:
        pass
    for p in KNOWN_EXE:
        if p and Path(p).exists():
            return p
    return None


def obsidian_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Obsidian.exe", "/NH"],
                             capture_output=True, text=True, timeout=8,
                             creationflags=NOWIN)
        return "Obsidian.exe" in out.stdout
    except Exception:
        return False


def active_title():
    try:
        out = subprocess.run(["tasklist", "/v", "/fi", "imagename eq Obsidian.exe",
                              "/fo", "csv", "/nh"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=NOWIN)
        for line in out.stdout.splitlines():
            if "Obsidian.exe" in line:
                fields = re.findall(r'"(?:[^"]|"")*"', line)
                if fields:
                    return fields[-1].strip('"')
    except Exception:
        pass
    return ""


def kill_obsidian():
    try:
        subprocess.run(["taskkill", "/F", "/IM", "Obsidian.exe"],
                       capture_output=True, creationflags=NOWIN)
    except Exception:
        pass
    for _ in range(20):
        if not obsidian_running():
            return True
        time.sleep(0.5)
    return not obsidian_running()


# ---------- 登记 ----------

def register_vault(root: Path):
    """把仓库写进 obsidian.json，返回其 id。"""
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        data = {"vaults": {}, "openSchemes": {"file": True}}
        if OBSIDIAN_JSON.exists():
            data = json.loads(OBSIDIAN_JSON.read_text(encoding="utf-8"))
        vaults = data.setdefault("vaults", {})
        target = os.path.normcase(os.path.normpath(str(root)))
        for vid, v in vaults.items():
            if os.path.normcase(os.path.normpath(v.get("path", ""))) == target:
                return vid
        vid = uuid.uuid4().hex[:16]
        vaults[vid] = {"path": str(root), "ts": int(time.time() * 1000)}
        OBSIDIAN_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
        return vid
    except Exception as e:
        eprint(f"[警告] 登记仓库失败: {e}")
        return None


# ---------- 打开 ----------

def open_via_cli(cli, root: Path):
    """用官方 CLI 热开仓库。
    关键：stdout/stderr 送 DEVNULL（不要 capture）——否则 CLI 的管道在命令结束后
    断开，Obsidian 主进程再写一次就 EPIPE 崩溃。
    """
    path_js = str(root).replace("\\", "/")
    code = "window.electron.ipcRenderer.sendSync('vault-open','%s',false)" % path_js
    try:
        r = subprocess.run([cli, "eval", "code=" + code],
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL,
                           timeout=25,
                           creationflags=NOWIN)
        return r.returncode == 0
    except Exception:
        return False


def open_via_uri(vid):
    uri = "obsidian://open?vault=" + urllib.parse.quote(vid)
    os.startfile(uri)


def open_vault(root: Path, dry_run=False):
    exe = find_obsidian_exe()
    running = obsidian_running()
    title = active_title() if running else ""
    already_active = running and root.name.lower() in title.lower()
    vid = register_vault(root)

    cli = find_cli()
    cli_ok = bool(cli)  # 不去 capture 探测（探测本身也会用到管道，可能触发崩溃）
    need_restart = running and not already_active and not cli_ok

    if dry_run:
        print(f"[dry-run] 仓库       : {root}")
        print(f"[dry-run] .obsidian  : {'有' if (root/'.obsidian').exists() else '无（将创建）'}")
        print(f"[dry-run] Obsidian   : {exe or '未找到'}")
        print(f"[dry-run] 运行中     : {running}   当前标题: {title or '(无)'}")
        print(f"[dry-run] 官方CLI    : {cli or '无'}  (可用={cli_ok})")
        if cli_ok:
            print("[dry-run] 将执行     : obsidian eval  (CLI 热开，不重启)")
        elif need_restart:
            print(f"[dry-run] 将执行     : 重启 Obsidian -> obsidian://open?vault={vid}")
        else:
            print(f"[dry-run] 将执行     : obsidian://open?vault={vid or '<path>'}")
        return 0

    # 1) 官方 CLI：热开任意文件夹（含新建），不重启
    if cli_ok:
        if open_via_cli(cli, root):
            print(f"已用官方 CLI 打开: {root}")
            return 0
        eprint("[提示] 官方 CLI 未成功，改用协议方式。")

    # 2) 兜底：协议（新仓库且 Obsidian 开着时，重启一次）
    if running and not already_active:
        print("改用协议：重启 Obsidian 以切换…")
        kill_obsidian()
        running = False
        time.sleep(0.5)
    try:
        if vid:
            open_via_uri(vid)
        else:
            os.startfile("obsidian://open?path=" + urllib.parse.quote(str(root), safe=""))
    except OSError as e:
        eprint(f"打开失败: {e}")
        eprint("请确认已安装 Obsidian。")
        return 1
    if already_active:
        print(f"Obsidian 已在打开该仓库: {root}")
    else:
        print(f"已用 Obsidian 打开: {root}")
    return 0


def main():
    args = sys.argv[1:]
    if any(a in ("-h", "--help") for a in args):
        print(__doc__)
        return 0
    dry = "--dry-run" in args
    root = resolve_vault(args)
    if not root.is_dir():
        eprint(f"路径不存在或不是文件夹: {root}")
        return 1
    created = ensure_vault(root)
    if created and not dry:
        print(f"已初始化仓库配置: {root}\\.obsidian")
    return open_vault(root, dry_run=dry)


if __name__ == "__main__":
    sys.exit(main())
