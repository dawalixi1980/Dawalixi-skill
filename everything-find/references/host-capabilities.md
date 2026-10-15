# 宿主能力契约 与 降级路径

本 skill 的搜索能力**依赖本机已有的 Everything**;它不自带索引、不自己遍历磁盘。三条路径按顺序探测,任一条通了就用它,并如实报告用的是哪条。

## 三条路径

| 优先级 | 路径 | 前提 | 实测状态 |
|---|---|---|---|
| 1 | **es.exe IPC** | `C:\Program Files\Everything\es.exe` 存在,且 Everything 本体在运行(两个进程:`-svc` 服务 + `-startup` 用户实例) | ✅ 已验证(1.1.0.27 ↔ 1.4.1.1032) |
| 2 | **Everything HTTP** | 本体启动时带了 HTTP 服务(`http_server_enabled=1`),且机器级策略 `allow_http_server=1`,监听 `127.0.0.1:8017` | ⚠️ 当前**未启用**(策略为 0 + 实例未重启),脚本已实现但未验证 |
| 3 | 都没有 | — | 报 `TOOL_UNAVAILABLE` |

## 探测方式

```powershell
# 路径 1
& 'C:\Program Files\Everything\es.exe' -get-everything-version   # 出 1.4.1.1032 即通
# 路径 2
Invoke-WebRequest 'http://127.0.0.1:8017/?search=es-test&json=1&count=1' -UseBasicParsing
```

脚本 `-Transport auto` 会自己按 1 → 2 探测,并在 JSON 的 `transport` 字段写明实际用了哪条。

## 降级损失(必须如实说明,不许假装)

| 缺失能力 | 损失 | 交付时必须写 |
|---|---|---|
| 无 es.exe,只有 HTTP | 单次查询延迟变高;`-get-result-count`/`-get-total-size` 等聚合能力受限 | "本次走 HTTP 接口" |
| 无 HTTP,只有 es.exe | 无(es 是一等公民) | 不必提 |
| 两者都不可用 | 无法搜索 | `TOOL_UNAVAILABLE` + 给出 `es.exe` 期望路径与"Everything 是否在运行"的检查方法;**绝不输出任何候选** |
| 索引未覆盖目标盘 | 该盘文件搜不到 | 在结论里注明"索引覆盖 C:/D:/E:/F:/G:/H:/I:/K: 与 Z:\" |
| Z:\ 是网络盘(文件夹索引) | 新增文件有延迟 | 提示"刚放进 Z: 的文件可能还没进索引" |

## 能力记录(每次交付的内部字段,不必全打给用户)

```
transport; edge_version(es); everything_version; 索引覆盖范围; 是否有候选被 -Count 截断; 阶梯是否被触发
```
