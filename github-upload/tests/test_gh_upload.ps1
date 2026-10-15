<#
  test_gh_upload.ps1 —— gh-upload.ps1 的离线回归测试(不联网、不写远端)

  覆盖:编码转义自检 / 干跑清单 / 参数错误 / 密钥自查拦截。
  用法:powershell -NoProfile -ExecutionPolicy Bypass -File tests\test_gh_upload.ps1
  退出码:0 = 全部通过, 1 = 有失败
  注意:本文件必须保存为 UTF-8 with BOM。
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $here
$script = Join-Path $skillDir 'scripts\gh-upload.ps1'
$failures = New-Object System.Collections.ArrayList

function Assert-True {
  param([bool]$Condition, [string]$Case, [string]$Message)
  if ($Condition) { Write-Output ("  PASS " + $Message) }
  else {
    Write-Output ("  FAIL " + $Message)
    [void]$failures.Add($Case + ': ' + $Message)
  }
}

function Invoke-Upload {
  param([string[]]$UploadArgs)
  $out = & powershell -NoProfile -ExecutionPolicy Bypass -File $script @UploadArgs 2>&1
  return @{ out = @($out); code = $LASTEXITCODE }
}

Write-Output 'case1 离线自检(中文转义)'
$r = Invoke-Upload @('-SelfTest')
Assert-True ($r.code -eq 0) 'case1' ('exit 0 (got ' + $r.code + ')')
Assert-True (@($r.out | Where-Object { $_ -like 'ESCTEST=PASS' }).Count -eq 1) 'case1' 'ESCTEST=PASS(非 ASCII 转 \\uXXXX)'

Write-Output 'case2 干跑:列出将上传的文件,不碰网络'
$r = Invoke-Upload @('-Repo', 'owner/name', '-Source', $skillDir, '-DryRun')
Assert-True ($r.code -eq 0) 'case2' ('exit 0 (got ' + $r.code + ')')
$fileLines = @($r.out | Where-Object { $_ -like 'FILE=*' })
Assert-True ($fileLines.Count -ge 10) 'case2' ('FILE= 清单 >=10 条(实际 ' + $fileLines.Count + ')')
Assert-True (@($r.out | Where-Object { $_ -like 'PREFIX=*COMMIT=DRYRUN*' }).Count -eq 1) 'case2' '输出带 COMMIT=DRYRUN'
Assert-True (@($fileLines | Where-Object { $_ -match '\.git/' }).Count -eq 0) 'case2' '排除 .git'
Assert-True (@($fileLines | Where-Object { $_ -match '__pycache__' }).Count -eq 0) 'case2' '排除 __pycache__'
Assert-True (@($fileLines | Where-Object { $_ -match 'SKILL\.md' }).Count -eq 1) 'case2' '包含 SKILL.md'

Write-Output 'case3 参数错误:仓库名不带 owner'
$r = Invoke-Upload @('-Repo', 'justname', '-Source', $skillDir, '-DryRun')
Assert-True ($r.code -eq 2) 'case3' ('exit 2 (got ' + $r.code + ')')
Assert-True (@($r.out | Where-Object { $_ -match 'BAD_ARGS' }).Count -ge 1) 'case3' '报 BAD_ARGS'

Write-Output 'case4 参数错误:目录不存在'
$r = Invoke-Upload @('-Repo', 'owner/name', '-Source', (Join-Path $env:TEMP 'no-such-dir-xyz'), '-DryRun')
Assert-True ($r.code -eq 2) 'case4' ('exit 2 (got ' + $r.code + ')')

Write-Output 'case5 密钥自查:疑似 token 必须拒传'
$tmp = Join-Path $env:TEMP 'gh-upload-secret-test'
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
# 假 token 在运行时拼出来:测试文件自身若含完整 token 字面量,会被密钥自查命中(自己拦自己)
$fake = 'ghp_' + (('A' * 36) -join '')
Set-Content -Path (Join-Path $tmp 'leak.txt') -Value ("token = " + $fake) -Encoding ASCII
$r = Invoke-Upload @('-Repo', 'owner/name', '-Source', $tmp, '-DryRun')
Assert-True ($r.code -eq 6) 'case5' ('exit 6 (got ' + $r.code + ')')
Assert-True (@($r.out | Where-Object { $_ -match 'SECRET_SUSPECT' }).Count -ge 1) 'case5' '报 SECRET_SUSPECT'
$r2 = Invoke-Upload @('-Repo', 'owner/name', '-Source', $tmp, '-DryRun', '-AllowSecrets')
Assert-True ($r2.code -eq 0) 'case5' ('-AllowSecrets 后可继续 (got ' + $r2.code + ')')
Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue

Write-Output ''
if ($failures.Count -eq 0) { Write-Output 'ALL TESTS PASSED'; exit 0 }
Write-Output ('FAILED: ' + $failures.Count + ' assertion(s)')
foreach ($f in $failures) { Write-Output ('  - ' + $f) }
exit 1
