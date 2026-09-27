# -*- coding: utf-8 -*-
"""台词字幕 + 两个全局开关的浏览器实播验收（三格各点一次 + 开关矩阵 + 语音页列表）。

判据全部落在「产品行动那一刻」，且**逐字比对**而不是"非空即过"：
  ① 走真实 UI 路径（openShip → setSkin → 点标签 → 点语音按钮 / 点开关），不直接调页面内部函数；
  ② 用 CDP 在页面脚本执行前包住 window.Audio，录下每个实例的 src / play / pause / 错误；
  ③ 出声断言：新 Audio 的 src 属于本皮肤档位，paused=false 且 currentTime 在涨；
  ④ 字幕断言：#mSub 正文 == 表里该槽位的正文（逐字），且 .who 带上这条的类别名；
  ⑤ 开关独立性：关「显示台词」→ 有声音无字幕；关「点击出声」→ 有字幕无新 Audio；
     两条都必须**实测到反向证据**，不许只验"开着的时候能显示"；
  ⑥ 阴性对照：选了「有音频但游戏本来没写词」的槽位（如部分船的摸头），
     必须出声且**不弹空字幕**——这既是产品行为，也是防止"字幕永远显示上一条"这类残留 bug；
  ⑦ 探针取不到页面状态时硬失败：SW / wordsOf 拿不到就整体判 FAIL，
     绝不让"没测到"长得像"测过了"（§48 的假绿灯教训）。

用法: py -3 scripts/diag/talk_verify.py [key ...]     # 不传则按判据自动挑样本
前置: 画廊服务器在 8777（双击 Output\\gallery_v2\\启动资产浏览器.bat）
"""
import sys, os, json, time, base64, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket
import chrome_tree

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9347
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_talk')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'

HOOK = r"""
window.__AUD = [];
(function(){
  const Real = window.Audio;
  function Wrapped(src){
    const el = new Real(src);
    const rec = {src: String(src||'').split('/').pop(), events: [], el: el};
    window.__AUD.push(rec);
    el.addEventListener('play', ()=>rec.events.push('play'));
    el.addEventListener('pause', ()=>rec.events.push('pause'));
    el.addEventListener('error', ()=>rec.events.push('error'));
    return el;
  }
  Wrapped.prototype = Real.prototype;
  window.Audio = Wrapped;
})();
"""

READY = r"""(async()=>{
  for(let i=0;i<120 && !window.GALLERY;i++) await new Promise(r=>setTimeout(r,250));
  await Promise.all([loadVoiceMap(), loadWords()]);
  const sv=(typeof SV!=='undefined'&&SV)||{}, sw=(typeof SW!=='undefined'&&SW)||null;
  return JSON.stringify({ships:(window.GALLERY||{}).ships?GALLERY.ships.length:0,
                         sv:Object.keys(sv).length, wordsReady: !!(sw&&sw.m&&sw.w),
                         fns:[typeof wordsOf, typeof lineText, typeof speak].join('/')});
})()"""

# 按判据挑样本：三格各一条「有触摸语音且有正文」的，再加一条「有音频但游戏没写词」的槽位
PICK = r"""(async()=>{
  await Promise.all([loadVoiceMap(), loadWords()]);
  const sv=(typeof SV!=='undefined'&&SV)||{};
  const out={paint:null,spine:null,live2d:null,notext:null,novoice:null,vtab:null,total:0};
  const l2=new Set(), sp=new Set();
  for(const s of GALLERY.ships){
    (s.live2dSkins||[]).forEach(k=>l2.add(k)); (s.spineSkins||[]).forEach(k=>sp.add(k));
    for(const sk of s.skins){
      out.total++;
      const e=sv[sk.key]; if(!e){ if(!out.novoice && !sk.image) out.novoice=sk.key; continue; }
      const w=(typeof wordsOf==='function')?wordsOf(sk.key)||{}:{};
      /* 语音标签页要挑**索引认为有语音**的船（voiceCount>0 才给标签），且这一行得有正文，
         否则换索引前后测的不是同一条路径，"行数/正文数"也无从对齐。 */
      if(!out.vtab && s.voiceCount>0 && (e.lines||[]).some(l=>w[l.cat])) out.vtab=sk.key;
      const tap=e.tap||{};
      for(const slot of ['touch_body','touch_special','touch_head']){
        if(!tap[slot]) continue;
        const text=w[slot]||'';
        if(text){ if(!out.paint && sk.image) out.paint=sk.key;
                  if(!out.spine && sp.has(sk.key)) out.spine=sk.key;
                  if(!out.live2d && l2.has(sk.key)) out.live2d=sk.key; }
        else if(!out.notext && sk.image) out.notext={k:sk.key,slot:slot};
      }
    }
  }
  return JSON.stringify(out);
})()"""

# 通用一次「点击 → 出声 + 字幕」，opts: {lines:bool} 用于开关矩阵
CLICK = r"""(async(key, tab, opts)=>{ try{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  const wantText = !(opts&&opts.nolines);
  await Promise.all([loadVoiceMap(), loadWords()]);
  const sv=(typeof SV!=='undefined'&&SV)||{};
  const e=sv[key]; if(!e) return JSON.stringify({key,tab,err:'语音表里没有这个皮肤（样本挑错或表没部署）'});
  if(typeof wordsOf!=='function' || !wordsOf(key)) return JSON.stringify({key,tab,err:'正文档取不到（skin_words.json 没部署或没 join 上）'});
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key,tab,err:'索引里找不到该皮肤'});
  const before=window.__AUD.length;
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const tabEl=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k===tab);
  if(!tabEl) return JSON.stringify({key,tab,err:'标签不存在'});
  if(!tabEl.classList.contains('dis')) tabEl.click();
  // 等语音条 / 动作下拉出现
  let btns=[];
  for(let i=0;i<80;i++){
    btns=[...document.querySelectorAll('.vbox button[data-vk]')];
    if(tab==='live2d'){ if(document.getElementById('l2Motion')) break; }
    else if(btns.length) break;
    await t(400); }
  const w=wordsOf(key)||{};
  const res={key, tab, opt:(typeof OPT!=='undefined'?JSON.stringify(OPT):'?'),
             audN:window.__AUD.length, buttons:btns.map(b=>b.textContent),
             pill:(document.querySelector('.vbox')||{}).textContent||'',
             l2voice:(document.getElementById('l2Voice')||{}).textContent||''};
  if(tab==='live2d'){
    const sel=document.getElementById('l2Motion');
    if(!sel) return JSON.stringify(Object.assign(res,{err:'Live2D 动作下拉未出现'}));
    for(let i=0;i<80 && !(l2State&&l2State.app&&l2State.app.stage.children[0]);i++) await t(500);
    const withv=[...sel.options].filter(o=>/（语音）/.test(o.textContent)).map(o=>o.value);
    const pickG=withv.find(g=>w[g]) || withv[0];
    if(!pickG) return JSON.stringify(Object.assign(res,{err:'没有带（语音）标记的组'}));
    res.slot=pickG; res.expect=w[pickG]||'';
    sel.value=pickG; sel.dispatchEvent(new Event('change'));
  } else {
    if(!btns.length) return JSON.stringify(Object.assign(res,{err:'语音条按钮未出现',
        box:(document.querySelector('.vbox')||{}).textContent||''}));
    /* 指定槽位时**必须真点到那个槽位**：早版一律点第一个按钮，于是"摸头无正文"的阴性对照
       实际点的是普通触摸，测出来的字幕属于另一条语音 = 假失败（也说明探针没跟着产品走）。 */
    const want=(opts&&opts.slot)||'';
    const b=want ? btns.find(x=>x.dataset.vk===want) : btns[0];
    if(!b) return JSON.stringify(Object.assign(res,{err:'该皮肤没有槽位按钮 '+want}));
    res.slot=b.dataset.vk; res.expect=w[b.dataset.vk]||'';
    res.tapFile=(e.tap||{})[res.slot]||'';
    b.click();
    res.syncNewAudio = window.__AUD.length - before;   // 点击那一瞬有没有真的 new Audio
  }
  let waited=0, a=null;
  for(let i=0;i<28;i++){
    const recs=window.__AUD.slice(before); a=recs[0];
    if(a && a.el && (a.el.currentTime>0.05 || a.el.error)) break;
    await t(250); waited+=250; }
  const recs=window.__AUD.slice(before);
  res.newAudio=recs.length;
  res.waited_ms=waited;
  const files=[]; for(const g in (e.l2d||{})) files.push(...e.l2d[g]);
  files.push(...Object.values(e.tap||{}));
  const own=files.map(p=>p.split('/').pop());
  res.audio = a? {src:a.src, ev:a.events, cur:a.el?+a.el.currentTime.toFixed(2):null,
                  paused:a.el?a.el.paused:null, err:a.el?a.el.error:null,
                  ownTier: !!(a && own.indexOf(a.src)>=0)} : null;
  res.playing = !!(a && a.el && a.el.currentTime>0.05 && !a.el.error && res.audio.ownTier);
  const sub=document.getElementById('mSub');
  res.sub = sub? {on: sub.classList.contains('on'),
                  who: (sub.querySelector('.who')||{}).textContent||'',
                  text: [...sub.querySelectorAll('span')].filter(x=>!x.classList.contains('who')).map(x=>x.textContent).join('')}
                : null;
  /* 期望字幕 = 「该槽位的正文」；关显示台词时期望空；游戏没写词的槽位期望也是空（阴性对照） */
  const wantSub = wantText ? (res.expect||'') : '';
  res.subMatch = !!(res.sub && res.sub.text === wantSub);
  /* 「谁在说」这行必须是**中文类别名**（表里的 voice_name），不是内部键 complete/touch_body */
  const lab=(typeof SW!=='undefined'&&SW.L&&SW.L[res.slot])||'';
  res.whoLabel=lab;
  res.whoOk = wantSub==='' ? true : !!(lab && res.sub && res.sub.who.indexOf(lab)>=0);
  return JSON.stringify(res);
}catch(err){ return JSON.stringify({key,tab,thrown:String(err).slice(0,200)}); }})"""

# 语音标签页：行数与正文逐字比对
VOICEPAGE = r"""(async(key)=>{
  const t=ms=>new Promise(r=>setTimeout(r,ms));
  await Promise.all([loadVoiceMap(), loadWords()]);
  let ship=null, sk=null;
  for(const s of GALLERY.ships){ const k=s.skins.find(x=>x.key===key); if(k){ship=s;sk=k;break;} }
  if(!sk) return JSON.stringify({key, err:'找不到皮肤'});
  openShip(ship); setSkin(sk); buildSkinList(ship);
  const tabEl=[...document.querySelectorAll('#mTabs .tab')].find(x=>x.dataset.k==='voice');
  if(!tabEl) return JSON.stringify({key, err:'没有语音标签'});
  if(tabEl.classList.contains('dis')) return JSON.stringify({key, err:'语音标签被置灰（索引 voiceCount 口径没换或该船确实无语音）',
                                                             vc: ship.voiceCount});
  tabEl.click();
  const e=(SV||{})[key]||{}, w=wordsOf(key)||{};
  const nLines=(e.lines||[]).length, nText=(e.lines||[]).filter(l=>w[l.cat]).length;
  let rows=[];
  for(let i=0;i<60;i++){ rows=[...document.querySelectorAll('.audwrap .aud')];
    if(rows.length>=Math.max(1,nLines)) break; await t(300); }
  const texts=rows.map(r=>{const x=r.querySelector('.tw'); return x?x.textContent:'';});
  const audios=rows.map(r=>{const a=r.querySelector('audio');
    return a?{src:a.src.split('/').pop(), h:Math.round(a.getBoundingClientRect().height)}:null; });
  /* 语音页的本职是"能播"：audio 不存在、或高宽为 0（被 flex 压扁）都算失败，
     光比"行数/正文数"会放过"只剩一行字、播放器没了"这类回退。 */
  const playable = audios.length && audios.every(a=>a && a.src && a.h>=20);
  const h4=(document.querySelector('.audwrap h4')||{}).textContent||'';
  return JSON.stringify({key, expectRows:nLines+(sk.voiceExtra||[]).length, gotRows:rows.length,
    expectTexts:nText, gotTexts:texts.filter(x=>x).length, head:h4,
    firstText:texts.find(x=>x)||'', firstAudio:audios[0], audioHeights:audios.map(a=>a&&a.h).slice(0,6),
    playable: !!playable,
    rowsAligned: texts.slice(0,nLines).every((tx,i)=> tx===(w[(e.lines[i]||{}).cat]||'')),
    extra:(sk.voiceExtra||[]).length, vc:ship.voiceCount});
})"""

SETOPT = r"""(k,on)=>{ const b=document.querySelector('#gOpt button[data-k="'+k+'"]');
  if(!b) return 'NO BUTTON'; if((typeof OPT!=='undefined')&&OPT[k]!==on) b.click();
  return k+'='+(typeof OPT!=='undefined'?OPT[k]:'?')+' cls='+(b.classList.contains('on')?'on':'off'); }"""

READOPT = r"""()=>JSON.stringify({opt:(typeof OPT!=='undefined'?OPT:null),
  cls:[...document.querySelectorAll('#gOpt button')].map(b=>b.dataset.k+':'+(b.classList.contains('on')?1:0)),
  ls:localStorage.getItem('gallery.opt.v1')})"""


def connect():
    for _ in range(90):
        try:
            tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
            w = [t['webSocketDebuggerUrl'] for t in tabs
                 if 'gallery_v2' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
            if w:
                return w[0]
        except Exception:
            pass
        time.sleep(0.5)
    return None


def main():
    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
        '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
        '--window-size=1400,900', '--autoplay-policy=no-user-gesture-required',
        '--enable-unsafe-swiftshader', '--use-angle=swiftshader',
        '--disable-background-timer-throttling', BASE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    fails = []
    try:
        ws_url = connect()
        if not ws_url:
            print('!! Chrome 里没出现画廊页面')
            return 1
        ws = websocket.create_connection(ws_url, timeout=180, max_size=None)
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

        def ev(expr):
            r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': True})
            d = r.get('exceptionDetails')
            if d:
                return 'EVALERR %s | %s' % (str(d.get('text'))[:120],
                                            str((d.get('exception') or {}).get('description')
                                                or (d.get('exception') or {}).get('value') or '')[:300])
            return r.get('result', {}).get('value')

        def jev(expr, label):
            """探针必须**取不到状态就硬失败**：把 EVALERR / 非 JSON 当成"通过"是假绿灯的成因。"""
            v = ev(expr)
            if not isinstance(v, str) or v.startswith('EVALERR'):
                raise RuntimeError('%s：探针没取到返回值，不能算通过 → %r' % (label, str(v)[:220]))
            try:
                return json.loads(v)
            except Exception as e:
                raise RuntimeError('%s：返回值不是 JSON（%s）→ %s' % (label, e, v[:220]))

        def shot(tag):
            """--shots：截下"字幕正显示着"的那一刻给人工目视验收——判据过了不代表长得对。"""
            if '--shots' not in sys.argv:
                return None
            r = cmd('Page.captureScreenshot', {'format': 'png'})
            p = os.path.join(ROOT, '.diag', 'talk_shot_%s.png' % tag)
            open(p, 'wb').write(base64.b64decode(r['data']))
            print('   截图:', os.path.relpath(p, ROOT).replace('\\', '/'))
            return p

        cmd('Page.enable')
        cmd('Page.addScriptToEvaluateOnNewDocument', {'source': HOOK})
        cmd('Page.navigate', {'url': BASE})
        time.sleep(3)
        ready = jev(READY, '页面就绪')
        print('就绪:', json.dumps(ready, ensure_ascii=False))
        if not ready.get('ships') or not ready.get('sv') or not ready.get('wordsReady'):
            print('❌ 索引 / 语音表 / 正文档没全部到位，后面的判据都不成立')
            return 1

        pick = jev(PICK, '挑样本')
        print('样本:', json.dumps(pick, ensure_ascii=False))
        args = [a for a in sys.argv[1:] if not a.startswith('--')]
        if args:
            pick = dict(pick, paint=args[0], spine=args[0] if len(args) > 1 else None,
                        live2d=args[-1] if len(args) > 2 else None)

        def setopt(k, on):
            print('   开关:', ev('(%s)(%s,%s)' % (SETOPT, json.dumps(k), 'true' if on else 'false')))

        # 基线必须**当轮设**：无头 Chrome 被 kill 时不保证把 localStorage 落盘，
        # 上一轮崩溃时的开关状态会原样活到这一轮（实测开局 opt={voice:false,lines:false} → 三格全"没出声"）。
        setopt('voice', True)
        setopt('lines', True)

        for tab, key in (('painting', pick.get('paint')), ('spine', pick.get('spine')),
                         ('live2d', pick.get('live2d'))):
            if not key:
                fails.append('%s 没挑到样本（挑样本的判据没匹配到皮肤）' % tab)
                continue
            r = jev('(%s)(%s,%s,%s)' % (CLICK, json.dumps(key), json.dumps(tab), 'null'), '%s 实播' % tab)
            ok = r.get('playing') and r.get('subMatch') and r.get('whoOk')
            print(f'{"✅" if ok else "❌"} [{tab}] {key} 出声={r.get("playing")} '
                  f'字幕逐字一致={r.get("subMatch")} 中文类别名={r.get("whoOk")} 槽位={r.get("slot")} '
                  f'新Audio={r.get("newAudio")} opt={r.get("opt")} '
                  f'audio={json.dumps(r.get("audio"), ensure_ascii=False)}')
            print(f'      字幕=「{(r.get("sub") or {}).get("text","")[:60]}」 期望=「{(r.get("expect") or "")[:60]}」 '
                  f'谁=「{(r.get("sub") or {}).get("who","")}」 条={r.get("pill","")[:40]}')
            shot('%s_%s' % (tab, key))
            if not ok:
                fails.append(f'[{tab}] {key}: ' + json.dumps(r, ensure_ascii=False)[:300])

        # ---- 开关矩阵：两条独立，各自都要验到「反向证据」 ----
        k = pick.get('paint')
        if k:
            setopt('lines', False)
            r = jev('(%s)(%s,%s,%s)' % (CLICK, json.dumps(k), '"painting"', '{"nolines":true}'), '关显示台词')
            ok = r.get('playing') and r.get('sub') is not None and r['sub']['text'] == ''
            print(f'{"✅" if ok else "❌"} [开关独立性] 关显示台词 → 仍出声={r.get("playing")} '
                  f'字幕为空={(r.get("sub") or {}).get("text","")!r}')
            if not ok:
                fails.append('关显示台词后不是「有声无字」: ' + json.dumps(r, ensure_ascii=False)[:300])
            setopt('lines', True)

            setopt('voice', False)
            r = jev('(%s)(%s,%s,%s)' % (CLICK, json.dumps(k), '"painting"', 'null'), '关点击出声')
            ok = (not r.get('playing')) and r.get('newAudio') == 0 and r.get('subMatch')
            print(f'{"✅" if ok else "❌"} [开关独立性] 关点击出声 → 新 Audio={r.get("newAudio")} '
                  f'仍上字幕={r.get("subMatch")} 字幕=「{(r.get("sub") or {}).get("text","")[:40]}」')
            if not ok:
                fails.append('关点击出声后不是「有字无声」: ' + json.dumps(r, ensure_ascii=False)[:300])
            setopt('voice', True)

        # ---- 阴性对照：有音频、游戏没写词的槽位 → 出声且不留空字幕框 ----
        nt = pick.get('notext')
        if nt:
            r = jev('(%s)(%s,%s,%s)' % (CLICK, json.dumps(nt['k']), '"painting"',
                                        json.dumps({'slot': nt['slot']})), '阴性对照')
            ok = r.get('playing') and r.get('sub') and r['sub']['text'] == ''
            print(f'{"✅" if ok else "❌"} [阴性对照] {nt["k"]} 的 {nt["slot"]} 无正文 → '
                  f'出声={r.get("playing")} 字幕={json.dumps((r.get("sub") or {}).get("text"), ensure_ascii=False)}')
            shot('notext_%s' % nt['slot'])
            if not ok:
                fails.append('无正文槽位没走「出声但不弹字幕」: ' + json.dumps(r, ensure_ascii=False)[:300])
        else:
            fails.append('没挑到「有音频但无正文」的阴性对照样本，这一条等于没测')

        # ---- 语音标签页 ----
        vk = pick.get('vtab')
        if not vk:
            fails.append('没挑到「索引认为有语音、且该行有正文」的语音页样本 ⇒ 这条判据等于没测')
        else:
            r = jev('(%s)(%s)' % (VOICEPAGE, json.dumps(vk)), '语音页')
            ok = (r.get('gotRows') == r.get('expectRows') and r.get('gotTexts') == r.get('expectTexts')
                  and r.get('rowsAligned') and r.get('playable'))
            print(f'{"✅" if ok else "❌"} [语音页] {vk} 行数 {r.get("gotRows")}/{r.get("expectRows")} '
                  f'正文 {r.get("gotTexts")}/{r.get("expectTexts")} 逐行对齐={r.get("rowsAligned")} '
                  f'每行可播={r.get("playable")} audio高={r.get("audioHeights")} '
                  f'首条=「{(r.get("firstText") or "")[:30]}」 变体包={r.get("extra")}')
            shot('voicepage_%s' % vk)
            if not ok:
                fails.append('语音页台词列表不符: ' + json.dumps(r, ensure_ascii=False)[:300])

        # ---- 持久化：设成**非常规组合**再重开，才证明确实读的是盘上那份（默认值也能骗过"全 true"的判据）----
        setopt('lines', False)
        print('   重开前:', ev('(%s)()' % READOPT))
        cmd('Page.navigate', {'url': BASE})
        time.sleep(3)
        jev(READY, '重开后就绪')
        after = jev('(%s)()' % READOPT, '持久化')
        ok = (after.get('opt') or {}).get('voice') is True and (after.get('opt') or {}).get('lines') is False \
            and 'voice:1' in after.get('cls', []) and 'lines:0' in after.get('cls', [])
        print(f'{"✅" if ok else "❌"} [持久化] 重开后={json.dumps(after, ensure_ascii=False)}')
        if not ok:
            fails.append('开关持久化/回显不符: ' + json.dumps(after, ensure_ascii=False)[:200])
        setopt('lines', True)   # 交还给用户时保持默认全开
    finally:
        try:
            ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)

    if fails:
        print('\n[FAIL] %d 条判据未过：' % len(fails))
        for f in fails:
            print('  - %s' % f)
        return 1
    print('\n[PASS] 三格实播 + 开关矩阵 + 阴性对照 + 语音页列表 + 持久化 全部通过')
    return 0


if __name__ == '__main__':
    sys.exit(main())
