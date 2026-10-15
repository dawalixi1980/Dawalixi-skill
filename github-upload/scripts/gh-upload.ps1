<#
  gh-upload.ps1 —— 没有可用 git 通道时,用 GitHub REST API 把本地目录上传成一次提交

  为什么需要它:本机 git 全局配了代理(如 http.proxy=http://127.0.0.1:7897),
  代理没运行时 `git push/clone` 直接超时;而 .NET 的 HTTPS 到 api.github.com
  往往是通的 —— 于是改走 Git Data API,不依赖 git 传输层。

  链路:POST /git/blobs(base64) → POST /git/trees(base_tree) → POST /git/commits → PATCH /git/refs/heads/{branch}

  用法:
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\gh-upload.ps1 `
      -Repo "owner/name" -Source ".\my-skill" -Message "添加 my-skill"

  参数:
    -Repo      owner/name(必填)
    -Source    本地目录(必填)
    -Prefix    仓库内目标前缀,默认取 Source 的目录名
    -Message   提交信息,默认 "add <prefix>"
    -Branch    分支,默认 main(必须已存在)
    -Exclude   额外排除的相对路径通配(默认已排除 .git/__pycache__/*.pyc)
    -Force     允许非快进更新分支(默认拒绝)
    -DryRun    只列出将上传的文件与体积,不调用任何写接口
    -AllowSecrets  已知文件里有疑似密钥时仍继续(默认拒传)

  输出(控制台只打 ASCII):
    FILE=<相对路径> BYTES=<n>
    PREFIX=... FILES=<n> BYTES=<n> COMMIT=<sha> URL=<...>
  退出码:0 成功 | 2 BAD_ARGS | 3 NO_CREDENTIAL | 4 API_ERROR | 5 VERIFY_FAILED | 6 SECRET_SUSPECTED

  本文件必须保存为 UTF-8 with BOM(PowerShell 5.1 否则按 ANSI 读会语法崩)。
#>
[CmdletBinding()]
param(
  [string]$Repo,
  [string]$Source,
  [string]$Prefix = '',
  [string]$Message = '',
  [string]$Branch = 'main',
  [string[]]$Exclude = @(),
  [switch]$Force,
  [switch]$DryRun,
  [switch]$AllowSecrets,
  [switch]$SelfTest
)

$ErrorActionPreference = 'Continue'

function Fail([int]$code, [string]$msg) {
  Write-Output ("SCHEMA=github-upload/v1 ERROR=" + $msg)
  exit $code
}

# 非 ASCII 一律转成 \u 转义:PS 5.1 直接把含中文的 -Body 字符串发出去会变成 '?'
function Esc-Ascii([string]$s) {
  $sb = New-Object System.Text.StringBuilder
  foreach ($ch in $s.ToCharArray()) {
    $c = [int]$ch
    if ($c -lt 128) { [void]$sb.Append($ch) } else { [void]$sb.Append(('\u{0:x4}' -f $c)) }
  }
  return $sb.ToString()
}

function Send-Json {
  param([string]$Method, [string]$Url, [hashtable]$Headers, [string]$Json)
  $bytes = [Text.Encoding]::ASCII.GetBytes((Esc-Ascii $Json))
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType 'application/json' -Body $bytes -TimeoutSec 120
}

# 离线自检:不需要仓库/目录,只验证编码转义这一处最容易错的地方
if ($SelfTest) {
  $raw = '中文abc'
  $want = '\u4e2d\u6587abc'
  $got = Esc-Ascii $raw
  if ($got -eq $want) { Write-Output 'ESCTEST=PASS'; exit 0 }
  Write-Output ("ESCTEST=FAIL got=" + $got)
  exit 1
}

if ($Repo -notmatch '^[^/]+/[^/]+$') { Fail 2 'BAD_ARGS repo-must-be-owner/name' }
if (-not $Source) { Fail 2 'BAD_ARGS source-required' }
if (-not (Test-Path -LiteralPath $Source -PathType Container)) { Fail 2 'BAD_ARGS source-not-a-directory' }
$sourceFull = (Get-Item -LiteralPath $Source).FullName
if (-not $Prefix) { $Prefix = Split-Path -Leaf $sourceFull }
if (-not $Message) { $Message = "add $Prefix" }

# ---------------------------------------------------------------- 取凭据
$token = ''
try {
  $env:GIT_TERMINAL_PROMPT = '0'
  $cred = 'protocol=https
host=github.com

' | & git credential fill 2>$null
  $line = @($cred | Where-Object { $_ -like 'password=*' } | Select-Object -First 1)
  if ($line.Count -gt 0) { $token = ($line[0] -replace '^password=', '') }
} catch { }
if (-not $token) {
  try {
    $token = (& gh auth token 2>$null | Select-Object -First 1)
  } catch { }
}
if (-not $token) { Fail 3 'NO_CREDENTIAL' }

$H = @{
  Authorization          = "token $token"
  'User-Agent'           = 'github-upload-skill'
  Accept                 = 'application/vnd.github+json'
  'X-GitHub-Api-Version' = '2022-11-28'
}
$api = "https://api.github.com/repos/$Repo"

# ---------------------------------------------------------------- 文件清单
# 排除规则用 -like 通配(反斜杠字面量,避免正则结尾反斜杠把 -match 抛异常)
$defaultExclude = @('*\.git\*', '*\__pycache__\*', '*.pyc', '*.pdb', '*~$*')
$files = New-Object System.Collections.ArrayList
foreach ($f in (Get-ChildItem -LiteralPath $sourceFull -Recurse -File -Force)) {
  $rel = $f.FullName.Substring($sourceFull.Length + 1)
  $skip = $false
  foreach ($pat in $defaultExclude) { if ($rel -like $pat) { $skip = $true; break } }
  if (-not $skip) {
    foreach ($ex in $Exclude) {
      if ($ex -and ($rel -like $ex)) { $skip = $true; break }
    }
  }
  if (-not $skip) { [void]$files.Add([pscustomobject]@{ rel = ($rel -replace '\\', '/'); full = $f.FullName; size = $f.Length }) }
}
if ($files.Count -eq 0) { Fail 2 'BAD_ARGS no-files' }
$totalBytes = ($files | Measure-Object -Property size -Sum).Sum

# ---------------------------------------------------------------- 密钥自查
if (-not $AllowSecrets) {
  $suspicious = New-Object System.Collections.ArrayList
  $patterns = @('ghp_[A-Za-z0-9]{20,}', 'github_pat_[A-Za-z0-9_]{20,}', 'AKIA[0-9A-Z]{16}', 'BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY', '(?i)api[_-]?key\s*[:=]\s*["'']?[A-Za-z0-9_\-]{24,}')
  foreach ($f in $files) {
    if ($f.size -gt 2MB) { continue }
    $txt = ''
    try { $txt = Get-Content -LiteralPath $f.full -Raw -Encoding UTF8 -ErrorAction SilentlyContinue } catch { continue }
    if (-not $txt) { continue }
    foreach ($p in $patterns) {
      if ($txt -match $p) { [void]$suspicious.Add($f.rel + ' <' + $p + '>'); break }
    }
  }
  if ($suspicious.Count -gt 0) {
    foreach ($s in $suspicious) { Write-Output ("SECRET_SUSPECT " + $s) }
    Fail 6 'SECRET_SUSPECTED use -AllowSecrets to override'
  }
}

foreach ($f in $files) { Write-Output ("FILE=" + $f.rel + " BYTES=" + $f.size) }
if ($DryRun) {
  Write-Output ("PREFIX=$Prefix FILES=$($files.Count) BYTES=$totalBytes COMMIT=DRYRUN URL=")
  exit 0
}

# ---------------------------------------------------------------- 身份与基线
try {
  $me = Invoke-RestMethod -Method Get -Uri 'https://api.github.com/user' -Headers $H -TimeoutSec 60
  Write-Output ("AUTH_AS=" + $me.login)
} catch { Fail 4 ('API_ERROR user ' + $_.Exception.Message) }

try {
  $ref = Invoke-RestMethod -Method Get -Uri "$api/git/ref/heads/$Branch" -Headers $H -TimeoutSec 60
} catch { Fail 4 ("API_ERROR ref-$Branch " + $_.Exception.Message) }
$baseCommit = $ref.object.sha
try {
  $base = Invoke-RestMethod -Method Get -Uri "$api/git/commits/$baseCommit" -Headers $H -TimeoutSec 60
} catch { Fail 4 ('API_ERROR base-commit ' + $_.Exception.Message) }
if (-not $Force -and $base.parents.Count -gt 0) {
  # 只允许在分支 tip 之上追加;非快进必须显式 -Force
}
Write-Output ("BASE_COMMIT=" + $baseCommit)

# ---------------------------------------------------------------- blobs
$tree = New-Object System.Collections.ArrayList
foreach ($f in $files) {
  $b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($f.full))
  $body = '{"content":"' + $b64 + '","encoding":"base64"}'
  try {
    $blob = Send-Json -Method Post -Url "$api/git/blobs" -Headers $H -Json $body
  } catch { Fail 4 ("API_ERROR blob " + $f.rel + ' ' + $_.Exception.Message) }
  [void]$tree.Add(@{ path = "$Prefix/$($f.rel)"; mode = '100644'; type = 'blob'; sha = $blob.sha })
}

# ---------------------------------------------------------------- tree / commit / ref
$treeJson = @{ base_tree = $base.tree.sha; tree = @($tree) } | ConvertTo-Json -Depth 8 -Compress
try {
  $newTree = Send-Json -Method Post -Url "$api/git/trees" -Headers $H -Json $treeJson
} catch { Fail 4 ('API_ERROR tree ' + $_.Exception.Message) }

$commitJson = @{ message = $Message; tree = $newTree.sha; parents = @($baseCommit) } | ConvertTo-Json -Depth 6 -Compress
try {
  $newCommit = Send-Json -Method Post -Url "$api/git/commits" -Headers $H -Json $commitJson
} catch { Fail 4 ('API_ERROR commit ' + $_.Exception.Message) }

$refJson = @{ sha = $newCommit.sha; force = [bool]$Force } | ConvertTo-Json -Compress
try {
  $null = Send-Json -Method Patch -Url "$api/git/refs/heads/$Branch" -Headers $H -Json $refJson
} catch { Fail 4 ('API_ERROR ref-update ' + $_.Exception.Message) }

# ---------------------------------------------------------------- 回读校验
try {
  $check = Invoke-RestMethod -Method Get -Uri "$api/commits/$Branch" -Headers $H -TimeoutSec 60
} catch { Fail 5 ('VERIFY_FAILED ' + $_.Exception.Message) }
if ($check.sha -ne $newCommit.sha) {
  Fail 5 ("VERIFY_FAILED tip-is-" + $check.sha)
}
$url = "https://github.com/$Repo/tree/$Branch/$Prefix"
Write-Output ("PREFIX=$Prefix FILES=$($files.Count) BYTES=$totalBytes COMMIT=" + $newCommit.sha + " URL=$url")
exit 0
