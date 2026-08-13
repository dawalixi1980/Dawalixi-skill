---
name: openclaw-agent-mgmt
description: 管理 openclaw 多 agent 系统（双环境通用：本机 Windows 或腾讯云服务器）：新建独立 agent（独立 workspace 文件夹）、把微信账号扫码接入并绑定给指定 agent、查看/清理 agent 与账号、导出微信登录二维码。当用户要求"新建/添加 openclaw agent"、"给某个 agent 绑定微信"、"接入新微信号"、"扫码登录微信"、"删除/清理 openclaw 账号"、"查看 agent 列表"、"给 openclaw 加人"、"独立文件夹/工作区"时触发。用 --target 指定操作环境。
---

# OpenClaw Agent 管理 Skill（双环境通用）

管理 openclaw（多 agent 机器人系统）。支持：创建隔离 agent、微信扫码接入并绑定、账号/agent 清理、二维码导出。

**双环境**：
- `--target local`（默认）：操作本机 Windows 上的 openclaw
- `--target server`：通过 SSH 操作腾讯云服务器上的 openclaw

## 一、查看现状

```bash
# 本机
python scripts/oc_agents.py list
python scripts/oc_agents.py accounts
# 服务器
python scripts/oc_agents.py list --target server
python scripts/oc_agents.py accounts --target server
```

## 二、新建独立 agent

创建独立 workspace 文件夹 + 身份文件 + 注册 agent：

```bash
# 本机
python scripts/oc_agents.py add xiaolin
# 服务器
python scripts/oc_agents.py add xiaolin --target server
```

脚本自动：
1. 创建独立工作目录（本机 `~\.openclaw\workspace-<name>\`，服务器 `/root/.openclaw/workspace-<name>/`）
2. 写入 IDENTITY.md / SOUL.md / USER.md / AGENTS.md 身份文件
3. 执行 `openclaw agents add <name> --workspace ...`

验证：`python scripts/oc_agents.py list [--target ...]`

## 三、微信扫码接入新账号

每个微信账号扫码登录（一次性，二维码约 1-2 分钟有效，需尽快扫）。

### 步骤 1：启动扫码

```bash
python scripts/oc_agents.py login [--target ...]
```

输出形如：`QR_URL: https://liteapp.weixin.qq.com/q/xxx?qrcode=yyy&bot_type=3`
扫码进程在后台运行。

### 步骤 2：生成二维码图片并保存到用户可见位置

```bash
python scripts/oc_agents.py qr "H:\用户目录\微信登录二维码.png" [--target ...]
```

依赖 python `qrcode` 库（`pip install qrcode pillow`，本机若缺先装）。

### 步骤 3：引导用户扫码

- 打开本地图片 → 手机微信「扫一扫」扫屏幕
- 或把二维码链接发给用户，手机浏览器打开
- 扫码后日志显示「已将此 OpenClaw 连接到微信」

### 步骤 4：确认新账号

```bash
python scripts/oc_agents.py accounts [--target ...]
```

新账号形如 `xxxxxxxx-im-bot`。

## 四、把微信账号绑定给 agent

```bash
python scripts/oc_agents.py bind linzong 59a50b8a6df7-im-bot [--target ...]
```

验证：`python scripts/oc_agents.py list [--target ...]`（看 Routing 行）

## 五、清理账号 / agent

### 只保留微信主账号，删除其他渠道

编辑 openclaw 配置文件（本机 `~\.openclaw\openclaw.json`，服务器 `/root/.openclaw/openclaw.json`）：
- `channels`：仅保留 `openclaw-weixin.enabled=true`，其余设 `false` 或删账号
- `plugins.entries`：仅保留 `openclaw-weixin/deepseek/browser/memory-tencentdb`，其余渠道插件设 `false`
- `accounts.json` 只留要保留的账号；删除对应账号的 `.json`/`.sync.json`/`.context-tokens.json` 文件
- 删除 `/root/.openclaw/credentials/openclaw-weixin-<acct>-allowFrom.json` 白名单（服务器）
- 清理 `bindings` 中引用已删账号的规则

### 删除整个 agent

```bash
openclaw agents delete <name> --force
```

## 六、重启与验证

```bash
# 本机（Windows，openclaw 通常前台/服务方式运行）
openclaw gateway status
# 服务器
systemctl --user restart openclaw-gateway.service
systemctl --user is-active openclaw-gateway.service
ss -tlnp | grep 18789
```

## 环境说明

| 项 | 本机 (local) | 服务器 (server) |
|----|-------------|----------------|
| openclaw 状态目录 | `~\.openclaw` | `/root/.openclaw` |
| 命令 | `openclaw`（npm 全局） | node + openclaw.mjs 绝对路径 |
| 微信账号 | `~\.openclaw\openclaw-weixin\accounts.json` | `/root/.openclaw/openclaw-weixin/accounts.json` |
| 二维码中转 | 本机 openclaw 目录 | `/tmp` |

脚本 `scripts/oc_agents.py` 已自动处理以上差异，直接用 `--target` 切换即可。

## 安全提醒

- openclaw token、SSH 凭据均为敏感信息，只在脚本内使用，不写进日志/回复。
- 删除账号/agent 是破坏性操作，操作前先备份配置文件（`openclaw.json`、`openclaw-weixin/` 目录）。
