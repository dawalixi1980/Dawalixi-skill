# Everything 查询语法 与 es.exe 实测要点

搜索语法由 Everything 本体解释,`es.exe` 只是 IPC 客户端;**两者版本对应关系**:本机实测 `es.exe 1.1.0.27` ↔ `Everything 1.4.1.1032`。

## 1. 查询运算符

| 写法 | 含义 | 注意 |
|---|---|---|
| `甲 乙` | AND(默认) | 空格分隔即"全都要有";词越多越窄 |
| `甲 \| 乙` | OR | `\|` 需转义,引号包住整串亦可 |
| `!甲` | NOT | 排除 |
| `甲*` / `?` | 通配 | `*` 任意长度,`?` 单字符 |
| `ext:dwg;pdf` | 扩展名 | 分号 = 或;`;` 前不能有空格 |
| `path:H:\图纸` | 路径包含 | ⚠️ **本机 1.4 实测不生效(恒 0)**,限目录请用 es 的 `-path <dir>` |
| `parent:"H:\图纸\子目录"` | 直接父目录 | 只匹配该目录的直属文件 |
| `size:>10mb` / `size:1mb..5mb` | 大小 | 支持 `> >= < <=` 与区间 |
| `dm:2024` / `dm:today` / `dm:2024-07-03` | 修改时间 | `dc:` 创建,`da:` 访问,`rc:` 最近变化 |
| `rc:>100` | 运行次数 | Everything 自己统计的"打开过几次" |
| `regex:` 前缀 或 `-r` | 正则 | 正则模式会禁用其他运算符的常规解析,慎用 |
| `case:` / `-i` | 区分大小写 | 中文无效,英文名有用 |

## 2. es.exe 常用选项(全部实测过)

| 选项 | 作用 |
|---|---|
| `-full-path-and-name` | **输出完整路径**(本 skill 的硬要求) |
| `-no-header` | 不打表头 |
| `-n <num>` | 限制返回条数(**必须给**,否则会吐上万行) |
| `-size` / `-dm` / `-ext` / `-dc` / `-rc` | 附加列:大小 / 修改时间 / 扩展名 / 创建时间 / 运行次数 |
| `-csv` / `-tsv` / `-efu` | 控制台输出格式;`-export-csv <文件>` 直接落盘 |
| `-utf8-bom` | 导出文件写 UTF-8 BOM → **中文唯一的稳路** |
| `-get-result-count` | 只打印命中总数(用于判定阶梯是否命中) |
| `-get-total-size` | 命中总大小 |
| `-p` / `-match-path` | 查询串匹配完整路径(不是只匹配文件名) |
| `-r` / `-regex` | 正则 |
| `-parent <dir>` / `-path <dir>` | 限定父目录 / 限定目录树(等价于 `parent:` / `path:`) |
| `-sort <name\|size\|date-modified\|…>[-ascending\|-descending]` | 排序;`-s` 等价按完整路径排 |
| `-instance <name>` | 多实例时指定实例 |
| `-timeout <ms>` | 索引未加载完时的等待上限 |
| `-no-result-error` | 无结果时返回非 0 错误码 |
| `-version` / `-get-everything-version` | 客户端 / 本体版本 |
| `-exit` / `-save-db` / `-reindex` | 退出本体 / 存库 / 重建索引(破坏性,不要随手用) |

## 3. 实测踩过的坑(务必照着做)

0. **多词查询必须「一词一参数」**(最坑的一条,差点毁掉整个 skill)。含空格的**单个**参数会被 es.exe 当成一个整词,多词查询几乎全部 0 命中:

   | 调用 | 结果 |
   |---|---|
   | `es.exe -get-result-count 'AD-03' '设计图'` | **7**(正确) |
   | `es.exe -get-result-count 'AD-03 设计图'` | **0**(错!) |
   | `es.exe -get-result-count 'ext:dwg' '路基'` | **11343**(正确) |
   | `es.exe -get-result-count 'ext:dwg 路基'` | **0**(错!) |

   推论:凡是"看起来没搜到"的多词查询,先怀疑是不是被当成了一个整词,而不是先改词。脚本 `ev-search.ps1` 已把每个词拆成独立参数,`validate_skill.py` 会对这条规则做回归校验。
1. **中文乱码**:`es.exe` 往控制台写的是系统 ANSI(本机 936)。在 PowerShell 里直接 `& es.exe …` 再打印,中文会烂。
   → **正解**:`-export-csv <文件> -utf8-bom`,然后用 `Import-Csv -Encoding UTF8` 读文件。脚本已这么做,控制台只回 ASCII 摘要。
2. **`-path` 只认长路径**。`$env:TEMP` 这类 8.3 短路径(`C:\Users\ADMINI~1\...`)传进去**恒 0 命中**,必须换成 Everything 索引里存的长路径:
   ```powershell
   $dir = (Get-Item -LiteralPath $dir).FullName   # 短 → 长
   es.exe -get-result-count -path $dir 'EVFND'    # 长:3 条;短:0 条(实测)
   ```
   `ev-search.ps1 -Path` 已自动做这步规范化,并把规范化后的值写进 JSON 的 `path_filter`(原始输入在 `path_filter_input`)。
3. **命中 0 条时退出码仍是 0**(实测 `hits=0` → `exit=0`)。
   → 判"有没有搜到"必须看 `-get-result-count` 的数字或结果行数,**不能看退出码**;需要非 0 就加 `-no-result-error`。
4. **不加 `-n` 会全量输出**。本机 `ext:dwg 路基` 命中 11342 条 → 必须限量。
5. **中文查询参数没问题**:PS 5.1 把参数按 ANSI 码页传给 `es.exe`,实测 `路基`、`AD-03` 都能正确命中(前提是按第 0 条拆成独立参数),不需要额外转码。
6. **空查询 = 返回全盘一切**,是灾难。任何一轮阶梯结果为空串时必须跳过,不许执行。
7. **索引范围**:`-get-result-count` 只反映已建索引的卷。本机为 C: D: E: F: G: H: I: K: 八个 NTFS 卷 + `Z:\`(网络盘,靠"文件夹索引"方式加入,更新有延迟)。
8. **新文件有延迟**:Everything 靠 USN 变更日志增量更新(本机 `monitor_update_delay=1000`ms),新建文件后约 1–2 秒才可搜到;测试脚本必须轮询等待,不能写完立刻断言。
9. **HTTP 服务默认是关的**(本机 `allow_http_server=0` 机器级策略 + 用户配置未生效)。所以首选始终是 es.exe IPC,HTTP 只是降级路径。
