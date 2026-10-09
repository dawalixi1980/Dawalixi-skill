---
name: obsidian-vault
description: 打开本地文件夹为 Obsidian 仓库，或为 OpenCode 桌面版项目；并一键装好全局命令与官方 CLI。当用户说「obskill」「打开ob」「打开 obsidian」「用 obsidian 打开这个文件夹」「obsidian仓库」「oc」「用 opencode 桌面版打开这个文件夹」「打开 opencode」时使用。功能：①装官方 Obsidian CLI ②装终端命令 ob（任意文件夹敲 ob 即用 Obsidian 打开当前文件夹）③装终端命令 oc（任意文件夹敲 oc 即用 OpenCode 桌面版打开当前文件夹）④skill 直接执行打开（无需敲终端、不生成多余文件）。
---

# obsidian-vault

四个功能：

1. **装官方 Obsidian CLI**：把 Obsidian 安装目录加进 PATH，终端可用 `obsidian`。
2. **装终端命令 `ob`**：任意文件夹敲 `ob` → 用 Obsidian 打开**当前文件夹**为仓库（`ob <文件夹>` 指定）。
3. **装终端命令 `oc`**：任意文件夹敲 `oc` → 用 **OpenCode 桌面版**打开**当前文件夹**为项目（`oc <文件夹>` 指定）。
4. **skill 直接打开**：用户说「obskill / 打开ob」→ 开 Obsidian；说「打开opencode / oc」→ 开 OpenCode 桌面版。不生成多余文件。

## 给 Agent 的执行规则

- 用户说 **「obskill」「打开ob」「打开 obsidian」** → 运行：
  ```bash
  python "<skill>/scripts/ob.py" "<目标文件夹>"
  ```
- 用户说 **「oc」「打开 opencode」「用 opencode 打开这个文件夹」** → 运行：
  ```bash
  python "<skill>/scripts/oc.py" "<目标文件夹>"
  ```
- 目标文件夹 = 用户所指的文件夹；不指定时默认用**当前工作目录**。
- 安装（装 CLI / ob / oc）→ `python "<skill>/scripts/install_ob.py"`。
- 回报：做了什么、打开了哪个路径。

## 文件（都在 scripts/）
| 文件 | 作用 |
|---|---|
| `ob.py` / `ob.cmd` | Obsidian 打开器 + 终端命令 |
| `oc.py` / `oc.cmd` | OpenCode 桌面版打开器 + 终端命令 |
| `install_ob.py` | 装 CLI + 全局命令（ob/oc） |

**不生成多余文件**：安装只把脚本放到 `%USERPROFILE%\.ob` 并加 PATH；目标文件夹只按需建 `.obsidian`。

## 各自原理
- **ob**：官方 CLI（`obsidian eval` + `vault-open`）优先；否则登记 + `obsidian://open?vault=<id>`（必要时重启 Obsidian）。
- **oc**：发深链 `opencode://open-project?directory=<URL 编码路径>`（桌面版已注册 `opencode://` 协议）。

## 一次性开关（无法脚本化）
Obsidian 的 `设置 → 通用 → 高级 → 命令行界面` 是 GUI 开关，脚本不能代开。开了 `ob` 用 CLI 秒开；不开走协议兜底。

## 命令
```bash
ob / oc                # 打开当前文件夹（Obsidian / OpenCode 桌面版）
ob <文件夹> / oc <文件夹>
ob --dry-run / oc --dry-run
```

## 排障
| 现象 | 处理 |
|---|---|
| `ob`/`oc` 不是内部或外部命令 | 新开终端（PATH 需重载） |
| oc 没反应 | 确认已装 OpenCode 桌面版（协议已注册）；`oc --dry-run` 看深链 |
| 打开的是上一个 Obsidian 仓库 | 走协议兜底；开 CLI 开关后可无重启切换 |

## 本机现状
- 命令目录：`C:\Users\Administrator\.ob`（已加 PATH）
- Obsidian：`E:\Obsidian`（已加 PATH，CLI 已启用）
- OpenCode 桌面版：`%LOCALAPPDATA%\Programs\@opencode-aidesktop\OpenCode.exe`（`opencode://` 协议已注册）
