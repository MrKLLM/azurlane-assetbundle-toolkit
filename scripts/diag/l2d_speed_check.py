# -*- coding: utf-8 -*-
"""验证「倍速播放」滑杆真的改了动作时钟，而且 1× 与改前一致。

为什么要有这个探针：倍速是**缩放内部模型 update 的 dt** 实现的（见 index.html 的
`im.update=function(...a){ a[0]*=l2Speed; ... }`），而这条改动的失败模式全是静默的：
  · 包错了对象（比如包了 model.update 而库实际调 internalModel.update）→ 滑杆怎么拖都不变；
  · 只影响新起播的动作 → 拖到 2× 时正在播的这条纹丝不动；
  · 顺手把 1× 也改了（dt 缩放写错方向/重复乘）→ 默认速度就不对，而"看起来在动"分辨不出。
⇒ 判据必须落在**可读的数字**上，而且要能自证刻度。

尺子：`home` 的 `GL1` 是一条**横跨整条 clip 的线性斜坡**（motion3 里只有首末两个作者键：
0.0066 @ 0s → 0.812 @ 18.25s，斜率 0.04413/s 的 clip 时间）。⇒ 量"GL1 从 0.10 涨到 0.30
用掉多少墙钟秒"就等于量"4.53 秒 clip 时间用掉多少墙钟秒"，两者相除即实测倍速。
用**两段门槛之差**而不是"从起播算起"，是为了把"起播那一刻"的模糊（选单 change + 交叉淡化）
整段消掉；再取两趟对照，噪声不会系统性偏一边。

三条判据（**全是比值，不读绝对值** —— 见下面那条环境坑）：
  ① 滑杆显示值随设定改变，且 `vEl`（喂给内部模型的虚拟时钟）斜率之比 ≈ 倍速（容差 ±20%）；
  ② 虚拟钟 → clip 时间恒为 1:1（`clip 跨度 / vEl 跨度 ≈ 1.00`，容差 ±15%）：这条与倍速无关，
     1× 也过 ⇒ 同时证明"没顺手改坏默认速度"（改前 1× 就是这个映射）；
  ③ 每条倍速下都没被暂停卡住（`autoUpdate` 仍为真）。

⚠️ 环境坑（2026-10-16 实测，差点误判成"倍速没生效"）：**无头环境不能读墙钟绝对速率**。
   本页在 swiftshader 下渲染很慢，PIXI ticker 把 `deltaMS` 钳在 100ms（`_maxElapsedMS`），
   ⇒ 模型时钟本来就只按墙钟的 ~0.6 倍推进（实测 1× 墙钟口径 0.59）。这个钳位对每条倍速
   一视同仁，所以**比值仍然可信**，绝对速率不可信。真实浏览器 60fps 下不触发钳位。

用法：
  py -3 scripts/diag/l2d_speed_check.py                    # 默认 gezi_2，测 2× / 1× / 0.5×
  py -3 scripts/diag/l2d_speed_check.py --key gezi_2 --speeds 2,1,0.5
⚠️ 本机 HTTP_PROXY 会劫持 127.0.0.1（CDP 与页面请求都变 502）⇒ 运行前清掉代理环境变量。
退出码: 0 = 全过；1 = 有判据未过；2 = 探针没跑起来。
"""
import argparse
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
import cdp_slot                 # noqa: E402
import chrome_tree              # noqa: E402
import _gallery_server as GS    # noqa: E402

CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
AP = argparse.ArgumentParser()
AP.add_argument('--key', default='gezi_2')
AP.add_argument('--speeds', default='2,1,0.5')
AP.add_argument('--win', default='1366,853')
A = AP.parse_args()

# 尺子：GL1 在 home 里的两个作者端点（motion3 原值）与两个采样门槛
GL1_T0, GL1_T1, GL1_V0, GL1_V1 = 0.0, 18.25, 0.0066, 0.812
TH_LO, TH_HI = 0.10, 0.30
CLIP_SPAN = (TH_HI - TH_LO) / ((GL1_V1 - GL1_V0) / (GL1_T1 - GL1_T0))   # 门槛之间有多少 clip 秒


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


JS_OPEN = r"""(async(key)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  for(let i=0;i<120 && !(window.GALLERY && typeof openShip==='function');i++) await t(300);
  if(!window.GALLERY || typeof openShip!=='function') return JSON.stringify({err:'页面脚本未就绪'});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k&&s.live2dSkins.includes(key)){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, skip:'no skin'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='live2d').click();
  for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
  if(!(l2State&&l2State.app&&l2State.app.stage.children[0]))
      return JSON.stringify({key, fail:'40s 内模型未加载'});
  const m=l2State.app.stage.children[0], core=m.internalModel.coreModel;
  const P=core._model.parameters;
  if(!P||!P.count) return JSON.stringify({fail:'读不到参数缓冲'});
  const ids=Array.from({length:P.count},(_,i)=>String((P.ids[i]&&P.ids[i].string)||P.ids[i]));
  const gi=ids.indexOf('GL1');
  if(gi<0) return JSON.stringify({fail:'该模型没有 GL1，换 --key'});
  window.__sp={ m, gi, read:()=>P.values[gi] };
  return JSON.stringify({ok:1, key, gl1:+P.values[gi].toFixed(4)});
}catch(e){ return JSON.stringify({err:String(e&&e.message||e)}); } })"""

# 实现侧读数：喂给内部模型的虚拟时钟（秒）相对墙钟的斜率。这条必须先过——
# 它把两种完全不同的失败分开：「我的时钟没按倍速走」vs「库根本不吃这个时间参数」。
JS_CLOCK = r"""(async(speed)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const sl=document.getElementById('l2Speed'); if(!sl) return JSON.stringify({err:'没有 #l2Speed'});
  sl.value=String(speed); sl.dispatchEvent(new Event('input'));
  const sel=document.getElementById('l2Motion');
  if([...sel.options].some(o=>o.value==='home')){ sel.value='home'; sel.dispatchEvent(new Event('change')); }
  await t(900);
  const a=window.__speedDbg&&window.__speedDbg();
  if(!a) return JSON.stringify({err:'没有 __speedDbg（倍速钩子没加载？）'});
  await t(2000);
  const b=window.__speedDbg();
  const dr=b.real-a.real, dv=b.vEl-a.vEl;
  return JSON.stringify({speed, patch:a.patch, shownSpeed:b.speed,
                         vElRate: dr>0?+(dv/dr).toFixed(3):null});
}catch(e){ return JSON.stringify({err:String(e&&e.message||e)}); } })"""

# 一条倍速下量一次：设滑杆 → 走页面入口起播 home → 等 GL1 依次穿过两个门槛 → 回报墙钟
JS_RUN = r"""(async(speed)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const sp=window.__sp; if(!sp) return JSON.stringify({err:'没有 __sp（先跑 JS_OPEN）'});
  const sl=document.getElementById('l2Speed'), val=document.getElementById('l2SpeedVal');
  if(!sl) return JSON.stringify({err:'没有 #l2Speed'});
  sl.value=String(speed); sl.dispatchEvent(new Event('input'));
  await t(200);
  const shown=val?val.textContent:null;
  /* 起播走页面自己的选单（不直接调 startMotion —— 那会绕过产品的 play()） */
  const sel=document.getElementById('l2Motion');
  if(![...sel.options].some(o=>o.value==='home')) return JSON.stringify({err:'没有 home 动作'});
  sel.value='home'; sel.dispatchEvent(new Event('change'));
  /* dir=1 上穿 / dir=-1 下穿。**先等斜坡回到起点再量**：重播后 GL1 是从上一条动作的值
     淡过来的，不等它落下去就量，两段门槛会在同一拍里一起越过（实测 wallMs=0）。 */
  const waitTh=(th,limit,dir)=>{ return new Promise(res=>{ const t0=performance.now();
    const tick=()=>{ const v=sp.read();
      if(dir>0?v>=th:v<=th) return res(performance.now());
      if(performance.now()-t0>limit) return res(null);
      setTimeout(tick,60); };
    tick(); }); };
  const low=await waitTh(0.07, 30000, -1);
  if(low===null) return JSON.stringify({err:'GL1 未回落到 0.07 以下（30s）—— 重播没生效？'});
  const a=await waitTh(0.10, 60000, 1); if(a===null) return JSON.stringify({err:'GL1 未涨到 0.10（60s）'});
  const dA=window.__speedDbg?window.__speedDbg().vEl:null;
  const b=await waitTh(0.30, 90000, 1); if(b===null) return JSON.stringify({err:'GL1 未涨到 0.30（90s）'});
  const dB=window.__speedDbg?window.__speedDbg().vEl:null;
  return JSON.stringify({speed, shown, wallMs:Math.round(b-a), vElA:dA, vElB:dB,
                         v0:+sp.read().toFixed(4), paused:!sp.m.autoUpdate});
}catch(e){ return JSON.stringify({err:String(e&&e.message||e)}); } })"""


def main():
    port = free_port()
    httpd = GS.make_server(port=port, root=os.path.join(ROOT, 'Output'))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print(f'服务器（正本 _gallery_server）: http://127.0.0.1:{port}/gallery_v2/index.html', flush=True)
    dport, profile = cdp_slot.slot(ROOT, 'speed')
    url = f'http://127.0.0.1:{port}/gallery_v2/index.html?v={int(time.time())}'
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={dport}',
                             '--remote-allow-origins=*', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
                             '--use-angle=swiftshader', f'--window-size={A.win}', url],
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

        def cmd(method, params=None, timeout=240):
            nid[0] += 1
            ws.send(json.dumps({'id': nid[0], 'method': method, 'params': params or {}}))
            ws.settimeout(timeout)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == nid[0]:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:200])
                    return r.get('result', {})

        def ev(expr):
            # 页面在导航/重载时执行上下文会被销毁（库探针同样踩过）⇒ 退避重试，别当成产品失败
            for i in range(8):
                try:
                    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True,
                                                 'awaitPromise': True})
                except RuntimeError as e:
                    if 'context was destroyed' in str(e) or 'Cannot find context' in str(e):
                        print(f'  [retry {i+1}/8] 上下文被销毁（页面在导航），2s 后重试', flush=True)
                        time.sleep(2)
                        continue
                    raise
                if r.get('exceptionDetails'):
                    return 'EXC ' + json.dumps(r['exceptionDetails'], ensure_ascii=False)[:250]
                return r.get('result', {}).get('value')
            return 'EXC 上下文反复被销毁'

        bad = []
        def say(cond, msg):
            print(('  PASS  ' if cond else '  FAIL  ') + msg, flush=True)
            if not cond:
                bad.append(msg)

        boot = ev(f'({JS_OPEN})({json.dumps(A.key)})')
        print('打开模型:', boot, flush=True)
        if not isinstance(boot, str) or '"ok"' not in boot:
            print('[ERROR 2] 模型没打开：', boot)
            return 2
        print(f'尺子：GL1 {TH_LO}→{TH_HI} = {CLIP_SPAN:.3f} 秒 clip 时间', flush=True)

        speeds = [float(x) for x in A.speeds.split(',') if x.strip()]
        clock, got = {}, {}
        for s in speeds:
            # ① 实现侧的钟：补丁在位，且 vEl 的斜率随倍速变
            r = ev(f'({JS_CLOCK})({s})')
            print(f'  时钟 {s}×:', r, flush=True)
            try:
                o = json.loads(r)
            except Exception:
                o = {'err': str(r)[:120]}
            if 'err' in o:
                say(False, f'{s}× 时钟读数失败：{o["err"]}')
            else:
                say(bool(o.get('patch')), f'{s}× 虚拟时钟补丁在位（im.update 含 l2VEl）')
                clock[s] = o.get('vElRate')

            # ② 动作侧：GL1 两段门槛之间用掉多少墙钟 + 多少虚拟秒
            r = ev(f'({JS_RUN})({s})')
            print(f'  动作 {s}×:', r, flush=True)
            try:
                o = json.loads(r)
            except Exception:
                o = {'err': str(r)[:120]}
            if 'err' in o:
                say(False, f'{s}× 动作测不起来：{o["err"]}')
                continue
            got[s] = o
            say(abs(float(o['shown'].rstrip('×')) - s) < 0.05, f'{s}× 滑杆显示值 = {o["shown"]}')
            say(not o['paused'], f'{s}× 量的时候没被暂停卡住')
            # 虚拟钟 → clip 时间必须是 1:1（这条与倍速无关，1× 也过 ⇒ 证明没改坏默认速度）
            vd = (o.get('vElB') or 0) - (o.get('vElA') or 0)
            if vd > 0:
                per = CLIP_SPAN / vd
                say(abs(per - 1.0) <= 0.15,
                    f'{s}× 虚拟钟→clip 时间 = {per:.3f} 秒/秒（应 ≈1.00，容差 ±15%）')
            wallRate = CLIP_SPAN / (o['wallMs'] / 1000.0)
            print(f'        （参考）{s}× 墙钟口径速率 {wallRate:.3f} —— 无头慢渲染下 '
                  f'PIXI ticker 把 deltaMS 钳在 100ms，绝对值本来就低于标称，只读比值', flush=True)

        c1 = clock.get(1.0)
        if c1:
            for s in speeds:
                if s == 1.0 or s not in clock:
                    continue
                ratio = clock[s] / c1
                say(abs(ratio - s) / s <= 0.20,
                    f'① vEl 斜率 {s}× / 1× = {ratio:.3f}（应 ≈{s}，容差 ±20%）')
        else:
            say(False, '没有 1× 的时钟读数，比值判据无从下手（--speeds 里要带 1）')

        print()
        if bad:
            print(f'[FAIL] {len(bad)} 条未过：')
            for b in bad:
                print('   -', b)
            return 1
        print('[PASS] 倍速滑杆真的改了动作时钟，且 1× 与改前一致')
        return 0
    finally:
        try:
            ws and ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        httpd.shutdown()


if __name__ == '__main__':
    sys.exit(main())
