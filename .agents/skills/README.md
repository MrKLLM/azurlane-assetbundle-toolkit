# 项目技能留存（.agents/skills/）

本目录**留存本项目在开发过程中沉淀的 agent 技能**，供任何 agent（千问办公 / WorkBuddy / Codex / Claude Code 等）按需取用。

- **性质**：知识资产，与 `docs/` 同级看待，纳入 git 跟踪。
- **来源**：开发本项目时由各 agent 逐步生成。其中 5 个由千问办公生成，3 个由早期其他 agent 生成。
- **布局**：扁平结构 `.agents/skills/<技能名>/SKILL.md`，便于 agent 直接发现。
  正文超 500 行的技能按 skill-creator 拆成「主文件（骨架+索引）+ `references/*.md`（按需加载）」，内容只搬位置不改一字。
  已被取代的技能移入 `docs/archive/legacy-agents-skills/`（本目录 `_archive/` 现为空，保留作约定目录）——离开技能扫描路径，agent 不会误加载。
- **说明**：本目录是**留存副本**，不是运行时目录。千问办公只认用户级 `~/.qwenworkcn/skills/`，读不到这里；其他 agent 若要启用，需将其纳入各自的技能加载路径（如 WorkBuddy 的项目级 `.workbuddy-ai/skills/`，或建符号链接指向本目录）。

## 活跃技能（10 个，本目录顶层）

| 技能 | 说明 |
|---|---|
| `unity-assetbundle-painting-restore` | 立绘/Spine 数据驱动还原管线核心知识（PPtr/externals 解析、布局四步语义、画框红线、3D 宿舍 glTF 装配）。项目主线工作的主要依据 |
| `safe-pipeline-fix-targeted-rerun` | 管线修复 / 权威源切换 / 纯等价重构的安全落地：定位受影响子集 → 零回退验证 → 小范围重跑 → 换入（分支 B~J） |
| `headless-chrome-cdp-batch-export` | 无头 Chrome + CDP 批量驱动网页渲染/截图/导出，对应 `docs/WORKFLOWS.md` WF-14 |
| `live2d-web-runtime-integration` | 网页集成 Live2D Cubism 运行时（pixi 组合）、动作/按部位点击/台词字幕层与无头 CDP 验收 |
| `live2d-motion-extraction-audit` | Live2D 动作从 AssetBundle 重导出的完整性/保真审计（三类 clip 容器枚举、常量曲线对表 moc3 默认值） |
| `spine-web-runtime-integration` | 网页集成 Spine 3.8 运行时做动态立绘渲染与批量出图（setSkin、引擎绘制序、取景陷阱） |
| `decision-brief` | 技术汇报后附「人话版」现状与决策说明（已定/未定分离、≤3 选项、翻盘留痕） |
| `shared-worktree-takeover-commit` | 多会话共用同一工作树时，核验并接管他人遗留改动的六步流水线 |
| `windows-hardlink-dedup-verify` | Windows/NTFS 硬链接去重安全流程（证「按文件名引用的消费方」零破坏；正本↔副本硬链防改完忘部署） |
| `windows-long-running-batch-detach` | Windows 用完全脱离宿主的分离进程跑长时批处理，并三分法判定真跑完/崩了/被截断 |

## 已归档技能（8 个，`docs/archive/legacy-agents-skills/`）

> 归档件**冻结不改**，保持历史原貌；离开技能扫描路径，agent 不会自动加载。需要时 `git mv` 回本目录即可恢复。

**第一批（3 个，功能已被现有文档取代）**：2026 年归档搬迁（提交 `167b91c`）从 `_archive/` 移入（本目录 `_archive/` 现为空，保留作约定目录）。

| 技能 | 状态 | 功能现归属 | 归档件独有、未被别处覆盖的内容 |
|---|---|---|---|
| `progress-tracker` | 已被吸收 | `AGENTS.md` §进度文档维护 + §格式规范 | 状态更新规则表、扩展更新规则、`[待确认]` 标记约定、`templates/status_format.md`（新项目模板） |
| `workflow-recorder` | 已被吸收 | `AGENTS.md` 写入路由 + `docs/WORKFLOWS.md` 既有格式 | 去重检查逻辑、条目模板、序号递增规则、触发词 |
| `troubleshooting-logger` | 已停用 | `PROJECT_STATUS.md` §9.3 五个系统性根因修复 | 5 字段条目格式（症状/根因/方案/文件/范围）、触发词 |

**第二批（5 个，2026-11-13 低频/冗余归档）**：经 skill-creator 全局盘点，触发频率极低或与模型原生能力/AGENTS.md 高度重叠。**不是被取代**——知识仍在归档件里，相关任务重启时取回即可。

| 技能 | 归档理由 | 知识现归属 / 取回条件 |
|---|---|---|
| `binary-container-vs-crypto` | 对应 §6 待办 7「逆向 sharecfgdata」悬置中，不重启不触发；核心是通用零假设对照纪律 | 重启逆向时取回；密码取证专门判据（IC/many-time-pad）仍在归档件 |
| `enforce-project-rule-as-git-hook` | git hook 机械属模型原生；项目闸门规则 AGENTS.md 已有 13 处 | 规则常驻 `AGENTS.md` §提交闸门；装 hook 的详细自测流程在归档件 |
| `cn-blocked-resource-mirror-fetch` | 仅下载被墙资源时用，09-20 后未触发；镜像 URL 会过期 | 需要时取回；模型亦能自行找镜像 |
| `windows-local-server-launcher` | 启动器已建好极少重建；GBK/TIME_WAIT 坑已沉淀 | 坑见 `docs/TROUBLESHOOTING.md`；启动器生成流程在归档件 |
| `project-doc-governance` | 路由表已在 AGENTS.md；文档膨胀才用 | 规则常驻 `AGENTS.md` 写入路由；瘦身四步管线在归档件 |

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
- 新增技能请沿用 `<技能名>/SKILL.md` 结构，并在此表补一行；被取代的技能移入 `docs/archive/legacy-agents-skills/` 而非删除。
