# -*- coding: utf-8 -*-
"""语音 v2 接线的浏览器实播验收：静态立绘 / Spine / Live2D 三格各自点一次，断言**真的出声**。

判据落在"产品行动那一刻"（不是查表、不是查 DOM 存在）：
  ① 走真实 UI 路径（openShip → setSkin → 点标签 → 点语音按钮），不直接调页面内部函数；
  ② 用 CDP 在页面脚本执行前包住 window.Audio，录下每个实例的 src/play/pause/ended/错误；
  ③ 断言：新出现的 Audio 的 src 尾部 = 本皮肤序号档的那个文件，且 paused=false、currentTime 在涨；
  ④ 无语音皮肤必须显式显示 🔇，而不是静默空白。

用法: py -3 scripts/diag/voice_v2_verify.py [key1 key2 ...]   # 不传则自动挑样本
前置: 画廊服务器在 8777（双击 Output\\gallery_v2\\启动资产浏览器.bat）
"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket
import chrome_tree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9345
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_voice_v2')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'

HOOK = r"""
window.__AUD = [];
(function(){
  const Real = window.Audio;
  function Wrapped(src){
    const el = new Real(src);
    const rec = {src: String(src||'').split('/').pop(), t0: +(performance.now()/1000).toFixed(2),
                 events: [], dur: null};
    window.__AUD.push(rec);
    el.addEventListener('play', ()=>rec.events.push('play@'+(performance.now()/1000).toFixed(2)));
    el.addEventListener('pause', ()=>rec.events.push('pause@'+(performance.now()/1000).toFixed(2)));
    el.addEventListener('ended', ()=>{rec.events.push('ended'); rec.dur=el.duration;});
    el.addEventListener('error', ()=>rec.events.push('error'));
    rec.el = el;
    return el;
  }
  Wrapped.prototype = Real.prototype;
  window.Audio = Wrapped;
})();
"""

PICK = r"""(async()=>{
  for(let i=0;i<90 && !window.GALLERY;i++) await new Promise(r=>setTimeout(r,300));
  await new Promise(r=>setTimeout(r,400));
  // ⚠️ 两个坑：表是 mountSkinVoice 里异步拉的（不 await 就谁都"无语音"）；
  //    且 `let SV` 不挂到 window 上，用 window.SV 取恒为 undefined ⇒ 三视图挑不到样本、
  //    只有"无语音"那条空洞通过 = 假绿灯。必须 await loadVoiceMap() 后按裸名取。
  await loadVoiceMap();
  const sv=(typeof SV!=='undefined'&&SV)||{};
  const out={paint:null,spine:null,live2d:null,novoice:null, total:0, sv_n:Object.keys(sv).length};
  const tapOf=k=>{const e=sv[k]; return e&&e.tap&&Object.keys(e.tap).length?e:null;};
  for(const s of GALLERY.ships){
    for(const sk of s.skins){
      out.total++;
      const e=tapOf(sk.key);
      if(!e) { if(!out.novoice && !sv[sk.key]) out.novoice=sk.key; continue; }
      if(!out.paint && sk.image) out.paint=sk.key;
      if(!out.spine && s.spineSkins && s.spineSkins.includes(sk.key)) out.spine=sk.key;
      if(!out.live2d && s.live2dSkins && s.live2dSkins.includes(sk.key)) out.live2d=sk.key;
    }
  }
  return JSON.stringify(out);
})()"""

CASE = r"""(async(key, tab)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  await loadVoiceMap(); const sv=(typeof SV!=='undefined'&&SV)||{};
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, tab, err:'索引里找不到该皮肤'});
  const before=window.__AUD.length;
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k===tab).click();
  const res={key, tab, expect:Object.entries(((sv[key]||{}).tap)||{}).map(([k,v])=>k+':'+v.split('/').pop())};
  // 等语音条出现（表是异步来的）
  let bar=null;
  for(let i=0;i<60;i++){ 
    const b=document.querySelectorAll('.vbox button[data-vk], #l2Groups option');
    if(tab==='live2d'){ if(document.getElementById('l2Voice') && /语音 \d+ 组/.test(document.getElementById('l2Voice').textContent)) {res.l2v=document.getElementById('l2Voice').textContent; break;} }
    else if(b.length && document.querySelectorAll('.vbox button[data-vk]').length){ bar=1; break; }
    await t(500); }
  const btns=[...document.querySelectorAll('.vbox button[data-vk]')];
  res.buttons=btns.map(b=>b.textContent);
  if(tab==='live2d'){
    const sel=document.getElementById('l2Motion');
    if(!sel) return JSON.stringify(Object.assign(res,{err:'Live2D 组下拉未出现'}));
    res.withVoice=[...sel.options].filter(o=>/（语音）/.test(o.textContent)).map(o=>o.value);
    const pickv=res.withVoice[0];
    if(!pickv) return JSON.stringify(Object.assign(res,{err:'没有带（语音）标记的组'}));
    for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
    sel.value=pickv; sel.dispatchEvent(new Event('change'));
    await t(1500);
    res.group=pickv;
  } else {
    if(!btns.length) return JSON.stringify(Object.assign(res,{err:'语音条按钮未出现',
        box:(document.querySelector('.vbox')||{}).textContent||''}));
    btns[0].click(); await t(1500);
    res.clicked=btns[0].textContent;
  }
  const recs=window.__AUD.slice(before);
  res.audios=recs.map(r=>({src:r.src, ev:r.events, cur:r.el?+r.el.currentTime.toFixed(2):null,
                           paused:r.el?r.el.paused:null, err:r.el?r.el.error:null}));
  const a=recs[0];
  res.playing = !!(a && a.el && a.el.currentTime>0.1 && !a.el.paused && !a.el.error);
  res.src_is_own_index_tier = !!(a && sv[key] && (function(){
      const files=[]; const e=sv[key];
      for(const g in (e.l2d||{})) files.push(...e.l2d[g]);
      files.push(...Object.values(e.tap||{}));
      return files.some(p=>p.split('/').pop()===a.src);})());
  return JSON.stringify(res);
}catch(e){ return JSON.stringify({key, tab, thrown:String(e).slice(0,160)}); }})"""

NOVOICE = r"""(async(key)=>{
  await loadVoiceMap(); const sv=(typeof SV!=='undefined'&&SV)||{};
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, err:'找不到'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  [...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='painting').click();
  await new Promise(r=>setTimeout(r,2500));
  const box=document.querySelector('.vbox');
  return JSON.stringify({key, inSV: !!sv[key], box: box?box.textContent.trim():'(无语音条)',
                         silent: box?/无语音/.test(box.textContent):false});
})"""


def main():
    args = sys.argv[1:]
    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
        '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
        '--window-size=1400,900', '--autoplay-policy=no-user-gesture-required',
        '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
        '--disable-background-timer-throttling', BASE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ws = None
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                w = [t['webSocketDebuggerUrl'] for t in tabs
                     if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if w:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not w:
            print('!! Chrome 里没出现画廊页面')
            return 1
        ws = websocket.create_connection(w[0], timeout=180, max_size=None)
        _id = 0

        def cmd(m, p=None):
            nonlocal _id
            _id += 1
            ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
            ws.settimeout(180)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:200])
                    return r.get('result', {})

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
            if r.get('exceptionDetails'):
                return 'EVALERR ' + str(r['exceptionDetails'].get('text'))[:200]
            return r.get('result', {}).get('value')

        cmd('Page.enable')
        cmd('Page.addScriptToEvaluateOnNewDocument', {'source': HOOK})
        cmd('Page.navigate', {'url': BASE})
        time.sleep(3)
        pick = json.loads(ev(PICK) or '{}')
        print('自动挑样本:', json.dumps(pick, ensure_ascii=False))
        keys = args or [k for k in (pick.get('paint'), pick.get('live2d'), pick.get('spine')) if k]
        bad = 0
        for k in keys:
            for tab in (['live2d'] if k == pick.get('live2d') else
                        ['spine'] if k == pick.get('spine') else ['painting']):
                r = json.loads(ev(f'({CASE})({json.dumps(k)}, {json.dumps(tab)})'))
                ok = r.get('playing') and r.get('src_is_own_index_tier')
                bad += 0 if ok else 1
                print(f'{"✅" if ok else "❌"} [{tab}] {k}: '
                      f'按钮={r.get("buttons")} 期望={r.get("expect")}')
                for a in (r.get('audios') or []):
                    print(f'     Audio {a["src"]} cur={a["cur"]}s paused={a["paused"]} '
                          f'err={a["err"]} ev={a["ev"]}')
                for extra in ('l2v', 'withVoice', 'group', 'clicked', 'err', 'thrown', 'box'):
                    if r.get(extra):
                        print(f'     {extra}={r[extra]}')
        if pick.get('novoice'):
            r = json.loads(ev(f'({NOVOICE})({json.dumps(pick["novoice"])})'))
            ok = r.get('inSV') is False and r.get('silent')
            bad += 0 if ok else 1
            print(f'{"✅" if ok else "❌"} [无语音显式标注] {r}')
        print('\n判定:', '全部真出声' if not bad else f'{bad} 项未通过')
        return 1 if bad else 0
    finally:
        chrome_tree.kill_tree(proc.pid)


if __name__ == '__main__':
    sys.exit(main())
