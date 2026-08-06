#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""创建项目标准目录骨架。

用法：
    python scripts/init_project.py "项目名称" [--base-dir 输出根目录]

产物（以项目名称建目录）：
    <项目根>/施工日志/
    <项目根>/照片归档/按标段/
    <项目根>/隐蔽工程/
"""

import argparse
import os


def main():
    parser = argparse.ArgumentParser(description="创建施工日志项目目录骨架")
    parser.add_argument("project", help="项目名称（也是项目根目录名）")
    parser.add_argument("--base-dir", default=".", help="项目根目录的父目录（默认当前目录）")
    args = parser.parse_args()

    root = os.path.join(args.base_dir, args.project)
    dirs = [
        "施工日志",
        "照片归档/按标段",
        "照片归档/按桩号",
        "隐蔽工程",
    ]
    for d in dirs:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    print(f"项目目录已创建：{root}")


if __name__ == "__main__":
    main()
