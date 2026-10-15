# github-upload

把本地目录上传成 GitHub 上**一次真正的提交**,**不依赖 git 命令**。

用在:git push/clone 超时(代理没开)、`gh` 未登录、只装了 .NET 没有可用 git 通道、
或你只想"把这一坨文件传上去"。

## 包含内容

| 文件 | 作用 |
|---|---|
| `SKILL.md` | 契约:Invariants、状态机、通道选择、上传前必做、错误码 |
| `references/credential-transport.md` | 凭据发现顺序(环境变量 → gh → git credential fill)、通道判定、代理坑、scope 与安全红线 |
| `references/git-data-api.md` | Git Data API 端点/载荷/base64/`base_tree` 语义 + 三个实测坑 + 事后校验 |
| `scripts/gh-upload.ps1` | 上传器:干跑、密钥自查、blobs→tree→commit→ref、回读校验 |
| `scripts/validate_skill.py` | 契约校验器(frontmatter/章节/引用/BOM/关键实现/禁止写法) |
| `tests/test_gh_upload.ps1` | 离线回归:转义自检、干跑清单、参数错误、密钥拦截 |
| `tests/test_validate_skill.py` | 校验器回归(1 正例 + 4 反例) |

## 用一次

```powershell
$S = ".\scripts\gh-upload.ps1"

# 1) 干跑:只列文件与体积
powershell -NoProfile -ExecutionPolicy Bypass -File $S -Repo "owner/name" -Source ".\my-skill" -DryRun

# 2) 真上传
powershell -NoProfile -ExecutionPolicy Bypass -File $S `
  -Repo "owner/name" -Source ".\my-skill" -Message "添加 my-skill"
# -> PREFIX=my-skill FILES=12 BYTES=... COMMIT=<sha> URL=https://github.com/owner/name/tree/main/my-skill
```

## 验证

```powershell
python scripts\validate_skill.py           # 契约校验
powershell -NoProfile -File tests\test_gh_upload.ps1    # 离线回归(不联网)
python tests\test_validate_skill.py        # 校验器回归
```

## 已知限制

- 只往**已存在**的分支追加,不建仓库、不建分支、不改可见性、不删远端文件;
- 单文件上限 100 MB(>50 MB 不建议走 API),一次提交建议 < 1000 个文件;
- 空目录不会被上传(Git 语义);
- 非快进更新必须显式 `-Force`;
- 校验只保证"提交落地且 tip 对上",不保证内容正确——内容由校验器与人判断。

## 边界(非目标)

不做仓库管理(创建/删除/改名/可见性/成员)、不做分支与 PR 流程、不替代 git 的日常使用。
它只是"通道不通时的备用上传路径"。
