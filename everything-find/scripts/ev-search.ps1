<#
  ev-search.ps1 —— everything-find 的查询封装
  ------------------------------------------------------------------
  职责:机械搜索。把「用户给的名称/关键词」变成 Everything 查询,执行删词阶梯,
        输出含完整绝对路径的候选 JSON(带机械预排序字段)。
        语义判断(哪个最匹配、怎么出 5 选表格)由 LLM 按 SKILL.md 完成。

  ★ 关键实测(2026-10-14,es 1.1.0.27 / Everything 1.4.1.1032):
    含空格的「单个参数」会被 es.exe 当成整词 → 多词查询几乎全部 0 命中。
    正确做法:每个词作为**独立参数**传递。例:
        es.exe -get-result-count 'AD-03' '设计图'      -> 7      (对)
        es.exe -get-result-count 'AD-03 设计图'        -> 0      (错!)

  输出约定:
    - 控制台:单行纯 ASCII 摘要(避免 PowerShell 5.1 往 stdout 打中文被编码破坏)
    - 文件:results.json(UTF-8 无 BOM),含完整绝对路径、大小、时间、coverage、exact_name
  退出码:0 = 正常(含 NO_MATCH)  2 = BAD_ARGS  3 = TOOL_UNAVAILABLE
  兼容性:Windows PowerShell 5.1(本文件必须带 UTF-8 BOM,否则 5.1 按 ANSI 读会语法崩)
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)][string]$Query,
  [int]$Count = 50,
  [string[]]$Ext,
  [string]$Path = '',
  [switch]$Regex,
  [switch]$Ladder,
  [ValidateSet('auto', 'es', 'http')][string]$Transport = 'auto',
  [string]$EsPath = '',
  [string]$HttpBase = 'http://127.0.0.1:8017',
  [string]$OutDir = '',
  [int]$TimeoutMs = 20000
)

$ErrorActionPreference = 'Continue'

# ---------------------------------------------------------------- 基础工具

function Get-EsCandidates {
  $list = New-Object System.Collections.ArrayList
  if ($EsPath) { [void]$list.Add($EsPath) }
  [void]$list.Add('C:\Program Files\Everything\es.exe')
  [void]$list.Add('C:\Program Files (x86)\Everything\es.exe')
  if ($env:DSH_HOME) { [void]$list.Add((Join-Path $env:DSH_HOME 'tools\everything\es.exe')) }
  $cmd = Get-Command 'es.exe' -ErrorAction SilentlyContinue
  if ($cmd) { [void]$list.Add($cmd.Source) }
  [void]$list.Add((Join-Path $PSScriptRoot 'es.exe'))
  return @($list)
}

function Get-Text([object]$Value) {
  if ($null -eq $Value) { return '' }
  return ([string]$Value).Trim()
}

function Get-QueryTerms([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return @() }
  $ms = [regex]::Matches($Text, '"[^"]*"|\S+')
  $out = New-Object System.Collections.ArrayList
  foreach ($m in $ms) {
    $t = $m.Value.Trim()
    if ($t.Length -gt 0) { [void]$out.Add($t) }
  }
  return @($out)
}

function Get-NormName([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return '' }
  $t = $Text.Trim()
  $t = [regex]::Replace($t, '\.[A-Za-z0-9]{1,8}\s*$', '')
  $t = $t -replace '[\s\-_（）()【】\[\],，.。、·]', ''
  return $t.ToLowerInvariant()
}

function Get-Tokens([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return @() }
  $parts = [regex]::Split($Text, '[\s·、,，。．/\\|（）()【】\[\]]+')
  return @($parts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
}

function Get-Coverage([string]$QueryText, [string]$Name) {
  $toks = @(Get-Tokens $QueryText)
  if ($toks.Count -eq 0) { return 1.0 }
  $n = $Name.ToLowerInvariant()
  $hit = 0
  foreach ($t in $toks) { if ($n.Contains($t.ToLowerInvariant())) { $hit++ } }
  return [math]::Round(($hit / $toks.Count), 3)
}

function Format-Size([object]$Bytes) {
  $b = 0
  if (-not [int64]::TryParse((Get-Text $Bytes), [ref]$b)) { return '' }
  if ($b -ge 1073741824) { return ('{0:N2} GB' -f ($b / 1073741824)) }
  if ($b -ge 1048576) { return ('{0:N2} MB' -f ($b / 1048576)) }
  if ($b -ge 1024) { return ('{0:N1} KB' -f ($b / 1024)) }
  return "$b B"
}

function ConvertTo-DateTime([string]$Text) {
  if ([string]::IsNullOrWhiteSpace($Text)) { return [datetime]::MinValue }
  $t = $Text.Trim()
  $formats = @('yyyy/M/d H:mm', 'yyyy/MM/dd HH:mm', 'yyyy-M-d H:mm', 'yyyy-MM-dd HH:mm', 'yyyy/M/d H:mm:ss', 'yyyy-MM-dd HH:mm:ss')
  foreach ($f in $formats) {
    $dt = [datetime]::MinValue
    if ([datetime]::TryParseExact($t, $f, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$dt)) { return $dt }
  }
  $dt2 = [datetime]::MinValue
  if ([datetime]::TryParse($t, [ref]$dt2)) { return $dt2 }
  return [datetime]::MinValue
}

# ------------------------------------------------- 查询词条(每词独立参数)

function Get-SearchTerms {
  param([string]$Base, [string[]]$Exts)
  $terms = New-Object System.Collections.ArrayList
  foreach ($t in Get-QueryTerms $Base) { [void]$terms.Add($t) }
  $cleanExt = @()
  foreach ($e in @($Exts)) {
    $v = (Get-Text $e).TrimStart('.').Trim()
    if ($v.Length -gt 0) { $cleanExt += $v }
  }
  if ($cleanExt.Count -gt 0) { [void]$terms.Add('ext:' + ($cleanExt -join ';')) }
  return @($terms)
}

# ---------------------------------------------------------------- es.exe 调用

function Invoke-EsCount {
  param([string]$Es, [string[]]$Terms, [switch]$UseRegex, [string]$PathFilter)
  $esArgs = @('-get-result-count')
  if ($UseRegex) { $esArgs += '-r' }
  if ($PathFilter) { $esArgs += @('-path', $PathFilter) }
  foreach ($t in @($Terms)) { $esArgs += $t }
  try { $out = & $Es @esArgs 2>$null } catch { return -1 }
  $txt = (($out | Out-String)).Trim()
  $m = [regex]::Match($txt, '\d[\d,]*')
  if (-not $m.Success) { return -1 }
  return [int64](($m.Value) -replace ',', '')
}

function Invoke-EsRows {
  param([string]$Es, [string[]]$Terms, [switch]$UseRegex, [int]$Max, [string]$CsvPath, [string]$PathFilter)
  if (Test-Path $CsvPath) { Remove-Item $CsvPath -Force -ErrorAction SilentlyContinue }
  $esArgs = @('-export-csv', $CsvPath, '-utf8-bom', '-full-path-and-name', '-size', '-dm', '-ext', '-n', "$Max")
  if ($UseRegex) { $esArgs += '-r' }
  if ($PathFilter) { $esArgs += @('-path', $PathFilter) }
  foreach ($t in @($Terms)) { $esArgs += $t }
  try { & $Es @esArgs 2>$null | Out-Null } catch { return @() }
  if (-not (Test-Path $CsvPath)) { return @() }
  try { return @(Import-Csv -Path $CsvPath -Encoding UTF8) } catch { return @() }
}

function Test-EsAlive {
  param([string]$Es)
  try {
    $v = & $Es '-get-everything-version' 2>$null
    $txt = (($v | Out-String)).Trim()
    if ($txt -match '^\d+\.\d+') { return $txt }
    return ''
  } catch { return '' }
}

function Test-HttpAlive {
  param([string]$Base, [int]$TimeoutSec = 3)
  try {
    $u = $Base.TrimEnd('/') + '/?search=everything-find-probe&json=1&count=1'
    $r = Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec $TimeoutSec
    return ($r.StatusCode -eq 200)
  } catch { return $false }
}

function Invoke-HttpSearch {
  param([string]$Base, [string[]]$Terms, [int]$Max)
  $search = (@($Terms) -join ' ')
  $u = $Base.TrimEnd('/') + '/?search=' + [uri]::EscapeDataString($search) + '&json=1&path_column=1&count=' + $Max
  $resp = Invoke-RestMethod -Uri $u -TimeoutSec 20
  $items = @($resp.results)
  $rows = New-Object System.Collections.ArrayList
  foreach ($it in $items) {
    $dir = Get-Text $it.path
    $nm = Get-Text $it.name
    $full = $nm
    if ($dir.Length -gt 0) { $full = ($dir.TrimEnd('\') + '\' + $nm) }
    $ext = ''
    if ($nm -match '\.([A-Za-z0-9]{1,8})$') { $ext = $Matches[1] }
    [void]$rows.Add([pscustomobject]@{
        Filename        = $full
        Size            = (Get-Text $it.size)
        'Date Modified' = (Get-Text $it.date_modified)
        Extension       = $ext
      })
  }
  $total = 0
  if ($resp.totalResults) { $total = [int64]$resp.totalResults }
  return @{ rows = @($rows); total = $total }
}

# ---------------------------------------------------------------- 删词阶梯

function Add-LadderRound {
  param($Rounds, $Seen, [string]$Label, [string]$Text)
  $t = Get-Text $Text
  if ($t.Length -eq 0) { return }
  $key = $t.ToLowerInvariant()
  if ($Seen.Contains($key)) { return }
  [void]$Seen.Add($key)
  [void]$Rounds.Add([pscustomobject]@{ label = $Label; query = $t })
}

function New-Ladder {
  param([string]$Original)
  $rounds = New-Object System.Collections.ArrayList
  $seen = New-Object 'System.Collections.Generic.HashSet[string]'

  Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R0-原始查询' -Text $Original

  $r1 = Get-Text $Original
  $r1 = [regex]::Replace($r1, '\.[A-Za-z0-9]{1,8}\s*$', '')
  $r1 = [regex]::Replace($r1, '(?i)[\s_\-]*(副本|复件|copy|final|最终版|终版|备份|修订版|最新版)\s*[-_]?\s*\d*\s*([（(]\s*\d+\s*[）)])?\s*$', '')
  $r1 = [regex]::Replace($r1, '[（(]\s*\d+\s*[）)]\s*$', '')
  $r1 = ($r1 -replace '\s+', ' ').Trim()
  Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R1-去扩展名与尾缀' -Text $r1

  $r2 = [regex]::Replace($r1, '[（(【\[][^）)】\]]*[）)】\]]', ' ')
  $r2 = [regex]::Replace($r2, '^\s*\d{1,4}\s*[-_.、]\s*', '')
  $r2 = ($r2 -replace '\s+', ' ').Trim()
  Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R2-去括号与编号' -Text $r2

  $toks = @(Get-Tokens $r2)
  if ($toks.Count -ge 1) {
    $byLen = @($toks | Sort-Object -Property Length -Descending)
    $n = [math]::Min(2, $byLen.Count)
    $take = @($byLen | Select-Object -First $n)
    Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R3-留最长2个特征词' -Text ($take -join ' ')
    $one = [string]$byLen[0]
    Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R4-只留最长特征词' -Text $one
    if ($one.Length -ge 4) { Add-LadderRound -Rounds $rounds -Seen $seen -Label 'R4b-前缀通配' -Text ($one + '*') }
  }
  return @($rounds)
}

# ---------------------------------------------------------------- 主流程

$ErrorCode = 'NONE'
$ErrorMessage = ''
$ExitCode = 0

$baseQuery = Get-Text $Query
if ($baseQuery.Length -eq 0) {
  Write-Output 'SCHEMA=everything-find/result/v1 TRANSPORT=none USED_ROUND=-1 HITS=0 RETURNED=0 TRUNCATED=0 JSON= ERROR=BAD_ARGS MSG=query-empty'
  exit 2
}
if ($Count -lt 1) { $Count = 1 }
if ($Count -gt 500) { $Count = 500 }

$extUsed = @()
foreach ($e in @($Ext)) {
  $v = (Get-Text $e).TrimStart('.').Trim()
  if ($v.Length -gt 0) { $extUsed += $v }
}

# 目录过滤:Everything 的 -path 只认长路径;短路径(8.3,如 C:\Users\ADMINI~1\...)恒 0 命中。
# 这里统一规范化成 Get-Item 给出的真实长路径。
$pathFilter = Get-Text $Path
if ($pathFilter.Length -gt 0) {
  try {
    if (Test-Path -LiteralPath $pathFilter) { $pathFilter = (Get-Item -LiteralPath $pathFilter).FullName }
  } catch { }
  $pathFilter = $pathFilter.TrimEnd('\')
}

if (-not $OutDir) { $OutDir = Join-Path $env:TEMP 'everything-find' }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$jsonPath = Join-Path $OutDir 'results.json'
$csvPath = Join-Path $OutDir 'raw.csv'

# --- 通道探测
$esResolved = ''
foreach ($c in Get-EsCandidates) {
  if ($c -and (Test-Path $c)) { $esResolved = $c; break }
}
$escVersion = ''
$evVersion = ''
$useEs = $false
$useHttp = $false

if ($Transport -eq 'es' -or $Transport -eq 'auto') {
  if ($esResolved) {
    $escVersion = (& $esResolved -version 2>$null | Out-String).Trim()
    $evVersion = Test-EsAlive -Es $esResolved
    if ($evVersion -ne '') { $useEs = $true }
  }
}
if (-not $useEs -and ($Transport -eq 'http' -or $Transport -eq 'auto')) {
  if (Test-HttpAlive -Base $HttpBase) { $useHttp = $true }
}
if (-not $useEs -and -not $useHttp) {
  $ErrorCode = 'TOOL_UNAVAILABLE'
  $ErrorMessage = "es.exe not found or Everything not reachable; HTTP not reachable at $HttpBase; es.exe expected at $esResolved"
}

$transportUsed = 'none'
if ($useEs) { $transportUsed = 'es' } elseif ($useHttp) { $transportUsed = 'http' }

$rounds = @()
$usedRound = -1
$rows = @()
$totalHits = 0
$results = @()
$termsUsed = @()

if ($ErrorCode -eq 'NONE') {
  if ($Ladder) { $ladderRounds = New-Ladder -Original $baseQuery }
  else { $ladderRounds = @([pscustomobject]@{ label = 'R0-原始查询'; query = $baseQuery }) }

  $roundLog = New-Object System.Collections.ArrayList
  $idx = 0
  foreach ($r in $ladderRounds) {
    $terms = Get-SearchTerms -Base $r.query -Exts $extUsed
    if (@($terms).Count -eq 0) { $idx++; continue }

    if ($useEs) { $hits = Invoke-EsCount -Es $esResolved -Terms $terms -UseRegex:$Regex -PathFilter $pathFilter }
    else {
      $probe = Invoke-HttpSearch -Base $HttpBase -Terms $terms -Max 1
      $hits = [int64]$probe.total
    }
    [void]$roundLog.Add([pscustomobject]@{ round = $idx; label = $r.label; query = ($terms -join ' '); terms = @($terms); hits = $hits })
    if ($hits -gt 0) { $usedRound = $idx; $termsUsed = @($terms); $totalHits = $hits; break }
    $idx++
  }

  if ($usedRound -ge 0) {
    if ($useEs) { $rows = Invoke-EsRows -Es $esResolved -Terms $termsUsed -UseRegex:$Regex -Max $Count -CsvPath $csvPath -PathFilter $pathFilter }
    else {
      $resp = Invoke-HttpSearch -Base $HttpBase -Terms $termsUsed -Max $Count
      $rows = @($resp.rows)
      if ($totalHits -le 0) { $totalHits = [int64]$resp.total }
      if ($pathFilter) {
        $pf = $pathFilter.ToLowerInvariant() + '\'
        $rows = @($rows | Where-Object { ((Get-Text $_.Filename).ToLowerInvariant()).StartsWith($pf) })
      }
    }
    if (@($rows).Count -gt 0 -and $totalHits -le 0) { $totalHits = @($rows).Count }
  }
  else {
    $ErrorCode = 'NO_MATCH'
    $ErrorMessage = 'No results after ' + @($roundLog).Count + ' ladder round(s).'
  }
  $rounds = @($roundLog)

  $effectiveQuery = $baseQuery
  if ($usedRound -ge 0) {
    foreach ($r in @($rounds)) { if ($r.round -eq $usedRound) { $effectiveQuery = $r.query; break } }
  }

  # 名称匹配只认名称词:函数过滤器(ext:/size:/dm:/path: 等)不参与 coverage 与 exact_name,
  # 否则一旦带 -Ext,exact_name 永远为 false、coverage 永远被扣分,机械预排序就失真了。
  $filterPattern = '^(ext|size|dm|dc|da|rc|path|parent|file|folder|case|regex|content|type|child|childcount|empty|dupe|attrib):'
  $nameTerms = @()
  foreach ($t in @($termsUsed)) { if ($t -notmatch $filterPattern) { $nameTerms += $t } }
  $nameQuery = ($nameTerms -join ' ')
  if ([string]::IsNullOrWhiteSpace($nameQuery)) { $nameQuery = $baseQuery }

  # --- 归一化 + 机械预排序
  $normalized = New-Object System.Collections.ArrayList
  foreach ($row in @($rows)) {
    $full = Get-Text $row.Filename
    if ($full.Length -eq 0) { continue }
    $name = $full
    $dir = ''
    try {
      $name = [IO.Path]::GetFileName($full)
      $dir = [IO.Path]::GetDirectoryName($full)
    } catch { }
    $extOfFile = ''
    if ($name -match '\.([A-Za-z0-9]{1,8})$') { $extOfFile = $Matches[1] }
    $sizeRaw = Get-Text $row.Size
    $sizeBytes = 0
    [void][int64]::TryParse($sizeRaw, [ref]$sizeBytes)
    $modified = Get-Text $row.'Date Modified'
    [void]$normalized.Add([pscustomobject]@{
        name        = $name
        path        = $full
        dir         = $dir
        ext         = $extOfFile
        size_bytes  = $sizeBytes
        size_human  = (Format-Size $sizeRaw)
        modified    = $modified
        modified_dt = (ConvertTo-DateTime $modified)
        coverage    = (Get-Coverage -QueryText $nameQuery -Name $name)
        coverage_original = (Get-Coverage -QueryText $baseQuery -Name $name)
        exact_name  = ((Get-NormName $nameQuery) -ne '' -and (Get-NormName $nameQuery) -eq (Get-NormName $name))
      })
  }

  $sorted = @($normalized | Sort-Object -Property @{ Expression = 'exact_name'; Descending = $true },
      @{ Expression = 'coverage'; Descending = $true },
      @{ Expression = 'modified_dt'; Descending = $true },
      @{ Expression = 'path'; Descending = $false })

  $rank = 0
  $out = New-Object System.Collections.ArrayList
  foreach ($s in $sorted) {
    $rank++
    [void]$out.Add([ordered]@{
        rank       = $rank
        name       = $s.name
        path       = $s.path
        dir        = $s.dir
        ext        = $s.ext
        size_bytes = $s.size_bytes
        size_human = $s.size_human
        modified   = $s.modified
        coverage   = $s.coverage
        coverage_original = $s.coverage_original
        exact_name = [bool]$s.exact_name
      })
  }
  $results = @($out)
  if ($ErrorCode -eq 'NONE' -and $results.Count -eq 0) {
    $ErrorCode = 'NO_MATCH'
    $ErrorMessage = 'Query matched but no rows returned.'
  }
  if ($ErrorCode -eq 'NO_MATCH') {
    $usedRound = -1
    $results = @()
    if ($totalHits -lt 0) { $totalHits = 0 }
  }
}

if ($ErrorCode -eq 'TOOL_UNAVAILABLE') { $ExitCode = 3 }
elseif ($ErrorCode -eq 'BAD_ARGS') { $ExitCode = 2 }

$truncated = [bool]($totalHits -gt $results.Count)
$usedLabel = ''
foreach ($r in @($rounds)) { if ($r.round -eq $usedRound) { $usedLabel = $r.label } }

$termsUsedClean = @($termsUsed | Where-Object { -not [string]::IsNullOrEmpty($_) })

$payload = [ordered]@{
  schema             = 'everything-find/result/v1'
  transport          = $transportUsed
  query_original     = $baseQuery
  terms_used         = $termsUsedClean
  query_used         = ($termsUsedClean -join ' ')
  effective_query    = $effectiveQuery
  name_query         = $nameQuery
  ext_filter         = @($extUsed)
  path_filter        = $pathFilter
  path_filter_input  = $Path
  regex              = [bool]$Regex
  ladder_enabled     = [bool]$Ladder
  used_round         = $usedRound
  used_round_label   = $usedLabel
  rounds             = @($rounds)
  total_hits         = $totalHits
  returned           = $results.Count
  truncated          = $truncated
  results            = $results
  es_path            = $esResolved
  es_version         = $escVersion
  everything_version = $evVersion
  http_base          = $HttpBase
  error_code         = $ErrorCode
  error              = $ErrorMessage
  generated_at       = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
}

try {
  $json = $payload | ConvertTo-Json -Depth 6
  [IO.File]::WriteAllText($jsonPath, $json, (New-Object Text.UTF8Encoding($false)))
} catch {
  Write-Output ('SCHEMA=everything-find/result/v1 TRANSPORT=' + $transportUsed + ' USED_ROUND=-1 HITS=0 RETURNED=0 TRUNCATED=0 JSON= ERROR=BAD_ARGS MSG=' + (($_.Exception.Message) -replace '\s+', '-'))
  exit 2
}

$truncFlag = 0
if ($truncated) { $truncFlag = 1 }
Write-Output "SCHEMA=everything-find/result/v1 TRANSPORT=$transportUsed USED_ROUND=$usedRound HITS=$totalHits RETURNED=$($results.Count) TRUNCATED=$truncFlag JSON=$jsonPath ERROR=$ErrorCode ESC=$escVersion EV=$evVersion"
exit $ExitCode
