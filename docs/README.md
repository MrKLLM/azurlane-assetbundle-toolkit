# 文档导航索引

> 本目录所有文档的用途与归属一览。**写入路由规则以根目录 `AGENTS.md` 为准**（什么内容写进哪个文件）。新会话请先读根目录 `PROJECT_STATUS.md` 了解进度，再按需查本文定位具体文档。

## 目录结构

```
docs/
├── README.md                 # 本导航索引
├── DEV_LOG.md                # 操作手册：技术选型、完整步骤、故障排除
├── WORKFLOWS.md              # 可复用工作流（按主题追加）
├── TROUBLESHOOTING.md        # 踩坑记录：问题 → 原因 → 解决方案
├── ERRORS.log                # 导出/合成运行错误流水
├── tools/                    # 单个工具的使用说明
│   ├── ALPA使用说明.md
│   └── AssetStudio使用说明.md
└── archive/                  # 一次性报告、被取代的旧交接文档（只读归档）
    ├── 2026-06-21_目录审计报告.md
    └── 2026-06-28_Spine旧交接.md
```

## 各文档职责

| 文档 | 什么时候写 / 查 |
|------|----------------|
| `../PROJECT_STATUS.md`（仓库根目录） | 当前进度快照、各部分状态、接手须知、待办。**跨会话对接首选**，就地精简更新 |
| `DEV_LOG.md` | 想了解“整个流程怎么跑”“技术选型依据”时；仅在流程变更时更新 |
| `WORKFLOWS.md` | 沉淀可复用的操作步骤（如“如何全量合成 v2 立绘”） |
| `TROUBLESHOOTING.md` | 遇到具体报错，先来这里查是否已解决；解决新问题后追加条目 |
| `ERRORS.log` | 批量导出/合成脚本运行时的错误流水（机器生成） |
| `tools/*.md` | 某个第三方工具（ALPA / AssetStudio）的用法与下载 |
| `archive/*.md` | 历史一次性产物，仅供追溯，不再维护 |

## 使用建议

- 接手任务：`PROJECT_STATUS.md` → 需要细节再进 `DEV_LOG.md` / `WORKFLOWS.md`。
- 排查问题：`TROUBLESHOOTING.md` → `ERRORS.log`。
- 新增长尾内容前，先对照 `AGENTS.md` 的「文档写入路由表」确认归属，**不要往 PROJECT_STATUS.md 追加会话流水**。
