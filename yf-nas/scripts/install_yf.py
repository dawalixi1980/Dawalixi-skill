#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
install_yf - 安装 yf 终端命令到本机（任意电脑跑一次即可）

做的事:
  1. 把 yf.py / yf.cmd 复制到 %USERPROFILE%\\.yf
  2. 把 %USERPROFILE%\\.yf 加入用户 PATH（终端可直接 `yf`）

用法:
  python install_yf.py
"""

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
YF_HOME = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".yf"
FILES = ["yf.py", "yf.cmd"]


def add_user_path(folder) -> bool:
    folder = str(folder).rstrip("\\")
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
            # 若已存在但不在最前，提到最前，确保新 yf 覆盖旧 yf
            parts = [p for p in parts if os.path.normcase(p.rstrip("\\")) != os.path.normcase(folder)]
            winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, folder + ";" + ";".join(parts))
            return True
        winreg.SetValueEx(k, "Path", 0, winreg.REG_EXPAND_SZ, folder + (";" + cur if cur else ""))
    return True


def main():
    print("安装 yf 终端命令")
    missing = [f for f in FILES if not (HERE / f).exists()]
    if missing:
        print(f"[错误] 缺少文件: {', '.join(missing)}（应位于 {HERE}）")
        return 1
    YF_HOME.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(HERE / f, YF_HOME / f)
    print(f"  已装到: {YF_HOME}")
    add_user_path(YF_HOME)
    print(f"  已把 {YF_HOME} 放到用户 PATH 最前（会覆盖旧的 yf）")
    print("\n完成。新开一个终端后：")
    print("  yf whoami        看本机来源名(主机名)")
    print("  yf run           在项目文件夹里：检索项目 + 补 01-08 架构")
    print("  yf go            归类好后同步到 NAS 的 <主机名> 层")
    print("  yf pull          拉取某个分类+某来源（推荐最新）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
