# everything-find

用本机 **Everything** 索引按名称找文件,输出**含完整路径**的候选,并固定给出 **5 选 markdown 表格** + **最匹配结论**。搜索无结果时按删词阶梯自动降级重搜。

定位:一个"搜索 + 判读"skill。搜索交给 Everything(毫秒级全盘),判读交给 LLM(哪个才是最匹配的那一份)。

## 包含内容

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 核心契约:Invariants、状态机、查询构造、判定分档、删词阶梯、评分档位、**固定输出表格**、错误码 |
| `references/everything-syntax.md` | Everything 查询语法 + es.exe 选项 + 实测踩坑 |
| `references/ranking-rubric.md` | 四档匹配度定义、并列定序 4 规则、理由写法、真实实例 |
| `references/fallback-ladder.md` | 删词阶梯 R1–R4 定义、留痕格式、反例 |
| `references/host-capabilities.md` | es.exe / HTTP / 都不可用 三条降级路径与损失说明 |
| `references/dwg-shot.md` | 无头 AutoCAD 出图:应答链、两种模式、分辨率、四个坑、局限 |
| `scripts/ev-search.ps1` | 查询封装:输出 `results.json`(完整路径 + 机械预排序),控制台只回 ASCII 摘要 |
| `scripts/dwg-shot.ps1` | dwg → 高清 PNG(+可选文字清单):accoreconsole 出 PDF → PyMuPDF 光栅化 |
| `scripts/pdf2png.py` | 矢量 PDF → PNG,按目标像素宽度反算缩放 |
| `scripts/png-check.py` | 量尺寸与墨量,用于判定"空页" |
| `scripts/compute-window.py` | 从 DXF 算"只包住主体"的打印窗口(迭代剔除游离图签) |
| `scripts/dxf-text.py` | 抽全图文字(图名/图号/说明/表格/图层名) |
| `scripts/validate_skill.py` | 契约校验器:frontmatter、必需章节、引用文件、表格列、枚举、BOM、遗留占位符 |
| `tests/test_ev_search.ps1` | 搜索回归测试:精确命中 / 近似误匹配 / 中文 / 无结果 / 路径限定 / 完整路径不变式 |
| `tests/test_dwg_shot.ps1` | 出图回归测试:宽度 / 墨量非空 / 自动选到 layout / 文字里读出图名与图号 |
| `tests/test_validate_skill.py` | 校验器自身回归测试(正常 skill 通过、人为破坏被抓出) |
| `install.ps1` | 安装到 `%DSH_HOME%\skills\everything-find`(拷贝) + 自检;`-Remove` 卸载 |

## 用一次

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\ev-search.ps1 -Query "AD-03 一般路基设计图" -Ladder
# -> SCHEMA=... TRANSPORT=es USED_ROUND=2 HITS=12 RETURNED=12 JSON=<path> ERROR=NONE
```

然后用任意工具读 `JSON=` 指向的文件;`results[].path` 就是必须交付的完整路径。

## 出图看图纸对不对(无头 AutoCAD)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\dwg-shot.ps1 `
  -Path "H:\...\AD-03 一般路基设计图.dwg" -Text -Width 2400
# -> FILE=dwg001 SRC=AD-03 一般路基设计图.dwg MODE=layout W=2400 H=1697 INK=2.116 PNG=<path> SECS=11 STATUS=OK
# -> MANIFEST=<OutDir>\manifest.json FILES=1 FAILED=0
```

- **不用人开 CAD**:`accoreconsole.exe` 是 AutoCAD 的无界面引擎,同一套字体(SHX 汉字保真);单张约 11 秒
- **高清靠矢量**:出矢量 PDF 再按 `-Width` 光栅化,2000–2500px 足够视觉模型判读
- **auto 模式**:先按布局出图(图框/标题栏都在布局里),空页则回退模型空间 + 自动窗口
- `-Text` 顺带抽出图名/图号/说明 → 判断"是不是这张图"最便宜的判据
- 细节见 [references/dwg-shot.md](references/dwg-shot.md)

## 验证

```powershell
python scripts\validate_skill.py                        # 契约校验
powershell -NoProfile -File tests\test_ev_search.ps1     # 搜索回归(自建夹具)
powershell -NoProfile -File tests\test_dwg_shot.ps1      # 出图回归(用仓库里的 AD-03)
python tests\test_validate_skill.py                      # 校验器回归
```

## 已知限制

- 只覆盖 Everything 已索引的卷(C: D: E: F: G: H: I: K: + 网络盘 Z:);网络盘新增文件有延迟。
- HTTP 降级路径已实现但**未验证**(本机 `allow_http_server=0`)。
- 不读文件内容,不判断图纸内容是否正确;不改动任何文件。
- 依赖 Everything 1.4 的 IPC;升级到 1.5 后需重测(es.exe 与本体版本要匹配)。

## 边界(非目标)

不做文件管理(移动/改名/删除)、不做内容检索(OCR/看图的活)、不做多机/云盘联合检索。
