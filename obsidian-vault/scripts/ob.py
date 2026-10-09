#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ob - 用 Obsidian 打开一个本地文件夹作为仓库（自适应、可移植、零第三方依赖）

打开策略（从最好到兜底，自动选择，任一电脑都成立）:
  1. 官方 Obsidian CLI（若已启用）：obsidian eval + vault-open IPC
     —— 热启动/冷启动都能开任意未登记目录，不打扰当前仓库。
  2. 登记进 obsidian.json + obsidian://open?vault=<id>
     —— 冷启动有效；若 Obsidian 正开着别的仓库，则自动重启后再开。

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
    path_js = str(root).replace("\\", "/")
    code = "window.electron.ipcRenderer.sendSync('vault-open','%s',false)" % path_js
    try:
        r = subprocess.run([cli, "eval", "code=" + code],
                           capture_output=True, text=True, timeout=25,
                           creationflags=NOWIN)
        return r.returncode == 0, (r.stdout or "").strip(), (r.stderr or "").strip()
    except Exception as e:
        return False, "", str(e)


def open_via_uri(vid):
    uri = "obsidian://open?vault=" + urllib.parse.quote(vid)
    os.startfile(uri)


def open_vault(root: Path, dry_run=False):
    cli = find_cli()
    exe = find_obsidian_exe()
    running = obsidian_running()
    title = active_title() if running else ""
    already_active = running and root.name.lower() in title.lower()

    if dry_run:
        print(f"[dry-run] 仓库       : {root}")
        print(f"[dry-run] .obsidian  : {'有' if (root/'.obsidian').exists() else '无（将创建）'}")
        print(f"[dry-run] 官方CLI    : {cli or '未安装/未启用'}")
        print(f"[dry-run] Obsidian   : {exe or '未找到'}")
        print(f"[dry-run] 运行中     : {running}   当前标题: {title or '(无)'}")
        if cli:
            print(f"[dry-run] 将执行     : obsidian eval "
                  f"\"code=window.electron.ipcRenderer.sendSync('vault-open',"
                  f"'{str(root).replace(chr(92), '/')}',false)\"")
        elif running and not already_active:
            print("[dry-run] 将执行     : 重启 Obsidian 后 obsidian://open?vault=<id>")
        else:
            print("[dry-run] 将执行     : obsidian://open?vault=<id>")
        return 0

    # 1) 官方 CLI
    if cli:
        enabled, info = cli_enabled(cli)
        if enabled:
            ok, out, err = open_via_cli(cli, root)
            if ok:
                print(f"已用官方 CLI 打开: {root}")
                return 0
            eprint(f"[提示] 官方 CLI 调用未成功（{err or out or '未知原因'}），改用协议方式。")
        else:
            eprint("[提示] 官方 CLI 命令已就绪，但功能未开启：")
            eprint("       Obsidian → 设置 → 通用 → 高级 → 打开『命令行界面』(只点一次)，")
            eprint("       或用命令: obsidian 的方式无需再管。本次先用协议方式打开。")

    # 2) 兜底：登记 + URI（必要时重启 Obsidian）
    if running and not already_active:
        print("当前 Obsidian 打开的是别的仓库，正在重启以切换到目标仓库…")
        if not kill_obsidian():
            eprint("无法结束 Obsidian，请手动关闭后重试。")
            return 1
        running = False

    vid = register_vault(root)
    if not vid:
        eprint("登记仓库失败，尝试直接用协议打开。")
    try:
        open_via_uri(vid) if vid else os.startfile(
            "obsidian://open?path=" + urllib.parse.quote(str(root), safe=""))
        print(f"已打开: {root}")
        return 0
    except OSError as e:
        eprint(f"打开失败: {e}")
        eprint("请确认已安装 Obsidian。")
        return 1


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
