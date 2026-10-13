# -*- coding: utf-8 -*-
"""一次无头运行拿两拍全量片台账（renderOrder/UV/顶点/不透明度），为"手不见了"定性。

为什么：`docs/HANDOFF_6.37_手不见了_2026-10-12.md` §3 说唯一不知道的是"那只手现在在哪"，
三种可能 (a) 被盖住 (b) 画在别处 (c) 没画。要分开它们，需要**同一模型在两拍上的逐片对照**：
  · 10.87s —— 直播复现时确认过"两手都在"（提交 03c9a7f）；
  · 15.40s —— 同一路径确认"右手没了（腕上只剩手镯）"，也是用户存档 132422 那一拍。
两拍都走产品自己的入口（`#l2Motion` 选 home + 点 `#l2Replay`），**只起播一次、时刻单调往前走**
（仪器底线 4：每条存档都点一次重播会让动作淡入把参数拖后 0.25~0.55）。
拿到表后逐片差分：op 由亮到灭 / 顶点面积由正常到坍缩 ⇒ 就是消失的那只手，不再依赖任何先验名单。

同时落 renderOrders / drawOrders / textureIndices / vertexUvs —— 前者判 (a) 被盖住，
UV 用来和 texture 上的图案（金色手镯）交叉验证"手部片"身份。

三条自证（缺一条本表不许引用）：
① 两拍的 Param25/Param27 读数与用户存档 132415/132422 偏差 ≤0.05（证明推到了同一拍）；
② drawables.count 必须等于 770；
③ renderOrders 必须是 [0,770) 的排列。
"""
import base64
import io
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request

import numpy as np
from PIL import Image

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import cdp_slot                 # noqa: E402
import chrome_tree              # noqa: E402
import _gallery_server as GS    # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
KEY = 'gezi_2'
STOPS = [(10.87, 'good'), (15.40, 'bad')]   # (clip 内秒, 标签)
OUT = os.path.join(ROOT, '.diag', 'wrist_ledger.json')
# --group idle —— 换一条动作跑同一套台账（验"腕口那族整窗 op=0 是不是被 idle 的 PartOpacity 闸着"）
GROUP = sys.argv[sys.argv.index('--group') + 1] if '--group' in sys.argv else 'home'
GROUP_STEP = 0.12
if GROUP != 'home':
    OUT = os.path.join(ROOT, '.diag', f'wrist_ledger_{GROUP}.json')

# 两种模式（默认保持原样：两拍对照台账，别的会话还在用）：
#   --sweep 15.00:16.00:0.05  同一趟播放里按细时刻跑一串（判"手短暂消失"到底是哪几帧）
#   --png                     每个时刻同时抓一张画布图（用产品暂停键的同一配方）
# 细扫存在的理由：两拍对照的 A/B/C 全是 0（没有片被关掉、没有片塌面积），但用户确实看到腕上没手
# ⇒ 消失可能只持续几帧（两拍都落在"有手"的一侧），也可能走**剪贴蒙版**（op 与面积都不变）。
JS_PNG = r"""(()=>{const app=l2State.app; app.render();
  try{ return app.view.toDataURL('image/png'); }catch(e){ return 'ERR '+(e.message||e); }})"""

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
  const ph=!!m.internalModel.physics;
  if(ph){ m.internalModel.__phEval=m.internalModel.physics.evaluate; m.internalModel.physics.evaluate=function(){}; }
  return JSON.stringify({key, ok:true, physicsOff:ph});
}catch(e){ return 'ERR '+(e.message||e); }})"""

JS_PLAY = r"""(async(a)=>{const m=l2State.app.stage.children[0],im=m.internalModel;
  if(im.__phEval) im.physics.evaluate=im.__phEval;
  const s=document.getElementById('l2Motion'); s.value=a.g;
  s.dispatchEvent(new Event('change',{bubbles:true}));
  const b=document.getElementById('l2Replay'); if(b)b.click();
  m.autoUpdate=false;
  /* ⚠️ 必须回报"到底起播了没有"：产品侧 play() 是 try{playVoice(); mm.startMotion()}catch{return false}
     —— 语音一抛异常动作就不起播，而按钮点击本身不报错。10-13 的 --twice 第一版就是因为
     只看点击的返回值，把"模型停在默认参数上空推时钟"当成了第二遍，对照整个作废。 */
  await new Promise(r=>setTimeout(r,400));      // 换组要等库把动作表切过去，否则读到的还是上一条
  const st=im.motionManager.state;
  return JSON.stringify({want:a.g, group:st.currentGroup, idx:st.currentIndex, playing:!!st.motion});})"""

JS_SNAP = r"""(async(a)=>{
  const m=l2State.app.stage.children[0], cm=m.internalModel.coreModel, D=cm._model.drawables;
  const P=cm._model.parameters;
  if(a.from===undefined){
    const pv={}; for(let i=0;i<P.count;i++){ const q=P.ids[i];
      if(q==='Param25'||q==='Param27')pv[q]=+P.values[i].toFixed(3); }
    const im=m.internalModel, ppu=im.pixelsPerUnit||1;
    return JSON.stringify({head:1, count:D.count, p:pv,
      tf:[+(im.width/ppu).toFixed(4),+(im.height/ppu).toFixed(4),
          +ppu.toFixed(3), +m.scale.x.toFixed(5), +m.x.toFixed(2), +m.y.toFixed(2)]});
  }
  const rows=[];
  for(let i=a.from;i<Math.min(a.to,D.count);i++){
    const id=D.ids[i]; const nm=String((id&&id.string)||id);
    const uv=D.vertexUvs[i]; let u0=9,v0=9,u1=-9,v1=-9;
    if(uv) for(let k=0;k<uv.length;k+=2){ if(uv[k]<u0)u0=uv[k]; if(uv[k]>u1)u1=uv[k];
      if(uv[k+1]<v0)v0=uv[k+1]; if(uv[k+1]>v1)v1=uv[k+1]; }
    const p=D.vertexPositions[i]; let x0=1e9,y0=1e9,x1=-1e9,y1=-1e9;
    if(p&&p.length) for(let k=0;k<p.length;k+=2){ if(p[k]<x0)x0=p[k]; if(p[k]>x1)x1=p[k];
      if(p[k+1]<y0)y0=p[k+1]; if(p[k+1]>y1)y1=p[k+1]; }
    rows.push([nm, D.textureIndices[i], D.drawOrders[i], D.renderOrders[i],
               +D.opacities[i].toFixed(3), D.maskCounts[i], D.vertexCounts[i],
               D.indices[i]?D.indices[i].length:0,
               [+u0.toFixed(4),+v0.toFixed(4),+u1.toFixed(4),+v1.toFixed(4)],
               (p&&p.length)?[+x0.toFixed(3),+y0.toFixed(3),+x1.toFixed(3),+y1.toFixed(3)]:null]);
  }
  return JSON.stringify({from:a.from, rows});
})"""
BATCH = 100


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
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
    dport, profile = cdp_slot.slot(ROOT, 'ledger')
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={dport}',
                             '--remote-allow-origins=*', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
                             '--window-size=1366,853', url],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        import websocket
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{dport}/json'))
                cand = [t['webSocketDebuggerUrl'] for t in tabs
                        if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if cand:
                    ws = websocket.create_connection(cand[0], timeout=240, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print('[ERROR 2] DevTools 连不上')
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

        def ev(expr, tries=8):
            """⚠️ 页面刚导航完时首个 eval 会报 "Execution context was destroyed"（实测 10-13 二跑
            在 boot 那一下撞上，首跑正常）⇒ 竞态，只对这一种错误重试，别把它当页面故障放过去。"""
            for k in range(tries):
                try:
                    return _ev(expr)
                except RuntimeError as e:
                    if 'Execution context was destroyed' not in str(e) or k == tries - 1:
                        raise
                    print(f'  [retry {k + 1}/8] 上下文被销毁（页面在导航），2s 后重试', flush=True)
                    time.sleep(2)

        def _ev(expr):
            r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                         'awaitPromise': True})
            if r.get('exceptionDetails'):
                return 'EVALERR ' + str(r['exceptionDetails'])[:300]
            return r.get('result', {}).get('value')

        boot = ev(JS_BOOT + f'("{KEY}")')
        boot = json.loads(boot) if isinstance(boot, str) and boot.strip().startswith('{') else boot
        if not (isinstance(boot, dict) and boot.get('ok')):
            print('[ERROR 2] 页面没起来：', boot)
            return 2
        print('boot ok · 物理摆动已停' if boot.get('physicsOff') else 'boot ok')
        def cur_group():
            return ev("(()=>String(l2State.app.stage.children[0].internalModel.motionManager"
                      ".state.currentGroup))()")

        def start_play(label):
            """起播并**验真**，返回验真过程中已烧掉的 clip 秒数（调用方要把它计进 t）。

            ⚠️ 时机陷阱：`mm.startMotion()` 是**排队**，点完立刻读 state 还是上一条（idle）
            —— 10-13 第一版在这里当场误判"没起播"，把明明在播的一趟判废了。必须推几步时钟再读。
            产品侧 play() 是 try{playVoice(); mm.startMotion()}catch{return false}，语音抛异常
            就真的不起播，所以这一步不能省，只是不能读太早。
            """
            def fire():
                r = ev(f'({JS_PLAY})({{g:"{GROUP}"}})')
                try:
                    return json.loads(r)
                except Exception:
                    return {'raw': str(r)[:120]}

            st = fire()
            spent = 0.0
            for k in range(3):
                for _ in range(3):                     # 推 0.36s 让队列落地
                    ev(f'l2State.app.stage.children[0].update({int(GROUP_STEP * 1000)})')
                    ev('new Promise(r=>requestAnimationFrame(()=>r(1)))')
                    spent += GROUP_STEP
                if cur_group() == GROUP:
                    print(f'  {label}: 已起播 {GROUP}（验真烧掉 {spent:.2f}s）{st}', flush=True)
                    return spent
                print(f'  {label} 第 {k + 1} 次验真失败（当前 {cur_group()}，fire 返回 {st}）'
                      f'⇒ 再点一次', flush=True)
                st = fire()
            raise SystemExit(f'对照作废：{label} 三步内 motionManager 仍没切到 {GROUP}'
                             f'（当前 {cur_group()}）—— 这趟的任何差值都不许引用')

        print('起播 …', flush=True)
        t = start_play('第一遍')
        # 阶梯层是否真的建起来了？n=0 ⇒ 页面侧取曲线的字段名不对，整层空转（别把空转当"修过了"）
        print('  snapStair: ', ev('JSON.stringify(window.__snapStairDbg'
                                  '?window.__snapStairDbg():{absent:1})'), flush=True)
        print('  诊断: ', ev("""(()=>{const im=l2State.app.stage.children[0].internalModel;
            const d=im.motionManager.definitions&&im.motionManager.definitions.home;
            const o=d&&d[0];
            return JSON.stringify({snapDbg:window.__snapDbg?window.__snapDbg():null,
              defType:typeof o, defKeys:o?Object.keys(o).slice(0,12):null,
              curve0:(o&&o.curves&&o.curves[0])?Object.keys(o.curves[0]):null,
              nCurves:o&&o.curves?o.curves.length:null,
              sample:(o&&o.curves)?o.curves.filter(c=>String(c.id||'').match(/^Param2[57]$/)).slice(0,1)
                        .map(c=>[c.target,c.id,String(c.segments).slice(0,90)]):null});})()"""), flush=True)
        def snap_all(tag):
            head = ev(f'({JS_SNAP})({{}})')
            head = json.loads(head)
            n = head['count']
            rows = []
            for f in range(0, n, BATCH):
                part = ev(f'({JS_SNAP})({{"from":{f},"to":{f + BATCH}}})')
                if not isinstance(part, str) or not part.strip().startswith('{'):
                    print(f'  [ERROR] 第 {f} 批返回异常：{str(part)[:300]}')
                    return 2
                pj = json.loads(part)
                if 'rows' not in pj:
                    print(f'  [ERROR] 第 {f} 批缺 rows：{str(pj)[:300]}')
                    return 2
                rows += pj['rows']
            return dict(count=n, p=head['p'], tf=head['tf'], rows=rows)

        out = {}
        # t 不在这里归零：start_play 验真时已经推掉 0.36s，抹掉它会让整趟比真实 clip 时刻晚这么多
        stops, STEP = STOPS, 120
        OUTDIR = os.path.join(ROOT, '.diag', 'l2d_sweep', time.strftime('%m%d-%H%M%S'))
        outfile = OUT          # 默认两拍台账；--sweep 另存，绝不覆盖 .diag/wrist_ledger.json
        if '--sweep' in sys.argv:                        # 细扫：一串时刻，标签就是时刻本身
            a, b, dt = [float(x) for x in
                        sys.argv[sys.argv.index('--sweep') + 1].split(':')]
            STEP = max(1, int(round(dt * 1000)))
            stops = [(round(a + i * dt, 3), f'{a + i * dt:.2f}')
                     for i in range(int(round((b - a) / dt)) + 1)]
            outfile = os.path.join(OUTDIR, 'sweep.json')
        if '--png' in sys.argv or '--sweep' in sys.argv:
            os.makedirs(OUTDIR, exist_ok=True)
        pngs = {}
        # --twice：同一页面会话里连跑两遍，比「刚加载」与「全热」是否逐帧逐片一致。
        #   动机：用户假设"新的手没预加载 / 晚到一步"⇒ 若两遍完全一致，时序说当场判死；
        #   若只有第一遍缺手，才是加载时机问题。两遍都点一次 #l2Replay ⇒ 淡入拖后是受控变量。
        passes = ['p1'] + (['p2'] if '--twice' in sys.argv else [])
        for pi, ptag in enumerate(passes):
            if pi:
                print('第二遍起播（纹理/网格/着色器此时全热）…', flush=True)
                t = start_play('第二遍')
            for tgt, tag in stops:
                while t < tgt - 1e-6:
                    step = min(STEP, max(1, int(round((tgt - t) * 1000))))
                    ev(f'l2State.app.stage.children[0].update({step})')
                    ev('new Promise(r=>requestAnimationFrame(()=>r(1)))')
                    t += step / 1000.0
                snap = snap_all(tag)
                # 单趟不加 p1_ 前缀：--sweep 的分析器把标签当 float 解析（10-13 加 --twice 时踩过）
                key = f'{ptag}_{tag}' if len(passes) > 1 else tag
                out[key] = dict(t=tgt, tReached=round(t, 2), pas=ptag, snap=snap)
                line = (f'  [{ptag}] t={tgt}s（推到 {t:.2f}s）Param25={snap["p"].get("Param25")} '
                        f'Param27={snap["p"].get("Param27")} · {snap["count"]} 片')
                if '--png' in sys.argv:                  # 产品暂停键同一配方：先 render 再 toDataURL
                    # ⚠️ JS_PNG 是**箭头函数表达式**，必须带 () 调用；只 eval 表达式会返回函数对象，
                    #    returnByValue 把它序列化成 {} ⇒ 每帧都"抓图失败"（10-13 第一跑就栽在这）。
                    d = ev(JS_PNG + '()')
                    if isinstance(d, str) and d.startswith('data:image/png;base64,'):
                        raw = base64.b64decode(d.split(',', 1)[1])
                        im = Image.open(io.BytesIO(raw))
                        std = round(float(np.asarray(im.convert('L'), dtype=float).std()), 2)
                        open(os.path.join(OUTDIR, f'{key}.png'), 'wb').write(raw)
                        pngs[key] = dict(px=[im.width, im.height], std=std)
                        line += f' · 画布 {im.width}x{im.height} 灰度σ={std}'
                        if std < 1.0:
                            line += ' ⚠️空白（仪器底线 5：量的就是画布矩形本身）'
                    else:
                        line += f' · 抓图失败 {str(d)[:70]}'
                print(line, flush=True)
        out['_png'] = pngs
        json.dump(out, open(outfile, 'w'), ensure_ascii=False)
        print('落盘', outfile, '· 图在', OUTDIR if '--png' in sys.argv else '(没抓图)')
        return 0
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()


if __name__ == '__main__':
    sys.exit(main())
