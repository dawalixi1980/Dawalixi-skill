<#
  test_dwg_shot.ps1 —— dwg-shot.ps1 的回归测试

  用仓库里的真实图纸(cad 图纸\AD-03 一般路基设计图.dwg)跑一遍"布局出图 + 抽文字",
  断言:PNG 存在且宽度正确、墨量非空、模式选到 layout、文字里能读出图名与图号。

  用法:powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_dwg_shot.ps1
  退出码:0 = 全部通过, 1 = 有失败
  注意:本文件必须保存为 UTF-8 with BOM。
#>
[CmdletBinding()]
param(
  [string]$Fixture = '',
  [int]$Width = 2000
)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $here
$shot = Join-Path $skillDir 'scripts\dwg-shot.ps1'
$outDir = Join-Path $env:TEMP 'dwg-shot-test'
$failures = New-Object System.Collections.ArrayList

function Assert-True {
  param([bool]$Condition, [string]$Case, [string]$Message)
  if ($Condition) { Write-Output ("  PASS " + $Message) }
  else {
    Write-Output ("  FAIL " + $Message)
    [void]$failures.Add($Case + ': ' + $Message)
  }
}

if (-not $Fixture) {
  $Fixture = Join-Path (Split-Path -Parent $skillDir) 'cad 图纸\AD-03 一般路基设计图.dwg'
}
if (-not (Test-Path -LiteralPath $Fixture)) {
  Write-Output ("FAIL fixture not found: " + $Fixture)
  Write-Output '      (仓库根目录应存在 cad 图纸\AD-03 一般路基设计图.dwg)'
  exit 1
}
if (Test-Path -LiteralPath $outDir) { Remove-Item $outDir -Recurse -Force -ErrorAction SilentlyContinue }

Write-Output 'case1 run dwg-shot (auto + text)'
$sw = [Diagnostics.Stopwatch]::StartNew()
$raw = & powershell -NoProfile -ExecutionPolicy Bypass -File $shot -Path $Fixture -Text -Width $Width -OutDir $outDir 2>&1
$code = $LASTEXITCODE
$sw.Stop()
$lines = @($raw)
$lines | ForEach-Object { Write-Output ("  | " + $_) }
Assert-True ($code -eq 0) 'case1' ("exit code is 0 (got " + $code + ")")
Assert-True ($sw.Elapsed.TotalSeconds -lt 180) 'case1' 'finished within 180s'

$manifest = Join-Path $outDir 'manifest.json'
Assert-True (Test-Path -LiteralPath $manifest) 'case1' 'manifest.json written'

$rec = $null
if (Test-Path -LiteralPath $manifest) {
  try { $rec = (Get-Content $manifest -Raw -Encoding UTF8 | ConvertFrom-Json).results[0] } catch { $rec = $null }
}
Assert-True ($null -ne $rec) 'case1' 'manifest has one result'

if ($rec) {
  Write-Output 'case2 image quality'
  Assert-True (Test-Path -LiteralPath $rec.png) 'case2' 'PNG file exists'
  Assert-True ([math]::Abs([int]$rec.width - $Width) -le 2) 'case2' ("PNG width is ~" + $Width)
  Assert-True ([int]$rec.height -gt 400) 'case2' 'PNG height sane'
  Assert-True ([double]$rec.ink -ge 1.0) 'case2' ("ink coverage >= 1% (got " + $rec.ink + ")")
  Assert-True ($rec.mode_used -eq 'layout') 'case2' 'auto mode picked layout'
  Assert-True ($rec.status -eq 'OK') 'case2' 'status is OK'
  Assert-True (Test-Path -LiteralPath $rec.pdf) 'case2' 'vector PDF kept'

  Write-Output 'case3 text extraction'
  Assert-True ($rec.text -ne '' -and (Test-Path -LiteralPath $rec.text)) 'case3' 'text file exists'
  if ($rec.text -and (Test-Path -LiteralPath $rec.text)) {
    $txt = Get-Content -LiteralPath $rec.text -Raw -Encoding UTF8
    Assert-True ($txt -match '路基一般设计图') 'case3' 'text contains 图名 (路基一般设计图)'
    Assert-True ($txt -match 'AD-03') 'case3' 'text contains 图号 (AD-03)'
  }
}

Write-Output ''
if ($failures.Count -eq 0) {
  Write-Output 'ALL TESTS PASSED'
  exit 0
}
Write-Output ("FAILED: " + $failures.Count + " assertion(s)")
foreach ($f in $failures) { Write-Output ("  - " + $f) }
exit 1
