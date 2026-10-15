---
name: github-upload
description: "当需要把一个本地目录/文件上传到 GitHub 仓库(建目录、提交、推送),而 git 命令推不上去(push/clone 超时、代理没运行、认证失败、没有 gh 登录)时使用。走 GitHub REST 的 Git Data API 直接造一次提交,不依赖 git 传输层;含凭据发现、中文编码处理、密钥自查与提交后回读校验。关键词:上传 GitHub、推到仓库、git push 超时、gh 未登录、代理不通、commit 到远端、把 skill 传到 github、publish to github。"
---

# github-upload

把本地目录变成 GitHub 上一次真正的提交,**不依赖 git 命令**。
适用场景:`git push` 超时 / 代理没开 / `gh` 未登录 / 只想"把这一坨文件传上去"。

## Invariants(不可协商)

1. **不打印、不落盘 token**。凭据只在本进程内存里用作 `Authorization` 头;日志里只能出现用户名。
2. **默认不覆盖别人的提交**:更新分支必须是在当前 tip 之上的快进;需要改写历史时必须显式 `-Force`。
3. **公开仓库先脱敏**:真实路径、客户名、个人信息上传前替换成示例值;无法判断时先问一句。
4. **不传密钥**:脚本会自动扫描疑似密钥(`ghp_`/`github_pat_`/`AKIA`/私钥头/长 api_key),命中即拒传,除非显式 `-AllowSecrets`。
5. **上传后必须回读校验**:比对分支 tip 的 sha 与本次提交 sha 一致,并抽查至少一个文件内容,才允许报成功。
6. **失败要说清是哪一步**:凭据、ref、blob、tree、commit、ref-update、verify 各有独立错误码,不许含糊成"失败了"。

## 状态机

```
precheck -> credential -> file_scan -> blob -> tree -> commit -> ref_update -> verify
```

| 状态 | 产物 | 失败码 |
|---|---|---|
| `precheck` | `owner/name`、本地目录、目标前缀、分支 | `BAD_ARGS` |
| `credential` | token(内存)+ `AUTH_AS` 用户名 | `NO_CREDENTIAL` |
| `file_scan` | 相对路径清单 + 体积 + 疑似密钥结论 | `SECRET_SUSPECTED` |
| `blob` / `tree` / `commit` / `ref_update` | 各步 sha | `API_ERROR` |
| `verify` | 回读 tip sha == 本次 sha | `VERIFY_FAILED` |

## 用法

```powershell
# 先干跑:只列文件与体积,不调写接口
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gh-upload.ps1 `
  -Repo "owner/name" -Source ".\my-skill" -DryRun

# 真上传
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gh-upload.ps1 `
  -Repo "owner/name" -Source ".\my-skill" -Message "添加 my-skill"
```

常用参数:`-Prefix`(仓库内目录名,默认取本地目录名)、`-Branch`(默认 `main`,必须已存在)、
`-Exclude @('samples/*')`、`-Force`(允许非快进)、`-AllowSecrets`(跳过密钥自查)。

输出(控制台只有 ASCII):

```
AUTH_AS=dawalixi1980
BASE_COMMIT=<sha>
FILE=SKILL.md BYTES=11582
...
PREFIX=my-skill FILES=22 BYTES=337920 COMMIT=<sha> URL=https://github.com/owner/name/tree/main/my-skill
```

## 通道选择(为什么不用 git)

| 通道 | 什么时候用 | 判定方法 |
|---|---|---|
| `git push` | 代理正常、有凭据 | `git -c http.proxy= -c https.proxy= ls-remote <url>` 能返回 |
| **REST Git Data API** | git 超时 / 代理没开 / 不想装 git | `Invoke-WebRequest https://api.github.com -Method Head` 返回 200 |
| `gh` CLI | 已 `gh auth login` | `gh auth status` |

三条通道的实际差别、凭据发现顺序与各种坑,见 [references/credential-transport.md](references/credential-transport.md);
API 细节(端点、载荷、限制、编码)见 [references/git-data-api.md](references/git-data-api.md)。

## 上传前必做

1. **脱敏**:公开仓库尤其严格。至少替换:本机绝对路径、客户/项目名、人名、内网地址。
2. **剔除**:`.git/`、`__pycache__/`、构建产物、真实图纸/文档样例(除非确认可公开)。
3. **干跑一次**(`-DryRun`):看清到底要传哪些文件、多大体积。
4. **确认目标位置**:仓库是"每个 skill 一个顶层目录"还是"单仓库单 skill",前缀别放错。

## 错误码

| 码 | 含义 | 处理 |
|---|---|---|
| `0` | 成功(且已回读校验) | 报告 COMMIT 与 URL |
| `2` | `BAD_ARGS` | 参数/目录/清单为空 → 修正重跑 |
| `3` | `NO_CREDENTIAL` | 按 references 里的顺序找凭据;找不到就让用户 `gh auth login` 或给 PAT |
| `4` | `API_ERROR` | 看是哪一步(ref/blob/tree/commit/ref-update),限流/权限/分支不存在各有提示 |
| `5` | `VERIFY_FAILED` | **不要报成功**;回读 tip 与文件内容,失败则如实说明 |
| `6` | `SECRET_SUSPECTED` | 要么剔除该文件,要么确认无密钥后 `-AllowSecrets` |

## 不做的事

- 不删远端文件/目录(本 skill 只做新增与覆盖,不做删除);
- 不改仓库设置、不建仓库、不改可见性(建仓库需要 `Administration` 权限,超出本 skill 职责);
- 不处理大文件(单文件 >100 MB 会被 GitHub 拒,>50 MB 会告警);
- 不把"上传成功"当成"内容正确":内容对不对由人和校验器判断。
