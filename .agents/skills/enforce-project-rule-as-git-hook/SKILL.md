---
name: enforce-project-rule-as-git-hook
version: 1.1.0
description: 把口头规则变成真正拦得住的 git 提交闸门的流程：先分清缺的是「约束」还是「执行」，再按检查对象选 hook 位（消息格式类只能挂 commit-msg，因为 pre-commit 运行时消息文件还不存在），装完必须自测拦截分支并检查闸门会不会拦死自己的合法变更。当用户说「加个约束」「每次任务完成都要检查 X，没有就加上」「为什么这条规则没人遵守」「pre-commit / commit-msg / .git/hooks」「提交被拦了 / 想绕过闸门」，或要把 DoD、文档同步、提交规范类规则落成硬约束时使用。不覆盖 CI 强制与代码评审规则。
---

# 把项目规则变成可执行的提交闸门

## Overview

写在文档里的规则只在「想起来」时生效；要每轮都生效，就得有一道非零退出的脚本拦着。
本技能管从口头规则到「装好、拦得住、且不误伤自己」这一段。

## 第 0 步：先分清缺的是约束还是执行

- 规则**已经在文档里**却没被执行 → 不要新写规则，直接上闸门。加第二条规则只会让文档更长、执行率不变。
- 规则**不在文档里** → 先写进规则文档（DoD / 收尾清单），再决定要不要强制。
- 上闸门的判据：这条规则是否**每轮都必须回答**。是 → 闸门；偶尔相关 → 留在文档。
  闸门越多，绕行越多，最后所有闸门都靠 `SKIP=1` 活着。

## 第 1 步：按检查对象选 hook 位（选错等于白做）

| 要检查的东西 | 挂哪个 hook | 输入 |
|---|---|---|
| 暂存区文件集合（改了代码必须带文档、禁止提交产物目录） | `pre-commit` | 无参，自己读 `git diff --cached` |
| **commit message 内容 / 格式** | `commit-msg` | `$1` = 消息文件路径 |
| 提交完成后的通知、统计 | `post-commit` | — |

- **决定性事实**：`pre-commit` 运行时 commit message 文件**还不存在**，所以任何「消息里必须有一行 X」的规则只能挂 `commit-msg`。踩过一次才知道。
- 多条闸门可以叠在同一个 hook 文件里，但绕行开关必须一闸一个（第 4 步）。
- ⚠️ **检查对象在 gitignore 目录里时，hook 是错的工具**：hook 只看暂存区，而 gitignore 目录
  永远不会出现在暂存区——挂上去等于永远绿灯。这类规则（例：「临时区不留唯一副本代码」）
  要落成**独立的、有退出码的检查脚本**，写进 DoD/收尾清单里要求阶段收尾跑一次。
  它不是硬闸门（拦不住忘记跑它的人），但**比一条注定不触发的 hook 强**，而且能被别的
  编排器调用（例如放进一键流水线的 preflight 阶段）。判断顺序：
  检查对象能否从 `git diff --cached` 看到？不能 → 不要挂 hook，写检查器。

## 第 2 步：正本入库 + 副本生效

`.git/hooks/` 不被 git 跟踪，所以：

```
scripts/git-hooks/<hook>        # 正本，入库、可 review、可版本化
  ↓ cp + chmod +x
.git/hooks/<hook>               # 生效副本；换机器 / 重新 clone 后必须重装
```

- 改逻辑**只改正本**，改完重新 copy；直接改 `.git/hooks/` 会让副本悄悄跑出仓库。
- 在 hook 文件头部注释里写死：重装命令 + 第 3 步的自测命令。下一会话照抄即可，不必重新推导。
- 把重装命令也写进项目的规则文档（它属于「换机器就失效」的那类隐性依赖）。

## 第 3 步：必须自测「拦」的那条分支

只验证它放行 = 没测。一个条件写反（`=` 与 `!=`、grep 大小写、路径前缀漏了斜杠）看起来都是「正常工作」。

```sh
# pre-commit：用临时索引，不污染真实暂存区
T=$(mktemp); export GIT_INDEX_FILE=$T; git read-tree HEAD
touch scripts/_selftest.tmp && git add scripts/_selftest.tmp && ./scripts/git-hooks/pre-commit; echo $?  # 期望 1
touch docs/_selftest.tmp     && git add docs/_selftest.tmp     && ./scripts/git-hooks/pre-commit; echo $?  # 期望 0
rm -f scripts/_selftest.tmp docs/_selftest.tmp $T; unset GIT_INDEX_FILE

# commit-msg：直接调 hook 传消息文件（不产生真实提交）
printf '测试\n' > /tmp/msg.txt;                                       .git/hooks/commit-msg /tmp/msg.txt; echo $?  # 期望 1
printf '测试\n\n技能: 无新增（纯格式化）\n' > /tmp/msg.txt;            .git/hooks/commit-msg /tmp/msg.txt; echo $?  # 期望 0
```

⚠️ `git commit --dry-run` **不会跑 hook**，别用它当自测手段（会得到假绿灯）。

## 第 4 步：检查新闸门会不会拦死自己的合法变更

最常见的一类失效：闸门的「合规白名单」里没有**规则文件自己**。

> 真实案例：规则「改代码必须同步文档」把「文档」定义为状态文档 + `docs/**`。于是「只改 hook 正本 + 改规则文档 AGENTS.md」这一次提交被自己的闸拦死——改闸门的人正是写规则的人，而他手上没有别的文件可带。修法是把规则文件本身也纳入白名单。

- 装完专门跑一遍「只改规则 / 只改闸门」的提交，确认能通过。
- 顺带检查反方向：白名单太宽会让闸门形同虚设（把整棵仓库算作「文档」等于没闸）。

## 第 5 步：绕行开关分立 + 失败信息自带出路

- **一闸一个开关**：`DOC_CHECK_SKIP` 只放行文档闸，`SKILL_CHECK_SKIP` 只放行技能闸，互不覆盖。共用一个 `SKIP=1` 会让「合法绕过一条」顺带绕过全部。
- 绕行必须打印一行警告，不静默放行（让绕过在输出里留下痕迹）。
- 拦截信息里必须写三样：① 本次触发规则的具体文件列表；② 每种合规写法的**原文示例**（可直接抄）；③ 绕行开关的名字。共享工作树下别人第一次撞上来时，错误文本是唯一说明书。
- 判据：一个从没读过规则文档的协作者，只看错误文本能否一次改对。

## 第 6 步：交代影响范围，并同一轮就用它

- 声明 blast radius：本地 hook 对**所有**会话和协作者生效。多人共用一个工作树时，新闸门会拦到正在并行提交的别人——提前说明，别让人家对着陌生报错自己排查。
- 给出一条最小回退：删 `.git/hooks/<hook>` 即可停用（正本留着不影响任何人），不需要 revert 提交。
- **同一轮立刻用它**：本次提交的消息自己带上要求的行。新闸门最容易被绕过的时点就是它上线的那一轮。

## Hook 骨架（POSIX sh，两条通用写法）

```sh
#!/bin/sh
[ -n "$RULE_CHECK_SKIP" ] && { echo "[hook] ⚠️ 已绕过本检查——请确认本次确属例外。" >&2; exit 0; }
staged=$(git diff --cached --name-only --diff-filter=ACMRD)   # A/C/M/R/D，排除意外状态
trigger=0; offend=""
for f in $staged; do
  case "$f" in
    src/*) trigger=1; offend="$offend\n    $f" ;;     # 触发集：写具体前缀，别写 '*'
    docs/*|README.md) ;;                              # 白名单里要包含规则文件自己
  esac
done
[ "$trigger" = "0" ] && exit 0
# ... 不满足则 cat >&2 <<EOF 给出处路; exit 1
exit 0
```

## 边界（这些不归本地 hook）

- 本地 hook **挡不住** `git commit --no-verify`，也挡不住没装副本的机器。它的定位是「防自己漏」，不是安全边界；共享仓库要真拦必须配 CI 或服务端 hook。
- 「上一轮承诺的改动到底落没落地」属于决议落地审计，走文档治理类技能，别混进本技能。
- 消息内容校验若还要求格式（如 `类型: 摘要`），同一 hook 里按「缺行」和「格式错」分别报错，不要合并成一条模糊提示。
