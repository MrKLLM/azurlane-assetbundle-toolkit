# reference.md — 可复用代码模板

以下模板来自碧蓝航线 231 皮肤 CG 批量导出实战（`.diag/run_cg_export.py` / `gallery_src/cg_export.html`），改名即可复用。

## 1. CDP 驱动脚本骨架（Python）

依赖：`pip install websocket-client`

```python
# -*- coding: utf-8 -*-
"""无头 Chrome + CDP 驱动自治导出页。
用法: py -3 run_export.py [--only a,b,c] [--size 2400] [--timeout 1800] [--redo]
"""
import sys, os, json, time, subprocess, urllib.request
sys.stdout.reconfigure(encoding='utf-8')
import websocket

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'  # 按机器调整
PORT = 9333
DEBUG_DIR = os.path.abspath('.chrome_profile')   # 独立 user-data-dir，勿复用日常 profile

def arg(name, default=None):
    return sys.argv[sys.argv.index(name)+1] if name in sys.argv else default

only, size = arg('--only', ''), arg('--size', '2400')
timeout = int(arg('--timeout', '1800'))

url = f'http://127.0.0.1:8777/export.html?autostart=1&size={size}'
if only:
    url += '&only=' + only
if '--redo' in sys.argv:
    url += '&redo=1'

os.makedirs(DEBUG_DIR, exist_ok=True)
# 坑2: 独立 profile；坑1: --remote-allow-origins=*；坑3: swiftshader 软渲染
proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*',
    f'--user-data-dir={DEBUG_DIR}', '--no-first-run', '--no-default-browser-check',
    '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900',
    url,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# /json 就绪 ≠ 页面就绪；这里只找 tab
def wait_ws():
    for _ in range(60):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            for t in tabs:
                if 'export' in t.get('url', '') and t.get('webSocketDebuggerUrl'):
                    return t['webSocketDebuggerUrl']
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError('CDP 未就绪')

ws = websocket.create_connection(wait_ws(), timeout=30)
_id = 0
def ev(expr):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': 'Runtime.evaluate',
                        'params': {'expression': expr, 'returnByValue': True}}))
    while True:
        m = json.loads(ws.recv())
        if m.get('id') == _id:
            return m.get('result', {}).get('result', {}).get('value')

t0, last = time.time(), ''
while time.time() - t0 < timeout:
    # 坑5: 目标 DOM 未就绪时返回 None，用 or '' 容错
    prog = ev("document.querySelector('#prog')?.textContent") or ''
    tail = ev("(function(){var l=document.querySelectorAll('#log div');"
              "return l.length?l[l.length-1].textContent:''})()") or ''
    line = f'{prog} | {tail[:110]}'
    if line != last:
        print(f'[{int(time.time()-t0):4d}s] {line}', flush=True)
        last = line
    if ('全部结束' in tail) or ('已停止' in tail):   # 与导出页的结束标记一致
        break
    time.sleep(2)
ws.close()
proc.terminate()
```

## 2. 自治导出页关键 JS 片段

### WebGL 上下文（坑4）

```js
const gl = canvas.getContext('webgl', { preserveDrawingBuffer: true, antialias: true });
// 没有 preserveDrawingBuffer:true，事件循环清帧后 toBlob 拿到黑图
```

### URL 参数解析 + 断点续跑

```js
const qs = new URLSearchParams(location.search);
const AUTOSTART = qs.get('autostart') === '1';
const ONLY = (qs.get('only') || '').split(',').filter(Boolean);
const SIZE = parseInt(qs.get('size') || '2400');
const REDO = qs.get('redo') === '1';

function log(msg) {
  const d = document.createElement('div');
  d.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`;
  document.getElementById('log').appendChild(d);
}
function setProg(done, total) {
  document.getElementById('prog').textContent = `${done}/${total}`;
}

async function exists(name) {
  const r = await fetch(`/exists?name=${encodeURIComponent(name)}`);
  return (await r.json()).exists;
}

async function run() {
  const items = ALL_ITEMS.filter(n => !ONLY.length || ONLY.includes(n));
  let done = 0;
  setProg(0, items.length);
  for (const name of items) {
    if (!REDO && await exists(name)) {          // 断点续跑：已导出的跳过
      log(`跳过（已存在）: ${name}`);
      done++; setProg(done, items.length);
      continue;
    }
    try {
      const blob = await renderOne(name, SIZE); // 项目自己的渲染函数
      const r = await fetch(`/save?name=${encodeURIComponent(name)}`,
                            { method: 'POST', body: blob });
      if (!r.ok) throw new Error(`落盘失败 HTTP ${r.status}`);
      log(`完成: ${name}`);
    } catch (e) {
      log(`失败: ${name} — ${e.message}`);       // 单项失败不中断队列
    } finally {
      disposeItem(name);                        // 坑4: 逐项 dispose 纹理防显存堆爆
      done++; setProg(done, items.length);
    }
  }
  log('全部结束');                               // 驱动脚本依赖此结束标记
}

// 等资源/字体/运行时就绪后再自动开跑，避免渲染竞态
window.addEventListener('load', () => {
  if (AUTOSTART) setTimeout(run, 500);
});
```

### HTML 进度区（驱动脚本轮询目标）

```html
<div id="prog">0/0</div>
<div id="log"></div>
```

## 3. 本地服务器落盘接口要点

- `POST /save?name=<x>`：body 为二进制 blob，按 `Content-Type`（如 `image/png`）定扩展名，写入输出目录；返回 200/500
- `GET /exists?name=<x>`：返回 `{"exists": true|false}`，支撑断点续跑
- 静态资源响应加 `Cache-Control: no-cache`，根治「改了页面/JS 但无头浏览器用旧缓存」导致的假象
- 服务器与导出页同源（同端口），避免 fetch 跨域问题

## 4. 踩坑速查表

| 现象 | 根因 | 解法 |
|---|---|---|
| websocket 握手 403 / 连接被拒 | CDP 新版安全策略拒 Origin | 启动参数加 `--remote-allow-origins=*` |
| `/json` 返回旧 tab、行为诡异 | 同 profile 残留 chrome 占端口 | 独立 `--user-data-dir`，启动前清残留进程 |
| WebGL 黑屏 / 页面崩 | 无头环境无 GPU | `--enable-unsafe-swiftshader --use-angle=swiftshader` |
| toBlob 得到黑图/空图 | 帧缓冲已被清空 | 上下文加 `preserveDrawingBuffer: true` |
| 批量中途越来越慢/崩显存 | 纹理未释放 | 每项渲染完 `dispose()`，输出尺寸设上限 |
| 探针返回 null、轮询报错 | `/json` 就绪 ≠ 页面就绪 | 探针用 `?.` + `or ''` 容错，或先查 DOM 存在性 |
| 改了页面但行为没变 | 浏览器旧缓存 | 服务器发 `Cache-Control: no-cache` |
