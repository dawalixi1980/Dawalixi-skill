# STATUS —— 现状(截至 2026-10-14)

## 定位

`everything-find`:一个"搜索 + 判读"skill。搜索交给本机 **Everything**(毫秒级全盘),
判读交给 **LLM**(从候选里挑出最匹配的一条),固定输出含**完整绝对路径**的 **5 选 markdown 表格**。
搜不到时按删词阶梯自行降级重搜。定位未变。

## 本轮完成的能力

| 能力 | 落地形式 |
|---|---|
| Everything 接入 | `es.exe 1.1.0.27` 走 IPC 直连正在运行的 `Everything 1.4.1.1032`,**不用开 HTTP、不用管理员、不用重启 Everything** |
| 全盘检索 | 索引覆盖 C: D: E: F: G: H: I: K: 八个 NTFS 卷 + 网络盘 `Z:\` |
| 完整路径 | `-export-csv -utf8-bom -full-path-and-name` 落盘后按 UTF-8 读,绕开控制台编码;`results[].path` 即完整绝对路径 |
| 名称检索 | 每个查询词作为**独立参数**传给 es.exe(见下方"关键修复") |
| 删词阶梯 | R0 原始 → R1 去扩展名/尾缀 → R2 去括号与编号 → R3 留最长 2 词 → R4 留最长 1 词 → R4b 前缀通配;首次命中即停,全程留痕 |
| 判读契约 | 4 档匹配度(精确/高/中/低)+ 4 条并列定序 + 固定 6 列输出表格 + "最匹配是 #N" 结论 |
| 错误码 | `NONE` / `NO_MATCH` / `AMBIGUOUS` / `TOOL_UNAVAILABLE` / `BAD_ARGS` / `QUERY_TIMEOUT` |
| 降级路径 | es.exe IPC(首选,已验证)→ Everything HTTP(已实现,**未验证**)→ `TOOL_UNAVAILABLE` |
| 可机检 | 契约校验器 + 校验器回归测试 + 搜索回归测试(6 场景 31 条断言)+ 出图回归测试 |
| **出图判读**(新增) | `dwg-shot.ps1`:无头 AutoCAD(`accoreconsole`)出**矢量 PDF → 高清 PNG**,默认 A3、2000–2500px 供视觉模型判读;`-Text` 顺带抽图名/图号/说明 |

## 文件

```
SKILL.md                     契约:Invariants / 状态机 / 查询构造 / 判定 / 阶梯 / 评分 / 输出表格 / 错误码
references/everything-syntax.md     查询语法 + es.exe 选项 + 9 条实测坑
references/ranking-rubric.md        四档定义、并列定序 4 规则、理由写法、真实实例
references/fallback-ladder.md       R1–R4 定义、留痕格式、反例
references/host-capabilities.md     三条降级路径与损失说明
scripts/ev-search.ps1               查询封装 → results.json(完整路径 + 机械预排序)
scripts/dwg-shot.ps1                dwg → 高清 PNG(accoreconsole 出 PDF + PyMuPDF 光栅化)+ 可选文字清单
scripts/pdf2png.py / png-check.py / compute-window.py / dxf-text.py    出图与抽字助手
references/dwg-shot.md              出图应答链、两种模式、分辨率建议、四个坑、局限
tests/test_dwg_shot.ps1             出图回归:宽度 / 墨量非空 / 自动选 layout / 读出图名与图号
scripts/validate_skill.py           契约校验器
tests/test_ev_search.ps1            搜索回归:精确 / 近似误匹配 / 中文 AND / 无结果 / 限目录 / 完整路径
tests/test_validate_skill.py        校验器回归(1 正例 + 4 反例)
install.ps1                         安装到 $DSH_HOME\skills\everything-find + 自检
```

## 关键修复(本轮踩到并已固化)

1. **es.exe 多词查询必须"一词一参数"**。含空格的单个参数被当成整词:
   `'AD-03' '设计图'` → 7 条正确,`'AD-03 设计图'` → **0 条**。校验器已把这条调用形态纳入回归。
2. **`-path` 只认长路径**。`$env:TEMP` 是 8.3 短路径(`C:\Users\ADMINI~1\...`),直接传给 `-path` 恒 0 命中;
   实测短 = 0、长 = 3。脚本自动用 `Get-Item` 规范化,并把原值/实际值分别写进 `path_filter_input` / `path_filter`。
3. **`path:` 运算符在本机 Everything 1.4 不生效**(恒 0),限目录一律走 es 的 `-path`。
4. **`es.exe` 命中 0 条时退出码仍为 0** → 判定命中数不能看退出码。
5. **.ps1 文件必须带 UTF-8 BOM**:PowerShell 5.1 把无 BOM 脚本按 ANSI 读,中文注释会拆坏语法(本轮真实踩过,报"Missing ] at end of attribute")。
6. **控制台中文不可靠**:脚本改为把 JSON 写成 UTF-8 文件 + 控制台只回一行纯 ASCII 摘要。
7. **函数过滤器会污染匹配度(实测暴露并已修)**:`-Ext pdf` 会把 `ext:pdf` 当成一个"名称词"参与
   `coverage` / `exact_name`,导致 `exact_name` 永远为 false、coverage 永远被扣(实测 0.667)。
   现在新增 `name_query`(剔除 `ext:/size:/dm:/path:` 等过滤器)专供匹配度计算,`effective_query` 仍记录完整查询。
8. **`python unittest` 的 stderr 在 `$ErrorActionPreference='Stop'` 下会被当成终止性错误**,
   `install.ps1` 已用 `Invoke-Capture` 包住。
9. **名称变体命中不了,必须靠"目录枚举"(实测新增 R5)**:用户给「**安**马屯」「崆**垌**」,
   文件名是「**马**安屯」「崆**峒**」(语序颠倒 + 异体字),按名字搜恒 0;改用
   `-Query 'ext:pdf' -Path '<可疑目录>'` 枚举目录,一次命中
   `Z:\…\方案设计（评审后最新版）\河西街道（6.0m路面宽）\PDF\…（崆峒村委会）.pdf`(18.79 MB)。
   已把 R5-目录枚举和「名称变体」对照表写进 `references/fallback-ladder.md`,SKILL.md 判定段同步。

## 验证结果(真实输出,非"应该能过")

```
$ python scripts/validate_skill.py
PASS 契约校验通过                                        (exit=0)

$ python tests/test_validate_skill.py
Ran 5 tests in 0.430s ... OK                              (exit=0)
  test_real_skill_passes / test_missing_section_detected / test_dangling_reference_detected
  / test_missing_bom_detected / test_multi_term_single_arg_detected

$ powershell -File tests\test_ev_search.ps1
fixture dir: C:\Users\Administrator\AppData\Local\Temp\everything-find-tests
case1..case6 全 PASS,ALL TESTS PASSED                      (exit=0)
```

真实检索样例:`-Query 'AD-03 一般路基设计图' -Ladder` → `used_round=0 HITS=7`,7 条候选全含完整路径,
其中 5 条是真正的 `.dwg`/`.pdf`,另 2 条是 Temp 里的 `.bak` 与 4 KB 的转换残件。

```
$ powershell -File install.ps1
[validate] PASS 契约校验通过
[validator-test] Ran 5 tests ... OK
[search-test] ALL TESTS PASSED
INSTALL OK
skill dir : C:\Users\Administrator\.dsh\skills\everything-find
es.exe    : C:\Program Files\Everything\es.exe        (exit=0)
```

**安装已实测生效**:装完后 DSH **当场**刷新了技能目录,`everything-find` 已出现在本会话的可用技能清单里,
不需要重启后端。

## 仍未完成 / 已知限制

- **HTTP 降级路径未验证**:本机 `C:\Program Files\Everything\Everything.ini` 里 `allow_http_server=0`,
  且用户配置的 8017 端口因实例未重启也未生效。`-Transport http` 的代码已写,但按"未 run 不得声称 pass"记为 **unrun**。
- 网络盘 `Z:\` 靠文件夹索引,新增文件有延迟;`-Path Z:\...` 的限目录匹配同样只认长路径。
- 只读:不打开/移动/改名/删除;不读文件内容、不做 OCR。
- `install.ps1` 里 `python unittest` 的 stderr 日志在 `$ErrorActionPreference='Stop'` 下会被 PowerShell
  当成终止性错误,已用 `Invoke-Capture`(临时降级为 Continue)包住——这是本轮踩到的第 7 个坑。

## 出图判读(dwg-shot,2026-10-14 新增)

**能力**:给一个 dwg → 出一张高清 PNG;不需要人开 CAD、不弹窗、不碰用户正开着的图纸。

**原理**:`accoreconsole.exe`(AutoCAD 无界面引擎,同一套字体,SHX 汉字保真)按脚本 `-PLOT` 出**矢量 PDF**,
再用 PyMuPDF **按目标像素宽度**光栅化 —— "高清"只是 `-Width` 一个参数。

**auto 模式**:先按**布局**出图(真实交付图的 A3 图框/标题栏/图名图号都在布局里);
若该页墨量 < 0.2%(空页)则回退**模型空间 + 自动窗口**(`compute-window.py` 迭代剔除游离图签)。

**实测(AD-03 一般路基设计图,450 KB,单张 11 秒)**:

| 出图方式 | 墨量 | 判读效果 |
|---|---|---|
| **布局 + A3 2400px** | **2.12%** | 图名「路基一般设计图」、图号「AD-03」、土基压实度表(表头+数值)、四条说明、尺寸与构件名全部清晰 ← **首选** |
| 模型空间 + 范围(Extents) | 0.74% | 有字但很小(游离图签把主体缩没了) |
| 模型空间 + 自动窗口 | 0.59% | 剔掉了游离文字,但该图模型里两张断面本来相距很远 → 中间大片空白 |

**新增四个坑(已固化进代码与校验器)**:

10. **dwg 路径含中文 → accoreconsole 挂死**(无输出、不退出,实测挂了 4 分钟)→ 一律先复制到 ASCII 临时路径。
11. **`-PLOT` 应答链步数随空间不同**(图纸空间/模型空间),多一个或少一个空行就会把答案错位到「输入文件名」提示上,然后**永远等你输入** → 两条链在 `New-PlotScript` 里写死。
12. **中文版提示带英文键**(`[是(Y)/否(N)]`)→ 答 `Y/N/M/L/E/F/C/W` 即可,不需要中文输入法。
13. **生成 .scr 必须 ANSI(GBK)编码**(纸名里有"毫米"、布局名里有"模型"),而 `dwg-shot.ps1` 自身必须 UTF-8 BOM。

**验证结果(真实输出)**:

```
$ python scripts/validate_skill.py            -> PASS 契约校验通过            (exit=0)
$ python tests/test_validate_skill.py         -> Ran 5 tests ... OK            (exit=0)
$ powershell -File tests\test_dwg_shot.ps1    -> ALL TESTS PASSED              (exit=0)
     case1 运行:exit 0 / <180s   case2 画质:PNG 宽=2000 / INK 2.116% / MODE=layout
     case3 文字:含「路基一般设计图」与「AD-03」
$ powershell -File tests\test_ev_search.ps1   -> ALL TESTS PASSED              (exit=0)
```

**局限**:依赖本机装 AutoCAD(2022);一个布局一张图(多布局需 `-LayoutName` 逐张跑);
缺失的外部参照(图框)不会补上;不判断图纸内容含义——"对不对"由 LLM/视觉判读。
要彻底脱离 AutoCAD,可换开源渲染器([go-cad](https://github.com/unitedrhino/go-cad) / [cad2x-converter](https://github.com/orcastor/cad2x-converter)),中文 SHX 渲染质量待实测。

## 下一步优先级

1. **多布局图纸**:目前只出默认布局;需要时加 `-AllLayouts`(逐布局出图 + 页码)。
2. **批量出图**:一次 accoreconsole 循环 `OPEN`+`PLOT` 多张,或走 `PUBLISH` + DSD 出图集,摊薄启动开销。
3. **内容索引**:对一批 dwg 批量 `dxf-text.py` 建本地索引,实现"搜『沉沙井』→ 哪些 dwg 含这个词"(Everything 1.4 无 `content:`)。
4. (可选)若要 HTTP 降级:改 `allow_http_server=1` 并重启 Everything,把 unrun 转成 pass。
5. (可选)**脱离 AutoCAD**:实测 [go-cad](https://github.com/unitedrhino/go-cad) / [cad2x-converter](https://github.com/orcastor/cad2x-converter) 的中文渲染,与本方案横向对比。
