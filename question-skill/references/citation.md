# 乐享检索与佐证规范

> 前置：乐享 MCP 已配置。未配置 → 用 `lexiang-setup`。返回 **401** → 不重试，转 `lexiang-setup` 续期。

## 一、工具清单

| 目的 | 工具 |
|---|---|
| 盘点团队 / 知识库 | `team_list_teams` · `space_list_spaces` · `space_describe_space`（取 `root_entry_id`） |
| 关键词检索 | `search_kb_search`（`keyword="…"`） |
| 语义检索 | `search_kb_embedding_search`（**`filters.keyword`**，非顶层 keyword） |
| 浏览目录 | `entry_list_children` |
| 读条目元信息 | `entry_describe_entry` |
| **读正文** | `entry_describe_ai_parse_content` |

## 二、检索流程

1. `space_list_spaces` / `team_list_teams` 定位目标库。
2. `search_kb_search` 精确关键词 → 召回后再语义检索补充。
3. `entry_list_children` 浏览目录，确保不遗漏。
4. 需要正文时 `entry_describe_ai_parse_content` 按需读取。
5. 记录**检索日期**。

## 三、链接拼接（引用出处用）

> `{domain}` 来自 `whoami()` 的 `company.company_domain`；**禁止**把 `company_from` 拼成子域名。

| domain 类型 | 格式 |
|---|---|
| 三级域名（`csig.lexiangla.com`） | `https://csig.lexiangla.com/pages/abc` |
| 顶级域名（`lexiangla.com`） | `https://lexiangla.com/pages/abc?company_from=xxx` |

`target_type` 路径：`kb_page → /pages/<id>`；`kb_file`/`kb_video → /teams/<tid>/docs/<id>`。

## 四、出处标注格式

- 乐享：**《文档名》** ＋ 链接 ＋（检索日期 `YYYY-MM-DD`）。
- 教材：**《书名》第 X 页**（章节）。
- 截图：`media/<slug>.md`。

## 五、冲突 / 降级

| 情形 | 处理 |
|---|---|
| 三方一致 | 采信，标三处出处 |
| 截图与乐享冲突 | **并列呈现 + 标注**，不擅裁 |
| 乐享无结果 | 明说"未检索到，以下基于教材/通用知识" |
| 内容可能过时 | 标检索日期，提示以最新版为准 |

## 六、下载文件归档

从乐享**下载**的知识性文件（PDF / PPT / Word / 附件…）**单独归档**，按来源库分类：

```
library/lexiang/<来源库>/<文档>.<ext>
```

- **书籍类**（整本 PDF）→ `library/books/`，**不与乐享下载、截图混放**。
- 下载后登记到 `library/源文件清单.md`。
- 生成的公式 / 函数图**不放这里**，放 `wiki/<章>/<知识点>/img/`。
