<#
  install.ps1 —— 把 everything-find 装到 DSH 的 skill 目录
  ------------------------------------------------------------------
  默认安装到 $env:DSH_HOME\skills\everything-find(拷贝,不建 junction)。
  顺带确保 es.exe 可用(缺失时从 voidtools 官方地址下载到 $env:DSH_HOME\tools\everything\)。
  安装后自动跑契约校验 + 搜索回归测试。

  用法:
    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Remove
  注意:本文件必须保存为 UTF-8 with BOM。
#>
[CmdletBinding()]
param(
  [switch]$Remove,
  [switch]$SkipTests
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:DSH_HOME) { $env:DSH_HOME = Join-Path $env:USERPROFILE '.dsh' }
$skillsRoot = Join-Path $env:DSH_HOME 'skills'
$dst = Join-Path $skillsRoot 'everything-find'
$esTarget = Join-Path $env:DSH_HOME 'tools\everything\es.exe'
$esZipUrl = 'https://www.voidtools.com/ES-1.1.0.27.zip'

# --- 安全闸:目标路径必须是我们认得的那个
$expectedTail = 'skills\everything-find'
if (-not $dst.EndsWith($expectedTail)) {
  Write-Output ("ABORT: refusing to touch unexpected path: " + $dst)
  exit 2
}

if ($Remove) {
  if (Test-Path $dst) {
    Remove-Item -Path $dst -Recurse -Force
    Write-Output ("removed skill: " + $dst)
  } else {
    Write-Output ("nothing to remove: " + $dst)
  }
  exit 0
}

# --- 1. 确保 es.exe
$esCandidates = @('C:\Program Files\Everything\es.exe', $esTarget)
$esFound = ''
foreach ($c in $esCandidates) { if (Test-Path $c) { $esFound = $c; break } }
if (-not $esFound) {
  Write-Output 'es.exe not found - downloading from voidtools ...'
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $esTarget) | Out-Null
  $zip = Join-Path $env:TEMP 'everything-find-es.zip'
  Invoke-WebRequest -Uri $esZipUrl -OutFile $zip -UseBasicParsing -TimeoutSec 120
  $tmp = Join-Path $env:TEMP 'everything-find-es'
  if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
  Expand-Archive -Path $zip -DestinationPath $tmp -Force
  $es = Get-ChildItem $tmp -Recurse -Filter 'es.exe' | Select-Object -First 1
  Copy-Item $es.FullName $esTarget -Force
  $esFound = $esTarget
  Write-Output ("installed es.exe: " + $esTarget)
} else {
  Write-Output ("es.exe found: " + $esFound)
}
$esVersion = (& $esFound -version 2>$null | Out-String).Trim()
Write-Output ("es.exe version: " + $esVersion)

# --- 2. 拷贝 skill
if (-not (Test-Path $skillsRoot)) { New-Item -ItemType Directory -Force -Path $skillsRoot | Out-Null }
if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
Copy-Item -Path $src -Destination $dst -Recurse -Force
Get-ChildItem $dst -Recurse -Directory | Where-Object { $_.Name -eq '__pycache__' } | ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
Write-Output ("installed skill: " + $dst)

# --- 3. 校验 + 测试
# 注意:python unittest 会把日志写到 stderr,PowerShell 在 $ErrorActionPreference='Stop' 下
# 会把原生命令的 stderr 当成终止性错误(NativeCommandError),所以这里显式降级为 Continue 再还原。
function Invoke-Capture {
  param([scriptblock]$Block)
  $prev = $ErrorActionPreference
  $ErrorActionPreference = 'Continue'
  $out = & $Block 2>&1
  $code = $LASTEXITCODE
  $ErrorActionPreference = $prev
  return @{ out = @($out); code = $code }
}

$failed = 0
$validator = Join-Path $dst 'scripts\validate_skill.py'
if (Test-Path $validator) {
  $r = Invoke-Capture { & python $validator $dst }
  $r.out | ForEach-Object { Write-Output ("[validate] " + $_) }
  if ($r.code -ne 0) { $failed = 1 }
}

$pythonTest = Join-Path $dst 'tests\test_validate_skill.py'
if ((Test-Path $pythonTest) -and (-not $SkipTests)) {
  $r = Invoke-Capture { & python $pythonTest }
  $r.out | Select-Object -Last 4 | ForEach-Object { Write-Output ("[validator-test] " + $_) }
  if ($r.code -ne 0) { $failed = 1 }
}

$searchTest = Join-Path $dst 'tests\test_ev_search.ps1'
if ((Test-Path $searchTest) -and (-not $SkipTests)) {
  $r = Invoke-Capture { & powershell -NoProfile -ExecutionPolicy Bypass -File $searchTest -EsPath $esFound }
  $r.out | ForEach-Object { Write-Output ("[search-test] " + $_) }
  if ($r.code -ne 0) { $failed = 1 }
}

if ($failed -ne 0) {
  Write-Output 'INSTALL DONE WITH FAILURES - see output above'
  exit 1
}
Write-Output 'INSTALL OK'
Write-Output ('skill dir : ' + $dst)
Write-Output ('es.exe    : ' + $esFound)
Write-Output 'note: 实测 DSH 会话内即可看到新技能(技能目录会在会话中途刷新);若未出现,新开一个会话。'
exit 0
