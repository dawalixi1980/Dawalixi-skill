#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按命名规范重命名并归档施工照片。

用法：
    python scripts/archive_photos.py --project "项目名称" --manifest 照片清单.json [--base-dir 输出根目录]

照片清单.json 结构（数组，每项一张照片）：
[
  {
    "source": "D:/手机导出/IMG_001.jpg",
    "日期": "2026-07-23",
    "标段": "璟湾路",
    "桩号/部位": "K0+000",
    "工序": "浇筑",
    "序号": 1
  }
]

规则：
- 目标名 = <日期>_<标段>_<桩号/部位>_<工序>[_<序号>].jpg
- 归档到 <项目根>/照片归档/按标段/<标段>/<日期>/<工序>/
- 工序含「隐蔽」时同时复制一份到 <项目根>/隐蔽工程/
- 自动跳过已存在且内容一致的目标文件；源文件不存在则报错跳过
"""

import argparse
import hashlib
import json
import os
import shutil

ARCHIVE_ROOT = "照片归档/按标段"
HIDDEN_DIR = "隐蔽工程"


def load_json(path):
    for enc in ("utf-8-sig", "gbk", "utf-8"):
        try:
            with open(path, "r", encoding=enc) as f:
                return json.load(f)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    raise ValueError(f"无法解析照片清单 JSON：{path}")


def sha1(path, chunk=1 << 16):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            data = f.read(chunk)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def archive_one(item, root):
    src = item.get("source")
    if not src or not os.path.exists(src):
        print(f"  [跳过] 源文件不存在：{src}")
        return None
    date = item.get("日期", "")
    seg = item.get("标段", "")
    stake = item.get("桩号/部位", "")
    proc = item.get("工序", "")
    seq = item.get("序号")
    base = f"{date}_{seg}_{stake}_{proc}"
    if seq:
        base += f"_{seq}"
    name = base + os.path.splitext(src)[1].lower()

    dest_dir = os.path.join(root, ARCHIVE_ROOT, seg, date, proc)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, name)
    if os.path.exists(dest) and sha1(src) == sha1(dest):
        print(f"  [已存在] {dest}")
    else:
        shutil.copy2(src, dest)
        print(f"  [归档] {dest}")

    if "隐蔽" in proc:
        hid_dir = os.path.join(root, HIDDEN_DIR, seg)
        os.makedirs(hid_dir, exist_ok=True)
        hid = os.path.join(hid_dir, name)
        shutil.copy2(dest, hid)
        print(f"  [隐蔽留底] {hid}")
    return dest


def main():
    parser = argparse.ArgumentParser(description="归档施工照片")
    parser.add_argument("--project", required=True, help="项目名称（也是项目根目录名）")
    parser.add_argument("--manifest", required=True, help="照片清单 JSON 路径")
    parser.add_argument("--base-dir", default=".", help="项目根目录的父目录（默认当前目录）")
    args = parser.parse_args()

    root = os.path.join(args.base_dir, args.project)
    items = load_json(args.manifest)
    archived = 0
    for item in items:
        if archive_one(item, root):
            archived += 1
    print(f"归档完成：{archived}/{len(items)} 张照片 → {root}")


if __name__ == "__main__":
    main()
