# -*- coding: utf-8 -*-
"""openclaw agent 管理（双环境通用版）

支持两套环境：
  --target local   (默认) 在本机 Windows 上管理本地 openclaw（命令用 `openclaw`）
  --target server         通过 SSH 管理腾讯云服务器上的 openclaw

用法：
  python oc_agents.py list [--target local|server]
  python oc_agents.py add <name> [--target ...]
  python oc_agents.py bind <agent> <account> [--target ...]
  python oc_agents.py login [--target ...]
  python oc_agents.py qr <out_png> [--target ...]
  python oc_agents.py accounts [--target ...]
"""
import sys
import os
import json
import base64
import subprocess
import argparse

# ---------- 服务器 SSH 参数（仅 --target server 用）----------
SERVER_HOST = "49.235.167.212"
SERVER_PORT = "22"
SERVER_USER = "root"
SERVER_PASSWORD = "7119968cjw+-="
PLINK = r"C:\Users\ADMINI~1\AppData\Local\Temp\opencode\plink.exe"
SERVER_HOSTKEY = "ssh-ed25519 255 SHA256:UCRw+t5kuwTub3KnyOI0ilhn2QZomddLdw+VHwmVb4Q"
SERVER_NODE = "/root/.nvm/versions/node/v22.23.1/bin/node"
SERVER_ENTRY = "/root/.local/share/pnpm/global/5/.pnpm/openclaw@2026.7.1_@aws-sdk+credential-provider-node@3.972.46_@smithy+signature-v4@5.6.12/node_modules/openclaw/openclaw.mjs"
SERVER_STATE = "/root/.openclaw"
SERVER_QR_URL_FILE = "/tmp/openclaw-qr-url.txt"
SERVER_QR_PNG = "/tmp/openclaw-login-qr.png"


# ---------- 本地 Windows 参数 ----------
LOCAL_STATE = os.path.expanduser("~/.openclaw")
LOCAL_QR_URL_FILE = os.path.join(LOCAL_STATE, "openclaw-qr-url.txt")
LOCAL_QR_PNG = os.path.join(LOCAL_STATE, "openclaw-login-qr.png")
# 本机 openclaw 可执行文件（Windows npm 全局安装）
LOCAL_OPENCLAW = os.path.join(os.path.expanduser("~/AppData/Roaming/npm"), "openclaw.cmd")


def _local_run(args, timeout=120):
    """本机直接运行 openclaw 命令。"""
    exe = LOCAL_OPENCLAW if os.path.exists(LOCAL_OPENCLAW) else "openclaw"
    try:
        p = subprocess.run(
            [exe] + args,
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            shell=(exe == "openclaw"),
        )
        return p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "(timeout)"


def _server_run(cmd, timeout=120):
    """在服务器上执行一条 shell 命令。"""
    try:
        p = subprocess.run(
            [PLINK, "-ssh", "-batch", "-hostkey", SERVER_HOSTKEY, "-P", SERVER_PORT,
             "-l", SERVER_USER, "-pw", SERVER_PASSWORD, SERVER_HOST, cmd],
            capture_output=True, timeout=timeout,
        )
        return p.stdout.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "(timeout)"


def _server_run_b64(script, timeout=120):
    """把一段 Python 脚本传到服务器执行。"""
    b64 = base64.b64encode(script.encode("utf-8")).decode("ascii")
    remote = "/tmp/oc_mgmt_tmp.py"
    return _server_run(f"echo {b64} | base64 -d > {remote} && python3 {remote}", timeout)


def _oc(target, args, timeout=120):
    """按 target 运行 openclaw CLI 命令，返回输出。"""
    if target == "server":
        inner = " ".join(args)
        return _server_run(f"{SERVER_NODE} {SERVER_ENTRY} {inner}", timeout)
    return _local_run(args, timeout)


def list_agents(target):
    out = _oc(target, ["agents", "list"])
    print(out)
    print("--- 微信账号 ---")
    if target == "server":
        print(_server_run(f"cat {SERVER_STATE}/openclaw-weixin/accounts.json 2>/dev/null"))
    else:
        p = os.path.join(LOCAL_STATE, "openclaw-weixin", "accounts.json")
        if os.path.exists(p):
            print(open(p, encoding="utf-8").read())


def add_agent(target, name):
    ws_server = f"{SERVER_STATE}/workspace-{name}"
    ws_local = os.path.join(LOCAL_STATE, f"workspace-{name}")
    if target == "server":
        script = f'''
import os
base = "{ws_server}"
os.makedirs(os.path.join(base, "memory"), exist_ok=True)
for fn, content in {{
"IDENTITY.md": "# IDENTITY.md\\n\\n- **Name:** {name}\\n- **Creature:** AI 助理\\n- **Emoji:** 🤖\\n",
"SOUL.md": "# SOUL.md\\n\\n## 核心原则\\n- 真诚帮助，直接做事。先查再问。\\n- 独立 AI 助理「{name}」，独立工作目录与记忆。\\n",
"USER.md": "# USER.md\\n\\n- **姓名/称呼：** （待补充）\\n- **时区：** GMT+8\\n",
"AGENTS.md": "# AGENTS.md\\n\\n独立工作区。阅读 SOUL/USER/memory 后工作。\\n",
}}.items():
    p = os.path.join(base, fn)
    if not os.path.exists(p):
        open(p, "w", encoding="utf-8").write(content)
print("workspace ready:", base)
'''
        print(_server_run_b64(script))
        print(_oc("server", ["agents", "add", name, "--workspace", ws_server, "--non-interactive", "--json"]))
    else:
        os.makedirs(os.path.join(ws_local, "memory"), exist_ok=True)
        files = {
            "IDENTITY.md": f"# IDENTITY.md\n\n- **Name:** {name}\n- **Creature:** AI 助理\n- **Emoji:** 🤖\n",
            "SOUL.md": f"# SOUL.md\n\n## 核心原则\n- 真诚帮助，直接做事。先查再问。\n- 独立 AI 助理「{name}」，独立工作目录与记忆。\n",
            "USER.md": "# USER.md\n\n- **姓名/称呼：** （待补充）\n- **时区：** GMT+8\n",
            "AGENTS.md": "# AGENTS.md\n\n独立工作区。阅读 SOUL/USER/memory 后工作。\n",
        }
        for fn, content in files.items():
            p = os.path.join(ws_local, fn)
            if not os.path.exists(p):
                with open(p, "w", encoding="utf-8") as f:
                    f.write(content)
        print("workspace ready:", ws_local)
        print(_oc("local", ["agents", "add", name, "--workspace", ws_local, "--non-interactive", "--json"]))


def bind(target, agent, account):
    print(_oc(target, ["agents", "bind", "--agent", agent, "--bind", f"openclaw-weixin:{account}", "--json"]))
    print("--- 当前 bindings ---")
    print(_oc(target, ["agents", "bindings"]))


def login(target):
    """后台启动微信扫码，轮询提取二维码链接。"""
    if target == "server":
        script = f'''
import subprocess, os, time, re
node = "{SERVER_NODE}"
entry = "{SERVER_ENTRY}"
cmd_str = f"TERM=xterm-256color {{node}} {{entry}} channels login --channel openclaw-weixin --verbose"
log = open("/tmp/openclaw-login.log", "w")
proc = subprocess.Popen(["script", "-q", "-c", cmd_str, "/dev/null"], stdout=log, stderr=subprocess.STDOUT, cwd="/root")
print("login PID:", proc.pid)
pat = re.compile(r"https://liteapp\\S+")
url = None
for _ in range(15):
    time.sleep(2)
    log.flush()
    txt = open("/tmp/openclaw-login.log", encoding="utf-8", errors="replace").read()
    m = pat.search(txt)
    if m:
        url = m.group(0).rstrip(".,;")
        break
if url:
    print("QR_URL:", url)
    open("{SERVER_QR_URL_FILE}", "w").write(url)
else:
    print("NO_URL")
    print(txt[:800])
'''
        print(_server_run_b64(script, timeout=60))
    else:
        # 本地 Windows：用 Popen 后台启动，日志写文件
        log_path = os.path.join(LOCAL_STATE, "openclaw-login.log")
        os.makedirs(LOCAL_STATE, exist_ok=True)
        logf = open(log_path, "w", encoding="utf-8")
        exe = LOCAL_OPENCLAW if os.path.exists(LOCAL_OPENCLAW) else "openclaw"
        proc = subprocess.Popen(
            [exe, "channels", "login", "--channel", "openclaw-weixin", "--verbose"],
            stdout=logf, stderr=subprocess.STDOUT,
        )
        print("login PID:", proc.pid)
        # 轮询日志找链接
        import re
        url = None
        for _ in range(20):
            time.sleep(2)
            logf.flush()
            try:
                txt = open(log_path, encoding="utf-8", errors="replace").read()
            except Exception:
                txt = ""
            m = re.search(r"https://liteapp\S+", txt)
            if m:
                url = m.group(0).rstrip(".,;")
                break
        if url:
            print("QR_URL:", url)
            with open(LOCAL_QR_URL_FILE, "w", encoding="utf-8") as f:
                f.write(url)
        else:
            print("NO_URL")
            print(txt[:800])


def qr(target, out_png):
    """把最新扫码链接转成 PNG 并保存到本地。"""
    if target == "server":
        script = f'''
import qrcode
url = open("{SERVER_QR_URL_FILE}").read().strip()
qrcode.make(url).save("{SERVER_QR_PNG}")
print("QR_PNG ready")
'''
        print(_server_run_b64(script))
        b64 = _server_run(f"cat {SERVER_QR_PNG} | base64").strip()
        if b64:
            with open(out_png, "wb") as f:
                f.write(base64.b64decode(b64))
            print("saved:", out_png)
        else:
            print("download failed")
    else:
        import qrcode
        url = open(LOCAL_QR_URL_FILE, encoding="utf-8").read().strip()
        qrcode.make(url).save(out_png)
        print("saved:", out_png)


def accounts(target):
    if target == "server":
        print(_server_run(f"cat {SERVER_STATE}/openclaw-weixin/accounts.json 2>/dev/null"))
    else:
        p = os.path.join(LOCAL_STATE, "openclaw-weixin", "accounts.json")
        if os.path.exists(p):
            print(open(p, encoding="utf-8").read())
        else:
            print("(无账号文件)")


def main():
    ap = argparse.ArgumentParser(description="openclaw agent 管理（双环境）")
    ap.add_argument("cmd", nargs="?", default="list",
                    choices=["list", "add", "bind", "login", "qr", "accounts"])
    ap.add_argument("args", nargs="*", help="命令参数")
    ap.add_argument("--target", choices=["local", "server"], default="local",
                    help="local=本机(默认) server=腾讯云服务器")
    args = ap.parse_args()

    target = args.target
    if args.cmd == "list":
        list_agents(target)
    elif args.cmd == "add":
        if not args.args:
            print("用法: oc_agents.py add <name> [--target ...]")
            return
        add_agent(target, args.args[0])
    elif args.cmd == "bind":
        if len(args.args) < 2:
            print("用法: oc_agents.py bind <agent> <account> [--target ...]")
            return
        bind(target, args.args[0], args.args[1])
    elif args.cmd == "login":
        login(target)
    elif args.cmd == "qr":
        if not args.args:
            print("用法: oc_agents.py qr <out_png> [--target ...]")
            return
        qr(target, args.args[0])
    elif args.cmd == "accounts":
        accounts(target)


if __name__ == "__main__":
    main()
