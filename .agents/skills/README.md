# 项目技能留存（.agents/skills/）

本目录**留存本项目在开发过程中沉淀的 agent 技能**，供任何 agent（千问办公 / WorkBuddy / Codex / Claude Code 等）按需取用。

- **性质**：知识资产，与 `docs/` 同级看待，纳入 git 跟踪。
- **来源**：开发本项目时由各 agent 逐步生成。其中 5 个由千问办公生成，3 个由早期其他 agent 生成。
- **布局**：扁平结构（`.agents/skills/<技能名>/SKILL.md`），便于 agent 直接发现。
- **说明**：本目录是**留存副本**，不是运行时目录。千问办公只认用户级 `~/.qwenworkcn/skills/`，读不到这里；其他 agent 若要启用，需将其纳入各自的技能加载路径（如 WorkBuddy 的项目级 `.workbuddy-ai/skills/`，或建符号链接指向本目录）。

## 技能清单与状态

| 技能 | 状态 | 说明 |
|---|---|---|
| `unity-assetbundle-painting-restore` | **活跃** | 立绘/Spine 数据驱动还原管线核心知识（含 PPtr/externals 解析、布局四步语义、画框红线、系统性坑速查表）。项目主线工作的主要依据 |
| `headless-chrome-cdp-batch-export` | **活跃** | 无头 Chrome + CDP 批量驱动网页导出，对应 `docs/WORKFLOWS.md` WF-14 |
| `safe-pipeline-fix-targeted-rerun` | **活跃** | 管线修复后"定位受影响子集 → 零回退验证 → 小范围重跑 → 换入"的标准流程 |
| `windows-local-server-launcher` | **活跃** | Windows 双击启动本地 http.server 的启动器生成器（含 GBK/CRLF、TIME_WAIT 等坑） |
| `project-doc-governance` | **已执行** | 文档治理四步管线。2026-09-16 已执行完毕（提交 `d889ee9`），规则常驻 `AGENTS.md`；文档再次膨胀时可重跑 |
| `progress-tracker` | **已被吸收** | 功能已完整内联进 `AGENTS.md` §进度文档维护 与 §格式规范，技能本身冗余，留作溯源 |
| `workflow-recorder` | **部分冗余** | 条目格式已固化在 `docs/WORKFLOWS.md`（WF-1 ~ WF-14），现按 `AGENTS.md` 写入路由续写，无需技能 |
| `troubleshooting-logger` | **已停用** | 被 `PROJECT_STATUS.md` §9.3「五个系统性根因修复」取代。`docs/TROUBLESHOOTING.md` 最后条目为 #11（2026-06-20），近三个月无新增 |

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
- 新增技能请沿用 `<技能名>/SKILL.md` 结构，并在此表补一行状态。
