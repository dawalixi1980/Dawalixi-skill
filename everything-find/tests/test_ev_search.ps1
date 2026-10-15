<#
  test_ev_search.ps1 —— everything-find 的搜索回归测试
  自建夹具(带中文的文件名)放进 %TEMP%\everything-find-tests,等 Everything 索引到,
  再跑 6 个场景。控制台只输出 ASCII,避免 PowerShell 5.1 中文编码问题。

  用法:powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_ev_search.ps1
  退出码:0 = 全部通过, 1 = 有失败
  注意:本文件必须保存为 UTF-8 with BOM。
#>
[CmdletBinding()]
param([string]$EsPath = 'C:\Program Files\Everything\es.exe')

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $here
$script = Join-Path $skillDir 'scripts\ev-search.ps1'
$fixtureDir = Join-Path $env:TEMP 'everything-find-tests'
$failures = New-Object System.Collections.ArrayList

function Assert-True {
  param([bool]$Condition, [string]$Case, [string]$Message)
  if ($Condition) { Write-Output ("  PASS " + $Message) }
  else {
    Write-Output ("  FAIL " + $Message)
    [void]$failures.Add($Case + ': ' + $Message)
  }
}

function Invoke-Ev {
  param([string[]]$EvArgs)
  $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $script @EvArgs
  $line = @($out | Where-Object { $_ -like 'SCHEMA=*' } | Select-Object -First 1)
  if ($line.Count -eq 0) { return $null }
  $line = $line[0]
  $json = ''
  $m = [regex]::Match($line, 'JSON=(\S+)')
  if ($m.Success) { $json = $m.Groups[1].Value }
  $obj = $null
  if ($json -and (Test-Path $json)) {
    try { $obj = Get-Content $json -Raw -Encoding UTF8 | ConvertFrom-Json } catch { $obj = $null }
  }
  return @{ line = $line; json = $json; obj = $obj }
}

# ---------------------------------------------------------------- 夹具
if (-not (Test-Path $fixtureDir)) { New-Item -ItemType Directory -Force -Path $fixtureDir | Out-Null }
# $env:TEMP 常是 8.3 短路径(C:\Users\ADMINI~1\...),而 Everything 的 -path 只认长路径 → 统一规范化
$fixtureDir = (Get-Item -LiteralPath $fixtureDir).FullName
Write-Output ('fixture dir: ' + $fixtureDir)
$f1 = Join-Path $fixtureDir 'EVFND-测试路基横断面设计图-2024.dwg'
$f2 = Join-Path $fixtureDir 'EVFND-路基防护设计图 (1).dwg'
$f3 = Join-Path $fixtureDir 'EVFND-电缆沟大样图.pdf'
foreach ($f in @($f1, $f2, $f3)) { Set-Content -Path $f -Value 'evfnd fixture' -Encoding ASCII }

Write-Output 'waiting for Everything to index fixtures ...'
$deadline = (Get-Date).AddSeconds(30)
$indexed = 0
while ((Get-Date) -lt $deadline) {
  $indexed = 0
  try { $indexed = [int](& $EsPath -get-result-count 'EVFND' 2>$null) } catch { $indexed = 0 }
  if ($indexed -ge 3) { break }
  Start-Sleep -Milliseconds 800
}
Write-Output ('indexed fixtures: ' + $indexed)
if ($indexed -lt 3) {
  Write-Output 'FAIL fixtures not indexed - Everything service/instance may be down'
  exit 1
}

# ---------------------------------------------------------------- 场景 1 精确命中
Write-Output 'case1 exact-name hit'
$r = Invoke-Ev @('-Query', 'EVFND-测试路基横断面设计图-2024')
Assert-True ($null -ne $r -and $null -ne $r.obj) 'case1' 'returns parsable JSON'
if ($r.obj) {
  Assert-True ($r.obj.error_code -eq 'NONE') 'case1' 'error_code is NONE'
  Assert-True ([int]$r.obj.total_hits -ge 1) 'case1' 'at least one hit'
  Assert-True ($r.obj.results[0].exact_name -eq $true) 'case1' 'rank1 exact_name is true'
  Assert-True ($r.obj.results[0].ext -eq 'dwg') 'case1' 'rank1 ext is dwg'
  Assert-True ($r.obj.results[0].path -eq $f1) 'case1' 'rank1 path equals fixture full path'
  Assert-True (Test-Path $r.obj.results[0].path) 'case1' 'rank1 path exists on disk'
}

# ---------------------------------------------------------------- 场景 2 近似误匹配 + 阶梯
Write-Output 'case2 noisy name triggers ladder'
$r = Invoke-Ev @('-Query', 'EVFND-测试路基横断面设计图-2024 副本3 (2)', '-Ladder')
Assert-True ($null -ne $r -and $null -ne $r.obj) 'case2' 'returns parsable JSON'
if ($r.obj) {
  Assert-True ($r.obj.error_code -eq 'NONE') 'case2' 'ladder recovered a result'
  Assert-True ([int]$r.obj.used_round -ge 1) 'case2' 'used_round advanced past R0'
  Assert-True (@($r.obj.rounds).Count -ge 2) 'case2' 'round log recorded more than one round'
  Assert-True (@($r.obj.rounds)[0].hits -eq 0) 'case2' 'R0 recorded zero hits'
  Assert-True ($r.obj.results[0].path -eq $f1) 'case2' 'ladder resolved to the exact fixture'
  Assert-True ([double]$r.obj.results[0].coverage_original -lt 1) 'case2' 'coverage_original penalises dropped words'
}

# ---------------------------------------------------------------- 场景 3 中文关键词 AND
Write-Output 'case3 chinese multi-term AND'
$r = Invoke-Ev @('-Query', 'EVFND 路基防护')
Assert-True ($null -ne $r -and $null -ne $r.obj) 'case3' 'returns parsable JSON'
if ($r.obj) {
  Assert-True ([int]$r.obj.total_hits -ge 1) 'case3' 'multi-term AND works (es.exe per-term args)'
  Assert-True (@($r.obj.results | Where-Object { $_.path -eq $f2 }).Count -eq 1) 'case3' 'finds the 路基防护 fixture'
  Assert-True (@($r.obj.results | Where-Object { -not (Test-Path $_.path) }).Count -eq 0) 'case3' 'every returned path exists'
}

# ---------------------------------------------------------------- 场景 4 无结果
Write-Output 'case4 no match'
$r = Invoke-Ev @('-Query', 'ZZQXJWV-9917-绝对不存在的东西', '-Ladder')
Assert-True ($null -ne $r -and $null -ne $r.obj) 'case4' 'returns parsable JSON'
if ($r.obj) {
  Assert-True ($r.obj.error_code -eq 'NO_MATCH') 'case4' 'error_code is NO_MATCH'
  Assert-True (@($r.obj.results).Count -eq 0) 'case4' 'no fabricated results'
  Assert-True (@($r.obj.rounds).Count -ge 1) 'case4' 'ladder attempts are logged'
  Assert-True ([int]$r.obj.used_round -eq -1) 'case4' 'used_round is -1'
}

# ---------------------------------------------------------------- 场景 5 目录 + 类型过滤
Write-Output 'case5 path and ext filter'
$r = Invoke-Ev @('-Query', 'EVFND', '-Path', $fixtureDir, '-Ext', 'dwg')
Assert-True ($null -ne $r -and $null -ne $r.obj) 'case5' 'returns parsable JSON'
if ($r.obj) {
  Assert-True ([int]$r.obj.total_hits -ge 2) 'case5' 'two dwg fixtures found'
  $outside = @($r.obj.results | Where-Object { -not $_.path.StartsWith($fixtureDir + '\') })
  Assert-True ($outside.Count -eq 0) 'case5' 'all results live under the path filter'
  $pdfInside = @($r.obj.results | Where-Object { $_.ext -ne 'dwg' })
  Assert-True ($pdfInside.Count -eq 0) 'case5' 'ext filter applied'
}

# ---------------------------------------------------------------- 场景 6 完整路径不变式
Write-Output 'case6 full-path invariant'
$r = Invoke-Ev @('-Query', 'EVFND-测试路基横断面设计图-2024')
if ($r.obj) {
  $bad = @($r.obj.results | Where-Object { -not [IO.Path]::IsPathRooted($_.path) })
  Assert-True ($bad.Count -eq 0) 'case6' 'every path is absolute'
  $missing = @($r.obj.results | Where-Object { -not (Test-Path $_.path) })
  Assert-True ($missing.Count -eq 0) 'case6' 'every path resolves on disk'
  Assert-True ($r.obj.schema -eq 'everything-find/result/v1') 'case6' 'result schema version present'
  Assert-True ($null -ne $r.obj.transport -and $r.obj.transport -ne 'none') 'case6' 'transport recorded'
}

Write-Output ''
if ($failures.Count -eq 0) {
  Write-Output 'ALL TESTS PASSED'
  exit 0
}
Write-Output ('FAILED: ' + $failures.Count + ' assertion(s)')
foreach ($f in $failures) { Write-Output ('  - ' + $f) }
exit 1
