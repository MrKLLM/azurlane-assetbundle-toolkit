---
name: headless-chrome-cdp-batch-export
description: 无头 Chrome + CDP 批量驱动本地网页完成渲染/截图/资产导出。当任务需要用浏览器前端运行时（如 Spine/WebGL/Canvas/JS 库）批量产出图片或数据文件时使用——触发词：无头浏览器批量导出、CDP 驱动网页、headless chrome 批量截图、浏览器渲染落盘、autostart 参数自动化。不适用于单次网页截图和 QwenWork 内置媒体生成工具。
version: 1.2.0
---

# 无头 Chrome + CDP 批量导出

用无头 Chrome 通过 CDP（Chrome DevTools Protocol）驱动本地网页自治运行批量渲染任务，结果经 HTTP POST 回本地服务器落盘。已在碧蓝航线项目跑通 231 皮肤 Spine CG 批量导出（约 5 分钟全量），可直接复跑。

## 适用判断

- 渲染逻辑依赖浏览器运行时（Spine runtime、WebGL、Canvas、页面 JS 库），不值得用 Python 重写解析器 → 用本流程
- 产出物是图片/JSON 等文件，需要批量（几十~几百次）→ 用本流程
- 只截一次网页 → 直接 DevTools/截图工具，勿用本流程

## 步骤

1. **确定三层架构**
   - 本地 HTTP 服务器：托管导出页 + 提供落盘接口（`POST /save?name=<x>` 写文件、`GET /exists?name=<x>` 查已导出）
   - 自治导出页：一个 HTML，内嵌全部渲染逻辑，URL 参数控制行为，DOM 上暴露进度
   - CDP 驱动脚本：Python 起无头 Chrome，websocket 连 CDP，轮询进度直到结束标记
2. **写自治导出页**（详见 reference.md 的 JS 片段）
   - URL 参数：`autostart=1`（加载即自动跑全队列）、`only=a,b,c`（子集）、`size=<px>`（输出尺寸）、`redo=1`（跳过断点续跑强制重导）
   - 页面加载后等资源就绪再开跑；每完成一项，`canvas.toBlob` → `POST /save?name=` 回传落盘
   - 开跑前逐项 `GET /exists` 查重，已存在的跳过（断点续跑）；结束时向 `#log` 写「全部结束」类结束标记
   - 进度暴露：`#prog`（如 "37/231"）与 `#log`（逐条 append `<div>`），供驱动脚本轮询
3. **写 CDP 驱动脚本**（完整骨架见 reference.md）
   - 启动参数（五坑对应项一个不能少）：`--headless=new --remote-debugging-port=<port> --remote-allow-origins=* --user-data-dir=<独立目录> --no-first-run --no-default-browser-check --disable-background-timer-throttling --enable-unsafe-swiftshader --use-angle=swiftshader --window-size=1280,900`
   - 轮询 `http://127.0.0.1:<port>/json` 找到 URL 匹配目标页的 tab，取 `webSocketDebuggerUrl`
   - websocket 连接后用 `Runtime.evaluate`（`returnByValue: true`）轮询 `#prog`/`#log`，出现结束标记或超时退出，最后 `proc.terminate()`
4. **验证与收尾**
   - 抽查 1-3 张落盘产物（尺寸、内容非黑图）确认正确
   - 正确后再放量跑全量；跑完确认 Chrome 进程已退出（独立 user-data-dir 的进程可直接按 profile 识别）

## 关键坑位（五坑，缺一即翻车）

1. **`--remote-allow-origins=*` 必须加**：CDP 新版安全策略下，websocket 握手带 Origin 头会被 403 拒绝，表现为 `/json` 能列出 tab 但 `create_connection` 失败。
2. **独立 `--user-data-dir` + 清残留 chrome**：必须用独立 profile 目录，且启动前杀掉使用同一目录的残留 chrome 进程，否则调试端口被旧进程占用，`/json` 返回的是旧会话的 tab。
3. **WebGL 走软渲染**：无头环境 GPU 不可用，WebGL 页面会黑屏或崩溃。加 `--enable-unsafe-swiftshader --use-angle=swiftshader` 强制 SwiftShader 软渲染。实测 2400px 长边约 2s/张，可接受；输出尺寸设上限防纹理超限。
4. **`toBlob` 需要 `preserveDrawingBuffer:true`**：WebGL 上下文创建时必须传 `preserveDrawingBuffer: true`，否则事件循环清空帧缓冲后 `toBlob`/`toDataURL` 拿到黑图或空图。批量循环里逐项 `dispose()` 纹理/资源，防 4096² 页纹理堆爆显存。
5. **`Runtime.evaluate` 前须等页面就绪**：`/json` 出现 tab ≠ 页面加载完成。探针若在目标 DOM（如 `#prog`）存在前发送，evaluate 返回 null 或抛异常。驱动脚本应对 `null` 探针结果做容错重试，或先 evaluate 一个存在性检查再进入正常轮询。

## 验证类任务的额外坑（做"批量断言"而非"批量导出"时）

1. **断言要读运行时状态，别用画面代理指标**。判"动画/交互是否生效"要读引擎内部状态（如 Live2D 的 `motionManager.state.currentGroup`、Spine 的 `anim.getCurrent`）。帧哈希/`drawImage` 比对两头都骗人：无头环境 rAF 被节流 → **假阴性**；而 physics/眨眼等常驻动画让帧一直变化 → **假阳性**（曾据此误判"动画正常"）。
2. **异步生效要等一拍再断言**。触发函数内部常含 `fetch`（如 Live2D 加载 motion JSON），调用后立刻读状态会拿到空值 → 误判失败。加 ~1.5s 等待再采样。另注意某些状态会**自动回落**（idle 播完 `currentGroup` 归 null），所以"值变了"才是被触发的证据。
3. **冷启动要先轮询等待页面全局变量**。删过 profile 后页面加载变慢，`/json` 有 tab、甚至 `evaluate` 能跑，都不代表数据脚本已执行；直接访问 `window.<DATA>` 会 `ReferenceError`。探针开头写 `for(let i=0;i<80 && !window.GALLERY;i++) await t(300)`。
   - ⚠️ **就绪谓词本身会造成"门在生效"的假象**：`Runtime.evaluate` 里写
     `typeof G!=='undefined' && Array.isArray(G.ships) && G.ships.length`，返回的是**最后一个操作数的值**
     （一个数字），Python 侧 `is True` 恒假 → 门退化成白等满超时，症状是"工具很慢"而不是"门没生效"，
     且后续步骤可能照样成功，于是永远发现不了。→ **谓词一律显式降为布尔**：`String(<expr>)==='true'`
     或在 JS 侧 `=== true` / `Boolean(...)`；写完先故意在页面加载前跑一次，确认它真的会等待。
4. **两个 chrome 实例并发跑 CDP 会互相抢**，表现为 `Execution context was destroyed`。批量验证串行执行，或确保端口/profile 完全隔离且不重叠运行。
5. **清理残留 chrome 必须按 `--user-data-dir` 精确匹配命令行再 kill**：`Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | ? { $_.CommandLine -like '*<你的profile目录>*' }`。**绝不能按进程名全杀**——会误杀用户自己的浏览器。
6. **跨坐标空间的自动化探针，断言要落在产品语义上**。若探针要自己算目标坐标（模型单位 → 屏幕 → 再被页面反解回单位），往返误差在极端坐标处会被放大，导致"我猜它不该命中"类断言恒失败。改断言成产品契约（如"有判定区的模型任何点击都不该播出兜底动作组"）。
7. **上面第 1 条"读运行时状态"对视觉产物只够证「没死」，不够证「对」**（2026-09-26 实测）：
   Live2D 贴图整体错绑时，加载成功、drawable 计数正常、参数跨帧 min/max 全在动——代理指标**全部为真**，
   而画面是几十个部件碎片叠一堆。→ 渲染类产物的批量验证必须**同时**有：
   ① 状态断言（快、可全量、能进 CI）＋ ② 按 canvas `clip` 只截模型区的截图，**逐张看内容**
   （慢、只能抽样，但唯一能证"对"）。只有 ① 的验收报告不要写成"全绿"。
   看图要有**可比对象**（同皮肤静态图 > 同批未改动对照组 > 外部权威实现），否则会把
   正常的前缩透视/夸张构图判成"姿势反常"。
8. **探针脚本不要在启动时清空整个输出目录**——同一轮里第二次运行会把上一轮的证据删掉。
   只删本次要重产出的那些 key；跨轮对比依赖旧产物。

## 验证

- 抽查 1-3 张产物：非黑图、尺寸正确、内容符合预期 → 展示给用户确认
- 用户确认后再全量运行（呼应项目「全量运行前必须确认」规则）

## 参考

- `reference.md`：CDP 驱动脚本完整骨架 + 自治导出页落盘/断点续跑 JS 片段
- 碧蓝航线项目实例：`docs/WORKFLOWS.md` WF-14、`gallery_src/cg_export.html`、`.diag/run_cg_export.py`