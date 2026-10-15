# 凭据发现 与 传输通道

## 1. 凭据发现顺序(按成本从低到高)

| 顺序 | 来源 | 命令/位置 | 说明 |
|---|---|---|---|
| 1 | 环境变量 | `$env:GH_TOKEN` / `$env:GITHUB_TOKEN` | 有就直接用;**不要**打印 |
| 2 | gh CLI | `gh auth token` | 需要事先 `gh auth login`;本机常见状态是**未登录** |
| 3 | git 凭据助手 | `git credential fill` | 走 Windows 凭据管理器 / GCM,**本机实测有货** |
| 4 | 让用户提供 | 用户粘贴 PAT | 最后手段;要求最小 scope |

### 第 3 条怎么用(本机实测有效)

```powershell
$env:GIT_TERMINAL_PROMPT = '0'          # 禁止 git 自己弹交互
$cred = 'protocol=https
host=github.com

' | git credential fill 2>$null
$token = (@($cred | Where-Object { $_ -like 'password=*' })[0]) -replace '^password=',''
```

- 返回 `username=dawalixi1980` + `password=<40 位串>`(PAT/OAuth token)。
- **只打印用户名**;长度可以打印用于确认拿到了东西,token 本身任何日志里都不许出现。
- 潜在风险:凭据助手可能弹 GUI 授权窗 → 用 `Start-Job` + `Wait-Job -Timeout 45` 兜底,超时就放弃这条路。
- 本机凭据管理器的条目名形如:`LegacyGeneric:target=git:https://dawalixi1980@github.com`(可用 `cmdkey /list` 看到存在性,但**取不到明文**,明文要经 git credential fill)。

## 2. 传输通道判定

| 通道 | 判定命令 | 通了的样子 |
|---|---|---|
| git | `git -c http.proxy= -c https.proxy= ls-remote --heads <url>` | 打印 `refs/heads/main` |
| REST API | `Invoke-WebRequest https://api.github.com -Method Head` | HTTP 200 |
| gh | `gh auth status` | `Logged in to github.com as ...` |

**关键经验:git 与 .NET 走的是不同的网络栈。** 本机实测:

```
git    : fatal: Failed to connect to github.com:443 after 21694 ms   ← libcurl,超时
.NET   : Invoke-WebRequest https://api.github.com  →  200            ← 同一个时刻是通的
```

所以"git 推不上去"**不等于**"上不了 GitHub"。判据分开测,别互相背书。

## 3. 代理坑(本机踩过两次)

1. `~/.gitconfig` 里 `http.proxy = http://127.0.0.1:7897`,而 **7890/7897/10809/1080/8080 全没在监听** → git 每次连接直接失败/超时。
2. 绕过写法:`git -c http.proxy= -c https.proxy= <命令>`(本机实测:绕过后直连仍然超时,所以最终放弃 git 通道)。

排查用:

```powershell
git config --list --show-origin | Select-String 'proxy'
netsh winhttp show proxy
foreach ($p in 7890,7897,10809,1080,8080) { "$p : " + (Test-NetConnection 127.0.0.1 -Port $p -InformationLevel Quiet) }
```

## 4. 权限与 scope

| 要做的事 | 需要的能力 |
|---|---|
| 往已有仓库提交 | `Contents: Read and write`(经典 PAT 的 `repo`) |
| 建新仓库 | `Administration: Read and write`(经典 PAT 的 `repo` 也行) |
| 改可见性/删仓库 | 不在本 skill 职责内,明确告知用户人工做 |

拿到的凭据若权限不足,`POST /git/blobs` 会返回 403 —— 此时**不要**反复重试,直接报 `API_ERROR` 并把 GitHub 的原始 message 摘要出来。

## 5. 安全红线

- token 不落盘、不进命令行参数、不进提交信息、不出现在任何输出里;
- 上传前做**脱敏**(真实路径/客户名/人名);
- 上传前做**密钥自查**(见 `gh-upload.ps1` 的 `SECRET_SUSPECTED`);
- 公开仓库默认更严:不确定就先问用户,宁可不传。
