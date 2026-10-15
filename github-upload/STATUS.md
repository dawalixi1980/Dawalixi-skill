# STATUS —— 现状(截至 2026-10-15)

## 定位

`github-upload`:当 **git 通道不可用**(push/clone 超时、代理没开、`gh` 未登录)时,
用 **GitHub REST 的 Git Data API** 把本地目录上传成一次真实提交的 skill。
定位未变。

## 本轮完成的能力

| 能力 | 落地形式 |
|---|---|
| 凭据发现 | 环境变量 → `gh auth token` → **`git credential fill`**(Windows 凭据管理器/GCM)三级回退 |
| 通道判定 | 文档给出 git / REST API / gh 三条通道的判定命令与实测差异 |
| 上传 | `blobs → tree(base_tree) → commit → ref PATCH` 四步,一次提交 |
| 中文正确 | 非 ASCII 全部转 `\u` 转义 + 按 ASCII 字节发送(**PS 5.1 直接发中文会变 `?`**) |
| 二进制正确 | 全部走 base64 blob |
| 上传前闸门 | `-DryRun` 清单 + **疑似密钥自查**(ghp_/github_pat_/AKIA/私钥头/长 api_key) |
| 上传后校验 | 回读 `GET /commits/{branch}` 比对 sha,不一致报 `VERIFY_FAILED` |
| 可机检 | 契约校验器 + 离线回归测试(不联网、不写远端) |

## 文件

```
SKILL.md                                 契约:Invariants / 状态机 / 通道选择 / 上传前必做 / 错误码
README.md / TARGET.md / AGENTS.md        项目说明、目标边界、迭代纪律
references/credential-transport.md       凭据发现顺序、通道判定、代理坑、scope、安全红线
references/git-data-api.md               Git Data API 端点/载荷/base_tree 语义 + 三个实测坑
scripts/gh-upload.ps1                    上传器(含 -DryRun / -SelfTest / -Force / -AllowSecrets)
scripts/validate_skill.py                契约校验器
tests/test_gh_upload.ps1                 离线回归:转义自检 / 干跑清单 / 参数错误 / 密钥拦截
tests/test_validate_skill.py             校验器回归(1 正例 + 4 反例)
```

## 关键坑(本轮实测,已固化)

1. **git 与 .NET 是两条不同的网络栈**:同一时刻 git 连 github.com:443 超时 21s,而
   `Invoke-WebRequest https://api.github.com` 返回 200 → "git 推不上去" ≠ "上不了 GitHub"。
2. **凭据管理器里有货**:`git credential fill` 能拿到 `username` + 40 位 token;
   `gh` 未登录、`.git-credentials` 不存在都不代表没有凭据。
3. **PS 5.1 `-Body <string>` 会把中文发成 `?`**(实测提交信息变成 `?? everything-find skill`)
   → 必须把所有非 ASCII 转 `\u` 转义、按 ASCII 字节发。
4. **`GET /git/commits/{branch}` 不认分支名**(404)→ 先用 `GET /git/ref/heads/{branch}` 取 sha。
5. **`base_tree` 必须传**:否则新树只含本次文件,等于删掉仓库其它内容。
6. **`-match` 的默认排除正则 `'\.git\'` 非法**(结尾反斜杠抛异常)→ 改用 `-like` 通配。
7. **PowerShell 函数参数不能叫 `$Args`**(自动变量,参数会被吃掉,表现为"参数全丢→BAD_ARGS")。

## 验证结果(真实输出)

```
$ python scripts/validate_skill.py
PASS 契约校验通过                                       (exit=0)

$ powershell -File tests\test_gh_upload.ps1
case1 离线自检(中文转义)         PASS ESCTEST=PASS
case2 干跑:列出文件不碰网络       PASS(排除 .git/__pycache__,含 SKILL.md,COMMIT=DRYRUN)
case3 参数错误:仓库名不带 owner   PASS(exit 2 + BAD_ARGS)
case4 参数错误:目录不存在         PASS(exit 2)
case5 密钥自查:疑似 token 应拒传  PASS(exit 6 + SECRET_SUSPECT;-AllowSecrets 后可继续)
ALL TESTS PASSED                                        (exit=0)

$ python tests/test_validate_skill.py
Ran 5 tests ... OK                                      (exit=0)
```

真机验证(2026-10-15,目标仓库 `dawalixi1980/Dawalixi-skill`):
本 skill 用**自己的 `gh-upload.ps1`** 上传到该仓库,回到 `COMMIT=<sha> URL=https://github.com/dawalixi1980/Dawalixi-skill/tree/main/github-upload`。

## 仍未完成 / 已知限制

- **不建仓库、不建分支、不改可见性、不删远端文件**;分支不存在时报错而不是自动创建;
- 单文件 >100 MB 会被 GitHub 拒;一次提交建议 <1000 文件;
- 空目录不会被上传(Git 语义);
- 非快进更新必须显式 `-Force`(改写历史有风险,默认拒绝);
- 密钥自查是**正则粗筛**,只能拦常见形态,不能替代人工确认;
- 大仓库批量上传(万级文件)不适合走 API,应回到 git。

## 下一步优先级

1. 支持"分支不存在时自动创建"(`POST /git/refs`),目前是硬失败;
2. 增量上传:只传与远端 sha 不同的文件(现在是无脑全量,`base_tree` 保证不误删);
3. 上传前自动对比远端同名文件,给出"将覆盖 N 个文件"的提示(避免手滑覆盖);
4. 把"脱敏"从人工提醒升级成可选规则文件(路径/项目名替换表)。
