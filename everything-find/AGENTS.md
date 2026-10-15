# Agent 协作说明(everything-find)

## 每次迭代必须更新现状

对本目录做一轮有意义的迭代后——包括修改 `SKILL.md` 契约、references、`ev-search.ps1`、
校验器、测试、安装方式或仓库结构——必须同步更新根目录 [STATUS.md](./STATUS.md):

- 项目定位是否变化
- 本轮完成的能力与文件变更
- 仍未完成的事项与已知限制
- 校验器与测试的最新结果(贴真实输出结论,不是"应该能过")
- 下一步优先级是否调整

不要只记代码变更,也要记**契约行为、输出表格格式、删词阶梯规则、错误码、降级路径**的变化。

## 完成前的检查清单

1. 读 [TARGET.md](./TARGET.md),确认改动仍在目标与边界内。
2. `python scripts/validate_skill.py`
3. `python tests/test_validate_skill.py`
4. `powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_ev_search.ps1`
5. 需要装到 DSH 时:`powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1`
6. 交付说明里报告第 2–4 步的真实结果 + STATUS.md 是否已同步。

## 硬约束(违反即视为回归)

- **.ps1 文件必须带 UTF-8 BOM**。Windows PowerShell 5.1 会把无 BOM 的脚本按 ANSI(GBK)读,
  中文注释会拆坏语法。校验器会检查这一条。
- **es.exe 的每个查询词必须是独立参数**。含空格的单个参数会被当成一个整词(实测多词查询 0 命中);
  校验器会检查 `ev-search.ps1` 里这条调用形态是否还在。
- **交付路径必须是完整绝对路径**,不得拼接或缩写;`tests/test_ev_search.ps1` 的场景 6 会守这条不变式。
- **无结果不许编造**。零命中就是 `NO_MATCH`,阶梯跑完仍零命中必须如实上报。

## 范围边界

这是一个"搜索 + 判读"skill:搜索交给本机 Everything,判读交给 LLM。
除非用户明确要求,不要把它扩成文件管理器(移动/改名/删除)、内容检索(OCR/看图)或多机索引系统。
