---
name: headless-chrome-cdp-batch-export
description: 无头 Chrome + CDP 批量驱动本地网页完成渲染/截图/资产导出。当任务需要用浏览器前端运行时（如 Spine/WebGL/Canvas/JS 库）批量产出图片或数据文件时使用——触发词：无头浏览器批量导出、CDP 驱动网页、headless chrome 批量截图、浏览器渲染落盘、autostart 参数自动化。不适用于单次网页截图和 QwenWork 内置媒体生成工具。触发词（验收向）：点击没落地、开关无效还是探针没点到、画面改变判据全红而可逆判据全绿、取样哨兵值 None 参与比较、ES module 整块不初始化、vendor import 闭包、滑鼠标卡顿归因、帧时拆解、背景动效是不是罪魁、交替配对测量、顺序 A/B 的差不能当收益、property tree 节点数、静止不带 transform、判据放宽成恒真、绿着崩、首屏长列表分批渲染、分页探针、长任务按 bootDone 前后拆、选中态不亮、全局!important压组件、自动弹层veil拦鼠标、JS点击全绿鼠标全红。
version: 1.8.31
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

## 关键坑位（六坑，缺一即翻车）

1. **`--remote-allow-origins=*` 必须加**：CDP 新版安全策略下，websocket 握手带 Origin 头会被 403 拒绝，表现为 `/json` 能列出 tab 但 `create_connection` 失败。
2. **独立 `--user-data-dir` + 清残留 chrome**：必须用独立 profile 目录，且启动前杀掉使用同一目录的残留 chrome 进程，否则调试端口被旧进程占用，`/json` 返回的是旧会话的 tab。
3. **WebGL 走软渲染**：无头环境 GPU 不可用，WebGL 页面会黑屏或崩溃。加 `--enable-unsafe-swiftshader --use-angle=swiftshader` 强制 SwiftShader 软渲染。实测 2400px 长边约 2s/张，可接受；输出尺寸设上限防纹理超限。
4. **`toBlob` 需要 `preserveDrawingBuffer:true`**：WebGL 上下文创建时必须传 `preserveDrawingBuffer: true`，否则事件循环清空帧缓冲后 `toBlob`/`toDataURL` 拿到黑图或空图。批量循环里逐项 `dispose()` 纹理/资源，防 4096² 页纹理堆爆显存。
4b. **连不上浏览器时先怀疑探针自己，而不是 chrome**。真实案例（2026-10-08）：在 `main()` 里写了
   一句 `import urllib.parse`，Python 把 `urllib` 当成**该函数的局部名**，于是同一函数里更早的
   `urllib.request.urlopen(...)` 每次抛 `UnboundLocalError`；而那段轮询写的是 `except Exception: pass`，
   于是报错被完全吞掉，症状变成"chrome 起不来 / 连不上浏览器"，白查四轮。
   ⇒ ① **函数内不要 import 顶层已导入的模块**（要子模块就在文件头 `import urllib.parse`）；
   ② 轮询/重试的 `except` 必须**只容忍连接类异常**（`OSError/URLError/ValueError`），
   其余原样抛出或打印——`NameError/UnboundLocalError/AttributeError` 是探针坏了，不是环境没就绪。
   ③ 排障时先打印 `proc.poll()` 与最后一次异常类型，再动启动参数。
5. **`Runtime.evaluate` 前须等页面就绪**：`/json` 出现 tab ≠ 页面加载完成。探针若在目标 DOM（如 `#prog`）存在前发送，evaluate 返回 null 或抛异常。驱动脚本应对 `null` 探针结果做容错重试，或先 evaluate 一个存在性检查再进入正常轮询。


6. **手动驱动 ticker 抓帧时，帧号不是时间轴**（2026-10-11 实测，本案据此得出的"某姿势只持续 1.5 秒"全是假象）。
   无头里 rAF 被节流，于是每帧手动 `PIXI.Ticker.shared.tick(now)` + `app.render()`——但**动画时间跟着真实时间走**，
   而 `Page.captureScreenshot` 每帧要 0.7~1.2 秒 ⇒ 若按"帧号 = 1/fps 秒"排时间轴，帧号与内容时间**脱钩 7~34 倍**
   （18.25 秒的动画在第 16 帧就播完，后面几百帧全是"播完之后"的状态）。
   ⚠️ **喂合成时间戳不解决问题**：自己维护 `window.__tnow += 1000/fps` 再传给 `tick(now)`，实测自证直接报 FAIL
   ——动画时间不由我们喂的 now 决定。正解：**逐帧记 `time.monotonic()`，用它当时间轴**（模型既然按真实时间推进，
   墙钟间隔就是每帧的时间步长）；并加一条**时间轴自证**：拿一条已知曲线（本项目用某个参数的"第一次到 0 的时刻"）
   算出期望时刻，与墙钟轴比，不 PASS 的帧不许用于任何时序判据（单帧目视仍可用）。
   ⇒ 推论：凡是"逐帧差/能量/时长"类跨来源比较，两边必须先各自标定时间轴，否则比的是两套不同的尺子。
   ⚠️ **加了自证 ≠ 修好了时钟**：本项目按上面的墙钟轴重抓一遍，自证**仍然 FAIL**（期望 5.83s vs 真实轴 9.31s，
   起点锚与交叉淡入都会吃进时间）。正确产出是"这批帧不可用于时序判据"这个**否定结论**，不是"已修"。

## 深入参考（按需加载，不要一次全读）

主文件是批量导出工作流与六坑；做"批量断言/验证"而非导出时，Read 验证参考件（内含大量假灯判据，先 grep 定位）。

| 主题 | 参考件 |
|---|---|
| 验证类任务额外坑（视觉/交互态、画廊探针、帧时归因、像素验收、遮罩、分批渲染） | `references/verification-pitfalls.md` |

> 参考件较大时先 grep 定位小节再读，别整文件灌进上下文。
## 验证

- 抽查 1-3 张产物：非黑图、尺寸正确、内容符合预期 → 展示给用户确认
- 用户确认后再全量运行（呼应项目「全量运行前必须确认」规则）

## 参考

- `reference.md`：CDP 驱动脚本完整骨架 + 自治导出页落盘/断点续跑 JS 片段
- 碧蓝航线项目实例：`docs/WORKFLOWS.md` WF-14、`gallery_src/cg_export.html`、`.diag/run_cg_export.py`