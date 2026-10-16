# -*- coding: utf-8 -*-
"""验证「倍速播放」滑杆真的改了动作时钟，而且 1× 与改前一致。

为什么要有这个探针：倍速是**自建虚拟时钟**实现的（见 index.html 的
`im.update=function(dt,el){ ... origIMUpdate(dt*k, vEl); }`），而这条改动的失败模式全是静默的：
  · 包错了对象（库实际调的是 `internalModel.update`）→ 滑杆怎么拖都不变；
  · 喂错了参数（**动作时钟吃的是第二个参数**，只缩放 dt 完全无效）→ 同上；
  · 只影响新起播的动作 → 拖到 2× 时正在播的这条纹丝不动；
  · 顺手把 1× 也改了（缩放写错方向/重复乘）→ 默认速度就不对，而"看起来在动"分辨不出。
⇒ 判据必须落在**可读的数字**上，而且要能自证刻度。

三条判据：
  ① 滑杆显示值随设定改变，且 `vEl`（喂给内部模型的虚拟时钟）斜率之比 ≈ 倍速（容差 ±20%）；
  ② 1× 播完整条 `home` 用掉的**虚拟秒** ≈ clip 时长（`Meta.Duration` 18.25s，容差 ±1.2s）：
     虚拟钟与 clip 钟 1:1，同时证明"没顺手改坏默认速度"（改前 1× 就是这个映射）；
  ③ 2× 的墙钟播完时间明显短于 1×（**只断言方向**，理由见下）；
  ④ 点倍率数字一键回 1×（显示与内部 `l2Speed` 都回到 1）。

⚠️ 尺子换了三条，**前两条都被实测否证，别再走**：
   · ❌ `GL1` 长坡斜率（motion3 里只有首末两个作者键，看着是天赐的线性尺子）——它的**活值不是原始曲线**：
     实测偏 2.83 倍；把环境层关掉（`__ambOff`）反而偏到 4.12 倍。
     ⇒ 凡是要用"某个参数的轨迹"反推时间的判据，**先证它的活值真的跟曲线走**。
   · ❌ 墙钟比值 ≈ 2.0 —— 无头停帧对 2× 的伤害比 1× 小，比值被压扁（实测 1.46），只可作方向性断言。
   · ✅ 正解 = **一个离散事件**：`Meta.Loop=false` 的整条动作「播完」那一刻的虚拟秒。
     不用任何斜率，只读一个事件时刻；1× 实测 18.695 虚拟秒 ≈ 18.25 的 clip 时长。

⚠️ 环境坑：无头 swiftshader 下渲染慢，PIXI ticker 把 `deltaMS` 钳在 100ms（`_maxElapsedMS`），
   ⇒ 墙钟绝对速率本来就低于标称（1× 实测 0.5~0.6）。**只读比值/离散事件，别读绝对速率**。

用法：
  py -3 scripts/diag/l2d_speed_check.py                    # 默认 gezi_2，测 2× / 1× / 0.5×
  py -3 scripts/diag/l2d_speed_check.py --key gezi_2 --speeds 2,1,0.5
⚠️ 本机 HTTP_PROXY 会劫持 127.0.0.1（CDP 与页面请求都变 502）⇒ 运行前清掉代理环境变量（四个都要清）。
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

# 判据用的常量：home 的时长（motion3 Meta.Duration，且 Meta.Loop=false ⇒ 会播完）
CLIP_DUR = 18.25


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
  /* 点倍率数字 = 一键回 1×（不依赖键盘，也不用来回拖滑杆） */
  const bEl=document.getElementById('l2SpeedVal');
  if(bEl) bEl.click();
  await t(200);
  const d=window.__speedDbg&&window.__speedDbg();
  return JSON.stringify({speed, patch:a.patch, shownSpeed:b.speed,
                         vElRate: dr>0?+(dv/dr).toFixed(3):null,
                         resetShown:bEl?bEl.textContent:null, resetSpeed:d?d.speed:null});
}catch(e){ return JSON.stringify({err:String(e&&e.message||e)}); } })"""

# 只量**一次**的"虚拟钟 → clip 时间"比值（与倍速无关，1× 也过 ⇒ 顺带证明没改坏默认速度）。
# ⚠️ 原先每条倍速各量一次，两趟之间要等 GL1 从上一个动作淡回起点；那个等待不稳（实测会
# 两段门槛在同一拍一起越过 → wallMs=0），而这条比值按构造与倍速无关 ⇒ 量一次就够。
JS_END = r"""(async(speed)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const m=l2State.app.stage.children[0], mm=m.internalModel.motionManager;
  const sl=document.getElementById('l2Speed');
  if(!sl) return JSON.stringify({err:'没有 #l2Speed'});
  sl.value=String(speed); sl.dispatchEvent(new Event('input'));
  const sel=document.getElementById('l2Motion');
  if(![...sel.options].some(o=>o.value==='home')) return JSON.stringify({err:'没有 home 动作'});
  sel.value='home'; sel.dispatchEvent(new Event('change'));
  const t0=performance.now(); let tEnd=null;
  for(let i=0;i<1200;i++){                      // 最多等 120s（0.5× 下 18.25s 的 clip 要更久）
    await t(100);
    const g=mm.state&&mm.state.currentGroup;
    if(g&&g!=='home'){ tEnd=performance.now(); break; }
  }
  if(tEnd===null) return JSON.stringify({err:'120s 内 home 没播完（组没离开 home）'});
  const d=window.__speedDbg&&window.__speedDbg();
  return JSON.stringify({speed, endMs:Math.round(tEnd-t0), libEl:+m.elapsedTime.toFixed(1),
                         vEl:d?d.vEl:null, group:mm.state.currentGroup});
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
        print(f'判据常量：home 时长 {CLIP_DUR}s（Meta.Loop=false ⇒ 会播完）', flush=True)

        speeds = [float(x) for x in A.speeds.split(',') if x.strip()]
        clock = {}
        for s in speeds:
            r = ev(f'({JS_CLOCK})({s})')
            print(f'  时钟 {s}×:', r, flush=True)
            try:
                o = json.loads(r)
            except Exception:
                o = {'err': str(r)[:120]}
            if 'err' in o:
                say(False, f'{s}× 时钟读数失败：{o["err"]}')
                continue
            say(bool(o.get('patch')), f'{s}× 虚拟时钟补丁在位（im.update 含 l2VEl）')
            clock[s] = o.get('vElRate')
            if s != 1.0:
                say(str(o.get('resetShown')) == '1.0×' and o.get('resetSpeed') == 1,
                    f'{s}× 点倍率数字一键回 1×（显示 {o.get("resetShown")} · 内部 {o.get("resetSpeed")}）')

        # ② 不用任何曲线斜率的判据：整条 `home`（Meta.Loop=false，18.25s）播完那一刻的**虚拟秒**。
        #    虚拟钟与 clip 钟 1:1 时，1× 播完应当正好用掉 ≈18.25 虚拟秒（实测 18.65，含起播前摇）。
        #    ⚠️ **墙钟比值在本环境不可断言**：无头慢渲染下 ticker 会停/钳，2× 只量到 1.46 倍
        #    （停帧对 2× 的伤害比 1× 小，比值被压扁）⇒ 墙钟只作**方向性**判据。
        ends = {}
        for s in (1.0, 2.0):
            r = ev(f'({JS_END})({s})')
            print(f'  播完计时 {s}×:', r, flush=True)
            try:
                o = json.loads(r)
            except Exception:
                o = {'err': str(r)[:120]}
            if 'err' in o:
                say(False, f'{s}× 播完计时失败：{o["err"]}')
            else:
                ends[s] = o
        if 1.0 in ends:
            v1 = ends[1.0].get('vEl') or 0
            say(abs(v1 - CLIP_DUR) <= 1.2,
                f'② 1× 播完用掉虚拟秒 = {v1}（clip 时长 {CLIP_DUR}s，容差 ±1.2s）'
                f' ⇒ 虚拟钟与 clip 钟 1:1，且 1× 与改前一致')
        if 1.0 in ends and 2.0 in ends:
            r1, r2 = ends[1.0]['endMs'], ends[2.0]['endMs']
            say(r2 < r1 * 0.85,
                f'③ 2× 墙钟明显更短：{r1}ms → {r2}ms（{r1 / float(r2):.3f} 倍；'
                f'本环境停帧会把比值压到 2 以下，只断言方向）')

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
