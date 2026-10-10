# `docs/archive/` 索引 — 状态文档外迁台账

> **铁律**：本目录的 `PROJECT_STATUS_*_逐字外迁_*.md` 是**逐字保留区，勿编辑**——
> `scripts/diag/doc_verbatim_archive.py --verify` 拿 `git show HEAD:PROJECT_STATUS.md` 的对应行区间
> 与它们整块比对，改一个字下次归档就核对不过。要补充结论请写进 `TROUBLESHOOTING.md` / `WORKFLOWS.md`。

归档的语义是**外迁不是删除**：搬走的每一行都原样在这里，主文档原位留桩并指回段号。

## 按段号找（`PROJECT_STATUS.md` 桩里的 `A2x 段` 就查这张表）

| 段号 | 文件 | 装的是什么 |
|---|---|---|
| A1~A21b | `2026-09-26_PROJECT_STATUS_外迁归档.md` (747 行) | 历轮会话流水（2026-09-20~09-27）+ §6 已闭环待办条目 + 头部执行快照 |
| A22 / A22b | `PROJECT_STATUS_条目13-26_逐字外迁_2026-10-05.md` | §6 第 13/14/22/25/26 条 + 头部快照 |
| A23 | `PROJECT_STATUS_条目14-31_逐字外迁_2026-10-06.md` | §6 已闭环 14/28/29/30/31 条 |
| A24 | `PROJECT_STATUS_条目32_逐字外迁_2026-10-07.md` | §6 第 32 条（静态立绘 4496 张全量重渲） |
| A25 / A26 | `PROJECT_STATUS_已闭环条目_逐字外迁_2026-10-07.md` | §6 ★块 1~4 + 待办 5/9/10/13/20/22/25/26/27/35 + §7⑥ 背景库 P2 实现流水 |
| A27 | `PROJECT_STATUS_3D宿舍房间轮_逐字外迁_2026-10-10.md` | §6 待办 5 的「3D 宿舍 · 房间轮 + 进画廊」全过程（10-08~10-10） |
| A28 | `PROJECT_STATUS_S6重条目瘦身_逐字外迁_2026-10-10.md` | §6 四条重条目的过程段（36 花瓣轮六~九轮 / 37 交接项已判完 / 5·8 抄本与溯源） |
| — | `PROJECT_STATUS_历史归档.md` (1102 行) | v1 时代历史 |
| — | `2026-10-07_3D宿舍复刻可行性取证.md` (579 行) | **3D 宿舍 step 0~5 的权威取证数字**（追加 I~IX；蒙皮权重、ASTC、材质旋钮、GLB 产物数字） |
| — | `2026-10-07_3D宿舍_交接给下一轮.md` (120 行) | 3D 宿舍交接六步 |
| — | `2026-06-21_目录审计报告.md` / `2026-06-28_Spine旧交接.md` | 早期一次性审计 / 被取代的旧交接 |
| — | `legacy-agents-skills/` | 已下线的项目级技能旧副本 |

## 找东西的三条实际路径（按命中率排）

1. **知道是哪一轮** → 上表段号，或 `git log --oneline -- PROJECT_STATUS.md` 看归档提交。
2. **知道是哪个结论** → 别在 archive 里找，去 `TROUBLESHOOTING.md`（§1~131）/ `WORKFLOWS.md`（WF-1~38），
   那两处才是结论的正本；archive 只保过程。
3. **只知道关键词** → `grep -rl "<特征串>" docs/`。⚠️ 两个已知陷阱：
   - `§123 追加-I … 追加-XIII` 这类**行内加粗编号不是标题**，`grep '^#+.*追加'` 命中 0，只能按串 grep。
   - 主文档桩里的「逐字见 A2x 段」**有过写错的实例**（10-10 核实：step 0~5 的逐字数字不在 A25，
     实际在 `2026-10-07_3D宿舍复刻可行性取证.md`）。⇒ 引用指针前用特征串验一次，别信指针本身。

## 怎么做一次外迁（三步，缺一不可）

```bash
# 1) 干跑：只打印计划（基线行数 → 新行数、每段搬几行、留桩几行）
py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json
# 2) 落盘：追加归档段 + 改写主文档，并当场跑四条核对
py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json --apply
# 3) 复核：磁盘内容必须 == 基线 + 本次应有的结果（抓"写完又被人整文件写回"）
py -3 scripts/diag/doc_verbatim_archive.py --manifest .diag/xxx.json --verify
```

清单 JSON 形如 `{"doc","archive","base":"HEAD","title","segments":[{"label","lines":[a,b],"stub"}]}`，
行号是 **`git show base:doc` 的 1-based 闭区间**；主文档与基线不一致会中止（并行会话插队）。

⚠️ **行尾**：本仓库 `core.autocrlf=true`，工作树是 CRLF 而 blob 是 LF，所以守卫两侧都先归一化行尾
（见 `TROUBLESHOOTING.md` §130）。归档前后要用 `wc -l` 与 `git diff --numstat` 确认 diff 是**局部**的
（形如 `16  101`），而不是上千行的全文件重写。
