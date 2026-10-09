#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
yf - 项目归档同步工具（来源隔离的多机协作，纯 Python 标准库）

模型：NAS 上项目只有固定 01-08 架构；每台电脑同步时，把自己归类好的内容
      写进【分类/<本机主机名>/...】，各机互不覆盖。
      本机可覆盖自己旧内容；别的来源文件夹永不改动。

命令:
  yf run [路径]        搜索 NAS 项目 + 把 01-08 架构补进本地当前文件夹（建立映射）
  yf go  [路径]        同步：本地未归类 -> 直接拒绝；否则上传到 NAS 的 <主机名> 层
  yf pull [路径]       拉取：选【分类 + 来源(主机名)】，推荐最新时间的来源
  yf find <关键词>     按关键词搜项目 -> 在项目里搜文件 -> 选着拉取到本地
  yf sources [路径]    列出某项目各分类下有哪些来源（主机名/时间/IP）
  yf whoami            看本机将使用的来源名（主机名）+ IP
  yf list              查看映射
  yf root <路径>       设置 NAS 归档根目录
  yf open [路径]       用资源管理器打开该项目 NAS 文件夹
  yf setup             配置向导
  yf help              帮助
"""

import argparse
import difflib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path(os.environ.get("USERPROFILE", str(Path.home())))
BASE_DIR = HOME / ".yf"
LEGACY_DIR = HOME / ".cctv"
CONFIG_FILE = BASE_DIR / "config.json"

TOP = [
    "01招投标合同", "02基础资料", "03建议书可研", "04方案设计",
    "05初步设计", "06施工图", "07施工资料", "08其他资料",
]
LOG_DIR = "_同步日志"          # NAS 项目内的按机日志目录
PROJECT_LOG = "项目日志.txt"   # 本地项目内的日志
MARKER = ".yfsource"           # 标记“这是从别的来源拉取下来的”
SYS_JUNK = {"desktop.ini", "thumbs.db", ".ds_store", ".gitignore", ".gitattributes"}

HOST = (os.environ.get("COMPUTERNAME") or socket.gethostname() or "PC").strip()


def local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return ""


DEFAULT_CONFIG = {
    "nas_root": "Z:\\00市政交通所项目档案（存档）",
    "log_dir": LOG_DIR,
    "project_log": PROJECT_LOG,
    "auto_threshold": 85,
    "candidate_min": 40,
    "structure_template": TOP,
    "mappings": [],
}


def eprint(*a):
    print(*a, file=sys.stderr)


# ---------- 配置 ----------

def load_config():
    if LEGACY_DIR.exists() and not BASE_DIR.exists():
        try:
            shutil.copytree(LEGACY_DIR, BASE_DIR)
        except OSError:
            pass
    if not CONFIG_FILE.exists():
        BASE_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    text = CONFIG_FILE.read_text(encoding="utf-8-sig")
    cfg = json.loads(text)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- 映射检索 ----------

def norm_name(name):
    n = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]", "", name)
    n = re.sub(r"^(?:\d+[A-Za-z]*)+", "", n)
    return n


def similarity(a, b):
    ra = difflib.SequenceMatcher(None, a, b).ratio()
    rn = difflib.SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()
    return max(ra, rn) * 100


def nas_root_ok(cfg):
    root = cfg.get("nas_root", "")
    if not root or not os.path.isdir(root):
        eprint(f"NAS 归档根目录不可用: {root!r}")
        eprint("请先用: yf root <路径>  设置正确的根目录（建议用 UNC，如 \\\\NAS\\共享\\...）")
        return False
    return True


def scan_nas_folders(cfg):
    root = Path(cfg["nas_root"])
    out = []
    if not root.exists():
        return out
    for top in root.iterdir():
        if not top.is_dir() or top.name.startswith("."):
            continue
        if re.fullmatch(r"\d{4}", top.name):
            for sub in top.iterdir():
                if sub.is_dir() and not sub.name.startswith("."):
                    out.append((sub.name, str(sub)))
        else:
            out.append((top.name, str(top)))
    return out


def find_mapping(cfg, local):
    local = os.path.normpath(local)
    for m in cfg["mappings"]:
        if os.path.normpath(m["local"]) == local:
            return m
    # 兜底：读文件夹内的 .yfmap 标记（改名/移动/换机后仍有效）
    mk = os.path.join(local, ".yfmap")
    if os.path.isfile(mk):
        try:
            nas = open(mk, encoding="utf-8").read().strip()
        except OSError:
            nas = ""
        if nas:
            m = {"local": local, "nas": nas}
            cfg["mappings"].append(m)
            save_config(cfg)
            return m
    return None


def write_map_marker(local, nas):
    try:
        with open(os.path.join(local, ".yfmap"), "w", encoding="utf-8") as f:
            f.write(str(nas))
    except OSError:
        pass


def establish_mapping(cfg, local):
    local_name = os.path.basename(local)
    cands = scan_nas_folders(cfg)
    if not cands:
        print("NAS 归档里还没有项目文件夹，将新建同名文件夹。")
        nas = os.path.join(cfg["nas_root"], local_name)
        cfg["mappings"].append({"local": local, "nas": nas})
        save_config(cfg)
        return find_mapping(cfg, local)
    scored = sorted(((similarity(local_name, n), n, p) for n, p in cands),
                    key=lambda x: (-x[0], x[1]))
    shown = [s for s in scored if s[0] >= cfg.get("candidate_min", 40)][:8]
    if not shown:
        print("没有找到相似的项目文件夹，将新建同名文件夹。")
        nas = os.path.join(cfg["nas_root"], local_name)
    elif shown[0][0] >= cfg.get("auto_threshold", 85):
        nas = shown[0][2]
        print(f"[自动] 匹配到项目: {shown[0][1]}  ({shown[0][0]:.0f}%)")
    else:
        print("找到以下相近的 NAS 项目文件夹:")
        for i, (score, name, path) in enumerate(shown, 1):
            rel = os.path.dirname(path)
            flag = "  <- 推荐" if i == 1 else ""
            print(f"  #{i}  {score:3.0f}%  {rel}\\{name}{flag}")
        while True:
            try:
                ans = input("  回车选 #1；输编号；n 新建同名；q 取消: ").strip()
            except EOFError:
                ans = "1"
            if ans == "":
                nas = shown[0][2]
                break
            if ans.lower() == "n":
                nas = os.path.join(cfg["nas_root"], local_name)
                break
            if ans.lower() == "q":
                return None
            if ans.isdigit() and 1 <= int(ans) <= len(shown):
                nas = shown[int(ans) - 1][2]
                break
            print("  输入无效。")
    cfg["mappings"].append({"local": local, "nas": nas})
    save_config(cfg)
    print(f"已确认映射: {local}  ->  {nas}")
    return find_mapping(cfg, local)


# ---------- 骨架 / 校验 ----------

def ensure_skeleton(local: Path):
    created = []
    for name in TOP:
        d = local / name
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            created.append(name)
    return created


def validate_categorized(cfg, local: Path):
    """返回根目录里“未归类”的条目（01-08、日志、系统垃圾之外的所有东西）。"""
    allowed = set(TOP) | {cfg.get("project_log", PROJECT_LOG)}
    stray = []
    for it in local.iterdir():
        n = it.name
        if n in allowed:
            continue
        if n.lower() in SYS_JUNK or n.startswith("."):
            continue
        stray.append(n)
    return stray


# ---------- 复制引擎 ----------

def run_robocopy(src, dst, excludes=None, logfile=None):
    try:
        cmd = ["robocopy", str(src), str(dst), "/E", "/R:2", "/W:1", "/NP", "/XJ", "/MT:8"]
        if excludes:
            cmd.append("/XD")
            cmd.extend(str(x) for x in excludes)
        if logfile:
            cmd.append("/LOG:" + str(logfile))
        p = subprocess.run(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        code = p.returncode
    except FileNotFoundError:
        copy_incremental(src, dst, excludes)
        return 0
    return code


def copy_incremental(src, dst, excludes=None):
    excludes = {os.path.normpath(str(e)) for e in (excludes or [])}
    for dp, dns, fns in os.walk(src):
        if os.path.normpath(dp) in excludes:
            dns[:] = []
            continue
        rel = os.path.relpath(dp, src)
        tgt = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(tgt, exist_ok=True)
        for f in fns:
            s = os.path.join(dp, f)
            t = os.path.join(tgt, f)
            try:
                if (not os.path.exists(t)
                        or os.path.getsize(s) != os.path.getsize(t)
                        or os.path.getmtime(s) > os.path.getmtime(t)):
                    shutil.copy2(s, t)
            except OSError:
                pass


def human(n):
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f}{u}" if u == "B" else f"{n:.1f}{u}"
        n /= 1024


def plan_copy(src, dst, excludes):
    """列出需要复制的文件 (源, 目标, 大小)；跳过 excludes 目录；只拷缺失/更新/变大的。"""
    excludes = {os.path.normpath(str(e)) for e in (excludes or [])}
    todo = []
    for dp, dns, fns in os.walk(src):
        if os.path.normpath(dp) in excludes:
            dns[:] = []
            continue
        rel = os.path.relpath(dp, src)
        for f in fns:
            s = os.path.join(dp, f)
            t = os.path.join(dst, f) if rel == "." else os.path.join(dst, rel, f)
            try:
                st = os.stat(s)
            except OSError:
                continue
            need = True
            if os.path.exists(t):
                try:
                    tt = os.stat(t)
                    need = (st.st_size != tt.st_size) or (st.st_mtime > tt.st_mtime)
                except OSError:
                    need = True
            if need:
                todo.append((s, t, st.st_size))
    return todo


def do_copy(todo, label="复制"):
    """带进度条地复制 todo 列表。返回成功/失败数。"""
    total_f = len(todo)
    total_b = sum(x[2] for x in todo)
    if total_f == 0:
        print(f"{label}: 无需复制（已是最新）")
        return 0, 0
    done_f = done_b = 0
    ok = fail = 0
    t0 = time.time()
    last = [0.0]
    width = 28

    def render(force=False):
        now = time.time()
        if not force and now - last[0] < 0.12:
            return
        last[0] = now
        frac = (done_b / total_b) if total_b else (done_f / total_f)
        frac = min(frac, 1.0)
        fill = int(frac * width)
        bar = "#" * fill + "-" * (width - fill)
        el = now - t0
        eta = (el / frac - el) if frac > 0.001 else 0
        sys.stdout.write(
            f"\r{label} [{bar}] {frac*100:5.1f}%  {done_f}/{total_f} 个  "
            f"{human(done_b)}/{human(total_b)}  ETA {int(eta):>4}s ")
        sys.stdout.flush()

    for s, t, sz in todo:
        try:
            d = os.path.dirname(t)
            if d:
                os.makedirs(d, exist_ok=True)
            with open(s, "rb") as fs, open(t, "wb") as fd:
                while True:
                    buf = fs.read(1024 * 1024)
                    if not buf:
                        break
                    fd.write(buf)
                    done_b += len(buf)
                    render()
            shutil.copystat(s, t)
            ok += 1
        except OSError as e:
            fail += 1
            eprint(f"\n  复制失败 {s}: {e}")
        done_f += 1
        render(force=(done_f == total_f))
    print()
    print(f"{label}完成：成功 {ok}，失败 {fail}，共 {human(total_b)}，用时 {int(time.time()-t0)}s")
    return ok, fail


def marked_children(cat_dir: Path):
    """分类目录下，属于“拉取来源”的子文件夹（含 .yfsource 标记）。"""
    out = []
    if not cat_dir.is_dir():
        return out
    for child in cat_dir.iterdir():
        if child.is_dir() and (child / MARKER).exists():
            out.append(child)
    return out


# ---------- 日志 ----------

def write_log(cfg, mapping, action, cat="", detail=""):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}\t[{HOST}]\t{local_ip()}\t{action}\t{cat}\t{detail}\n"
    # NAS 每机一份
    try:
        ld = Path(mapping["nas"]) / cfg.get("log_dir", LOG_DIR)
        ld.mkdir(parents=True, exist_ok=True)
        with open(ld / f"{HOST}.log", "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        eprint(f"[日志] NAS 写入失败: {e}")
    # 本地项目日志
    try:
        with open(Path(mapping["local"]) / cfg.get("project_log", PROJECT_LOG),
                  "a", encoding="utf-8") as f:
            f.write(line)
    except OSError as e:
        eprint(f"[日志] 本地写入失败: {e}")


# ---------- 命令 ----------

def cmd_run(args):
    cfg = load_config()
    if not nas_root_ok(cfg):
        return 1
    local = os.path.normpath(os.path.abspath(args.local))
    os.makedirs(local, exist_ok=True)
    mapping = find_mapping(cfg, local) or establish_mapping(cfg, local)
    if mapping is None:
        eprint("已取消。")
        return 1
    ensure_skeleton(Path(local))
    write_map_marker(local, mapping["nas"])  # 写进文件夹，改名/移动也不丢映射
    print("本地 01-08 架构已就绪。")
    print("下一步：把文件归类到 01-08 里，然后在本文件夹运行  yf go")
    return 0


def cmd_go(args):
    cfg = load_config()
    if not nas_root_ok(cfg):
        return 1
    local = Path(os.path.normpath(os.path.abspath(args.local)))
    mapping = find_mapping(cfg, str(local))
    if mapping is None:
        print("该文件夹还没有映射，正在检索 NAS 项目…")
        ensure_skeleton(local)
        mapping = establish_mapping(cfg, str(local))
        if mapping is None:
            eprint("已取消。")
            return 1
        write_map_marker(str(local), mapping["nas"])

    stray = validate_categorized(cfg, local)
    if stray:
        eprint("检测到未归类的文件/文件夹（必须在 01-08 之内），已拒绝同步：")
        for s in stray:
            eprint("   - " + s)
        eprint("请先整理到对应分类，再运行 yf go。")
        return 2

    nas = Path(mapping["nas"])
    all_todo = []
    plan = []  # (分类, 目标, todo)
    for name in TOP:
        src = local / name
        if not src.exists():
            continue
        excludes = marked_children(src)  # 拉取来的来源不重复上传
        dst = nas / name / HOST
        todo = plan_copy(src, dst, excludes)
        if todo:
            plan.append((name, dst, todo))
            all_todo.extend(todo)

    if args.dry_run:
        for name, dst, todo in plan:
            print(f"[dry-run] {name}: {len(todo)} 个文件 -> {dst}")
        if not plan:
            print("[dry-run] 无待上传文件。")
        return 0
    if not all_todo:
        print("没有需要同步的文件（分类为空或已是最新）。")
        return 0
    print(f"待上传 {len(all_todo)} 个文件，开始…")
    do_copy(all_todo, "上传")
    for name, dst, todo in plan:
        dst.mkdir(parents=True, exist_ok=True)
        write_log(cfg, mapping, "go", name, f"{len(todo)}个文件 -> {HOST}")
        print(f"  [{name}] {len(todo)} 个文件 -> {dst}")
    print(f"同步完成。本机来源: {HOST}  ({local_ip()})")
    print(f"NAS: {nas}")
    return 0


def dir_sources(nas_cat: Path):
    out = []
    if not nas_cat.is_dir():
        return out
    for child in nas_cat.iterdir():
        if child.is_dir() and not child.name.startswith("."):
            try:
                mt = os.path.getmtime(child)
            except OSError:
                mt = 0
            out.append((child.name, child, mt))
    return out


def _fmt(ts):
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def cmd_sources(args):
    cfg = load_config()
    local = Path(os.path.normpath(os.path.abspath(args.local)))
    mapping = find_mapping(cfg, str(local))
    if mapping is None:
        eprint("无映射，请先 yf run。")
        return 1
    nas = Path(mapping["nas"])
    print(f"项目: {nas}")
    for name in TOP:
        srcs = dir_sources(nas / name)
        if not srcs:
            continue
        print(f"[{name}]")
        for sname, _, mt in sorted(srcs, key=lambda x: -x[2]):
            print(f"    {sname}    最后同步 {_fmt(mt)}")
    return 0


def cmd_pull(args):
    cfg = load_config()
    local = Path(os.path.normpath(os.path.abspath(args.local)))
    mapping = find_mapping(cfg, str(local))
    if mapping is None:
        eprint("该文件夹还没有映射，请先 yf run。")
        return 1
    nas = Path(mapping["nas"])

    # 选分类
    cats = [name for name in TOP if dir_sources(nas / name)]
    if not cats:
        print("NAS 上该项目还没有任何来源内容。")
        return 0
    print("可拉取的分类:")
    for i, c in enumerate(cats, 1):
        print(f"  #{i}  {c}")
    cat = None
    while cat is None:
        try:
            ans = input("选分类编号: ").strip()
        except EOFError:
            return 1
        if ans.isdigit() and 1 <= int(ans) <= len(cats):
            cat = cats[int(ans) - 1]

    # 选来源（推荐最新时间）
    srcs = sorted(dir_sources(nas / cat), key=lambda x: -x[2])
    print(f"[{cat}] 的来源（按最后同步时间，推荐第一个）:")
    for i, (sname, _, mt) in enumerate(srcs, 1):
        flag = "  <- 推荐(最新)" if i == 1 else ""
        print(f"  #{i}  {sname}    最后同步 {_fmt(mt)}{flag}")
    src = None
    while src is None:
        try:
            ans = input("选来源编号（回车=推荐#1，q 取消）: ").strip()
        except EOFError:
            return 1
        if ans == "":
            src = srcs[0]
            break
        if ans.lower() == "q":
            return 0
        if ans.isdigit() and 1 <= int(ans) <= len(srcs):
            src = srcs[int(ans) - 1]

    sname = src[0]
    d = nas / cat / sname
    t = local / cat / sname
    print(f"拉取: {d}  ->  {t}")
    print("扫描待拉取文件…")
    todo = plan_copy(d, t, None)
    t.mkdir(parents=True, exist_ok=True)
    do_copy(todo, "拉取")
    (t / MARKER).write_text(sname, encoding="utf-8")
    write_log(cfg, mapping, "pull", cat, f"{sname} -> 本地")
    print("完成。（已标记为拉取来源，yf go 不会把它再传回去）")
    return 0


def search_entries(root: Path, keyword: str, limit=60):
    """在项目里按文件名/文件夹名搜关键词，返回 (类型, 相对路径, 绝对路径)。"""
    kw = keyword.lower()
    hits = []
    for dp, dns, fns in os.walk(root):
        if os.path.basename(dp) == LOG_DIR:
            dns[:] = []
            continue
        rel = os.path.relpath(dp, root)
        base = "" if rel == "." else rel
        for d in list(dns):
            if kw in d.lower():
                hits.append(("d", os.path.join(base, d), os.path.join(dp, d)))
        for f in fns:
            if kw in f.lower():
                hits.append(("f", os.path.join(base, f), os.path.join(dp, f)))
        if len(hits) >= limit:
            break
    return hits


def cmd_find(args):
    cfg = load_config()
    if not nas_root_ok(cfg):
        return 1
    kw = args.names[0] if args.names else ask("输入搜索关键词: ")
    if not kw:
        eprint("用法: yf find <关键词> [--into 目标文件夹]")
        return 1
    into = Path(args.into).expanduser().resolve() if getattr(args, "into", None) else Path.cwd()

    projs = scan_nas_folders(cfg)
    kl = kw.lower()
    matches = [(n, p) for n, p in projs if kl in n.lower()]
    if not matches:
        scored = sorted(((similarity(kw, n), n, p) for n, p in projs), key=lambda x: -x[0])
        matches = [(n, p) for s, n, p in scored if s >= 50][:10]
    if not matches:
        print(f"没有匹配 '{kw}' 的项目。")
        return 0
    print("匹配到的项目:")
    for i, (n, p) in enumerate(matches, 1):
        print(f"  #{i}  {n}")
    if len(matches) == 1:
        proj = matches[0]
    else:
        proj = None
        while proj is None:
            ans = ask("选项目编号（回车=#1，q 取消）: ")
            if ans == "":
                proj = matches[0]
            elif ans.lower() == "q":
                return 0
            elif ans.isdigit() and 1 <= int(ans) <= len(matches):
                proj = matches[int(ans) - 1]
            else:
                print("  输入无效。")
    root = Path(proj[1])
    print(f"选定项目: {proj[0]}")
    print(f"在项目内搜索 '{kw}' ...（可能较慢）")
    hits = search_entries(root, kw, limit=60)
    if not hits:
        print("项目内没有文件名含该关键词。可换关键词。")
        return 0
    print(f"命中 {len(hits)} 项:")
    for i, (t, rel, _full) in enumerate(hits, 1):
        tag = "[目录]" if t == "d" else "      "
        print(f"  #{i} {tag} {rel}")
    sel = ask("选要拉取的编号（如 1 或 1,3；回车=#1；q 取消）: ")
    if sel.lower() == "q":
        return 0
    idxs = []
    if sel == "":
        idxs = [0]
    else:
        for part in sel.split(","):
            part = part.strip()
            if part.isdigit() and 1 <= int(part) <= len(hits):
                idxs.append(int(part) - 1)
    if not idxs:
        print("未选择。")
        return 0
    into.mkdir(parents=True, exist_ok=True)
    copied = 0
    for i in idxs:
        _t, rel, full = hits[i]
        src = Path(full)
        dst = into / src.name
        try:
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst, ignore_errors=True)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            copied += 1
            print(f"  已拉取: {rel}  ->  {dst}")
        except OSError as e:
            eprint(f"  拉取失败 {rel}: {e}")
    write_log(cfg, {"local": str(into), "nas": str(root)}, "find", kw,
              f"{copied} 项 -> {into}")
    print(f"完成：拉取 {copied} 项到 {into}")
    return 0


def cmd_whoami(args):
    print(f"本机来源名(主机名): {HOST}")
    print(f"本机 IP          : {local_ip() or '(未知)'}")
    print("同步时会写进 NAS 的: 分类\\" + HOST + "\\...")
    return 0


def cmd_list(args):
    cfg = load_config()
    print(f"NAS 归档根目录: {cfg.get('nas_root', '(未设置)')}")
    print("-" * 60)
    for i, m in enumerate(cfg.get("mappings", []), 1):
        print(f"{i}. {m['local']}\n    -> {m['nas']}")
    if not cfg.get("mappings"):
        print("暂无映射。在项目文件夹里运行 yf run。")
    return 0


def cmd_root(args):
    cfg = load_config()
    p = os.path.abspath(os.path.expanduser(args.path))
    if not os.path.isdir(p):
        eprint(f"路径不存在: {p}")
        return 1
    cfg["nas_root"] = p
    save_config(cfg)
    print(f"NAS 归档根目录已设为: {p}")
    return 0


def cmd_open(args):
    cfg = load_config()
    local = os.path.normpath(os.path.abspath(args.local))
    m = find_mapping(cfg, local)
    if not m:
        eprint("无映射。")
        return 1
    if not os.path.isdir(m["nas"]):
        eprint("NAS 项目文件夹不存在。")
        return 1
    os.startfile(m["nas"])
    return 0


def ask(prompt, default=""):
    try:
        return input(prompt).strip()
    except EOFError:
        return default


def cmd_setup(args):
    cfg = load_config()
    print("=== yf 配置向导（回车=默认）===")
    nas = ask(f"NAS 归档根目录 [{cfg.get('nas_root')}]: ")
    if nas:
        cfg["nas_root"] = os.path.abspath(nas)
    print(f"本机来源名（主机名）: {HOST}  （会自动作为 NAS 上的来源文件夹名）")
    save_config(cfg)
    print("已保存。")
    return 0


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("cmd", nargs="?")
    p.add_argument("names", nargs="*")
    p.add_argument("--user", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--into", default=None)
    p.add_argument("--help", action="store_true")
    args = p.parse_args()

    if args.help or not args.cmd or args.cmd in ("help", "--help", "-h"):
        print(__doc__)
        return 0
    cmd = args.cmd
    args.local = args.names[0] if args.names else os.getcwd()

    if cmd == "run":
        return cmd_run(args)
    if cmd == "go":
        return cmd_go(args)
    if cmd == "pull":
        return cmd_pull(args)
    if cmd == "find":
        return cmd_find(args)
    if cmd == "sources":
        return cmd_sources(args)
    if cmd == "whoami":
        return cmd_whoami(args)
    if cmd == "list":
        return cmd_list(args)
    if cmd == "root":
        if not args.names:
            eprint("用法: yf root <路径>")
            return 1
        args.path = args.names[0]
        return cmd_root(args)
    if cmd == "open":
        return cmd_open(args)
    if cmd == "setup":
        return cmd_setup(args)
    eprint(f"未知命令: {cmd}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
