# -*- coding: utf-8 -*-
"""背景库页（backgrounds.html）验收：图真的解码出像素、三档命名各自显示对、筛选与详情层可用、
   出处能回指到配置表的表/字段/行号，并**深浅两套主题各拍一张图交人看**。

判据形状照 `bgm_page_probe.py`（同一条 harness：自起服务器 + `cdp_slot` 隔离端口/profile）。
为什么第 1 组量的是 `naturalWidth>0` 而不是"卡片数量"：
   2026-10-07 第一版把懒加载挂在 IntersectionObserver 上，而连着的应用内浏览器页
   `innerHeight=0` ⇒ IO 永不判相交 ⇒ **1897 个格子全在、全空**。只量 DOM 存在会报绿。
   ⇒ 探针必须量"图片对象真的解出像素"，并且配一条**反向对照**：故意请求一张不存在的图，
      看 `.miss` 标记会不会出现（标记不出来 = 这组判据是假的）。
⚠️ 服务器自起一份，不复用 8777（那台可能跑着改动前的代码，也可能被另一个会话的探针占着）。
"""
import base64
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)
import cdp_slot                      # noqa: E402
import chrome_tree                   # noqa: E402
import paths as P                    # noqa: E402
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))
import _gallery_server as GS         # noqa: E402

CHROME = P.tool('AL_CHROME', 'chrome', r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
PORT, PROFILE = cdp_slot.slot(ROOT, 'bgp')
OUT_SHOTS = os.path.join(P.ROOT, '.diag')
FAIL = []
_httpd = None
_port = None


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAIL.append(msg)


def free_port():
    import socket
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def base():
    return f'http://127.0.0.1:{_port}/gallery_v2/'


def serve_up():
    global _httpd, _port
    _port = free_port()
    _httpd = GS.make_server(port=_port, root=P.OUT)
    threading.Thread(target=_httpd.serve_forever, daemon=True).start()
    try:
        b = urllib.request.urlopen(base() + 'bg_meta.json', timeout=8).read()
        return len(b) >= 100000, len(b)
    except Exception as e:
        print(f'  ! bg_meta.json 取不到: {e}')
        return False, 0


def main():
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    ok, n = serve_up()
    if not ok:
        print(f'[FAIL] 自起的服务器取不到 bg_meta.json（{n} 字节）⇒ 先跑 build_bg_meta.py')
        return 2
    META = json.load(open(os.path.join(P.OUT, 'gallery_v2', 'bg_meta.json'), encoding='utf-8'))
    proc = subprocess.Popen([CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
                             '--remote-allow-origins=*', f'--user-data-dir={PROFILE}',
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling',
                             '--use-angle=swiftshader', '--window-size=1440,1000',
                             base() + 'backgrounds.html'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        for _ in range(90):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json'))
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if 'backgrounds.html' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if u:
                    import websocket
                    ws = websocket.create_connection(u[0], timeout=120, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print('[FAIL] 128 秒内没连上浏览器')
            return 2
        _id = 0

        def cmd(m, p=None):
            nonlocal _id
            _id += 1
            ws.send(json.dumps({'id': _id, 'method': m, 'params': p or {}}))
            ws.settimeout(120)
            while True:
                r = json.loads(ws.recv())
                if r.get('id') == _id:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:160])
                    return r.get('result', {})

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'returnByValue': True, 'awaitPromise': True})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:200]}
            return r.get('result', {}).get('value')

        def shot(tag, sel=None):
            cmd('Page.enable')
            args = {'format': 'png'}
            if sel:
                # 网格整高有 39 万像素，不夹到视口就会拍出一张几乎全空的长图
                box = cmd('Runtime.evaluate', {
                    'expression': '(function(){var e=document.querySelector('
                                  + json.dumps(sel) + ');if(!e)return "";'
                                  'var b=e.getBoundingClientRect();'
                                  'var h=Math.min(b.height, innerHeight-b.top);'
                                  'return JSON.stringify({x:b.x,y:b.y,width:b.width,height:h});})()',
                    'returnByValue': True})
                try:
                    r = json.loads(box['result']['value'])
                except (KeyError, ValueError):
                    r = None
                if r and r.get('width'):
                    args['clip'] = {'x': r['x'], 'y': r['y'], 'width': r['width'],
                                    'height': r['height'], 'scale': 2.0}
            b64 = cmd('Page.captureScreenshot', args)['data']
            fp = os.path.join(OUT_SHOTS, f'bg_shot_{tag}.png')
            with open(fp, 'wb') as f:
                f.write(base64.b64decode(b64))
            return fp

        print('== 0) 默认视图 = 只藏"明确判过无角色"的（P2 人工逐格标注）==')
        CH = META['char']
        # ⚠️ 必须先等 boot 落完再读 DOM：第 0 组是整支探针里第一处量页面的地方，
        #    连上 CDP 时 `boot()` 的 fetch(bg_meta.json) 可能还没回来 ⇒ 0 卡片 0 chip，
        #    连着打红 4 条（实测首跑红、二跑绿，红的是探针自己造的，不是页面）。
        ev(r"""(async()=>{const t=ms=>new Promise(r=>setTimeout(r,ms));
              for(let i=0;i<150 && !document.querySelector('#gChar .chip');i++) await t(200);
              return 1})()""")
        d0 = ev(r"""(()=>{
          const chips=[...document.querySelectorAll('#gChar .chip')];
          const num=t=>+((t.match(/(\d+)\s*$/)||[0,0])[1]);
          const h=document.getElementById('gHint');
          return {cards:document.querySelectorAll('.card').length,
                  nChips:chips.length,
                  on:chips.filter(x=>x.classList.contains('on')).map(x=>x.textContent),
                  counts:chips.map(x=>[x.textContent.replace(/\s*\d+$/,''),num(x.textContent)]),
                  hintHidden:h.hidden, hintText:h.textContent.trim()};
        })()""")
        say(isinstance(d0, dict) and d0.get('nChips') == 5,
            f"「画面」chip 建出来了（{d0.get('nChips')} 颗）: {d0.get('counts') if isinstance(d0, dict) else d0}")
        say(isinstance(d0, dict) and d0.get('cards') == CH['has'] + CH['unlabeled'],
            f"默认视图 {d0.get('cards') if isinstance(d0, dict) else d0} 张 == 有角色 {CH['has']} "
            f"+ 未标注 {CH['unlabeled']}（全库 {len(META['items'])} 张；"
            f"只有**明确判过无角色**的才许被藏）")
        say(isinstance(d0, dict) and d0.get('on') and str(d0['on'][0]).startswith('隐藏无角色'),
            f"默认选中的 chip: {d0.get('on')!r}")
        say(isinstance(d0, dict) and not d0.get('hintHidden') and str(CH['none']) in d0.get('hintText', ''),
            f"常驻「已隐藏 N 张」条在位: {d0.get('hintText')!r}")
        p0 = shot('char_default')
        say(os.path.getsize(p0) > 30000, f"默认视图截图（交人看是否真以角色图为主）: {p0}")

        print('== 0b) 反向对照：五档 chip 各自数得对，且「全部」下常驻条自己收起 ==')
        d0b = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const pick=l=>[...document.querySelectorAll('#gChar .chip')]
              .find(x=>x.textContent.startsWith(l));
          const N=()=>document.querySelectorAll('.card').length;
          const dirs=()=>[...new Set([...document.querySelectorAll('.card')].map(c=>c.dataset.k.split('/')[0]))];
          pick('全部').click(); await t(900);
          const {all,hintAll}={all:N(),hintAll:document.getElementById('gHint').hidden};
          pick('无角色').click(); await t(900); const no=N();
          pick('仅确认有角色').click(); await t(900); const has=N(), hasDirs=dirs();
          pick('未标注').click(); await t(900); const unk=N(), unkDirs=dirs();
          pick('隐藏无角色').click(); await t(900); const shown=N();
          return {all,hintAll,no,has,unk,shown,hasDirs,unkDirs};
        })()""")
        say(isinstance(d0b, dict) and d0b.get('all') == len(META['items'])
            and d0b.get('no') == CH['none'] and d0b.get('has') == CH['has']
            and d0b.get('unk') == CH['unlabeled']
            and d0b.get('shown') == CH['has'] + CH['unlabeled'],
            f"五档计数逐条对: 全部 {d0b.get('all')} / 无角色 {d0b.get('no')} / 仅确认 {d0b.get('has')} "
            f"/ 未标注 {d0b.get('unk')} / 隐藏无角色 {d0b.get('shown')}")
        say(isinstance(d0b, dict) and d0b.get('hintAll'),
            "切到「全部」时常驻条收起（一张都没藏还写着「藏了 770 张」就是假条）")
        # 「未标注」这一档必须**一张场景背景都没有**：有就说明索引把没判过的当判过了。
        # 反向对照放同一条里：「仅确认有角色」档必须只有 bg/ 一个目录（标注只覆盖它）。
        unk_dirs = d0b.get('unkDirs') if isinstance(d0b, dict) else None
        has_dirs = d0b.get('hasDirs') if isinstance(d0b, dict) else None
        say(bool(unk_dirs) and 'bg' not in unk_dirs,
            f"「未标注」档里没有场景背景（盘上目录: {unk_dirs}）")
        say(has_dirs == ['bg'], f"「仅确认有角色」档只出场景背景（目录: {has_dirs}）")

        print('== 0c) 搜索撞上筛选：结果为空时必须说"是被画面筛挡的"，不许说"库里没有" ==')
        hidden_name = next(i['name'] for i in META['items'] if i.get('has_char') == 0)
        d0c = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const q=document.getElementById('q');
          q.value='__NAME__'; q.dispatchEvent(new Event('input')); await t(900);
          const r={cards:document.querySelectorAll('.card').length,
                   empty:document.getElementById('empty').textContent,
                   emptyShown:document.getElementById('empty').style.display,
                   hint:document.getElementById('gHint').textContent};
          q.value=''; q.dispatchEvent(new Event('input')); await t(700);
          r.back=document.querySelectorAll('.card').length;
          /* 后面几组判据量的是"未筛画面"的原始口径（tier/group/词根各自多少张），
             所以这里把画面筛选解到「全部」，让它们测的东西和改动前一致 */
          [...document.querySelectorAll('#gChar .chip')].find(x=>x.textContent.startsWith('全部')).click();
          await t(900); r.all=r_back=document.querySelectorAll('.card').length;
          return r;
        })()""".replace('__NAME__', hidden_name))
        say(isinstance(d0c, dict) and d0c.get('cards') == 0
            and '画面' in str(d0c.get('empty', '')) and '画面' in str(d0c.get('hint', '')),
            f"搜「{hidden_name}」（判过=无角色）在默认视图下空了，但空态与常驻条都写明是被"
            f"「画面」筛挡的: empty={str(d0c.get('empty'))[:52]!r}")
        say(isinstance(d0c, dict) and d0c.get('back') == CH['has'] + CH['unlabeled']
            and d0c.get('all') == len(META['items']),
            f"清空搜索恢复 {d0c.get('back')} 张；解到「全部」后 {d0c.get('all')} 张 —— "
            f"后续判据在未筛画面的口径上跑")

        print('== 1) 图是不是真解出像素（不是"格子在、内容空"）==')
        d = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          for(let i=0;i<120 && !document.querySelector('.card');i++) await t(200);
          await t(1500);
          const imgs=[...document.querySelectorAll('.card img')];
          const inView=imgs.filter(i=>{const b=i.getBoundingClientRect();
            return b.top<innerHeight&&b.bottom>0&&b.width>0;});
          return {cards:document.querySelectorAll('.card').length,
                  vh:innerHeight, vw:innerWidth,
                  withSrc:imgs.filter(i=>i.getAttribute('src')).length,
                  decoded:imgs.filter(i=>i.complete&&i.naturalWidth>0).length,
                  inView:inView.length,
                  inViewDecoded:inView.filter(i=>i.complete&&i.naturalWidth>0).length,
                  zeroSize:imgs.filter(i=>i.complete&&i.naturalWidth===0).length,
                  miss:document.querySelectorAll('.card.miss').length,
                  sub:(document.getElementById('sub')||{}).textContent||''};
        })()""")
        if isinstance(d, dict) and '__err' in d:
            say(False, f"页面 JS 异常: {d['__err']}")
        else:
            say(d['vh'] > 400, f"浏览器视口有真实尺寸 {d['vw']}×{d['vh']}（0×0 时懒加载类判据全是假的）")
            say(d['cards'] == len(META['items']),
                f"卡片 {d['cards']} 张 == bg_meta.json 的 {len(META['items'])} 条")
            say(d['inView'] > 4 and d['inViewDecoded'] == d['inView'],
                f"视口内 {d['inView']} 张缩略图全部解出像素（decoded={d['inViewDecoded']}）"
                f"；全页已解码 {d['decoded']}")
            say(d['zeroSize'] == 0 and d['miss'] == 0,
                f"解出但 0 像素的图 {d['zeroSize']} 张 / 标了缺失的 {d['miss']} 张（都要 0）")
            say(d['sub'].count('/') == 1 and str(META['counts']['exact']) in d['sub'],
                f"计数条: {d['sub']}")

        print('== 2) 反向对照：故意请求不存在的缩略图，.miss 必须亮起来 ==')
        nc = ev(r"""(async()=>{
          const c=document.querySelector('.card');
          const im=c.querySelector('img'); const old=im.getAttribute('src');
          im.src='bg_thumbs/__no_such_file__.webp';
          await new Promise(r=>setTimeout(r,900));
          const lit=c.classList.contains('miss');
          im.src=old; c.classList.remove('miss');
          await new Promise(r=>setTimeout(r,700));
          return {lit, recovered:im.complete&&im.naturalWidth>0};
        })()""")
        say(isinstance(nc, dict) and nc.get('lit'), f"坏图会打标记（.miss={nc}）—— 上面那条 ✅ 不是空集给的绿")

        print('== 3) 三档命名各自显示对，且没有把排版串漏出来 ==')
        d3 = ev(r"""(()=>{
          const cards=[...document.querySelectorAll('.card')];
          const by={};
          for(const c of cards){const b=c.querySelector('.badge');(by[b.className.split(' ')[1]] ||= []).push(c);}
          const txt=c=>c.querySelector('.t1').textContent;
          const pick=k=>by[k]?by[k][0]:null;
          return {counts:Object.fromEntries(Object.entries(by).map(([k,v])=>[k,v.length])),
                  exact:txt(pick('exact')), inferred:txt(pick('inferred')), none:txt(pick('none')),
                  hasPipe:[...cards].filter(c=>txt(c).includes('||')).length,
                  emptyTitle:[...cards].filter(c=>!txt(c).trim()).length,
                  badgeText:[...document.querySelectorAll('.badge')].slice(0,3).map(x=>x.textContent)};
        })()""")
        say(isinstance(d3, dict) and d3.get('counts', {}).get('exact') == META['counts']['exact']
            and d3.get('counts', {}).get('none') == META['counts']['none'],
            f"三档卡片数与数据一致: {d3.get('counts') if isinstance(d3, dict) else d3}")
        say(isinstance(d3, dict) and d3.get('hasPipe') == 0,
            f"没有一张卡的标题漏出游戏排版串 `||`（{d3.get('hasPipe')} 张）")
        say(isinstance(d3, dict) and d3.get('emptyTitle') == 0,
            f"没有空标题卡片（{d3.get('emptyTitle')} 张）")
        say(isinstance(d3, dict) and any('\u4e00' <= ch <= '\u9fff' for ch in str(d3.get('exact', ''))),
            f"确定档示例: {d3.get('exact')!r} / 推断档: {d3.get('inferred')!r} / 类目说明档: {d3.get('none')!r}")

        print('== 3b) 图内烤字档：页面标题必须逐字等于发布表（不是 OCR 原文）==')
        TJ = json.load(open(os.path.join(P.ROOT, 'inputs', 'gamecfg', 'bg_tip_titles.json'), encoding='utf-8'))['titles']
        expect = {'bg/' + k: v['cn'] for k, v in TJ.items()}
        d3b = ev(r"""(()=>{
          const out={};
          for(const c of document.querySelectorAll('.card')){
            const b=c.querySelector('.badge');
            if((b.className||'').includes('baked')) out[c.dataset.k]=c.querySelector('.t1').textContent;
          }
          return out;
        })()""")
        say(isinstance(d3b, dict) and len(d3b) == len(expect),
            f"图内文字档卡片 {len(d3b) if isinstance(d3b, dict) else d3b} 张 == 发布表 {len(expect)} 条")
        diff = {k: (d3b.get(k), expect[k]) for k in expect if isinstance(d3b, dict) and d3b.get(k) != expect[k]}
        say(not diff, f"6 条标题逐字一致（不一致: {diff}）")
        say(isinstance(d3b, dict) and all('醺' in str(d3b.get('bg/bg_worldcruise_11_tip', '')) for _ in [0]),
            f"`_11` 用的是目视定稿「微醺的海风」而不是 OCR 残文「微的海风e」: "
            f"{d3b.get('bg/bg_worldcruise_11_tip') if isinstance(d3b, dict) else d3b}")

        print('== 3c) 筛「图内文字」只剩这 6 张，且详情层写明取证方式 ==')
        d3c = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          [...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='图内文字').click();
          await t(600);
          const cards=[...document.querySelectorAll('.card')];
          const n=cards.length;
          cards[0].click(); await t(2200);
          const r={n, first:cards[0].querySelector('.t1').textContent,
                   open:document.getElementById('ov').classList.contains('open'),
                   warn:document.getElementById('ovwarn').textContent,
                   kv:document.getElementById('ovkv').textContent,
                   ev:(document.getElementById('ovev').textContent||'')};
          document.getElementById('ovclose').click();
          [...document.querySelectorAll('#gTier .chip')][0].click(); await t(400);
          return r;
        })()""")
        say(isinstance(d3c, dict) and d3c.get('n') == len(expect), f"筛「图内文字」得 {d3c.get('n') if isinstance(d3c,dict) else d3c} 张")
        say(isinstance(d3c, dict) and '图内文字' in str(d3c.get('warn', ''))
            and '烤' in str(d3c.get('warn', '')),
            f"详情层写明这是第二条源: {str(d3c.get('warn'))[:56]!r}")
        # 上一版这里断言的字面串与页面文案不一致（页面写「图内文字」、判据找「图内烤字」）——
        # 判据自己写错也会造红。顺手补一条通用检查：**不许把 markdown 星号当富文本用**，
        # 详情层是 textContent，`**加粗**` 会原样出现在界面上。
        stars = ev(r"""(()=>{
          const t=[...document.querySelectorAll('.card .t1,.card .t2,#ovwarn,#ovkv,#ovev,.badge')]
            .map(e=>e.textContent).filter(x=>x.includes('**'));
          return t.slice(0,3);
        })()""")
        say(isinstance(stars, list) and not stars, f"界面上没有漏出的 markdown 星号: {stars}")
        say(isinstance(d3c, dict) and 'OCR 原文' in str(d3c.get('kv', '')),
            "详情层列出 OCR 原文/置信/重合度（改判时能查是谁改的）")
        say(isinstance(d3c, dict) and '图内烤字' in str(d3c.get('ev', '')),
            "出处区写的是取证方式，而不是伪造一条表引用")

        print('== 4) 筛选与搜索 ==')
        # ⚠️ 这页的 chip 是**单选组**（要回到不限就点「全部」那颗），不是"再点同一颗取消"的开关。
        # 上一版照抄音乐库 usage chip 的"再点一次取消"写法，把产品没错的行为打成了红。
        d4 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const N=()=>document.querySelectorAll('.card').length;
          const pick=(host,label)=>{const c=[...document.querySelectorAll('#'+host+' .chip')]
              .find(x=>x.textContent.startsWith(label)); c.click(); return c;};
          /* 二级下拉按 **value** 选，不按可见文本：词根的中文标签来自 series 猜测
             （star_level 那组现在显示的是「响彻于天穹之音」），按文本匹配会把"标签取错"
             误判成"筛选没生效"。 */
          const pickSub=(v)=>{const s=document.getElementById('gSubSel');
              const o=[...s.options].find(x=>x.value===v); if(!o)return null;
              s.value=v; s.dispatchEvent(new Event('change')); return o;};
          const n0=N();
          const groups=[...document.querySelectorAll('#gGroup .chip')].map(x=>x.textContent.trim());
          pick('gTier','确定'); await t(500); const n1=N();
          const on1=document.querySelector('#gTier .chip.on').textContent;
          pick('gTier','全部'); await t(500); const n1b=N();
          pick('gGroup','场景背景'); await t(600); const n2=N();
          const subShown=!document.getElementById('gSub').hidden;
          const optTxt=[...document.querySelectorAll('#gSubSel option')].map(o=>o.textContent);
          pickSub('star_level'); await t(600); const n2s=N();
          pick('gGroup','其他'); await t(600); const nOther=N();
          const subN=document.querySelectorAll('#gSubSel option').length;
          pickSub('helpbg'); await t(600); const nHelp=N();
          pick('gGroup','全部'); await t(500); const n2b=N();
          const q=document.getElementById('q'); q.value='起舞于天原之上';
          q.dispatchEvent(new Event('input')); await t(600);
          const n3=N(); const ft=document.querySelector('.card .t1').textContent;
          q.value=''; q.dispatchEvent(new Event('input')); await t(500);
          const n4=N();
          return {n0,n1,n1b,n2,n2s,nOther,nHelp,n2b,n3,n4,on1,ft,groups,subShown,subN,optTxt};
        })()""")
        say(isinstance(d4, dict) and d4.get('n1') == META['counts']['exact']
            and str(d4.get('on1', '')).startswith('确定'),
            f"筛「确定」得 {d4.get('n1')} 张，选中态停在「{d4.get('on1')}」")
        say(isinstance(d4, dict) and d4.get('n1b') == d4.get('n0'), f"点「全部」解开档位筛，恢复 {d4.get('n1b')} 张")
        # P1 折叠：一级只剩 3 组 + 全部，且 6 个子类目**不该**再出现在这一层
        say(isinstance(d4, dict) and len(d4.get('groups') or []) == 4
            and not any('帮助说明' in g or '通用底图' in g for g in d4.get('groups', [])),
            f"一级类目折叠成 {len(d4.get('groups') or [])} 个 chip：{d4.get('groups')!r}")
        # 交叉核对：`group` 字段是 GROUP_OF_DIR 映射出来的，`root_dir` 是盘上真目录 ——
        # 两条码路不同源，写歪归类映射时这条会红（只比"页面数 == 索引数"是抓不到的）
        indep = {'scene': 'bg', 'login': 'loadingbg'}
        for g, d0 in indep.items():
            n_g = META['groups'][g]['count']
            n_d = sum(1 for i in META['items']
                      if i['root_dir'] == d0 or (g == 'login' and i['root_dir'] == 'loadingbg_hx'))
            say(n_g == n_d, f"分组 {g} 的 {n_g} 张与按盘上目录数出的 {n_d} 张一致（归类映射没写歪）")
        say(isinstance(d4, dict) and d4.get('n2') == META['groups']['scene']['count'],
            f"筛一级「场景背景」得 {d4.get('n2')} 张")
        say(isinstance(d4, dict) and d4.get('subShown'), "选中场景背景后二级下拉出现（词根细分）")
        # 标签可信度分档必须**看得见**：series 传播档要带「（未核实）」，
        # 否则 star_level 那 265 张抽象底纹会顶着「响彻于天穹之音」冒充核实过的名字
        n_unver = len([1 for v in META['roots'].values() if v['cn_from'] == 'series'])
        n_mark = len([t for t in (d4.get('optTxt') or []) if '未核实' in t])
        say(n_mark == n_unver and n_mark > 0,
            f"下拉里 {n_mark} 项标了「未核实」== 索引 series 档 {n_unver} 组（没和核实过的混在一起）")
        say(any('（未核实）' not in t and any('一' <= ch <= '鿿' for ch in t)
                for t in (d4.get('optTxt') or [])[1:]),
            "下拉里存在不带标记的中文词根名（pinyin 档确实在生效）")
        say(isinstance(d4, dict) and d4.get('n2s') == META['roots']['star_level']['n'],
            f"下拉选词根 star_level 得 {d4.get('n2s')} 张（索引里该组 {META['roots']['star_level']['n']} 张）")
        say(isinstance(d4, dict) and d4.get('nOther') == META['groups']['other']['count'],
            f"一级「其他」折叠了 6 类共 {d4.get('nOther')} 张")
        say(isinstance(d4, dict) and d4.get('subN') == 7,
            f"「其他」的二级下拉有 {d4.get('subN')} 项（全部 + 6 子类目）")
        say(isinstance(d4, dict) and d4.get('nHelp') == META['dirs']['helpbg']['count'],
            f"下拉选「帮助说明底图」得 {d4.get('nHelp')} 张")
        say(isinstance(d4, dict) and d4.get('n2b') == d4.get('n0'), f"类目解开后恢复 {d4.get('n2b')} 张")
        say(isinstance(d4, dict) and 0 < d4.get('n3', 0) < d4.get('n0'),
            f"搜中文系列名「起舞于天原之上」得 {d4.get('n3')} 张，首张标题 {d4.get('ft')!r}")
        say(isinstance(d4, dict) and d4.get('n4') == d4.get('n0'), f"清空搜索后恢复 {d4.get('n4')} 张")

        # ===== 4b) P1 变体合并 + P4 全屏/下载 =====
        d4b = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const pick=(host,label)=>[...document.querySelectorAll('#'+host+' .chip')]
              .find(x=>x.textContent.startsWith(label));
          pick('gGroup','登录/加载').click(); await t(600);
          const hx=[...document.querySelectorAll('.card')].filter(c=>
              [...c.querySelectorAll('.badge')].some(b=>b.textContent==='和谐版'));
          const same=[...document.querySelectorAll('.card')].filter(c=>
              [...c.querySelectorAll('.badge')].some(b=>b.textContent==='同名另一张'));
          let srcDir='';
          if(hx.length){hx[0].click(); await t(700);
            /* 2026-10-13 kv 改版：长说明进 dd 的 title（CSS 给 dd[title] 画了虚下纹）⇒
               判据要读「可见值 + title」合并串；只读 textContent 会把挪进 title 的
               源目录出处误判成"抹掉来源" */
            srcDir=[...document.querySelectorAll('#ovkv dd')]
              .map(d=>d.textContent+' '+d.title).join(' '); }
          const ovOpen=document.getElementById('ov').classList.contains('open');
          document.getElementById('ovfs').click(); await t(900);
          const fs=document.getElementById('fs');
          const im=document.getElementById('fsimg');
          const fsOn=fs.classList.contains('on');
          const fsPx=im.naturalWidth;
          const dl=document.getElementById('ovdl');
          const dlHref=dl.getAttribute('href'), dlName=dl.getAttribute('download');
          let dlOk=false, dlBytes=0;
          try{const r=await fetch(dlHref); dlBytes=(await r.arrayBuffer()).byteLength; dlOk=r.ok;}catch(e){}
          document.getElementById('fsclose').click(); await t(400);
          const fsClosed=!fs.classList.contains('on') && !im.getAttribute('src');
          document.getElementById('ovclose').click(); await t(300);
          pick('gGroup','全部').click(); await t(400);
          return {hx:hx.length, same:same.length, ovOpen, srcDir, fsOn, fsPx,
                  dlHref, dlName, dlOk, dlBytes, fsClosed};
        })()""")
        # 此刻停在「登录/加载」筛选态，所以只能和**该组内**的 __N 条数比 ——
        # 拿全量条数比会把 bg 里那 1 张算进来，报出一条假红。
        n_hx = sum(1 for i in META['items'] if i.get('variant') == 'hx')
        n_same_login = sum(1 for i in META['items']
                           if i.get('same_name_of') and i.get('group') == 'login')
        n_same_all = sum(1 for i in META['items'] if i.get('same_name_of'))
        say(isinstance(d4b, dict) and d4b.get('hx') == n_hx,
            f"登录类目里 {d4b.get('hx')} 张带「和谐版」角标（索引里 _hx 去重后 {n_hx} 张）")
        say(isinstance(d4b, dict) and d4b.get('ovOpen') and 'loadingbg_hx' in str(d4b.get('srcDir')),
            "和谐版详情层的类目标了源目录 loadingbg_hx（并进一类目≠抹掉来源）")
        say(isinstance(d4b, dict) and d4b.get('same') == n_same_login,
            f"「同名另一张」角标 {d4b.get('same')} 张 == 登录组内 __N {n_same_login} 张"
            f"（全量 {n_same_all} 张，余下在场景背景组）")
        say(isinstance(d4b, dict) and d4b.get('fsOn') and d4b.get('fsPx', 0) > 0,
            f"全屏层打开且原图真解出像素 {d4b.get('fsPx')}px（不是只换了个 class）")
        say(isinstance(d4b, dict) and d4b.get('dlOk') and d4b.get('dlBytes', 0) > 10000
            and str(d4b.get('dlHref', '')).startswith('../Raw/'),
            f"下载链接真取得到原图 {d4b.get('dlBytes')} 字节 / 文件名 {d4b.get('dlName')!r}")
        say(isinstance(d4b, dict) and d4b.get('fsClosed'),
            "退出全屏后遮罩与 img 都清掉（反向对照：不退干净就是下一张串图）")

        print('== 5) 详情层：原图真解码 + 出处可回指 ==')
        d5 = ev(r"""(async()=>{
          const t=ms=>new Promise(r=>setTimeout(r,ms));
          const chips=[...document.querySelectorAll('#gTier .chip')];
          chips.find(c=>c.textContent==='确定').click(); await t(500);
          document.querySelector('.card').click(); await t(2500);
          const ov=document.getElementById('ov').classList.contains('open');
          const im=document.getElementById('ovimg');
          return {ov, name:document.getElementById('ovname').textContent,
            en:document.getElementById('oven').textContent,
            imgSrc:im.getAttribute('src'), decoded:im.complete&&im.naturalWidth>0,
            nat:im.naturalWidth+'x'+im.naturalHeight,
            /* 同 d4b：长说明在 dd 的 title 里，判据读「dt 标签 + 可见值 + title」合并串 */
            kv:document.getElementById('ovkv').textContent+' '+
               [...document.querySelectorAll('#ovkv dd')]
              .map(d=>d.textContent+' '+d.title).join(' '),
            ev:(document.getElementById('ovev').textContent||'').slice(0,180),
            warn:document.getElementById('ovwarn').textContent.slice(0,60),
            theme:getComputedStyle(document.documentElement).getPropertyValue('--brand').trim()};
        })()""")
        say(isinstance(d5, dict) and d5.get('ov'), f"点开详情层（{d5.get('name') if isinstance(d5, dict) else d5}）")
        say(isinstance(d5, dict) and d5.get('decoded'),
            f"原图真的解出像素: {d5.get('imgSrc')} → {d5.get('nat')}")
        say(isinstance(d5, dict) and '行' in str(d5.get('ev', ''))
            and ('activity_sp_story' in str(d5.get('ev')) or 'expedition_data_by_map' in str(d5.get('ev'))),
            f"出处可回指到表/字段/行: {str(d5.get('ev'))[:120]!r}")
        say(isinstance(d5, dict) and '确定' in str(d5.get('warn', '')),
            f"口径说明随档位换: {str(d5.get('warn'))[:40]!r}")
        say(isinstance(d5, dict) and '画面' in str(d5.get('kv', ''))
            and '标注' in str(d5.get('kv', '')),
            f"详情层写明「画面」档与其出处（不是文件名规则）: "
            f"{[x for x in str(d5.get('kv','')).split('画面')][1][:26]!r}")
        say(isinstance(d5, dict) and bool(d5.get('theme')), f"theme.css token 生效: --brand={d5.get('theme')!r}")

        print('== 6) 主页入口 + served 页面与磁盘正本一致（防"跑的是改动前的代码"）==')
        d6 = ev(r"""(async()=>{
          const r=await fetch('index.html',{cache:'no-store'}); const b=await r.text();
          const s=await (await fetch('backgrounds.html',{cache:'no-store'})).arrayBuffer();
          return {idx:r.status, hasBtn:b.includes("location.href='backgrounds.html'"),
                  servedBytes:s.byteLength};
        })()""")
        disk = os.path.getsize(os.path.join(ROOT, 'gallery_src', 'backgrounds.html'))
        say(isinstance(d6, dict) and d6.get('idx') == 200 and d6.get('hasBtn'),
            f"index.html 里有「背景库」入口按钮")
        # ⚠️ 量字节必须用 `arrayBuffer().byteLength`，不能用 `text().length`：后者是 UTF-16 单元数，
        # 中文一页里有几百个，会把"正本 17309 字节"读成 15569 —— 上一版就是这条自己造出的假红灯。
        served = d6.get('servedBytes') if isinstance(d6, dict) else -1
        say(served == disk, f"served {served} 字节 == 正本 {disk} 字节（不一致就是跑着旧副本）")

        print('== 7) 两套主题截图（交人看，不由脚本判审美）==')
        # 上一版拍的时候详情层还开着，网格图被浮层挡了一半；先关层、回顶，再拍
        ev("""(()=>{document.getElementById('ovclose').click();
              [...document.querySelectorAll('#gTier .chip')][0].click();
              scrollTo(0,0);return 1})()""")
        time.sleep(0.9)
        p1 = shot('light')
        say(os.path.getsize(p1) > 30000, f"昼：{p1}")
        p2 = shot('light_grid', '.grid')
        say(os.path.getsize(p2) > 20000, f"网格特写：{p2}")
        # 推断档与类目说明档各拍一张：这两档是"名字从别处继承/压根没有"，最需要人眼确认没吹牛
        ev("""(()=>{const c=[...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='推断');
              c.click();scrollTo(0,0);return 1})()""")
        time.sleep(1.0)
        p2b = shot('inferred')
        say(os.path.getsize(p2b) > 20000, f"推断档网格：{p2b}")
        ev("""(()=>{const c=[...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='图内文字');
              c.click();scrollTo(0,0);return 1})()""")
        time.sleep(1.0)
        p2a = shot('baked_tier')
        say(os.path.getsize(p2a) > 20000, f"图内文字档网格：{p2a}")
        ev("""(()=>{const c=[...document.querySelectorAll('#gTier .chip')].find(x=>x.textContent==='类目说明');
              c.click();scrollTo(0,0);return 1})()""")
        time.sleep(1.0)
        p2c = shot('none_tier')
        say(os.path.getsize(p2c) > 20000, f"类目说明档网格：{p2c}")
        ev("""(()=>{[...document.querySelectorAll('#gTier .chip')][0].click();
              document.querySelector('.card').click();return 1})()""")
        time.sleep(2.0)
        p3 = shot('sheet')
        say(os.path.getsize(p3) > 20000, f"详情层：{p3}")
        ev("""(()=>{document.getElementById('ovclose').click();
              document.querySelector('#gTheme [data-t=dark]').click();return 1})()""")
        time.sleep(1.0)
        p4 = shot('dark')
        say(os.path.getsize(p4) > 30000, f"夜：{p4}")

        print()
        if FAIL:
            print(f'[FAIL] {len(FAIL)} 条判据未过')
            return 1
        print('[PASS] 背景库页全部判据通过（截图 .diag/bg_shot_*.png，需人眼过一遍）')
        return 0
    finally:
        try:
            if ws:
                ws.close()
        except Exception:
            pass
        chrome_tree.kill_tree(proc.pid)
        if _httpd:
            _httpd.shutdown()
            _httpd.server_close()


if __name__ == '__main__':
    sys.exit(main())
