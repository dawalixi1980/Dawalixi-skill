# GitHub Git Data API —— 用一次提交上传一个目录

不依赖 git 传输层,直接按 GitHub 的三棵树模型造提交:
**blobs(内容)→ tree(目录)→ commit(提交)→ ref(分支指针)**。

## 1. 端点与顺序

| 步骤 | 方法 + 路径 | 载荷要点 |
|---|---|---|
| 取分支 tip | `GET /repos/{o}/{r}/git/ref/heads/{branch}` | 得到 `object.sha`(commit sha) |
| 取基线提交 | `GET /repos/{o}/{r}/git/commits/{sha}` | 得到 `tree.sha`(作为 `base_tree`) |
| 建 blob | `POST /repos/{o}/{r}/git/blobs` | `{"content":"<base64>","encoding":"base64"}` |
| 建 tree | `POST /repos/{o}/{r}/git/trees` | `{"base_tree":"<sha>","tree":[{"path":"dir/a.md","mode":"100644","type":"blob","sha":"..."}]}` |
| 建 commit | `POST /repos/{o}/{r}/git/commits` | `{"message":"...","tree":"<sha>","parents":["<base sha>"]}` |
| 移动分支 | `PATCH /repos/{o}/{r}/git/refs/heads/{branch}` | `{"sha":"<new commit>","force":false}` |
| 回读校验 | `GET /repos/{o}/{r}/commits/{branch}` | 比较 `sha` 与本次提交,并抽查文件内容 |

`base_tree` 的作用:**增量**——只写你给的这些路径,仓库里其它文件保持不动。不传它就会得到一棵"只有你这些文件"的新树(等于删掉其它内容,危险)。

## 2. 三个实测坑(都踩过)

### 坑 1:`GET /git/commits/{branch}` 不带分支名

```
GET /repos/o/r/git/commits/main        → 404 Not Found
GET /repos/o/r/git/ref/heads/main      → 200,取 object.sha
GET /repos/o/r/git/commits/<sha>       → 200
```

`/git/commits/` 只认 **commit sha**;分支名要用 `/git/ref/heads/<branch>` 先解析。

### 坑 2:PowerShell 5.1 的 `-Body <string>` 会把中文发成 `?`

实测:提交信息写"添加 everything-find skill",远端显示成 `?? everything-find skill`。
原因:`Invoke-RestMethod` 传字符串时按 ASCII/Latin-1 编码,非 ASCII 直接丢。

**正解**:把 JSON 里所有非 ASCII 转义成 `\uXXXX`,按 **ASCII 字节**发送(JSON 语法本身允许这种转义):

```powershell
function Esc-Ascii([string]$s) {
  $sb = New-Object System.Text.StringBuilder
  foreach ($ch in $s.ToCharArray()) {
    $c = [int]$ch
    if ($c -lt 128) { [void]$sb.Append($ch) } else { [void]$sb.Append(('\u{0:x4}' -f $c)) }
  }
  return $sb.ToString()
}
$bytes = [Text.Encoding]::ASCII.GetBytes((Esc-Ascii $json))
Invoke-RestMethod -Method Post -Uri $url -Headers $h -ContentType 'application/json' -Body $bytes
```

二进制文件同理不受影响——它们本来就走 base64。

### 坑 3:分支必须已存在

`PATCH /git/refs/heads/{branch}` 只在分支存在时能用。要新建分支得走
`POST /git/refs`(`{"ref":"refs/heads/x","sha":"<base>"}`);本 skill 只做"往已有分支追加",没有分支就报错,避免误建。

## 3. 其它约束

| 约束 | 数值/行为 |
|---|---|
| 单文件大小 | blob API 上限 100 MB;>50 MB 会告警,不建议走 API |
| 单次 tree 条目 | 建议 < 1000 个文件;更多就分批或改用 git |
| 限流 | 认证请求 5000/h;超限返回 403 + `X-RateLimit-Remaining: 0` |
| 空目录 | **不会**被创建(Git 本来就不跟踪空目录),需要时放个 `.gitkeep` |
| 文件模式 | 普通文件 `100644`;可执行文件 `100755` |
| 提交者身份 | 用 token 对应用户;想指定 author/committer 可在 commit 载荷里加 `author`/`committer` |
| force | `force:false` 时非快进会被拒(409/422);改写历史必须显式 `force:true`,本 skill 要求 `-Force` |

## 4. 事后校验(必须做)

1. `GET /repos/{o}/{r}/commits/{branch}` → `sha` 必须等于本次新建的 commit sha;
2. `GET /repos/{o}/{r}/contents/{path}` → 抽查至少一个文件,`size` 与本地一致(内容可取 `content` 字段 base64 解码比对头几行);
3. 浏览器/网页链接给用户:`https://github.com/{o}/{r}/tree/{branch}/{prefix}`。

## 5. 与 git 命令的对应关系

| git 命令 | 等价 API |
|---|---|
| `git add` + 写对象 | `POST /git/blobs` |
| `git write-tree` | `POST /git/trees` |
| `git commit` | `POST /git/commits` |
| `git push` | `PATCH /git/refs/heads/{branch}` |
| `git log -1` | `GET /commits/{branch}` |

明白这层对应关系,就能在没有 git 的环境里做完整的提交(但**读历史/分支管理**仍建议用 git 或网页)。
