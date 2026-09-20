---
name: windows-hardlink-dedup-verify
description: Windows/NTFS 批量资产的硬链接去重安全流程——把逐字节相同的重复文件转成硬链接省磁盘，同时证明「按文件名引用的消费方（画廊/静态站/gallery index/图片墙）零破坏」。当用户想去重/省空间/清理重复文件但担心删了断链、磁盘被大量同内容资产占满、或明确说「硬链接去重」时使用。触发词：硬链接去重、hardlink、重复文件省空间、删重复怕断链、按文件名引用不能删、去重后校验画廊能打开、逐字节重复。
version: 1.0.0
---

# Windows 硬链接去重 + 三重校验安全流程

把一批**逐字节相同**的重复文件转成 NTFS 硬链接：磁盘只存一份数据，但每个文件路径都还在、读出来字节一模一样。核心区别于「删重复文件」——画廊的 `index.json` / 静态站的 `<img src>` 是**按文件名引用**的，直接删会断链显示不出来；硬链接去重后原路径依然能正常读，前端一行都不用改。

正因为消费方按文件名引用，去重的**成败判据不是「省了多少」，而是「受影响路径经本地 http.server 仍能 200 打开、字节与哈希一致」**。本技能用可复跑的脚本把这条判据钉死。

## 何时使用

- 资产目录里有大量逐字节相同的重复文件（如 `npcX`==`X`、`_asmr`/`_hx` 变体==本体、三视图同图），想省磁盘但不能删。
- 磁盘被只读批量产物占满，重复率高。
- 用户明确要「硬链接去重」，并要求「去重后逐组校验画廊/网页能正常打开」。

## 不适用

- 需要跨卷/跨盘去重（硬链接只能在**同一分区/卷**内）。
- 文件内容会各自被独立修改（硬链接共享数据，改一个=改全部；只读归档资产才安全）。
- 只是想删文件腾空间、且消费方不依赖文件名（用普通回收站删除即可，无需本流程）。
- 近似重复（视觉相似但字节不同）——本技能只处理**逐字节相同**，不做感知哈希。

## 前置约定

- Python 3（`os.link` 在 Windows 上创建硬链接），需在同一 NTFS 卷内。
- 三个脚本在 `scripts/` 下，通过环境变量 `DEDUP_ROOT`（产物根目录）与 `.diag/_dedup_plan.json` 传递方案；按需改脚本顶部 `DIRS`（要扫描的子目录列表）与扩展名。
- 遵守「先只读出方案 → 小样本 → 用户确认 → 全量」的项目红线：未展示小样本结果前不得全量。

## 工作流（5 步）

### 1. 只读扫描，生成去重方案

跑 `scripts/dedup_plan.py`。它按 **size 分组 → 同尺寸算 sha256 → 组内真实字节比对确认逐字节相同 → 跳过已互为硬链（同 `st_ino`）→ 每组选一个 canonical**，输出 `.diag/_dedup_plan.json` 与人类汇总（组数 / 重复文件数 / 预估可省空间）。不落盘任何资产改动。

```
cd "<项目根>"
DEDUP_ROOT="Output" PYTHONIOENCODING=utf-8 py -3 scripts/dedup_plan.py
```

把汇总（尤其是重复对是否都是**真实冗余**）展示给用户确认后再进入第 2 步。

### 2. 小样本试链（1–3 组）

跑 `scripts/dedup_apply.py 2`（参数 = 前 N 组，或 `all`）。逐 dup 流程：**建链前再次真实字节复核 → `os.remove` + `os.link` → 失败自动回退 `copy` → 逐文件校验 `nlink≥2` + sha256 与 canonical 全等**。把已应用路径写进 `.diag/_dedup_applied.txt`。期望「N 文件建链、0 问题」。

### 3. 端到端 HTTP 校验（小样本）

跑 `scripts/dedup_httpverify.py`：进程内起 `ThreadingHTTPServer` 根于产物目录，GET `_dedup_applied.txt` 里每个受影响路径，核对 **HTTP 200 + Content-Length + 下载字节 sha256 三重一致**。这一步证明硬链文件经画廊的 http.server 能正常打开——是「画廊零破坏」的直接证据。期望 `x/x 全部通过`。

### 4. 全量应用 + 全量校验

确认后跑 `scripts/dedup_apply.py all`，再对**全部**受影响路径重跑第 3 步。

> 幂等性：`all` 会把小样本那几组再处理一遍。已链的 dup 此时 `st_nlink` 已 >1，`remove`+`link` 回来是无害的，`freed` 因测的是 nlink 增量而**不重复计**——所以全量实际释放会略低于「小样本+预估」之和，属正常，不是丢链。

### 5. 磁盘实占核对 + 记录

按 inode 去重统计各目录 **logical（Σsize）vs physical（Σsize/nlink）**，抽样确认 `nlink>1`，核对物理实省 ≈ 方案预估。更新项目状态文档（一行记录：组数/重复数/实省/校验通过）并提交。去重脚本可留在 `.diag`（或 `scripts/`）供产物更新时复用。

## 三重校验的含义（为什么缺一不可）

- **逐文件 `nlink≥2` + sha256**：证明硬链真的生效、且内容与 canonical 逐字节相同。
- **本地 http.server GET 200**：证明按文件名引用的消费方（画廊/静态站）仍能解析并打开该路径——这是「不删只链」相对「删重复」的核心优势。
- **Content-Length + 下载哈希一致**：证明服务端读出的是完整正确字节，没有因链接/编码问题被截断。

## Pitfalls（踩过的坑）

- **`send2trash` 未安装**：主流程不删文件用不到它；但配套的「回收站兜底删除」若需要，别依赖 `send2trash`，改用 PowerShell `Microsoft.VisualBasic.FileIO.FileSystem::DeleteFile/DeleteItem(..., 'OnlyErrorDialogs', 'SendToRecycleBin')`。
- **PowerShell `-File` 模式类型字面量绑定失败**：`[Microsoft.VisualBasic.FileIO.FileSystem]` 在 `-File` 脚本里于**解析期**就绑定，报「找不到类型」。加 `-NoProfile` 屏蔽用户 profile 干扰，并改用 `powershell -NoProfile -Command '...'`（bash 用**单引号**包裹、`$` 原样传给 PS，规避引号地狱），`-Command` 模式下类型可正常加载。
- **跨卷**：硬链接只能同分区/卷；跨盘会 `OSError`，此时应放弃而非静默 copy（脚本已把失败回退为 copy 并计数，需检查回退数是否 >0）。
- **误把近似重复当重复**：一定做真实字节比对，不能只信 size 或只信 sha256（sha256 命中后再 open+read 逐字节确认）。
- **freed 统计偏低误判为失败**：见第 4 步幂等说明，重跑已链组不重复计属正常。
- **别与软链/快捷方式混**：软链是指针，目标没了就失效；硬链与正常文件几乎无差别，`http.server`/`<img>` 直接当普通文件读，更稳。

## Verification 清单

1. 方案汇总展示给用户且其确认重复均为真实冗余后才动手。
2. 小样本 apply「0 问题」+ 小样本 HTTP「x/x 全部通过」后才跑全量。
3. 全量 apply「0 问题、0 回退 copy」（有回退要逐条排查跨卷/权限）。
4. 全量 HTTP 校验**所有**受影响路径 200 + 长度 + sha256 全一致。
5. 磁盘实占 logical vs physical 差额 ≈ 预估，抽样 `nlink>1`。
