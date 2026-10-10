# -*- coding: utf-8 -*-
"""3D 宿舍页（gallery_src/room3d.html）的真实页面验收。

为什么必须打在**真实页面**上，而不是继续用 harness：
harness 是我自己拼的加载代码，它绿只说明"我以为的加载方式能跑"，不说明画廊里那一页能跑。
本页要交付给用户看，判据必须落在页面自己的产品可见状态上：
  1. 字节级可达（服务器"活着但半死"会吐 0 字节，光看 200 不够 —— 见画廊服务器两种失效形态）
  2. 页面自报的计数 与 GLB 文件本体 与 Unity 侧台账 **三方一致**（两个来源都可能错，一个来源不叫锚点）
  3. lightmap 真的走 UV1（`chanBad==0`），页号槽位数量对得上
  4. 三个"推断"开关（窗外天海 / 白云 / 绿叶）各自**开与关必须改变画面**，
     且同状态连拍两帧必须**逐字节相同**（先证明尺子不抖，再证明开关有效）
  5. 反向对照：lightmap 关掉、泛光拉到 0 —— 都该改变画面。不改变的旋钮是死块。
  6. 断掉承重文件（把 room.glb 改名）必须 fail-closed，不许"看着像成功"

⚠️ 无头浏览器必须带 `--window-size`：视口 0×0 时会"结构全在、内容全空"，
   探针开头先断言 innerHeight>400（踩过的坑，见 windows-gitbash-cjk-pitfalls §7）。
用法：py -3 scripts/diag/room3d_page_probe.py [--port 8777] [--keep-shots]
产物：.diag/dorm3d_room/page_*.png 与终端逐条 PASS/FAIL
"""
import base64
import io
import json
import os
import struct
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)
import cdp_slot            # noqa: E402
import chrome_tree         # noqa: E402
import paths as P          # noqa: E402

CHROME = P.tool('AL_CHROME', 'chrome', r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
GAL = os.path.join(P.OUT, 'gallery_v2')
SHOTS = os.path.join(P.ROOT, '.diag', 'dorm3d_room')
FAIL = []
PORT = 8777
for a in sys.argv[1:]:
    if a.startswith('--port'):
        PORT = int(a.split('=', 1)[1]) if '=' in a else int(sys.argv[sys.index(a) + 1])


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAIL.append(msg)


def get_bytes(url, timeout=90, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read()


# ───────────────────────── 1. 字节级可达 ─────────────────────────
def reachability():
    print('== 1. 服务端字节可达（不是只看 200）==')
    base = f'http://127.0.0.1:{PORT}/gallery_v2/'
    try:
        st, b = get_bytes(base + 'room3d.html', timeout=20)
    except Exception as e:
        # 8777 上可能跑着**正本**那份 _gallery_server.py：它的静态根是仓库根，
        # 于是 /gallery_v2/… 必 404，而 /Output/gallery_v2/… 是 200。
        alt = ''
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{PORT}/Output/gallery_v2/room3d.html',
                                         timeout=15) as r:
                alt = f'{r.status} {len(r.read())} 字节'
        except Exception:
            pass
        hint = ('  ⇒ 8777 跑的是**正本** gallery_src/_gallery_server.py（静态根=仓库根，URL 多一层 Output/）。'
                f'\n    要按线上口径验收请起部署副本：cd Output/gallery_v2 && py -3 _gallery_server.py（实测 {alt}）'
                if alt else '')
        say(False, f'页面取不到：{e}{hint}')
        return None
    say(st == 200 and len(b) > 8000, f'room3d.html {len(b)} 字节')
    say(b'__ROOM3D' in b and b'vendor/three/three.module.min.js' in b,
        '页面里探针钩子与 vendor 路径都在（不是旧版残留）')
    for rel, lo in [('dorm3d/room.glb', 20_000_000), ('dorm3d/room.glb.truth.json', 5_000),
                    ('dorm3d/room.lightmaps.json', 5_000), ('dorm3d/room.render.json', 300),
                    ('dorm3d/room.views.json', 300),
                    ('vendor/three/three.module.min.js', 100_000),
                    ('vendor/three/jsm/controls/OrbitControls.js', 2_000),
                    ('vendor/three/jsm/postprocessing/UnrealBloomPass.js', 2_000),
                    ('dorm3d/lightmaps/lm0_ast_sh_lightmap_01_final.png', 10_000)]:
        try:
            st, b = get_bytes(base + rel, timeout=120)
            say(st == 200 and len(b) >= lo, f'{rel} {len(b)} 字节（阈值 {lo}）')
        except Exception as e:
            say(False, f'{rel} 取不到：{e}')
    # 断点续传：31 MB 的模型没有 Range 就没法边下边看，服务器号称实现了 206
    try:
        req = urllib.request.Request(base + 'dorm3d/room.glb', headers={'Range': 'bytes=0-1023'})
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
            say(r.status == 206 and len(body) == 1024,
                f'Range 分段 206 / {len(body)} 字节（{r.headers.get("Content-Range")}）')
    except Exception as e:
        say(False, f'Range 请求失败：{e}')
    return base


# ─────────────────────── 2. GLB 本体独立计数 ───────────────────────
def glb_counts():
    """绕开页面与台账，直接按 glTF 规范数一遍 JSON chunk。第三个独立来源。

    ⚠️ 不能拿 `sum(len(mesh.primitives))` 当"three.js 会建出多少个 Mesh"——那是**错误**的：
      · 一个 mesh 有 >1 个 primitive 时，GLTFLoader 把节点变成 Group、每个 primitive 一个子 Mesh；
      · 同一个 mesh 可以被**多个节点引用**（家具复用），每个节点都会实例化一份。
      实测本产物：primitive 只有 279 个，而按节点展开是 299 个 Mesh / 219244 顶点 ——
      正好等于 Unity 侧台账的 prim_total/pos_total。拿 279 去比就会**假红灯**，
      而红到一定程度人就会去放松判据（那才是真正的失效）。两种口径都在这里同时报出来。
    """
    raw = open(os.path.join(GAL, 'dorm3d', 'room.glb'), 'rb').read()
    magic, version, _total = struct.unpack_from('<III', raw, 0)
    assert magic == 0x46546C67, f'不是 glTF 二进制（magic={magic:#x} version={version}）'
    jl, jtype = struct.unpack_from('<II', raw, 12)   # 偏移 12 才是第一个 chunk 的头
    assert jtype == 0x4E4F534A, '第一个 chunk 不是 JSON'
    g = json.loads(raw[20:20 + jl].decode('utf-8'))
    acc, meshes = g.get('accessors', []), g.get('meshes', [])

    def mpos(mi):
        return sum(acc[p['attributes']['POSITION']]['count'] for p in meshes[mi]['primitives']
                   if p.get('attributes', {}).get('POSITION') is not None)

    prims = [len(m.get('primitives', [])) for m in meshes]
    exp_meshes = exp_pos = 0
    for n in g.get('nodes', []):
        if 'mesh' not in n:
            continue
        pc = prims[n['mesh']]
        exp_meshes += 1 if pc == 1 else pc      # 单 primitive 直接挂节点上，多 primitive 拆成子 Mesh
        exp_pos += mpos(n['mesh'])
    return {"primitives": sum(prims), "pos_unique": sum(mpos(i) for i in range(len(meshes))),
            "instanced_meshes": exp_meshes, "pos_instanced": exp_pos,
            "nodes_with_mesh": sum(1 for n in g.get('nodes', []) if 'mesh' in n),
            "materials": len(g.get('materials', [])),
            "lights": len(g.get('extensions', {}).get('KHR_lights_punctual', {}).get('lights', [])),
            "blend": sum(1 for m in g.get('materials', []) if m.get('alphaMode') == 'BLEND')}


# ───────────────────────── CDP 驱动 ─────────────────────────
def connect(base):
    PORT_C, PROFILE = cdp_slot.slot(ROOT, 'r3dp')
    os.makedirs(SHOTS, exist_ok=True)
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT_C}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1440,1000',
                             base + 'room3d.html'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    for _ in range(120):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT_C}/json'))
            u = [t['webSocketDebuggerUrl'] for t in tabs
                 if 'room3d.html' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
            if u:
                import websocket
                ws = websocket.create_connection(u[0], timeout=240, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        return None, proc

    _id = 0

    def cmd(m, p=None):
        nonlocal _id
        _id += 1
        ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
        ws.settimeout(240)
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == _id:
                if 'error' in r:
                    raise RuntimeError(json.dumps(r['error'])[:200])
                return r.get('result', {})

    def ev(e):
        r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
        if r.get('exceptionDetails'):
            return {'__err': str(r['exceptionDetails'].get('text'))[:200]}
        return r.get('result', {}).get('value')
    return (cmd, ev), proc


# 同状态两帧必须逐字节相同 ⇒ 先证明尺子不抖，才有资格说"开关改变了画面"
HASH_JS = r"""(()=>{const c=document.querySelector('#stage canvas');
  if(!c) return {err:'canvas 还没建'};
  const o=document.createElement('canvas'); o.width=320; o.height=200;
  const x=o.getContext('2d',{willReadFrequently:true}); x.drawImage(c,0,0,320,200);
  const d=x.getImageData(0,0,320,200).data;
  let s=0, sat=0, ink=0, hist=new Array(8).fill(0);
  for(let i=0;i<d.length;i+=4){const r=d[i],g=d[i+1],b=d[i+2];
    const l=0.2126*r+0.7152*g+0.0722*b; s+=l; sat+=Math.max(r,g,b)-Math.min(r,g,b);
    if(Math.max(r,g,b)>40) ink++; hist[Math.min(7,l*8/255|0)]++;}
  return {n:d.length/4, sum:Math.round(s), sat:Math.round(sat), ink:ink/(d.length/4),
          hist:hist, w:c.width, h:c.height};})()"""


def stable(ev, tries=6):
    """取样到"连续两次逐字节相同"为止，返回 (稳定哈希, 第几次成功, 原始值)。

    ⚠️ 两件事都得防：
      · 拿 None 当哈希参与比较 —— 会把"取样失败"读成"画面没变"，于是所有"画面改变"
        判据红、所有"可逆"判据绿（上一版就是这个形状：5 红 5 绿，看着像页面坏了，
        其实是探针自己没点到按钮）。取不到稳定帧必须**显式判红并停**。
      · 页面在连续 rAF 里渲染，理论上取样可能落在合成中的不同瞬间。实测阻尼收敛后
        静止连拍 6 帧逐字节相同 ⇒ 不必改按需渲染，但"重试到相同"仍然比"赌一次"便宜。
    """
    prev = None
    for i in range(tries):
        cur = ev(HASH_JS)
        if not isinstance(cur, dict) or 'err' in cur or '__err' in cur:
            return None, i + 1, cur
        j = json.dumps(cur, sort_keys=True)
        if prev is not None and j == prev:
            return j, i + 1, cur
        prev = j
        time.sleep(0.12)
    return None, tries, prev


def click(ev, sel):
    """点一个开关并**回报它是否真的翻了**。

    ⚠️ 上一版这里把选择器原样拼进 `querySelector(%s)`，`"` 一嵌就成 JS 语法错，
    evaluate 返回 {'__err':…} 而我**把返回值丢了** ⇒ 六次点击一次都没落地，
    五个"画面改变"判据全红、五个"可逆"判据全绿（因为两边都是同一个没动过的画面）。
    ⇒ 探针必须自证"我点到了"，否则"开关无效"与"探针没点到"这两种红长得一模一样。
    """
    return ev(r"""(()=>{const b=document.querySelector(%r); if(!b) return {nf:1};
      const k=b.dataset.k, v0=window.__ROOM3D.on[k];
      b.click();
      return {cls:b.classList.contains('on'), v0:v0, v1:window.__ROOM3D.on[k],
              slots:window.__ROOM3D.lmSlots, cloud:window.__ROOM3D.cloudwMats,
              leaf:window.__ROOM3D.leafwMats};})()""" % sel)


def settle(ev, ms=260):
    """点完开关后要等页面真的重画一帧再取样。
    lightmap 那条路径里 toggle() 是 async（要 await 贴图），当场取样拍到的是**改之前**的那一帧。"""
    return ev("(async()=>{const t=m=>new Promise(r=>setTimeout(r,m)); await t(%d); return 1;})()" % ms)


def pick_view(ev, i):
    """点第 i 个机位按钮，回报页面**真的**把相机挪到哪了（不靠返回值猜，读 S.camPos）。"""
    return ev(r"""(()=>{const b=document.querySelector('#views .sw[data-v="%d"]');
      if(!b) return {nf:1};
      b.click();
      return {view:window.__ROOM3D.view, fov:window.__ROOM3D.viewFov,
              pos:window.__ROOM3D.camPos, on:b.classList.contains('on')};})()""" % i)


def main():
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    base = reachability()
    if not base:
        print('\n服务器没起：py -3 gallery_src/_gallery_server.py')
        return 2
    c = glb_counts()
    print('== 2. GLB 本体独立计数 ==')
    print('  ', json.dumps(c, ensure_ascii=False))

    con, proc = connect(base)
    if not con:
        print('[FAIL] 连不上无头浏览器')
        return 2
    cmd, ev = con
    try:
        print('== 3. 视口与载入（0×0 视口会得到"结构全在、内容全空"的假绿）==')
        v = ev('({w:innerWidth,h:innerHeight, dpr:devicePixelRatio})')
        say(isinstance(v, dict) and v.get('h', 0) > 400, f'视口 {v}')
        d = ev(r"""(async()=>{const t=ms=>new Promise(r=>setTimeout(r,ms));
          for(let i=0;i<400 && !(window.__ROOM3D&&window.__ROOM3D.done);i++) await t(300);
          return window.__ROOM3D?{done:window.__ROOM3D.done,err:window.__ROOM3D.err,
            mesh:window.__ROOM3D.meshObjects,pos:window.__ROOM3D.posTotal,
            lights:window.__ROOM3D.lights,lmSlots:window.__ROOM3D.lmSlots,
            lmMats:window.__ROOM3D.lmMats,
            lmPages:window.__ROOM3D.lmPages,chanOk:window.__ROOM3D.chanOk,
            chanBad:window.__ROOM3D.chanBad,channel:window.__ROOM3D.lmChannel,
            ambient:window.__ROOM3D.ambient,declared:window.__ROOM3D.declared,
            sceneTris:window.__ROOM3D.sceneTris,on:window.__ROOM3D.on,
            views:window.__ROOM3D.views,view:window.__ROOM3D.view,
            camPos:window.__ROOM3D.camPos,viewFov:window.__ROOM3D.viewFov,
            hud:(document.getElementById('hud')||{}).textContent||'',
            loadHidden:document.getElementById('load').classList.contains('hide'),
            sw:[...document.querySelectorAll('.sw[data-k]')].map(b=>b.dataset.k+':'+b.classList.contains('on'))}
            :{missing:1};})()""")
        if not isinstance(d, dict) or d.get('missing') or d.get('__err'):
            say(False, f'页面状态取不到：{str(d)[:200]}')
            return 1
        say(d['done'] and not d['err'], f"页面自报：done={d['done']} err={d['err'] or '无'}")
        say(bool(d['loadHidden']), '载入遮罩已收起（不是停在进度条上）')
        say(d['sceneTris'] > 1000, f"真的画出了三角 {d['sceneTris']}（0 = 画布是空的）")

        print('== 4. 三方一致：页面自报 ↔ GLB 本体（按节点实例化口径）↔ Unity 台账 ==')
        dec = d['declared'] or {}
        say(d['mesh'] == c['instanced_meshes'] == dec.get('prim'),
            f"网格 {d['mesh']} / GLB 实例化 {c['instanced_meshes']}"
            f"（primitive 本体只有 {c['primitives']}，差额来自多 primitive 节点与 mesh 复用）"
            f" / 台账 {dec.get('prim')}")
        say(d['pos'] == c['pos_instanced'] == dec.get('pos'),
            f"顶点 {d['pos']} / GLB 按节点 {c['pos_instanced']}（唯一 mesh 合计 {c['pos_unique']}）"
            f" / 台账 {dec.get('pos')}")
        say(d['lights'] == c['lights'], f"灯 {d['lights']} / GLB KHR_lights_punctual {c['lights']}")
        say(dec.get('blend') == c['blend'], f"透明材质 {c['blend']} / 台账 {dec.get('blend')}")
        say('lightmap 槽位' in d['hud'], f"HUD 报的是内容不是 MIME：{d['hud'][:88]}…")

        print('== 5. 烘焙 lightmap 走的是第二套 UV ==')
        say(d['channel'] == 1, f"texture.channel={d['channel']}（0 会采到漫反射 UV）")
        say(d['lmPages'] == 5, f"lightmap 页数 {d['lmPages']}")
        say(d['chanBad'] == 0 and d['chanOk'] > 0,
            f"UV1 校验 通过 {d['chanOk']} / 失败 {d['chanBad']}（失败>0 = 有槽位采样用错套 UV）")
        say(d['lmSlots'] == d['chanOk'], f"槽位数 {d['lmSlots']} 与被核对数一致（没有漏量的槽位）")
        say(d['lmMats'] == (d['declared'] or {}).get('lmMaterials'),
            f"挂上 lightMap 的**唯一材质** {d['lmMats']} / 台账 {dec.get('lmMaterials')}"
            "（槽位数会因材质复用大于它，两者不能混用）")
        say(bool(d['ambient']) and d['ambient'].get('mode') == 3,
            f"环境光取自包内 RenderSettings：{json.dumps(d['ambient'], ensure_ascii=False)}")

        print('== 5b. 机位表：构建期 sidecar ↔ 页面相机 ↔ 取景自证 ==')
        try:
            vs = json.load(io.open(os.path.join(GAL, 'dorm3d', 'room.views.json'), encoding='utf-8'))
        except Exception as e:
            vs = {'views': [], '_err': str(e)[:120]}
        names = [v['name'] for v in vs['views']]
        say(names == ['bedroom', 'living', 'kitchen'],
            f"sidecar 机位 {names}{('  读取失败 ' + vs.get('_err', '')) if vs.get('_err') else ''}")
        # F1 自证（生成器自己算的，这里重算一遍判它）：这一簇必须在画面里，
        # 否则该分区的面积/亮度统计量根本不代表那个分区（真实回退过：厨房与窗相差 149°，
        # 取角平分线后拍到的是壁炉墙）。
        for v in vs['views']:
            say(v['ang_cluster'] <= v['half_fov'],
                f"{v['name']}: 簇在画面内（{v['ang_cluster']}° ≤ 半视场 {v['half_fov']}°，"
                f"站位来自{v['how']}）")
        say([x.get('name') for x in (d['views'] or [])] == names,
            f"页面读到的机位表与 sidecar 一致：{[x.get('name') for x in (d['views'] or [])]}")
        if names and d['camPos']:
            p0 = vs['views'][0]['pos']
            dev = max(abs(a - b) for a, b in zip(d['camPos'], p0))
            say(dev < 1e-3, f"默认机位 {d['view']}：相机落在 sidecar 声明的 {p0}（最大偏差 {dev:.1e}）")
        for i, v in enumerate(vs['views'][1:], 1):
            settle(ev)
            before, _, _ = stable(ev)
            r = pick_view(ev, i)
            settle(ev)
            after, _, _ = stable(ev)
            moved = bool(r.get('pos')) and max(abs(a - b) for a, b in zip(r['pos'], v['pos'])) < 1e-3
            say(moved and r.get('view') == v['name'] and after != before and after is not None,
                f"点机位 {v['name']}：相机真的挪到 {v['pos']}、画面改变（当前 {r.get('view')}）")
        settle(ev)
        pick_view(ev, 0)
        settle(ev)

        print('== 6. 三个"推断"开关各自必须改变画面（先证明点击落地，再谈画面）==')
        h, tries, raw0 = stable(ev)
        if h is None:
            say(False, f'取不到稳定帧 ⇒ 尺子本身无效，后面全部不作结论：{json.dumps(raw0)[:200]}')
            return 1
        say(True, f'尺子可用：连续两次取样逐字节相同（第 {tries} 次尝试，ink={raw0["ink"]:.4f}）')
        for k, cn, rk in [('sky', None, None), ('cloudw', 'cloudwMats', 'cloud'),
                          ('leafw', 'leafwMats', 'leaf')]:
            settle(ev)
            before, _, _ = stable(ev)
            r = click(ev, '.sw[data-k="%s"]' % k)
            settle(ev)
            landed = isinstance(r, dict) and r.get('v0') is False and r.get('v1') is True
            say(landed, f'开关 {k}：点击真的落地了（S.on 由 {isinstance(r,dict) and r.get("v0")} '
                        f'翻成 {isinstance(r,dict) and r.get("v1")}）—— 探针不自证这一条，'
                        '"开关无效"与"探针没点到"两种红长得一样')
            if not landed:
                continue
            after, _, _ = stable(ev)
            m = r.get(rk) if rk else None
            if rk:
                say(after is not None and before is not None and after != before and (m or 0) > 0,
                    f'开关 {k}：画面改变（重画 {m} 张材质，默认本来是关的）')
            else:
                say(after != before and after is not None, f'开关 {k}：开之后画面改变')
            # 关掉必须还原，否则"开关"是单向滤镜，自证就假了
            click(ev, '.sw[data-k="%s"]' % k)
            settle(ev)
            back, _, _ = stable(ev)
            say(back == before, f'开关 {k}：关回去画面与开之前逐字节相同（可逆）')

        print('== 7. 反向对照：不改变画面的旋钮是死块 ==')
        settle(ev)
        before, _, _ = stable(ev)
        r = click(ev, '.sw[data-k="lm"]')
        say(isinstance(r, dict) and r.get('v0') is True and r.get('v1') is False,
            f'开关 lm：点击落地（{json.dumps(r, ensure_ascii=False)[:80]}）')
        settle(ev, 700)     # lightmap 那条路径要 await 贴图，260ms 不够
        off, _, _ = stable(ev)
        say(off != before and off is not None, '关掉 lightmap ⇒ 画面改变（它真的在参与渲染）')
        slots_off = ev('window.__ROOM3D.lmSlots')
        say(slots_off == 0, f'关掉后自报槽位 {slots_off}（不是只改了个数字）')
        click(ev, '.sw[data-k="lm"]')
        settle(ev, 700)
        say(stable(ev)[0] == before, '再开回来 ⇒ 逐字节回到原画面')
        ev("""(()=>{const r=document.getElementById('rBloom'); r.value='0';
             r.dispatchEvent(new Event('input',{bubbles:true}));})()""")
        settle(ev)
        say(stable(ev)[0] != before, '泛光 0.6→0 ⇒ 画面改变（滑杆不是死块）')
        ev("""(()=>{const r=document.getElementById('rExp'); r.value='2.0';
             r.dispatchEvent(new Event('input',{bubbles:true}));})()""")
        settle(ev)
        say(stable(ev)[0] != before, '曝光 1.2→2.0 ⇒ 画面改变')

        print('== 8. 截图交人看 ==')
        ev("""(()=>{const r=document.getElementById('rBloom'); r.value='0.6';
             r.dispatchEvent(new Event('input',{bubbles:true}));
             const e=document.getElementById('rExp'); e.value='1.2';
             e.dispatchEvent(new Event('input',{bubbles:true}));
             document.querySelector('.sw[data-k="sky"]').click();
             document.querySelector('.sw[data-k="cloudw"]').click();
             document.querySelector('.sw[data-k="leafw"]').click();})()""")
        settle(ev, 1200)
        cmd('Page.enable')
        b64 = cmd('Page.captureScreenshot', {'format': 'png'})['data']
        fp = os.path.join(SHOTS, 'page_with_inference.png')
        io.open(fp, 'wb').write(base64.b64decode(b64))
        print('  截图:', fp)
        say('非包内' in (ev("document.getElementById('hud').textContent") or ''),
            '开着天海时 HUD 明写"非包内数据"（不让用户把补摆的当成包里的）')
    finally:
        # chrome_tree.install 已登记：terminate 会连带杀掉它 fork 的 renderer/GPU 子进程，
        # 否则下一个会话会在同一个 profile 上撞车
        try:
            proc.terminate()
            proc.wait(timeout=12)
        except Exception:
            proc.kill()

    print('\n' + ('收尾：全部判据通过' if not FAIL else f'收尾：{len(FAIL)} 条判据红'))
    for f in FAIL:
        print('  ! ' + f)
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
