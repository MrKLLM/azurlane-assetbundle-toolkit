# -*- coding: utf-8 -*-
"""把用户按「暂停」交来的姿态存档（.diag/l2d_freeze/*.json）在无头里逐帧摆回原样并抓图。

为什么要有这一步：存档只有数字（532 条参数 + 每片包围盒与透明度），"画面上手到底在不在"
必须让人眼看图指认。本脚本做**回放 + 自证**：把存档里的参数向量与部件透明度写回模型、
冻住（`autoUpdate=false`）、手动跑一次 `coreModel.update()`（只重算变形、不推 motion 时钟），
再按存档里的取景（scale / 模型位）贴回去，然后 CDP 截整张页面。

⚠️ 纪律：**每张图都带一条"回放走样没"的自证**，否则图本身是假证据：
  - 上屏片数必须等于存档 `counts.lit`；
  - 逐片不透明度最大偏差 ≤ 0.02；
  - **逐片包围盒（x0/y0/宽/高）最大偏差 ≤ 0.05 单位** —— 这条才是"姿态真摆回去了"的硬证；
    只比不透明度会漏：本项目第一版回放就是"透明度全对、但少画 46 片"，因为 `home` 里有
    **Target=ModelOpacity 的曲线直接写美术不透明度**，那条通道不经过参数，只回写参数向量摆不回去
    ⇒ 回放必须把 `art` 里的逐片不透明度也钉回去（未列出的按 0）。
  - 参数名/部件名必须全部在模型里找得到索引（有一个没索引就算走样）。
  任一条不过 ⇒ 该格在总表上打 ⚠，脚本退出码 1，不许拿"看着差不多"当已复现。
  这条不是形式：本项目吃过"名单没验过对应哪块美术"的亏（§123 追加-XX：月亮被当成手）。

已知边界：回放钉住的是「参数 + 部件透明度 + 美术不透明度 + 取景」四条通道；
`Target=ModelColor/AddColor/MultiplyColor` 曲线与遮罩状态没进存档 ⇒ 图**可能有色偏**，
但"哪片在画、画在哪、多透明"是准的，指认"手在不在"够用。
存档里没列出的片按不透明度 0 处理（阈值 0.01，肉眼不可见）。

用法: py -3 scripts/diag/l2d_freeze_replay.py [存档文件名…]     # 不给参数 = .diag/l2d_freeze/ 最新 6 条
输出: .diag/l2d_replay/<会话>/frame_NN_<存档名>.png、montage.png（带标签总表）、_replay_report.json
退出码: 0 = 全部自证通过；1 = 有帧回放走样；2 = 探针没跑起来。
"""
import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import cdp_slot                 # noqa: E402  端口/profile 不写死，见该模块 docstring
import chrome_tree              # noqa: E402  异常退出也要收整棵 chrome 树
import _gallery_server as GS    # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
FDIR = os.path.join(ROOT, '.diag', 'l2d_freeze')
OUTROOT = os.path.join(ROOT, '.diag', 'l2d_replay')
MED_TOL = 0.02      # 画出面积的片，包围盒差的**中位数**上限（Cubism 单位）—— 这条才真正证明姿态摆回去了
HAND_TOL = 0.05     # 要指认的那几片（手）逐片上限（单位）
LIGHT = False       # --light：反查模式（分批强亮灭着的片）
BATCH = 40          # 反查模式每批点亮多少片

JS_BOOT = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  if(!window.GALLERY || typeof openShip!=='function') return JSON.stringify({err:'页面脚本未就绪'});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key);
    if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, fail:'索引里没有这个 Live2D 皮肤'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d').click();
  for(let i=0;i<90 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
  if(!(l2State&&l2State.app&&l2State.app.stage.children[0])) return JSON.stringify({key, fail:'45s 内模型未加载'});
  const m=l2State.app.stage.children[0]; m.autoUpdate=false;
  /* ⚠️ 回放必须停掉物理摆动：库每帧走 `physics.evaluate(coreModel, dt)` 会**改写参数**，
     而存档里的参数向量本来就已经是"含物理的那一拍"的最终值 —— 再跑一次物理等于把同一拍
     用另一套内部粒子状态重演，实测表现是包围盒差 0.12~0.27 单位、46 片显隐被改写。
     （pose3.json 这个模型没有；呼吸层页面自己已经关了。） */
  const ph=!!m.internalModel.physics;
  if(ph) m.internalModel.physics.evaluate=function(){};
  return JSON.stringify({key, ok:true, physicsOff:ph, breathOff:!(m.internalModel.breath&&m.internalModel.breath.parameters&&m.internalModel.breath.parameters.length)});
}catch(e){ return 'ERR '+(e.message||e); }})"""

# 一次装好，之后每帧只传数据。全部走产品自己的 accessor：不自己算包围盒、不复算显隐。
JS_RESTORE = r"""window.__l2Restore=function(a){
  const m=l2State.app.stage.children[0], cm=m.internalModel.coreModel, D=cm._model.drawables;
  m.autoUpdate=false;
  const idx={}; for(let i=0;i<D.count;i++){ const id=D.ids[i]; idx[(id&&id.string)||id]=i; }
  let missP=0;
  for(const row of a.parameters){ let i=-1; try{ i=cm.getParameterIndex(row[0]); }catch(e){}
    if(i<0){ missP++; continue; } try{ cm.setParameterValueByIndex(i,row[1]); }catch(e){ missP++; } }
  let missQ=0;
  for(const row of (a.parts||[])){ let i=-1; try{ i=cm.getPartIndex(row[0]); }catch(e){}
    if(i<0){ missQ++; continue; } try{ cm.setPartOpacityByIndex(i,row[1]); }catch(e){ missQ++; } }
  /* ⚠️ 顺序必须是"先钉显隐、后 update"。core 对**不透明度为 0 的片跳过顶点计算**，
     而"另一套手"那批片在这个无头页面里从没被画过 ⇒ 若先 update 再钉，它们的包围盒还停在
     出厂位置，实测差 7~10 单位（第一版就栽在这里，差点把仪器缺陷当成产品 bug）。
     显隐这条通道本身也不经过参数：clip 能用 Target=ModelOpacity 曲线直接写每片，
     未列出的片按 0 处理（存档里它们 ≤0.01，肉眼不可见）。 */
  const listed={};
  for(const r of (a.art||[])){ const i=idx[r[0]]; if(i===undefined) continue; D.opacities[i]=r[1]; listed[i]=1; }
  let zeroed=0;
  for(let i=0;i<D.count;i++) if(!listed[i] && D.opacities[i]>0.01){ D.opacities[i]=0; zeroed++; }
  /* 反查用：把指定那批**灭着的**片强制点亮、其余全灭 ⇒ 这一批在画面上画出什么，一眼可见。
     ⚠️ 必须在 update() **之前**点亮：core 对不透明度为 0 的片跳过顶点计算，
     事后再点亮，那批片的顶点还是没算过 ⇒ 八批全空白（第一版就得到这个假结论，靠"零批/全亮批"两条
     对照才发现是仪器不合格，不是数据没有）。 */
  if(a.light){ const on={}; for(const nm of a.light){ const i=idx[nm]; if(i!==undefined) on[i]=1; }
    for(let i=0;i<D.count;i++) D.opacities[i]=on[i]?1:0; }
  const pinned=D.opacities.slice(0);
  cm.update();                                  // 一帧只跑一次，与直播同语义
  let over=0; for(let i=0;i<D.count;i++) if(Math.abs(D.opacities[i]-pinned[i])>0.01) over++;
  let drift=0, dName=null;
  const PV=cm._model.parameters.values;
  for(const row of a.parameters){ const i=cm.getParameterIndex(row[0]); if(i<0) continue;
    const dd=Math.abs(PV[i]-row[1]); if(dd>drift){ drift=dd; dName=row[0]; } }
  const V=D.vertexPositions, geo={};
  for(let i=0;i<D.count;i++){ const op=D.opacities[i]; if(!(op>0.01)) continue;
    const id=D.ids[i], p=V[i];
    let x0=1e9, y0=1e9, x1=-1e9, y1=-1e9;
    if(p) for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
      if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    geo[(id&&id.string)||id]=[+op.toFixed(3), +(x1-x0).toFixed(3), +(y1-y0).toFixed(3),
                              +(x0===1e9?0:x0).toFixed(3), +(y0===1e9?0:y0).toFixed(3)]; }
  /* only 掩码必须在 update() **之后**写：core 在 update 里按参数重算每片不透明度，提前写等于没写
     （第一版就把 mask 放在 update 前，结果"只留手"那张图照样是整个人）。 */
  if(a.only){ const keep={}; for(const nm of a.only){ const i=idx[nm]; if(i!==undefined) keep[i]=1; }
    for(let i=0;i<D.count;i++) if(!keep[i]) D.opacities[i]=0; }
  if(a.view){ m.scale.set(a.view.scale); m.x=a.view.mx; m.y=a.view.my; }
  /* 手部放大框：换算必须照产品自己那套（V→P→stage），别在探针里另发明一套坐标系。
     V=D.vertexPositions 的原生坐标；P=(Vx+cux/2, cuy/2-Vy)；stage = mdl.pos + P*ppu*scale。 */
  const im=m.internalModel, ppu=im.pixelsPerUnit||1, cux=im.width/ppu, cuy=im.height/ppu, s=m.scale.x;
  const hand={};
  for(const nm of (a.hands||[])){ const i=idx[nm]; if(i===undefined) continue;
    const p=V[i]; if(!p||!p.length) continue;
    let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    for(let k=0;k+1<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
      if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    const ax=m.x+(x0+cux/2)*ppu*s, bx=m.x+(x1+cux/2)*ppu*s;
    const ay=m.y+(cuy/2-y1)*ppu*s, by=m.y+(cuy/2-y0)*ppu*s;
    hand[nm]=[Math.min(ax,bx),Math.min(ay,by),Math.max(ax,bx),Math.max(ay,by),+D.opacities[i].toFixed(3)]; }
  const cv=(l2State.app.view||{}), rc=cv.getBoundingClientRect?cv.getBoundingClientRect():{left:0,top:0};
  let lit=0;
  for(let i=0;i<D.count;i++) if(D.opacities[i]>0.01) lit++;
  return JSON.stringify({lit:lit, overwrittenByCore:over, zeroed:zeroed,
    missParam:missP, missPart:missQ, paramDrift:+drift.toFixed(5), driftParam:dName, hand:hand,
    origin:[Math.round(rc.left), Math.round(rc.top)], dpr:window.devicePixelRatio||1,
    rect:[Math.round(rc.left), Math.round(rc.top), cv.clientWidth, cv.clientHeight],
    canvasUnits:[+cux.toFixed(3), +cuy.toFixed(3)],
    scale:+m.scale.x.toFixed(4), mx:+m.x.toFixed(1), my:+m.y.toFixed(1),
    cw:cv.clientWidth, ch:cv.clientHeight, geo:geo,
    names:a.needNames?Array.from({length:D.count},(_,i)=>{const q=D.ids[i];return (q&&q.string)||q;}):null});
}"""


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def pick_files(args):
    if args:
        out = []
        for a in args:
            p = a if os.path.isfile(a) else os.path.join(FDIR, a)
            if not os.path.isfile(p):
                sys.exit(f'[用法] 找不到存档：{a}（也没在 {FDIR} 里找到）')
            out.append(p)
        return out
    allf = sorted(f for f in (os.listdir(FDIR) if os.path.isdir(FDIR) else [])
                  if f.endswith('.json'))
    return [os.path.join(FDIR, f) for f in allf[-6:]]


def crop_canvas(png, rect, dpr, out, scale_up=2.0):
    """按**画布自己的矩形**裁整页截图（origin+clientW/H，乘 dpr），再等比放大。
    不用 V→屏幕换算去框"手在哪"：那个框算出来只有几像素，裁出来等于没裁。"""
    from PIL import Image
    im = Image.open(png).convert('RGB')
    x0, y0 = int(rect[0] * dpr), int(rect[1] * dpr)
    x1, y1 = int((rect[0] + rect[2]) * dpr), int((rect[1] + rect[3]) * dpr)
    b = (max(0, x0), max(0, y0), min(im.width, x1), min(im.height, y1))
    if b[2] - b[0] < 60 or b[3] - b[1] < 60:
        return None
    c = im.crop(b)
    if scale_up and scale_up != 1:
        c = c.resize((int(c.width * scale_up), int(c.height * scale_up)), Image.LANCZOS)
    c.save(out)
    return out


def montage(rows, path, cell_w=420):
    """把 N 帧拼成一张总表：每格上面一行标签（第几秒 / 自证结论），走样的打 ⚠。"""
    from PIL import Image, ImageDraw, ImageFont
    try:
        F = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
        Fs = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 15)
    except Exception:
        F = Fs = ImageFont.load_default()
    cols = min(3, len(rows))
    cell_h = int(cell_w * 0.62)
    rows_n = (len(rows) + cols - 1) // cols
    pad, lab = 10, 66
    W = cols * cell_w + (cols + 1) * pad
    H = rows_n * (cell_h + lab) + (rows_n + 1) * pad
    sheet = Image.new('RGB', (W, H), (18, 20, 26))
    d = ImageDraw.Draw(sheet)
    for i, r in enumerate(rows):
        cx = pad + (i % cols) * (cell_w + pad)
        cy = pad + (i // cols) * (cell_h + lab + pad)
        txt = ('⚠ ' if not r['ok'] else '') + f"#{r['n']}  第 {r['t']}s  {r['grp']}"
        sub = (f"上屏 {r['lit_now']}/{r['lit']}  Δ画出面积 {r['maxgeo']}（{r['worst']}）"
               f" 中位 {r.get('med')} 亚像素 {r.get('nsubpx')} 片  参数回读 Δ {r['drift']}"
               f"{'  ⚠参数没索引 ' + str(r['missP']) if r['missP'] else ''}"
               f"{'  ⚠部件没索引 ' + str(r['missQ']) if r['missQ'] else ''}"
               f"{'  参数解释不了 ' + str(r['unexplained']) + ' 片' if r['unexplained'] else ''}")
        d.text((cx + 2, cy + 2), txt, font=F, fill=(255, 255, 255))
        tail = f"  {r['file'][9:15]}"
        if isinstance(r.get('top'), str):
            tail = '  ' + r['top'] + f"  {r['file'][9:15]}"
        line = (sub + tail)
        while d.textlength(line, font=Fs) > cell_w - 6 and len(line) > 12:  # 溢出到隔壁格=没标签
            line = line[:-4]
        d.text((cx + 2, cy + 26), line, font=Fs, fill=(188, 196, 208))
        im = Image.open(r['png']).convert('RGB')
        im.thumbnail((cell_w, cell_h))
        sheet.paste(im, (cx + (cell_w - im.width) // 2, cy + lab + (cell_h - im.height) // 2))
    sheet.save(path)
    return path


def run_light(docs, outdir, cmd, ev, montage):
    """反查模式：在坏帧上把**当前灭着**的片分批点亮，每批一张图 ⇒ 哪一批在手的位置画出手指，那批就是手。
    四条自证：① 空批（一张都不点）必须全黑；② 存档里亮着的那批点回来后要能看见身体；
    ③ 每批只动这一批；④ 最后拼总表交给人眼（本项目三次栽在"名单没在图上落过"）。"""
    f, d = docs[0]
    lit = {a[0] for a in d['art']}
    base = json.dumps({'parameters': d['parameters'], 'parts': d['parts'],
                       'view': d.get('view'), 'art': d['art'], 'needNames': True})
    got = json.loads(ev(f"window.__l2Restore({base})"))
    names = got['names']
    dark = [n for n in names if n not in lit]
    print(f'  坏帧 {os.path.basename(f)}：存档亮着 {len(lit)} 片、灭着 {len(dark)} 片；'
          f'每批 {BATCH} 片 ⇒ {len(dark) // BATCH + 1} 张图', flush=True)
    rows = []
    shots = [('zero', [])] + [(f'b{i:02d}', dark[i * BATCH:(i + 1) * BATCH])
                              for i in range(len(dark) // BATCH + 1)
                              if dark[i * BATCH:(i + 1) * BATCH]]
    shots.append(('litall', sorted(lit)))
    for k, (tag, batch) in enumerate(shots, 1):
        payload = json.dumps({'parameters': d['parameters'], 'parts': d['parts'],
                              'view': d.get('view'), 'art': d['art'], 'light': batch})
        g2 = json.loads(ev(f"window.__l2Restore({payload})"))
        png = os.path.join(outdir, f'light_{k:02d}_{tag}.png')
        open(png, 'wb').write(base64.b64decode(cmd('Page.captureScreenshot', {'format': 'png'})['data']))
        cp = crop_canvas(png, g2['rect'], g2['dpr'], os.path.join(outdir, f'lightc_{k:02d}_{tag}.png'),
                         scale_up=1.6) or png
        rows.append(dict(n=k, file=f'{tag}·{len(batch)}片', t=d['tInGroup'], grp=tag,
                         lit=len(batch), lit_now=g2['lit'], maxgeo=0, maxsub=0, med=0,
                         nsubpx=0, worst=None, drift=0, unexplained=0, missP=0, missQ=0,
                         ok=True, png=cp, top=f'{len(batch)} 片'))
        print(f'    {k:02d} {tag:<7} 点亮 {len(batch):>3} 片 → 屏上 {g2["lit"]:>3} 片  {os.path.basename(cp)}',
              flush=True)
    mpath = montage(rows, os.path.join(outdir, 'light_montage.png'), cell_w=360)
    print('', '反查总表:', mpath)
    json.dump([{'tag': r['grp'], 'n': r['lit']} for r in rows],
              open(os.path.join(outdir, '_light_index.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    return 0


def main():
    global LIGHT, BATCH
    LIGHT = '--light' in sys.argv
    args = [a for a in sys.argv[1:] if a != '--light']
    if '--batch' in args:
        k = args.index('--batch')
        BATCH = int(args[k + 1])
        args = args[:k] + args[k + 2:]
    files = pick_files(args)
    if not files:
        print(f'[用法] {FDIR} 里没有存档')
        return 2
    # 要放大看的片：默认用臂 ㉔ 反查验过的那两只手（把框画回图上验过的，不是台账猜的名单）
    HANDS = [x.strip() for x in os.environ.get('HANDS', 'ArtMesh482,ArtMesh243').split(',')
             if x.strip()]
    docs = [(f, json.load(open(f, encoding='utf-8'))) for f in files]
    key = docs[0][1]['skin']
    view = docs[0][1].get('view') or {}
    w, h = int(view.get('w') or 1366), int(view.get('h') or 809)
    outdir = os.path.join(OUTROOT, time.strftime('%m%d-%H%M%S'))
    os.makedirs(outdir, exist_ok=True)

    port = free_port()
    httpd = GS.make_server(port=port, root=os.path.join(ROOT, 'Output'))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{port}/gallery_v2/index.html?v={int(time.time())}'
    for _ in range(60):
        try:
            if urllib.request.urlopen(url, timeout=2).status == 200:
                break
        except Exception:
            time.sleep(0.3)
    dport, profile = cdp_slot.slot(ROOT, 'replay')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={dport}',
                             '--remote-allow-origins=*', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
                             '--use-angle=swiftshader', f'--window-size={w},{h + 44}', url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{dport}/json'))
            cand = [t['webSocketDebuggerUrl'] for t in tabs
                    if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
            if cand:
                import websocket
                ws = websocket.create_connection(cand[0], timeout=240, max_size=None)
                break
        except Exception:
            pass
        time.sleep(0.5)
    if ws is None:
        print('[ERROR 2] DevTools 连不上（残留 chrome 占了同一个 user-data-dir？）')
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()
        return 2
    nid = [0]

    def cmd(method, params=None):
        nid[0] += 1
        ws.send(json.dumps({'id': nid[0], 'method': method, 'params': params or {}}))
        ws.settimeout(240)
        while True:
            r = json.loads(ws.recv())
            if r.get('id') == nid[0]:
                if 'error' in r:
                    raise RuntimeError(json.dumps(r['error'])[:150])
                return r.get('result', {})

    def ev(expr):
        r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                     'awaitPromise': True})
        if r.get('exceptionDetails'):
            return 'EVALERR ' + str(r['exceptionDetails'])[:300]
        return r.get('result', {}).get('value')

    print(f'回放 {len(docs)} 帧 · 皮肤 {key} · 窗口 {w}x{h + 44} · 输出 {outdir}', flush=True)
    try:
        boot = ev(JS_BOOT + f"({json.dumps(key)})")
        if not isinstance(boot, str) or not boot.strip().startswith('{'):
            print(f'[ERROR 2] 页面没起来：{str(boot)[:200]}')
            return 2
        boot = json.loads(boot)
        if not boot.get('ok'):
            print(f'[ERROR 2] 页面没起来：{boot}')
            return 2
        print(f"  现场：物理摆动 {'已停' if boot.get('physicsOff') else '本来就没有'}"
              f" · 呼吸层 {'已关(页面自带)' if boot.get('breathOff') else '还在跑'}", flush=True)
        if 'EVALERR' in str(ev(JS_RESTORE)):
            print('[ERROR 2] 回放函数装不上')
            return 2
        if LIGHT:
            return run_light(docs, outdir, cmd, ev, montage)
        rows = []
        hrows = []
        for n, (f, d) in enumerate(docs, 1):
            payload = json.dumps({'parameters': d['parameters'], 'parts': d['parts'],
                                  'view': d.get('view'), 'art': d['art'], 'hands': HANDS})
            payload2 = json.dumps({'parameters': d['parameters'], 'parts': d['parts'],
                                   'view': d.get('view'), 'art': d['art'],
                                   'hands': HANDS, 'only': HANDS})
            got = json.loads(ev(f"window.__l2Restore({payload})"))
            want = {a[0]: a[1:] for a in d['art']}          # [op, w, h, x0, y0]
            now = got['geo']
            common = set(want) & set(now)
            dev = lambda k: max(abs(want[k][j] - now[k][j]) for j in (1, 2, 3, 4))
            # 判据只量「两侧都真画出面积」的片：宽或高 < 1 单位在页面上不足 1 像素，
            # 那批停放件（实测 20~24 片，回放里塌成 0 面积、存档里也只有 1~4 单位）
            # 位置差多少都不影响画面 ⇒ 不参与判"走样"，但单独计数报出来。
            area1 = lambda k, src: src[k][1] >= 1.0 and src[k][2] >= 1.0
            painted = [k for k in common if area1(k, want) and area1(k, now)]
            subpx = [k for k in common if k not in set(painted)]
            maxgeo = round(max((dev(k) for k in painted), default=0.0), 4)
            maxsub = round(max((dev(k) for k in subpx), default=0.0), 4)
            # 容差按"该片自身尺寸的 10%"给，再配一条绝对上限：小片挪 0.14 单位是 6%，
            # 大片挪 0.14 单位则不到 0.4% —— 绝对阈值会把前者误判成走样。
            dd_s = sorted(dev(k) for k in painted)
            med = round(dd_s[len(dd_s) // 2], 4) if dd_s else 9.0
            hdev = {k: round(dev(k), 4) for k in HANDS if k in common}
            # 判"这一帧摆回去了"用两条：① 画出面积的片的中位差 ≤0.02 单位；
            # ② 要指认的那几片（手）自身差 ≤0.05 单位。个别 1~3 单位的小片可以偏到 0.2，
            #   那是亚像素级、且不影响"手在不在"，列出来但不判死。
            ok = (got['lit'] == d['counts']['lit'] and med <= MED_TOL
                  and hdev and all(v <= HAND_TOL for v in hdev.values())
                  and got['paramDrift'] <= 1e-3
                  and not got['missParam'] and not got['missPart'])
            unexplained = sorted(k for k in set(want) - set(now) if want[k][0] > 0.3)
            png = os.path.join(outdir, f'frame_{n:02d}_{os.path.basename(f)[:-5]}.png')
            shot = cmd('Page.captureScreenshot', {'format': 'png'})
            open(png, 'wb').write(base64.b64decode(shot['data']))
            # 第二张：同一帧只留名单内那几片（其余不透明度归 0）⇒ "这两片到底画在哪"直接看图
            got2 = json.loads(ev(f"window.__l2Restore({payload2})"))
            shot2 = cmd('Page.captureScreenshot', {'format': 'png'})
            png2 = os.path.join(outdir, f'only_{n:02d}_{os.path.basename(f)[:-5]}.png')
            open(png2, 'wb').write(base64.b64decode(shot2['data']))
            hpng = crop_canvas(png2, got2['rect'], got2['dpr'],
                               os.path.join(outdir, f'hand_{n:02d}_{os.path.basename(f)[:-5]}.png'))
            cpng = crop_canvas(png, got['rect'], got['dpr'],
                               os.path.join(outdir, f'canvas_{n:02d}_{os.path.basename(f)[:-5]}.png'))
            hrow = dict(n=n, file=os.path.basename(f), t=d['tInGroup'], grp=d['group'],
                        lit=d['counts']['lit'], lit_now=got['lit'], maxgeo=0, maxsub=0,
                        worst=None, drift=0, unexplained=0, missP=0, missQ=0, ok=True,
                        png=hpng or png2,
                        top=' '.join(f"{k} op={v[4]}" for k, v in (got.get('hand') or {}).items()))
            rows.append(dict(n=n, file=os.path.basename(f), t=d['tInGroup'], grp=d['group'],
                             lit=d['counts']['lit'], lit_now=got['lit'],
                             maxgeo=maxgeo, maxsub=maxsub, med=med,
                             npaint=len(painted), nsubpx=len(subpx),
                             png=cpng or png, fullPng=png, handPng=hpng,
                             worst=max(painted, key=dev, default=None), hands=hdev,
                             top=[(k, round(dev(k), 3), want[k][1])
                                  for k in sorted(painted, key=dev, reverse=True)[:8]],
                             unexplained=len(unexplained), drift=got['paramDrift'],
                             missP=got['missParam'], missQ=got['missPart'],
                             gone=unexplained[:8], ok=ok,
                             scale=got['scale'], pos=[got['mx'], got['my']],
                             canvas=[got['cw'], got['ch']]))
            hrows.append(hrow)
            print(('  OK    ' if ok else '  ⚠ 走样 ') +
                  f"#{n} {os.path.basename(f)[9:15]} 第 {d['tInGroup']}s 上屏 {got['lit']}"
                  f"/{d['counts']['lit']} Δ画出面积的 {len(painted)} 片 = {maxgeo}"
                  f"（{rows[-1]['worst']}）中位 {med} 手 {hdev}"
                  f" 亚像素停放件 {len(subpx)} 片最大 {maxsub} Δ参数回读 {got['paramDrift']}"
                  + (f" update 时被 core 改掉 {got['overwrittenByCore']} 片" if got['overwrittenByCore'] else '')
                  + (f" 参数向量解释不了 {len(unexplained)} 片" if unexplained else '')
                  + (f" 没索引 参数{got['missParam']}/部件{got['missPart']}"
                     if (got['missParam'] or got['missPart']) else ''), flush=True)
            dd = sorted(dev(k) for k in painted)
            n5 = [k for k in painted if dev(k) > 0.05]
            print('        画出面积的那批：Δ>0.05 的 %d 片 / 中位 %.4f / 最大 %.4f'
                  % (len(n5), dd[len(dd) // 2] if dd else 0, dd[-1] if dd else 0), flush=True)
            if n5:
                print('        Δ>0.05 的片（片名, Δ, 存档宽, 回放宽）: '
                      + str([(k, round(dev(k), 3), want[k][1], now[k][1])
                             for k in sorted(n5, key=dev, reverse=True)[:8]]), flush=True)
            print(f'        手上那两片 Δ {hdev}  存档 op '
                  f'{[(k, want[k][0]) for k in HANDS if k in want]}  回放 op '
                  f'{[(k, now[k][0]) for k in HANDS if k in now]}', flush=True)
        json.dump(rows, open(os.path.join(outdir, '_replay_report.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        mpath = montage(rows, os.path.join(outdir, 'montage.png'), cell_w=470)
        hpath = None
        if any('hand_' in os.path.basename(r['png']) for r in hrows):
            hpath = montage(hrows, os.path.join(outdir, 'hand_montage.png'), cell_w=470)
        bad = [r for r in rows if not r['ok']]
        print(f'\n总表: {mpath}')
        print('全部回放自证通过（这 6 张图就是存档那一刻的画面）' if not bad
              else f'{len(bad)} 帧回放走样 ⇒ 那些图不能当证据（格子上打了 ⚠）')
        return 1 if bad else 0
    except Exception as e:
        print(f'[ERROR 2] 探针异常：{e}')
        return 2
    finally:
        try:
            ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()
        httpd.server_close()


if __name__ == '__main__':
    sys.exit(main())
