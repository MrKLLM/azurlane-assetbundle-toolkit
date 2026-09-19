# 项目技能留存（.agents/skills/）

本目录**留存本项目在开发过程中沉淀的 agent 技能**，供任何 agent（千问办公 / WorkBuddy / Codex / Claude Code 等）按需取用。

- **性质**：知识资产，与 `docs/` 同级看待，纳入 git 跟踪。
- **来源**：开发本项目时由各 agent 逐步生成。其中 5 个由千问办公生成，3 个由早期其他 agent 生成。
- **布局**：扁平结构 `.agents/skills/<技能名>/SKILL.md`，便于 agent 直接发现。
  已被取代的技能移入 `_archive/` 子目录——下划线前缀 + 多一层深度，agent 扫描时不会误加载。
- **说明**：本目录是**留存副本**，不是运行时目录。千问办公只认用户级 `~/.qwenworkcn/skills/`，读不到这里；其他 agent 若要启用，需将其纳入各自的技能加载路径（如 WorkBuddy 的项目级 `.workbuddy-ai/skills/`，或建符号链接指向本目录）。

## 活跃技能（5 个，本目录顶层）

| 技能 | 说明 |
|---|---|
| `unity-assetbundle-painting-restore` | 立绘/Spine 数据驱动还原管线核心知识（PPtr/externals 解析、布局四步语义、画框红线、系统性坑速查表）。项目主线工作的主要依据 |
| `headless-chrome-cdp-batch-export` | 无头 Chrome + CDP 批量驱动网页导出，对应 `docs/WORKFLOWS.md` WF-14 |
| `safe-pipeline-fix-targeted-rerun` | 管线修复后「定位受影响子集 → 零回退验证 → 小范围重跑 → 换入」的标准流程 |
| `windows-local-server-launcher` | Windows 双击启动本地 http.server 的启动器生成器（含 GBK/CRLF、TIME_WAIT 等坑） |
| `project-doc-governance` | 文档治理四步管线。2026-09-16 已执行完毕（提交 `d889ee9`），规则常驻 `AGENTS.md`；文档再次膨胀时可重跑 |

## 已归档技能（3 个，`_archive/`）

这些技能的功能**已被本项目现有文档取代**，本项目内不再需要，故归档留作跨项目复用参考。

> 归档件**冻结不改**，保持历史原貌。其内容按当时语境书写，路径与章节引用未必仍与本项目一致；跨项目复用时应按新项目重写路径。

| 技能 | 状态 | 功能现归属 | 归档件独有、未被别处覆盖的内容 |
|---|---|---|---|
| `progress-tracker` | 已被吸收 | `AGENTS.md` §进度文档维护 + §格式规范 | 状态更新规则表、扩展更新规则、`[待确认]` 标记约定、`templates/status_format.md`（新项目模板） |
| `workflow-recorder` | 已被吸收 | `AGENTS.md` 写入路由 + `docs/WORKFLOWS.md` 既有格式 | 去重检查逻辑、条目模板、序号递增规则、触发词 |
| `troubleshooting-logger` | 已停用 | `PROJECT_STATUS.md` §9.3 五个系统性根因修复 | 5 字段条目格式（症状/根因/方案/文件/范围）、触发词 |

**`troubleshooting-logger` 的停用原因值得记一笔**：`AGENTS.md` 路由表规定「踩坑 → `docs/TROUBLESHOOTING.md`」，但实际排查结果一直写进 `PROJECT_STATUS.md`——该文档最后条目停在 #11（2026-06-20），而 9 月两个系统性大 bug（`p_local` 多减、`mRawSpriteSize` 误用画框）都记在 `PROJECT_STATUS.md`。即**规范与实际做法脱节**，这正是 `project-doc-governance` 要治的问题类型。

## 与项目文档的分工

`AGENTS.md` 的「文档写入路由」是**内容该写进哪个文件**的权威规则；本目录的技能是**怎么把内容写对**的操作知识。二者互补：

- 状态/进度 → `PROJECT_STATUS.md`（就地更新）
- 可复用流程 → `docs/WORKFLOWS.md`
- 踩坑记录 → `docs/TROUBLESHOOTING.md`
- 运行错误 → `docs/ERRORS.log`
- 工具说明 → `docs/tools/`
- 一次性报告 → `docs/archive/`

## 维护约定

- 本目录为留存性质，**不随日常任务改动**；技能内容若在实践中发现错误或过时，可直接就地修订。
- **引用项目章节号前，务必先 `grep` 目标文档确认编号仍存在**——`PROJECT_STATUS.md` 曾于 2026-09-16 瘦身时把 `§12` 重编号为 `§9`，导致技能内多处引用失效。
- 新增技能请沿用 `<技能名>/SKILL.md` 结构，并在此表补一行；被取代的技能移入 `_archive/` 而非删除。
