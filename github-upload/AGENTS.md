# Agent 协作说明(github-upload)

## 每次迭代必须更新现状

对本目录做一轮有意义的迭代后(改契约、references、`gh-upload.ps1`、校验器、测试)必须同步更新 [STATUS.md](./STATUS.md):
项目定位、本轮能力与文件变更、未完成项与限制、校验器与测试的**真实结果**、下一步优先级。
纯格式化/临时调试可以不改正文,但要确认现状仍准确。

## 完成前检查清单

1. 读 [TARGET.md](./TARGET.md),确认改动仍在目标与边界内;
2. `python scripts/validate_skill.py`
3. `python tests/test_validate_skill.py`
4. `powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_gh_upload.ps1`
5. 真上传验证(可选,会写远端):对一个**自己的测试仓库**跑一次,确认 `COMMIT=` 与回读一致;
6. 交付说明里报告第 2–4 步的真实结果 + STATUS.md 是否已同步。

## 硬约束(违反即视为回归)

- **token 永不落盘/永不打印**:只能作为 `Authorization` 请求头;日志里只允许出现用户名。
- **默认不做非快进更新**:改写分支必须显式 `-Force`。
- **上传前必须密钥自查**;命中即拒传,除非显式 `-AllowSecrets`。
- **上传后必须回读校验**;回读不一致时报 `VERIFY_FAILED`,不许报成功。
- **.ps1 必须 UTF-8 with BOM**;`gh-upload.ps1` 必须保留 `Esc-Ascii` 转义路径。
- **公开仓库先脱敏**:真实路径/客户名/人名;不确定就先问。

## 范围边界

这是一个"通道不通时的备用上传路径",不是 git 的替代品。
除非用户明确要求,不要把它扩成仓库管理平台(建仓/删仓/权限/成员/PR 流程)。
