# dwg-shot:无头 AutoCAD 出图(给视觉模型判读用)

**给一个 dwg → 出一张高清 PNG**,不需要人开 CAD、不弹窗、不碰用户正开着的图纸;
可选顺带抽出全图文字(图名/图号/说明),用来做"内容检索 + 图纸核对"。

## 为什么能"高清"

不是截屏,是 **CAD 引擎出矢量 PDF,再按目标像素宽度光栅化**。所以分辨率只是一个参数:

| 用途 | `-Width` | A3 出图实际尺寸 |
|---|---|---|
| 喂视觉模型判读(推荐) | 2000–2500 | 2400×1697 |
| 看清说明小字 / 打印 | 4000–6000 | 4961×3508(300dpi) |
| 极限 | 12000(上限) | 9921×7017(600dpi) |

视觉模型会自己降采样,**所以"框对内容 + 2000–2500px"比"整页 10000px"更清楚也更省钱**。

## 用法

```powershell
$S = "<skill>\scripts\dwg-shot.ps1"

# 最常用:自动模式 + 抽文字
-File $S -Path "H:\...\AD-03 一般路基设计图.dwg" -Text

# 一批:给目录或通配
-File $S -Path "Z:\archive\...\施工图" -Width 3000 -OutDir "D:\出图"
-File $S -Path "H:\projects\tree\*.dwg" -Mode layout

# 指定布局名 / 强制模型空间 + 手动窗口
-File $S -Path x.dwg -Mode layout -LayoutName "布局2"
-File $S -Path x.dwg -Mode model -Window "-569.6,871.8,339.9,1252.3"
```

控制台**只打 ASCII 摘要**(PS 5.1 打中文会乱),真实路径在 `manifest.json` 里:

```
FILE=dwg001 SRC=AD-03 一般路基设计图.dwg MODE=layout W=2400 H=1697 INK=2.116 PNG=<path> SECS=11 STATUS=OK
MANIFEST=<OutDir>\manifest.json FILES=1 FAILED=0
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `-Path` | 必填 | dwg 文件 / 目录(递归) / 通配 |
| `-Mode` | `auto` | `auto`=先布局,空页则回退模型;`layout`;`model` |
| `-LayoutName` | 空(=默认布局) | 图纸有多个布局时指定 |
| `-Paper` | `ISO full bleed A3 (420.00 x 297.00 毫米)` | 纸名必须与设备一致,可用 `?` 在 CAD 里列 |
| `-Width` | 2400 | 输出 PNG 目标宽度(px),400–12000 |
| `-Window` | 空(=自动算) | 模型空间出图窗口:`x1,y1,x2,y2` |
| `-Text` | 关 | 顺带抽全图文字到 `<tag>.text.txt` |
| `-KeepDxf` | 关 | 保留中间 DXF(默认删掉) |
| `-OutDir` | `%TEMP%\dwg-shot` | 每张图一堆 `<tag>.*` 产物 + `manifest.json` |
| `-AcadDir` | `E:\Autocad2022\AutoCAD 2022` | AutoCAD 安装目录(找 `accoreconsole.exe`) |
| `-TimeoutSec` | 180 | 单张超时 |
| `-MinInk` | 0.2 | 低于此墨量(%)判为空页 |

退出码:`0` 全成功 / `1` 部分失败 / `2` BAD_ARGS / `3` NO_ACAD。

## auto 模式怎么选

1. 先按**布局**出图 —— 真实交付图的 A3 图框、比例、标题栏、图名图号都在布局里;
2. 用 `png-check.py` 量墨量,< `-MinInk`(空白页,说明该布局没内容)则:
3. 回退**模型空间 + 自动窗口**:`compute-window.py` 从 DXF 迭代剔除离群实体(游离说明/图签),
   算出一块只包住主体图形的窗口,再出图。

实测(AD-03 一般路基设计图,450 KB):

| 出图方式 | 墨量 | 效果 |
|---|---|---|
| 布局 + A3 | **2.12%** | 图名/图号/表格/说明/尺寸全清晰 ← **首选** |
| 模型空间 + 范围(Extents) | 0.74% | 有字但很小,因为含游离图签 |
| 模型空间 + 自动窗口 | 0.59% | 剔掉了游离文字,但模型里两张断面本来相距很远 → 中间大片空白 |

**结论:能按布局出就按布局出;模型空间只适合单张、紧凑的图纸。**

## 实测踩过的坑(代码里都已处理)

1. **dwg 路径含中文 → accoreconsole 挂死**(无输出、不退出,我第一次挂了 4 分钟)。
   → 一律先复制到 ASCII 临时路径(`<OutDir>\dwgNNN.dwg`)再出图。
2. **`-PLOT` 应答链步数随空间不同**:图纸空间 19 步、模型空间(窗口)19 步,
   但**模型空间比图纸空间少"是否先打印图纸空间 / 是否隐藏图纸空间对象"两个提示**。
   多一个或少一个空行,答案就会错位到「输入文件名」上,然后**永远等你输入**。
   → 脚本把两条链写死(`New-PlotScript`),不要手改。
3. **中文版 AutoCAD 的提示里带英文键**(`[是(Y)/否(N)]`),所以答 `Y/N/M/L/E/F/C/W` 即可,
   不需要中文输入法。
4. **脚本文件必须 ANSI(GBK)编码**,因为纸名/布局名里有"毫米""模型";
   而 `dwg-shot.ps1` 本身必须 **UTF-8 with BOM**,否则 PS 5.1 按 ANSI 读会语法崩。
5. 出图用的 `accoreconsole.exe` 是 AutoCAD 的无界面引擎,**共享同一个许可证**;
   本机实测可与已运行的 CAD 并存。若许可证被占满,脚本会超时 → 报 `SHOT_FAIL`。

## 局限

- 依赖本机装了 AutoCAD(本机 2022,R24.1)。要完全脱离 AutoCAD,可换开源渲染器
  ([go-cad](https://github.com/unitedrhino/go-cad) / [cad2x-converter](https://github.com/orcastor/cad2x-converter)),
  代价是中文 SHX 渲染质量待验证。
- **不读图纸内容含义**,只出图;判断"这张图对不对"是 LLM/视觉模型的事。
- 一个布局一张图;多布局图纸目前只出默认布局(需要时用 `-LayoutName` 逐张跑)。
- 缺失的外部参照(图框)不会被补上,图框位置会空着或打出"外部参照未找到"的路径文本。
