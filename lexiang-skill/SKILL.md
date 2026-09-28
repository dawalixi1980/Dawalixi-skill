---
name: lexiang-skill
description: 乐享（Lexiang）AI 知识库 MCP 技能包。统一封装配置、搜索（含向量语义检索）、文档写入、Block 编辑、文件上传下载、外部数据源导入六大模块。当用户提到「乐享」「lexiang」「知识库」并涉及：配置连接、搜索/查找/语义检索文档、创建或写入文档、编辑页面 Block、上传下载文件、导入腾讯会议录制或 iWiki 文档时使用。也适用于用户给出 lexiangla.com 链接需要读取或写入的场景。
---

# lexiang-skill — 乐享 AI 知识库 MCP 技能包

把乐享官方发布的 6 个 MCP skill 整合为一个可移植的技能包，并补充官方安装器未覆盖的
**preset 工具集机制**、**不依赖客户端 MCP 集成的直连方式**与**目录落位注意事项**。

---

## 一、这是什么

乐享（Lexiang，腾讯旗下）是团队知识库产品，官方提供 MCP 服务
`https://mcp.lexiang-app.com/mcp`，通过 **Bearer Token 静态鉴权**暴露知识库读写能力。

本技能包把官方 6 个 skill 收拢为模块：

| 模块 | 目录 | 能力 |
|---|---|---|
| 配置向导 | `setup/` | 首次配置、Token 续期、连接验证、故障排查 |
| 搜索阅读 | `search/` | 关键词检索、**向量语义检索**、知识库浏览、目录导航、文档读取 |
| 文档写入 | `writer/` | Markdown/HTML 导入、创建页面与文件夹、公众号收藏 |
| Block 编辑 | `blocks/` | Block 创建/更新/删除/移动、批量编辑、Markdown 转 Block |
| 文件管理 | `files/` | 三步上传、文件详情、下载、文件夹同步 |
| 连接器 | `connectors/` | 腾讯会议录制导入、iWiki 文档迁移 |

各模块详细用法见其目录下的 `SKILL.md` 与 `references/`。

---

## 二、MCP 配置（核心）

### 配置模板

见 `mcp.json`：

```json
{
  "mcpServers": {
    "lexiang": {
      "enabled": true,
      "url": "https://mcp.lexiang-app.com/mcp?preset=knowledge&company_from=<COMPANY_FROM>",
      "transportType": "streamable-http",
      "headers": {
        "Authorization": "Bearer <LEXIANG_TOKEN>"
      }
    }
  }
}
```

参数获取：登录 https://lexiangla.com/mcp 查看 `COMPANY_FROM` 与 `LEXIANG_TOKEN`（`lxmcp_` 开头）。

### 各客户端落位

| 客户端 | 配置文件 |
|---|---|
| 通用（mcporter） | `~/.mcporter/mcporter.json` |
| WorkBuddy | `~/.workbuddy/mcp.json` |
| OpenClaw | `~/.openclaw/config/mcporter.json` |
| **opencode** | `~/.config/opencode/opencode.jsonc` 的 `mcp` 字段（格式见下） |

opencode 用的是自己的 schema，**不是** `mcpServers` 包装：

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "lexiang": {
      "type": "remote",
      "url": "https://mcp.lexiang-app.com/mcp?preset=knowledge&company_from=<COMPANY_FROM>",
      "enabled": true,
      "headers": { "Authorization": "Bearer <LEXIANG_TOKEN>" }
    }
  }
}
```

> ⚠️ **鉴权方式**：乐享 MCP 使用 Bearer Token 静态鉴权，**不涉及 OAuth**。
> Agent 不要尝试发起 OAuth 授权、打开授权页或等待回调；token 无效时唯一做法是引导用户到
> `https://lexiangla.com/mcp` 续期。

---

## 三、preset 参数（官方安装器未文档化的关键机制）

MCP URL 上的 **`preset` 查询参数决定开放哪一组工具**。不传时只开放 7 个「元工具」，
导致调用 `team_list_teams`、`space_list_spaces` 等会返回 `tool is not allowed`。

实测对照（同一 token）：

| preset | 工具数 | 典型工具 |
|---|---|---|
| 不传 / `meta` / `connector` | 7 | `whoami`、`lexiang_search`、`lexiang_fetch`、`call_tool`、`get_tool_schema`、`search_tools`、`list_tool_categories` |
| `search` | 9 | 上述 + **`search_kb_search`**（关键词）、**`search_kb_embedding_search`**（向量） |
| `knowledge` | **79** | 上述 + `team_*`、`space_*`、`entry_*`、`block_*`、`file_*`、`smartsheet_*`、`comment_*`、`translation_*` 等全量管理能力 |

选择建议：

- **只做检索** → `preset=search`（上下文开销最小）
- **要用写入/编辑/上传**（本包 writer/blocks/files 模块）→ `preset=knowledge`
- **79 个工具会显著占用上下文**。若客户端支持按需启停 MCP，建议平时用 `search`，
  需要写文档时再切 `knowledge`。

---

## 四、直连方式（不依赖客户端 MCP 集成）

当客户端还没接好 MCP、或需要在脚本/CI 里调用时，可直接用 HTTP 调 MCP（streamable-http）。
本包提供助手脚本：

```bash
# 凭据来源优先级：环境变量 > ~/.config/lexiang/config.json
export COMPANY_FROM=xxx
export LEXIANG_TOKEN=lxmcp_xxx

python scripts/lexiang_mcp.py whoami
python scripts/lexiang_mcp.py teams
python scripts/lexiang_mcp.py spaces --team <team_id>
python scripts/lexiang_mcp.py search 投标 --type all          # 关键词检索
python scripts/lexiang_mcp.py vsearch "技术方案与项目经验" --limit 5   # 向量语义检索
python scripts/lexiang_mcp.py tools --preset knowledge         # 列出工具
python scripts/lexiang_mcp.py call space_list_spaces --args '{"team_id":"xxx"}'
```

协议要点：

- `POST` 到 MCP URL，头带 `Authorization: Bearer <token>`、
  `Accept: application/json, text/event-stream`
- 先 `initialize`，再发 `notifications/initialized`，然后 `tools/list` / `tools/call`
- 响应可能是 **SSE 包装**（`data: {...}`），解析时需兼容

---

## 五、安装落位注意事项

官方安装器 `npx @lexiang/skills install --target opencode` 会把 skill 放到
`~/.opencode/skills/`，但 **opencode 实际只扫描**：

```
.opencode/skills/<name>/SKILL.md          （项目级）
~/.config/opencode/skills/<name>/SKILL.md （全局，最常用）
.claude/skills/  ~/.claude/skills/
.agents/skills/  ~/.agents/skills/
```

**`~/.opencode/skills/` 不在其中**。装完请把目录移动到 `~/.config/opencode/skills/`，
否则技能不会被发现。安装后需重启客户端。

---

## 六、快速上手

1. 取凭据：https://lexiangla.com/mcp
2. 写配置：按上文对应客户端格式填入 `company_from` 与 token
3. 验证：调用 `whoami`，成功返回用户与组织信息即通
4. 检索：`search_kb_search`（关键词）/ `search_kb_embedding_search`（向量）
5. 遇到 401 → 引导用户到 `https://lexiangla.com/mcp?company_from=<值>` 点「续期」，
   **无需重新配置 token**

---

## 七、故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `tool is not allowed: xxx` | URL 未带 `preset` | 加 `?preset=knowledge`（或 `search`） |
| 401 未授权 | token 过期或租户不匹配 | 引导续期；确认 `company_from` 与 token 同租户 |
| 技能不出现 | 装错目录 | 移到 `~/.config/opencode/skills/` 并重启 |
| 连接无响应 | URL 缺 `company_from` | 补全查询参数 |
| 参数报错 | 工具签名变更 | 先 `get_tool_schema(tool_name=...)` 再调用 |

---

## 八、相关链接

- 获取配置：https://lexiangla.com/mcp
- 乐享平台：https://lexiangla.com
- MCP 协议：https://modelcontextprotocol.io
- opencode 技能目录规范：https://opencode.ai/docs/skills/
