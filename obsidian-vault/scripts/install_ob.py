#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_ob - 安装 obsidian-vault skill（任意电脑跑一次即可）:

  1. 装官方 Obsidian CLI：把 Obsidian 安装目录加入用户 PATH → 终端可用 `obsidian`
     （注意：Obsidian 内的"命令行界面"总开关是 GUI 设置，脚本无法代开，脚本会提示你点一次）
  2. 装终端命令 `ob`：任意文件夹敲 `ob` → 用 Obsidian 打开当前文件夹为仓库
  3. 装终端命令 `oc`：任意文件夹敲 `oc` → 用 OpenCode 桌面版打开当前文件夹为项目
     脚本统一装到 %USERPROFILE%\\.ob 并加入用户 PATH。

不生成其它文件（只创建 ~/.ob 下的命令本身；目标文件夹的 .obsidian 在打开时按需自动创建）。

用法:
  python install_ob.py
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OB_HOME = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".ob"
FILES = ["ob.py", "ob.cmd", "oc.py", "oc.cmd"]
NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def find_obsidian_exe():
    try:
        import winreg
        for hive, sub in [
            (winreg.HKEY_CLASSES_ROOT, r"obsidian\shell\open\command"),
            (winreg.HKEY_CURRENT_USER, r"Software\Classes\obsidian\shell\open\command"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Classes\obsidian\shell\open\command"),
        ]:
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
    for p in (Path(os.environ.get("LOCALAPPDATA", "")) / "Obsidian" / "Obsidian.exe",
              Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian" / "Obsidian.exe",
              Path(os.environ.get("ProgramFiles", "")) / "Obsidian" / "Obsidian.exe"):
        if p.exists():
            return str(p)
    return None


def add_user_path(folder) -> bool:
    folder = str(folder).rstrip("\\")
    if not folder:
        return False
    try:
        import winreg
    except ImportError:
        return False
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                        winreg.KEY_READ | winreg.KEY_WRITE) as k:
        try:
            cur, _ = winreg.QueryValueEx(k, "Path")
        except FileNotFoundError:
            cur = ""
        parts = [p for p in cur.split(";") if p]
        if any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(folder) for p in parts):
            return False
        winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ,
                          folder + (";" + cur if cur else ""))
    return True


def cli_ready():
    cli = shutil.which("obsidian")
    exe = find_obsidian_exe()
    if not cli and exe:
        com = Path(exe).with_name("Obsidian.com")
        if com.exists():
            cli = str(com)
    if not cli:
        return None, "未找到（需 Obsidian 1.12.4+ 安装器）"
    try:
        r = subprocess.run([cli, "version"], capture_output=True, text=True,
                           timeout=20, creationflags=NOWIN)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        if "not enabled" in out.lower():
            return cli, "命令已就绪，但未开启"
        return cli, "已启用"
    except Exception as e:
        return cli, f"探测失败: {e}"


def main():
    print("安装 obsidian-vault skill")

    missing = [f for f in FILES if not (HERE / f).exists()]
    if missing:
        print(f"[错误] 缺少文件: {', '.join(missing)}（应位于 {HERE}）")
        return 1

    # 1) 官方 CLI 命令 → PATH
    exe = find_obsidian_exe()
    if exe:
        if add_user_path(Path(exe).parent):
            print(f"  [1/2] 已把 Obsidian 目录加入 PATH: {Path(exe).parent}（命令 obsidian）")
        else:
            print("  [1/2] Obsidian 目录已在 PATH（命令 obsidian）")
    else:
        print("  [1/2] 未找到 Obsidian，请先安装 Obsidian")

    # 2) 全局 ob 命令 → PATH
    OB_HOME.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(HERE / f, OB_HOME / f)
    if add_user_path(OB_HOME):
        print(f"  [2/2] 已装 ob 命令到 {OB_HOME} 并加入 PATH")
    else:
        print(f"  [2/2] ob 命令已在 {OB_HOME}（PATH 已含）")

    cli, status = cli_ready()
    print(f"\n官方 CLI: {status}")
    if cli and "未开启" in status:
        print("  → 一次性开启：Obsidian → 设置 → 通用 → 高级 → 打开『命令行界面』")

    print("\n完成。新开一个终端后：")
    print("  ob        用 Obsidian 打开当前文件夹为仓库")
    print("  ob <文件夹>")
    print("  oc        用 OpenCode 桌面版打开当前文件夹")
    print("  oc <文件夹>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
