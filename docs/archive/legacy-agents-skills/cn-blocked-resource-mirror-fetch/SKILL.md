---
name: cn-blocked-resource-mirror-fetch
name_en: CN Blocked Resource Mirror Fetch
name_zh: 国内受限网络被墙资源镜像取数
description: Probe-and-fetch pipeline for blocked resources on restricted mainland-China networks. Use when raw.githubusercontent.com / github.com / registry.npmjs.org time out, return empty, or return 502, or when the user mentions blocked-source fallback (被墙、换源、国内镜像、下载不到). Covers GitHub raw/API/ repo files via ghproxy prefixes, npm packages via registry.npmmirror.com, and blocked-site static assets via public mirror sites, with a verified-dead-source blacklist.
description_en: Probe-and-fetch pipeline for blocked resources on restricted mainland-China networks, covering GitHub raw/API files, npm packages via npmmirror, and static assets via public mirror sites, with a verified-dead-source blacklist.
description_zh: 国内受限网络下被墙资源的探测与下载管线：GitHub raw/API/仓库文件走 ghproxy 前缀，npm 包走 registry.npmmirror.com，被墙站静态资源找公开镜像站直下；附实测失效源黑名单与结果校验规则。
argument-hint: Give the blocked URL or resource (GitHub file / npm package / static asset) to fetch and the local save path
argument-hint-en: Give the blocked URL or resource (GitHub file / npm package / static asset) to fetch and the local save path
argument-hint-zh: 给出被墙的 URL 或资源（GitHub 文件 / npm 包 / 静态资源）及本地保存路径
user-invocable: true
---

# 国内受限网络被墙资源镜像取数

## 何时使用

直连以下源出现超时 / 空响应 / 502 时启用本管线：

- `raw.githubusercontent.com`、`github.com`（文件、release、API）
- `registry.npmjs.org`、`unpkg.com`
- 任意被墙的国外站点静态资源（js/css/图片/模型文件）

## 第 0 步：连通性快速探测

先花几秒确认原源确实不可用、并批量验证候选镜像，不要凭印象换源：

```bash
# 判空判状态码（HTTP 200 但 body 为空 = 失败）
curl -sL --max-time 10 -o probe.out -w "%{http_code} $(wc -c < probe.out)B\n" "<URL>"
```

一次并行探测多个候选，选返回 200 且字节数合理的那个。

## 链 1：GitHub raw 文件 / 仓库内容

探测顺序（前缀式代理，原 URL 原样拼在后面）：

```bash
# ① ghproxy.net（实测 ✅）
curl -sL --max-time 20 "https://ghproxy.net/https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>"

# ② gh-proxy.com（实测 ✅，①失败时用）
curl -sL --max-time 20 "https://gh-proxy.com/https://raw.githubusercontent.com/<owner>/<repo>/<branch>/<path>"
```

下载 release / 仓库内任意文件同理：把 `github.com/...` 原 URL 加前缀即可。

## 链 2：GitHub API（列目录、找最新版本）

需要枚举仓库结构或定位最新版本目录时，代理 `api.github.com`：

```bash
# 递归列全仓库文件树
curl -sL --max-time 25 "https://ghproxy.net/https://api.github.com/repos/<owner>/<repo>/git/trees/master?recursive=1" -o tree.json

# 列某目录内容（如 versions/ 找最新版本号）
curl -sL --max-time 25 "https://gh-proxy.com/https://api.github.com/repos/<owner>/<repo>/contents/versions"
```

拿到版本号后回链 1 拼 raw URL 下载具体文件。

## 链 3：npm 包（含包内静态资源）

不走 npmjs/unpkg，用 npmmirror，**两步：先查版本、再拼 tgz 路径**（不要瞎猜版本号）：

```bash
# ① 元数据 JSON，读 dist-tags.latest（也可看 versions 里指定版本）
curl -sL --max-time 20 "https://registry.npmmirror.com/<pkg>" | python -c "import sys,json;print(json.load(sys.stdin)['dist-tags']['latest'])"

# ② 拼 tgz 下载（版本替换为上一步结果）
curl -sL --max-time 30 "https://registry.npmmirror.com/<pkg>/-/<pkg>-<ver>.tgz" -o pkg.tgz
tar xzf pkg.tgz   # 解出 package/ 目录，取所需文件
```

只要单个 min.js 时不必完整 npm install，解 tgz 拿文件即可。`data.jsdelivr.com/v1/packages/npm/<pkg>` 可作版本发现的备用通道（实测 npm 路径可达）。

## 链 4：被墙站点静态资源找公开镜像站

目标站被墙但其托管的静态资源（如运行时 js）常有人做公开镜像：

1. WebSearch「<资源名> 镜像 / 国内 CDN / 直链」寻找公开镜像站；
2. 对候选站 `curl -sIL` 验证直链可用后下载。

实测案例：被墙源上的 `live2dcubismcore.min.js` 最终从公开镜像站 `l2d.su/lib/live2dcubismcore.min.js` 直下拿到。

## 失效源黑名单（2026-09 实测）

| 源 | 结果 |
|---|---|
| `raw.githubusercontent.com` 直连 | 墙，空响应 |
| `gitclone.com` | 502 |
| `github.moeyy.xyz` | 不通 |
| `cdn.jsdelivr.net/gh/...` | 可达但服务端重定向回被墙的 raw，实际不可用 |
| `unpkg.com` | 不可靠 |

镜像站时效性强：黑名单失效应重新探测，不得凭清单直接断定某站已死；同理本表 ✅ 源也可能失效，探测失败即换下一条。

## 结果验证（必须）

- HTTP 200 ≠ 成功：下载后校验 body 非空、字节数符合预期（对比 Content-Length 或文件类型常识）。
- JSON/API 响应先本地 parse 确认是数据而非镜像站的错误页 HTML。
- tgz 解包后确认目标文件存在且非空再部署。
