---
name: shared-worktree-takeover-commit
description: 多会话共用同一工作树时，核验并接管他人遗留改动的流水线。六步：① 先在盘上核实「文件已被修改」通知是否真的落盘（git status / git diff --numstat / ls / grep）；② 按 mtime + 归属把脏改动分成「孤儿（可接管）」与「活跃（绝不碰）」；③ 接管走两次提交——先原样入库不改写、再另起一次把「当前状态」节接回事实；④ 共享长文档只用单点 Edit 插入（整文件写回在 Windows 下会因行尾归一炸出上千行噪声 diff）；⑤ 改名/搬迁类提交前逐文件比 sha256 证无损，再用 git 的 rename 检测复核 0 行改动；⑥ 逐文件 add、提交前重跑 git status、双推后用 git ls-remote 三方对齐核对。当工作树里压着不明归属的未提交改动、不确定别人的改动还在不在盘上、要代提他人内容、或推送前要确认真正远端已收到时使用。触发词：并发会话、接管遗留改动、代提交、工作树脏、孤儿改动、行尾噪声 diff、双推核对、这个改动还要不要提。
---

# 多会话工作树接管与安全提交

## 何时用

- `git status` 里有一批**不是本会话写的**未提交改动，要决定接不接、怎么接。
- 收到「文件已被修改」类提示，需要判断它是真落盘了还是别人的编辑器缓冲区。
- 用户说「我都不记得哪个会话管着了，你能接管处理掉吗」「代提交吧，同步两个远端」。

**不适用**：单会话独占工作树（按常规提交即可）；文档分层与体量瘦身 → `project-doc-governance`；数据管线产物重跑与零回退比对 → `safe-pipeline-fix-targeted-rerun`。

**与记忆分工**：本技能只放**按顺序可复跑的命令与判据**。“为什么这么做”与具体仓库的约定留在项目记忆里（如 `feedback-concurrent-session-commit-scope`、`git-dual-push-remotes`），不要在两边各写一份理由。

## 第 0 步：先验真——通知 ≠ 盘上事实

任何想据此修改自己结论的「别人已经改了 / 已经跑出了新结果」，先在盘上核实：

```bash
git status --short
git diff --numstat                      # 逐文件看改动规模与归属
git diff -- <file> | head -60
grep -n '<关键结论串或编号>' <file>       # 声称写进文档了？查一下
ls -la --time-style=+%m-%d\ %H:\M <file or dir>
```

判据：`git diff --numstat` 里没有该文件、或 `grep` 取不到声称的内容 → **按「未落盘的他人主张」处理**：写成条件句 + 指路（「若其成立以它为准，尚未落盘」），**不得拿它当既成事实改写自己的记录**。

实测：一夜四次此类提示，三次盘上根本没有（`git diff --numstat` / `ls` / `grep §41` 全为空）。第四次是真落盘了，但跑在我上一条命令之后——所以**核实要贴着动手的那一刻做**，中间隔几分钟就得重做。

## 第 1 步：分类闸门——孤儿 vs 活跃

对每个脏文件定归属，两条判据一起用：**mtime 新旧** + **内容类型**。

| 类别 | 判据 | 处理 |
|---|---|---|
| **孤儿** | 搜置 ≳ 半天；纯文档；内容自洽、无 TODO / 半成品痕迹 | 可接管（见第 2 步） |
| **活跃** | mtime 在几分钟内；或是代码（`.py` 等）/ 未跟踪的新工具 | **绝不碰**，那属于还在跑的会话 |

```bash
ls -la --time-style=+%m-%d\ %H:\M <脏文件们>
git log --oneline -3      # 对方是否其实已经提了
git diff --stat           # 规模；git diff -- <file> 看改的是哪级标题/段落
```

**切不干净时的默认顺序**：等 > 只提自己那部分（需绕过仓库的文档同步闸门时走其逃生门，且要显式设置呾在回复里说明为何确实无需改文档，属最后手段）> 代提别人内容（**必须有用户明确授权**）> 索引手术（`git update-index --cacheinfo` 之类会被安全审查拦下，别试）。

让位判据：对方随后自己提交了同一批文件 → 空转是正常结果，不是失败。实测：`git add` 之后、`git commit` 之前对方抢先提交，本次提交返回 `nothing added to commit but untracked files present`、退出码 1 —— **不要为此重跑或改历史**。

## 第 2 步：接管 = 两次提交，不许混成一次

**提交 A：原样入库。** 遗留内容一字不改，message 里写明是接管、并注明它撤回了什么错误结论。

```bash
git add <遗留文件>
git commit -m "接管 <日期> 遗留未提交的 <文件> <小节号>：<一句话结论>"
git log --oneline -1
```

**提交 B：把现状接回事实。** 目标是文档里那句「当前状态」——过时状态句会被下个会话当现状读，危害比缺记录更大。

1. 新增一节「<今日日期> 接管补记」，逐条列已成立结论，**每条配一个可独立复算的判据**。
2. 旧状态节标题就地加「**仅作留痕，勿当现状**」；正文里已不成立的「仍然成立的两条」这类句子**就地划掉并标注更正日期**（`~~旧结论~~ **作废**：<反证在哪>`），不要整段删除。
3. 补记里把内容拆成**实测事实 / 未证假设两层**。只解释“为什么会这样”、从没正向回放验证过的机制，不得写成结论；标题里也不要替未证的解释背书。
4. 顺手核对复现链：文档引用的脚本正本是否真在版本库里（`git ls-files <引用的脚本>`），缺了要补投。

```bash
git show HEAD:<file> | grep -n '当前状态'   # 确认改的是唯一那条现状节
grep -n '未落盘\|留痕\|待证\|未证' <file>   # 复核标注齐了
```

## 第 3 步：改共享长文档只用单点 Edit 插入

**禁止**用 python / 任何脚本把整个文件读出来再写回。Windows 上这会把全文件行尾归一成一种风格：实测一个 694 行 LF 的文档被写成 CRLF，`git diff` 一下变成 **1431 行噪声（737+/694-）**，真正的内容改动被埋掉。

```bash
git diff --stat <file>          # 数字远大于预期 = 行尾被归一，不是真改了很多
git checkout -- <file>          # 回退重来（先确认这文件只有你在动）
# 改用 Edit 单点插入 → 实测最终 diff 只有 +44/−1
```

两条附带判据：

- **不要用 `git show HEAD:<file>` 与工作区文件互比来判「谁改了」**——`git show` 出的是仓库内的 LF，`git checkout` 后的工作区常是 CRLF，两者天然不等。判归属只信 `git diff --numstat`。
- 工作树里 `LF will be replaced by CRLF` 的 warning 是常态噪声，**不代表有人改了这文件**；筛归属时忽略它。

## 第 4 步：改名 / 搬迁类——先证无损，再提交

```bash
# 逐文件比内容：HEAD 版 vs 新位置版（先看文件存在，再信哈希）
git show "HEAD:<旧路径>" | sha256sum
cat "<新路径>" | sha256sum
```

⚠️ `e3b0c44298fc` 是**空输入**的 sha256——路径拼错时它也会正常吐出一个“哈希”，于是 6 个文件全被判成「无损=0」。所以：**先 `ls` 证明被哈希的文件真存在**，再看哈希是否相等；出现全 0 或全一致这种极端结果，第一反应是查命令本身。

提交后用 git 自己的 rename 检测复核：内容零改动的搬迁应当显示 `N files changed, 0 insertions(+), 0 deletions(-)`，路径以 `{old => new}` 形式呈现。

```bash
git show --stat -M <sha> | tail -10
```

搬迁理由要写进 message（例：某归档目录仍会被递归扫描到、不下线，迁出才算真退役）。

## 第 5 步：提交

```bash
git add <逐个列出的文件>        # 禁 git add -A / add .：会夹带别人的会话
git diff --cached --name-only   # 自查暂存清单（注意 git status 没有 --cached 这个选项）
git status --short              # 提交前最后一遍：确认没把别人的改动带进去
git commit -m "<中文 message>"
git show --stat HEAD | tail -8  # 复核这条提交只含本次文件
```

- **message 里不要用 ASCII 双引号**。`git commit -m "$(cat <<'EOF' ... )"` 内层出现 `"` 会把命令替换打断，实测 message 正文被拆成裸词、泄进前一条 `git add` 当路径参数，报 `error: pathspec '...' did not match any file(s) known to git`。改用中文引号「」或反引号。
- 中途 `git add` 过又决定不提 → 必须 `git restore --staged <path>`，否则别人的一次 `git commit` 会把你的暂存内容带走。

## 第 6 步：推送与核对

双推仓库（一次 push 发多个公开面）先确认这批提交适合公开——推上去要改写历史才收得回。

```bash
git remote -v                      # 看清有几条 pushurl
git status -sb | head -2           # 领先多少
git push --dry-run <remote> master # 先看每个端点各一条 master -> master、无分叉
git push <remote> master
git ls-remote <remote1> master; git ls-remote <remote2> master; git rev-parse HEAD  # 三方对齐短 sha
```

- **核对远端别看本地跟踪引用**：以某远端名推送时，另一个远端的 `refs/remotes/<other>/master` 不会随之更新，`git log <other>/master..HEAD` 会一直显示虚假的「领先 N 个」。判据统一用 `ls-remote` 与 `rev-parse HEAD` 三方对齐（要消掉虚假领先就跑 `git fetch <other>`）。
- 远端有独立历史被拒时**绝不 `--force`**，把分叉情况交回用户判断。

## 收尾必须能报出的东西

一段归属判定表（孤儿/活跃 + 各自的 mtime 与证据）、每次代提或接管的 commit sha 与「未改写/原样」声明、空转或让位的说明、以及 `ls-remote` 三方一致的实测值。并明确列出**哪些脏改动没碰、留给谁**。
