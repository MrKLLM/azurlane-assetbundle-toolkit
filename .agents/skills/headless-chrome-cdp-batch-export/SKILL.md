---
name: headless-chrome-cdp-batch-export
description: 无头 Chrome + CDP 批量驱动本地网页完成渲染/截图/资产导出。当任务需要用浏览器前端运行时（如 Spine/WebGL/Canvas/JS 库）批量产出图片或数据文件时使用——触发词：无头浏览器批量导出、CDP 驱动网页、headless chrome 批量截图、浏览器渲染落盘、autostart 参数自动化。不适用于单次网页截图和 QwenWork 内置媒体生成工具。
version: 1.6.1
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
   4b. **同一类报错还有第二种成因**：探针刚连上 tab 就 `Runtime.evaluate`，而页面仍在导航 → 执行上下文被销毁。这种**不是并发问题**，串行也照犯。判据：先轮询 `document.readyState === 'complete'`，再对首次求值配"最多 6 次、每次 sleep 4s"的重试（同一张 tab 的默认上下文导航后会重建，重连即可）。⚠️ 别据此判产品坏了——本轮两个验收脚本就是这么假红过。另：脚本崩在半路会把 Chrome 整棵树漏在机器上（`proc.terminate()` 写在最后一行 = 异常时永不执行），注册 atexit 的整树 `taskkill /T /F` 才是兜底。
   4c. **第三种形态最阴：不报错，只是静默附着到别人的浏览器**（2026-09-27 实测）。探针的 `PORT` 与 `--user-data-dir` 写死时，第二个会话起不来新实例（端口被占），`/json` 列出的却是**别人那个正在跑的浏览器**里的同一 URL → 两边驱动交替点同一个页面。症状不是异常而是**数据整齐地错位**：每条断言读到的"当前值"恰好等于**上一次操作**的结果（实测：逐部位点击，`played` 整体滞后一位 ⇒ 62 个部位报出 38 条 WIRING 假红 + 一个模型"加载失败"）。
      ⇒ 判据：结果出现**统一偏移一位 / 整序列平移**这种"太整齐"的形状，先怀疑探针侧污染，不要去改产品；
      跑任何 CDP 探针前先查那条端口上有没有别的 python 在跑
      （`Get-CimInstance Win32_Process -Filter "Name like 'python%'"` 看命令行 + 按 `--user-data-dir` 归属性），
      是别人的长批量任务就等或换端口——**别去改他正在用的脚本**。根治：端口与 profile 一律走 env/CLI 参数。
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

### 视觉 / 交互态专用（2026-09-28~29 一轮前端改版攒下的，每条都对应一次假灯）

9. **CSS 伪类只能被"真实输入"点亮**。`el.dispatchEvent(new MouseEvent('mousemove'))`
   不会让 `:hover` / `:focus-visible` 命中——伪类由浏览器**命中测试**决定，不由事件决定。
   用合成事件测交互反馈，得到的永远是假绿。必须走 `Input.dispatchMouseEvent`。
   ⚠️ 而且**发一次 mouseMoved 不一定刷新命中测试**：要边小幅挪边轮询，直到
   `el.matches(':hover')` 为真再往下读。
10. **按压态的事件类型是 `mousePressed` / `mouseReleased`**。写成 `mouseDown`/`mouseUp`
    会被**静默忽略**——不报错、不警告，只是元素停在 hover 态，于是你读到"按压没反馈"，
    然后去改本来正确的产品代码。
11. **读计算样式必须轮询到过渡落位**。状态刚切换的同一轮求值里读 `getComputedStyle`，
    拿到的是 transition 的**第 0 帧**：`border-color` 还是旧值、`box-shadow` 会显示成
    `旧值, transparent 0 0 0 0`（多层过渡里缺的层按"透明 + 零长度"补齐），
    而**没参与过渡的自定义属性**（`--lift` 之类）已经跳到位 —— 三者不一致就是这一帧的特征。
    固定 `sleep(0.3)` 也不保险：挂了 `backdrop-filter` 的页面在无头里只有十几帧每秒，
    一条 .18s 的过渡要等好几帧才起步。一律**轮询到值落位或超时**，判"最终有没有到位"。
12. **想用"逐像素相同"证明"界面自己在动/没在动"，先排除两类污染**：
    ① `loading=lazy` 的图会在页面放着放着时继续到货 → 整图哈希必然变化；
    ② 任何**跟指针走的持久样式**（例：把镜面高光坐标写进卡片的 `--mx/--my`）会让
    划过的元素永久改变，"回到初始态"这条就永远红——而这恰恰暴露了真实缺陷（页面留下"我动过"的痕迹），
    正确解法是"指针离开即复位"，不是放宽判据。
    ⇒ 比对区要选**永远没有内容元素的条带**（容器 padding 留白那种），并先轮询到图片停止到货。
13. **给父元素的直接子元素统一设 `z-index` 会切碎层叠上下文**：子树里 `z-index:40` 的弹层
    压不过 DOM 中排在其后的兄弟，症状是"下拉面板和下一行文字混在一起"。
    判"弹层是否真的盖住"不要比 z-index 数值，要用 `document.elementFromPoint()`
    取一个**低于父容器底边**的点，断言命中目标在面板内部。
14. **判"看不见 / 没效果"必须按满偏算**。曾实测某 3D 倾斜只有 1.4°/1.8°，据此判定
    "肉眼约等于零"并删掉整条动效——但取样点在元素 68%/32% 处，**满偏本来有 4.5°**。
    要么按最大偏移设计断言，要么取多个点判 `max`。把"取样点偏小"当成"设计幅度小"
    会导致删掉用户其实要的东西（用户原话：要的是看得见，不是不要）。
15. **Chrome 会把 `color-mix()` 的计算值序列化成 `color(srgb R G B / A)` / `oklab(... / A)`**。
    取 alpha 只写 `rgba(...)` 正则的话，13% 的半透明会被读成**不透明**，
    "整块填色回来了"这类判据立刻假红。alpha 解析要同时认 `rgba()`、斜杠语法、以及 `oklab/color()`。
16. **把主观反馈翻译成能红的量化判据**，否则"还是不够高级"这种话没法验收。本轮的三条翻译：
    "还是毛玻璃" → 背景模糊 >10px **或** 面板底色 alpha >0.30 就红；
    "不要发光" → 非 `inset` 的 box-shadow 层里出现第 4 个长度值（spread）就红；
    "不要整块填色" → 选中项的 `background-image` 含 gradient、或底色 alpha >0.30 就红。
    每条都要配**阳性对照**（旧版本确实会被判红），否则判据可能是空的。
17. **"整屏逐像素相同"在密集仪表盘上必然假红，要先把屏幕分区**。第 12 条那招（挑一条
    永远没有内容元素的条带来比）在画廊能用，因为画廊底部天然有一条空带；仪表盘没有。
    实测连红三次，三次都不是产品问题：
    ① 半透明面板在 WebGL 活动后重新合成，**渐变 dither 变了** → 最大差 2、4727 个点，
       全落在半透明层覆盖处（肉眼完全看不出来）；
    ② CDP 可信鼠标**停在谁身上谁就点亮 `:hover`** → 卡片被抬 1px，文字逐通道差 **209**，
       于是"起浪那张"量的其实是 hover 不是水；
    ③ 被裁一半的元素 `getBoundingClientRect` **仍越过滚动容器底边** → 取样框量到了容器外
       故意露背景的区域，"渗进内容 133"是取样框写错。
    ⇒ 三条通用手法：**按"画了背景的元素的矩形"把屏幕分区**（背景可见区 / 不透明内容区 /
    故意留的半透明装饰区各自判，掩码里要排除 `html`/`body` 和背景层自己，否则背景可见区
    = 0 像素，判据退化成空）；**每次拍照前把指针停回同一个无 hover 角落**；
    **取样框与滚动容器及视口求交**。掩码算出的背景像素数要当断言查（<5000 直接判红），
    不然"没有可比的像素"会被当成通过。
18. **半透明面板 + 会动的装饰背景 = 背景渗进文字区**。alpha 0.90 听起来很实，量出来
    一颗星能在某个字下面造成 **36 级**差异。⇒ 承载数据/图片的面板**必须完全不透明**，
    装饰只留给没有数据的带（标题带、页脚带）。
    ⚠️ 反向陷阱同样致命：面板全不透明之后，装饰区若没有一块**真的能看见**的地方，
    主题会被挤到只剩栏缝——实测浪在背景可见区只剩 68 个像素，等于没有主题，
    而"不渗进内容"这条**照样全绿**。⇒ "不遮挡"与"存在感"是两条独立判据，
    后者要配正向对照（关掉装饰后背景可见区必须明显变化）。
18b. **而"卡片内部逐像素比对"这条通道，在背景会重绘的页面上是不可用的**（同一天换背景引擎后撞到）。
    两种噪声都能压过真实泄漏：① 切"装饰开/关"会改变合成层，Chrome **重新光栅化整页**，
    全站文字边缘都能差 ±209（实测 20 万个差异点，散布在明明不透明的面板内部）；
    ② 画布每重绘一次也有同样效应，于是"背景在动那张 vs 静止那张"在卡片内部量到 154。
    ⇒ 别再拿像素比"渗不渗进来"，换成两条**结构性**判据：
    ① 数据面 `getComputedStyle().backgroundColor` 的 alpha 必须 = 1；
    ② 每个数据元素的 `getBoundingClientRect()` 必须整张落在某个不透明面板的矩形内。
    逐像素只保留在**背景可见区**（那里没有文字层，量的就是装饰本身）。
    ⚠️ 换判据时必须同时留一条**会红**的正向对照：这次是"测得太严"造成假红，
    反过来"测得太松"就是假绿，是同一条纪律的两个方向。
    顺带：判据②替我逮住一个真 bug——为画装饰线给面板加 `overflow:hidden`，
    而列是 flex 容器 ⇒ 面板被压扁、卡片下沿被切 45px、日志格塌成 28px。
    **裁切类缺陷通常要靠"几何包含"才看得见；截图上它只是"少了半行字"。**

19. **界面"看起来坏了"常常是首屏在算贵东西**。控制台的 `/api/state` 要算输入指纹
    （`os.walk` 9 万个源包，几秒），前端 8 秒轮一次 ⇒ 每 8 秒白扫一遍盘，
    而**打开后的前十几秒页面只有图例渲染出来**，中间全空 —— 探针如果只 `sleep(2)`
    就断言，会把这条拍成"产品缺陷"。⇒ 服务端给这类聚合值加 TTL 缓存（失败不缓存，
    下一拍重试）；前端 `render()` 必须扛得住数据为 null，并把"正在算"显示成一句话
    而不是留一个 `—`；探针则必须**轮询到就绪再断言**（与第 3 条同一条规矩）。
9. **`/json` 必须按 URL 过滤 target**：`--headless=new` 启动后 `/json` 里可能有多个带
   `webSocketDebuggerUrl` 的条目（新标签页、扩展页、iframe），抓第一个会连到**错的调试目标**，
   症状是 `Runtime.evaluate` 直接超时或拿到空结果，看起来像"页面没加载完"。
   写 `if '<你的路径段>' in tab.get('url','') and tab.get('webSocketDebuggerUrl')`。
10. **`subprocess.Popen(chrome)` + `proc.terminate()` 不回收浏览器进程**：被杀的是启动器，
    真正的浏览器进程随 `--user-data-dir` 常驻。下一次用**同一个 profile** 启动 Chrome 时，
    它会直接复用那个还活着的旧实例（并忽略你新传的 URL）——于是探针拿到的是**上一轮的页面**，
    出现"我明明改了也部署了，截图却还是旧的"这种假矛盾，足以让人误判修复无效、甚至去改本来正确的代码。
    ⇒ 探针要么每次用唯一 profile（`chrome_x_<timestamp>`），要么收尾按 profile 精确清进程；
    判"修复无效"之前先确认自己没连到旧实例。
    **同一坑的两种更狠的形态（2026-09-27 各踩一次，把用户机器压到只剩 1.1GB 空闲）**：
    ① `proc.terminate()` 只杀启动器、**不杀进程树** —— crashpad / gpu(SwiftShader) / network /
       若干 renderer 会整棵留着继续吃 CPU 与内存（一次验收漏两棵树 = 16 个 chrome 进程）。
       正确收尾是整树杀：`subprocess.call(['taskkill','/T','/F','/PID',str(proc.pid)])`。
    ② 清理语句写在脚本**最后一行** ⇒ 中途抛异常（典型 `RuntimeError: Execution context was destroyed`）
       就压根执行不到，比"忘了写 terminate"更隐蔽，因为正常路径看着是对的。
       正确姿势：注册 `atexit`（本项目已抽成 `scripts/diag/chrome_tree.py:install(proc)`），
       新增探针一律走它，别再各自在末尾写 `terminate()`。
    ③ 自查残留时 `Get-CimInstance Win32_Process | ? { $_.CommandLine -match "chrome_x_1"` 这类写法
       会**匹配到执行查询的 powershell/bash 自己**（查询串就在它的 CommandLine 里），
       误报"还有 N 个残留"、甚至差点去 kill 自己的 shell —— 先按 `$_.Name -eq "chrome.exe"` 过滤再匹配。
11. **观测通道的编码问题会被当成被测对象的缺陷**：Python 在中文 Windows 上 stdout 默认 GBK，
    把 UTF-8 内容（如带中文的资源名）打成 mojibake 后打印出来，看起来像**被测数据编码坏了**。
    本项目据此写过一条"`.skel` 与 `.atlas` 区域名编码不一致"的错误结论，
    hexdump 才证明两边逐字节相同、都是合法 UTF-8。
    ⇒ 子进程输出一律 `env=dict(os.environ, PYTHONIOENCODING='utf-8')` +
    `sys.stdout.reconfigure(encoding='utf-8')`；**下"字节层/编码层"结论前必须直接 hexdump 原始字节**，
    不能引用任何经过终端编码的字符串。


## 验证

- 抽查 1-3 张产物：非黑图、尺寸正确、内容符合预期 → 展示给用户确认
- 用户确认后再全量运行（呼应项目「全量运行前必须确认」规则）

## 参考

- `reference.md`：CDP 驱动脚本完整骨架 + 自治导出页落盘/断点续跑 JS 片段
- 碧蓝航线项目实例：`docs/WORKFLOWS.md` WF-14、`gallery_src/cg_export.html`、`.diag/run_cg_export.py`