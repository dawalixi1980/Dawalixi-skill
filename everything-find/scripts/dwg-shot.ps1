<#
  dwg-shot.ps1 —— 无头 AutoCAD 出图:一个/一批 dwg → 高清 PNG(可选附带文字清单)

  为什么不用传统 CAD:accoreconsole.exe 是 AutoCAD 的无界面引擎,同一套渲染与字体
  (SHX 汉字 100% 保真),不弹窗、不碰用户正开着的图纸;脚本驱动出 PDF(矢量),
  再用 PyMuPDF 光栅化到任意像素宽度 —— "高清"只是 -Width 一个参数。

  默认策略(auto):先按【布局】出图(真实交付图的 A3 图框/比例/标题栏都在布局里),
  若该页墨量低于 -MinInk(判定为空页),回退到【模型空间 + 自动窗口】出图。

  实测坑(都已在代码里处理):
    1. dwg 路径含中文会让 accoreconsole 挂死 → 一律先复制到 ASCII 临时路径再出图;
    2. -PLOT 应答链步数不同:图纸空间 19 步、模型空间(窗口)也 19 步;多/少一个空行就会
       把答案错位到「输入文件名」提示上,然后永远等你输入 → 本脚本按实测链写死;
    3. 中文版提示里带英文键([是(Y)/否(N)]),答 Y/N/M/L/E/F/C/W 即可;
    4. 脚本文件必须用 ANSI(GBK)写,因为纸名里有"毫米"。

  输出(控制台只打 ASCII,避免 PS 5.1 中文编码问题),每张一行:
      FILE=<tag> SRC=<basename> MODE=layout W=2400 H=1697 INK=2.12 PNG=<path> PDF=<path> TXT=<path> SECS=42 STATUS=OK
  明细(真实路径、窗口、日志)写在 <OutDir>\manifest.json(UTF-8),用 read 工具读。

  退出码:0 = 全部成功  1 = 部分失败  2 = BAD_ARGS  3 = NO_ACAD
  本文件必须保存为 UTF-8 with BOM(PowerShell 5.1 否则按 ANSI 读会语法崩)。
#>
[CmdletBinding()]
param(
  [Parameter(Mandatory = $true, Position = 0)][string[]]$Path,
  [ValidateSet('auto', 'layout', 'model')][string]$Mode = 'auto',
  [string]$LayoutName = '',
  [string]$Paper = 'ISO full bleed A3 (420.00 x 297.00 毫米)',
  [int]$Width = 2400,
  [string]$Window = '',
  [switch]$Text,
  [switch]$KeepDxf,
  [string]$OutDir = '',
  [string]$AcadDir = 'E:\Autocad2022\AutoCAD 2022',
  [int]$TimeoutSec = 180,
  [double]$MinInk = 0.2
)

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$pyPdf2Png = Join-Path $here 'pdf2png.py'
$pyPngCheck = Join-Path $here 'png-check.py'
$pyWindow = Join-Path $here 'compute-window.py'
$pyText = Join-Path $here 'dxf-text.py'
$accore = Join-Path $AcadDir 'accoreconsole.exe'

if (-not (Test-Path -LiteralPath $accore)) {
  Write-Output ("SCHEMA=dwg-shot/v1 ERROR=NO_ACAD ACCORE=" + $accore)
  exit 3
}

# ---------------------------------------------------------------- 输入解析
$files = New-Object System.Collections.ArrayList
foreach ($p in $Path) {
  if ([string]::IsNullOrWhiteSpace($p)) { continue }
  if (Test-Path -LiteralPath $p -PathType Container) {
    foreach ($f in (Get-ChildItem -LiteralPath $p -Filter '*.dwg' -File -Recurse -ErrorAction SilentlyContinue)) { [void]$files.Add($f) }
  }
  elseif ($p -match '[\*\?]') {
    foreach ($f in (Get-ChildItem -Path $p -File -ErrorAction SilentlyContinue)) { [void]$files.Add($f) }
  }
  elseif (Test-Path -LiteralPath $p) {
    [void]$files.Add((Get-Item -LiteralPath $p))
  }
}
if ($files.Count -eq 0) {
  Write-Output 'SCHEMA=dwg-shot/v1 ERROR=BAD_ARGS MSG=no-dwg-matched'
  exit 2
}
if ($Width -lt 400) { $Width = 400 }
if ($Width -gt 12000) { $Width = 12000 }

if (-not $OutDir) { $OutDir = Join-Path $env:TEMP 'dwg-shot' }
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$OutDir = (Get-Item -LiteralPath $OutDir).FullName

$results = New-Object System.Collections.ArrayList
$failed = 0
$idx = 0

# ---------------------------------------------------------------- 辅助函数
function New-AsciiCopy([string]$source, [string]$target) {
  try { Copy-Item -LiteralPath $source -Destination $target -Force; return $true } catch { return $false }
}

function Invoke-Acc([string]$dwg, [string]$scr, [string]$tag, [int]$timeoutSec) {
  $outFile = Join-Path $OutDir ("$tag.acc.log")
  if (Test-Path $outFile) { Remove-Item $outFile -Force -ErrorAction SilentlyContinue }
  $p = Start-Process -FilePath $accore -ArgumentList @('/i', $dwg, '/s', $scr) `
    -RedirectStandardOutput $outFile -RedirectStandardError (Join-Path $OutDir "$tag.acc.err") `
    -PassThru -NoNewWindow
  $done = $p.WaitForExit($timeoutSec * 1000)
  if (-not $done) { try { Stop-Process -Id $p.Id -Force } catch { } }
  # accoreconsole 的 stdout 是 UTF-16LE,转成 UTF-8 便于 read 工具查看
  try {
    (Get-Content $outFile -Encoding Unicode -ErrorAction SilentlyContinue) |
      Set-Content (Join-Path $OutDir "$tag.acc.txt") -Encoding UTF8
  } catch { }
  return $done
}

function New-PlotScript([string]$kind, [string]$pdf, [string]$paper, [string]$layout, [string]$win) {
  $head = @('FILEDIA', '0', 'CMDDIA', '0', '-PLOT', 'Y')
  if ($kind -eq 'layout') {
    $body = @($layout, 'DWG To PDF.pc3', $paper, 'M', 'L', 'N', 'E', 'F', 'C', '', '', '', '', '', '', $pdf, 'N', 'Y')
    return $head + $body
  }
  $area = @()
  if ($win) {
    $c = $win -split ','
    if ($c.Count -eq 4) { $area = @('W', ($c[0] + ',' + $c[1]), ($c[2] + ',' + $c[3])) }
  }
  if ($area.Count -eq 0) { $area = @('E') }
  $body = @('模型', 'DWG To PDF.pc3', $paper, 'M', 'L', 'N') + $area + @('F', 'C', '', '', '', '', $pdf, 'N', 'Y')
  return $head + $body
}

function New-DxfScript([string]$dxf) {
  return @('FILEDIA', '0', 'CMDDIA', '0', 'DXFOUT', $dxf, '16')
}

function Write-Script([string[]]$lines, [string]$path) {
  # 必须 ANSI(GBK):纸名/布局名里有中文
  $lines | Set-Content -Path $path -Encoding Default
}

function Get-PdfToPng([string]$pdf, [string]$png, [int]$width) {
  $r = & python $pyPdf2Png $pdf $png "$width" 2>&1
  $line = @($r | Where-Object { $_ -like 'PDF2PNG_OK*' } | Select-Object -First 1)
  if ($line.Count -eq 0) { return $null }
  $parts = $line[0] -split '\s+'
  return @{ w = [int]$parts[1]; h = [int]$parts[2]; pages = [int]$parts[3] }
}

function Get-Ink([string]$png) {
  $r = & python $pyPngCheck $png 2>&1
  $line = @($r | Where-Object { $_ -like 'IMG_OK*' } | Select-Object -First 1)
  if ($line.Count -eq 0) { return -1.0 }
  $m = [regex]::Match($line[0], 'ink=([0-9.]+)%')
  if ($m.Success) { return [double]$m.Groups[1].Value }
  return -1.0
}

# ---------------------------------------------------------------- 主循环
foreach ($f in $files) {
  $idx++
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $tag = 'dwg{0:d3}' -f $idx
  $srcPath = $f.FullName
  $asciiDwg = Join-Path $OutDir ("$tag.dwg")
  $pdfLay = Join-Path $OutDir ("$tag.layout.pdf")
  $pdfMod = Join-Path $OutDir ("$tag.model.pdf")
  $pngLay = Join-Path $OutDir ("$tag.layout.png")
  $pngMod = Join-Path $OutDir ("$tag.model.png")
  $dxfPath = Join-Path $OutDir ("$tag.dxf")
  $txtPath = Join-Path $OutDir ("$tag.text.txt")
  $logPath = Join-Path $OutDir ("$tag.acc.txt")

  $rec = [ordered]@{
    tag = $tag; src = $srcPath; mode_requested = $Mode; mode_used = '';
    pdf = ''; png = ''; text = ''; dxf = ''; width = 0; height = 0; ink = 0.0;
    window = ''; status = 'OK'; seconds = 0; log = $logPath
  }

  if (-not (New-AsciiCopy $srcPath $asciiDwg)) {
    $rec.status = 'COPY_FAIL'; $rec.seconds = [int]$sw.Elapsed.TotalSeconds
    [void]$results.Add($rec); $failed++; continue
  }

  $modeUsed = ''
  $pngOut = ''
  $pdfOut = ''
  $ink = -1.0
  $dims = $null

  # 1) 布局出图
  if ($Mode -eq 'auto' -or $Mode -eq 'layout') {
    $scr = Join-Path $OutDir ("$tag.layout.scr")
    Write-Script (New-PlotScript 'layout' $pdfLay $Paper $LayoutName '') $scr
    [void](Invoke-Acc $asciiDwg $scr $tag $TimeoutSec)
    if (Test-Path -LiteralPath $pdfLay) {
      $dims = Get-PdfToPng $pdfLay $pngLay $Width
      $ink = Get-Ink $pngLay
      if ($null -ne $dims) { $modeUsed = 'layout'; $pngOut = $pngLay; $pdfOut = $pdfLay }
    }
  }

  # 2) 空页或指定 model → 模型空间 + 自动窗口
  $needModel = ($Mode -eq 'model') -or ($Mode -eq 'auto' -and ($modeUsed -eq '' -or $ink -lt $MinInk))
  if ($needModel) {
    if (-not (Test-Path -LiteralPath $dxfPath)) {
      $scrD = Join-Path $OutDir ("$tag.dxf.scr")
      Write-Script (New-DxfScript $dxfPath) $scrD
      [void](Invoke-Acc $asciiDwg $scrD $tag $TimeoutSec)
    }
    $win = $Window
    if (-not $win -and (Test-Path -LiteralPath $dxfPath)) {
      $rw = & python $pyWindow $dxfPath 2>&1
      $ml = @($rw | Where-Object { $_ -like 'WINDOW *' } | Select-Object -First 1)
      if ($ml.Count -gt 0) { $win = $ml[0].Substring(7).Trim() }
    }
    $scrM = Join-Path $OutDir ("$tag.model.scr")
    Write-Script (New-PlotScript 'model' $pdfMod $Paper '模型' $win) $scrM
    [void](Invoke-Acc $asciiDwg $scrM $tag $TimeoutSec)
    if (Test-Path -LiteralPath $pdfMod) {
      $d2 = Get-PdfToPng $pdfMod $pngMod $Width
      $ink2 = Get-Ink $pngMod
      if ($null -ne $d2) {
        $modeUsed = 'model'; $pngOut = $pngMod; $pdfOut = $pdfMod; $dims = $d2; $ink = $ink2
        $rec.window = $win
      }
    }
  }

  # 3) 文字清单(可选)
  if ($Text) {
    if (-not (Test-Path -LiteralPath $dxfPath)) {
      $scrD = Join-Path $OutDir ("$tag.dxf.scr")
      Write-Script (New-DxfScript $dxfPath) $scrD
      [void](Invoke-Acc $asciiDwg $scrD $tag $TimeoutSec)
    }
    if (Test-Path -LiteralPath $dxfPath) {
      [void](& python $pyText $dxfPath $txtPath 2>&1)
      if (Test-Path -LiteralPath $txtPath) { $rec.text = $txtPath }
    }
  }

  if ($KeepDxf -and (Test-Path -LiteralPath $dxfPath)) { $rec.dxf = $dxfPath }
  elseif (-not $KeepDxf -and (Test-Path -LiteralPath $dxfPath)) { Remove-Item $dxfPath -Force -ErrorAction SilentlyContinue }

  if ($modeUsed -eq '') {
    $rec.status = 'SHOT_FAIL'
    $failed++
  } else {
    $rec.mode_used = $modeUsed
    $rec.pdf = $pdfOut
    $rec.png = $pngOut
    $rec.ink = [math]::Round($ink, 3)
    if ($null -ne $dims) { $rec.width = $dims.w; $rec.height = $dims.h }
    if ($ink -ge 0 -and $ink -lt $MinInk) { $rec.status = 'BLANK_PAGE' }
  }
  $rec.seconds = [int]$sw.Elapsed.TotalSeconds
  [void]$results.Add($rec)

  Write-Output ("FILE=$tag SRC=" + $f.Name + " MODE=$($rec.mode_used) W=$($rec.width) H=$($rec.height) INK=$($rec.ink) PNG=$($rec.png) SECS=$($rec.seconds) STATUS=$($rec.status)")
}

$manifest = Join-Path $OutDir 'manifest.json'
try {
  @{ schema = 'dwg-shot/v1'; generated_at = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'); out_dir = $OutDir; results = @($results) } |
    ConvertTo-Json -Depth 5 | Set-Content -Path $manifest -Encoding UTF8
} catch { }

Write-Output ("MANIFEST=$manifest FILES=$($results.Count) FAILED=$failed")
if ($failed -gt 0) { exit 1 }
exit 0
