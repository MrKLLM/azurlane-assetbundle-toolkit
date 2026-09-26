# -*- coding: utf-8 -*-
"""量"附件的贴图区域到底画了多少非黑像素"——给取景判据做选型取证（只读）。

背景：`spine_framing_scan.py` 修掉了第一类（setup alpha=0 的巨幕，13/328）。还有第二类
**不透明的纯色黑底巨幕**（`heimu`/`1heidi`）：它 alpha=1、真的在渲染，"会不会落笔"对它无效，
于是照样把取景框撑大 2~6.8 倍（扫已导出 CG 得 12/234 受影响）。

本工具把每个 part **面积前 8 的附件**连同其贴图区域的像素统计一起打出来：
  ink      = 贴图区域里 alpha>8 的纹素占比
  nonBlack = 其中 max(r,g,b)>40 的占比（"画了非近黑的东西"）
  lum      = 落笔纹素的平均亮度 / p95 亮度
  colors   = 量化到 4bit/通道后的不同颜色数（判"是不是纯色板"）
拿 12 个阳性 + 若干阴性对照看这几列能不能分开，才决定判据写什么——
上一轮"沿所有动画采样曾 alpha>0"就是没做这一步才在阳性对照上翻车的。

用法:
  py -3 scripts/diag/spine_region_ink_scan.py --only aluomangshi_2,antu_3,2b_2
  py -3 scripts/diag/run_detached.py --log .diag/spine_ink_scan.log -- py -3 scripts/diag/spine_region_ink_scan.py
输出：stdout 每 part 一行 JSON（含 atts 数组），末尾 `SUMMARY {...}`。
前置：本地服务器 127.0.0.1:8777 在跑（脚本自带预检）。
"""
import sys, os, json, time, subprocess, urllib.request, argparse

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
SPINE_DIR = os.path.join(ROOT, 'Output', 'Spine_v2')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
PORT = 9352
RESTART_EVERY = 8        # 每个 part 会把 1~3 张整页（最多 16MB）读进内存，换页要勤
TOPN = 8
MAX_ANIMS = 6

JS = r"""
(async (folder, parts, TOPN) => {
  const t = ms => new Promise(r => setTimeout(r, ms));
  if (typeof loadScriptOnce === 'function') { try { await loadScriptOnce('./vendor/spine/spine-all.js'); } catch (e) {} }
  for (let i = 0; i < 60; i++) { if (typeof spine !== 'undefined' && spine.webgl) break; await t(500); }
  if (typeof spine === 'undefined') return JSON.stringify({err: 'spine 运行时未就绪'});

  const out = [];
  for (const part of parts) {
    const rec = {folder, part};
    const t0 = performance.now();
    const canvas = document.createElement('canvas');
    try {
      const base = '../Spine_v2/' + folder + '/';
      const sr = await fetch(base + part + '.skel'); if (!sr.ok) throw new Error('skel ' + sr.status);
      const bytes = new Uint8Array(await sr.arrayBuffer());
      const ar = await fetch(base + part + '.atlas'); if (!ar.ok) throw new Error('atlas ' + ar.status);
      const atlasTxt = await ar.text();
      const pageNames = [];
      for (const ln of atlasTxt.split('\n')) {
        const s2 = (ln || '').replace(/\r$/, '');
        if (/^[A-Za-z0-9_].*\.(png|jpg)$/i.test(s2) && !ln.startsWith(' ') && !ln.startsWith('\t') && !s2.includes(':')) pageNames.push(s2);
      }
      /* 真图片：page.width/height 由 spine 从 getImage() 取，必须是真实尺寸，
         否则后面按归一化 uv 反算页像素坐标会错。 */
      const imgs = {}, pageData = {};
      for (const pgn of pageNames) {
        const img = new Image(); img.crossOrigin = 'anonymous';
        await new Promise((rs, rj) => { img.onload = rs; img.onerror = () => rj(new Error('tex ' + pgn)); img.src = base + pgn; });
        imgs[pgn] = img;
      }
      const texImg = new Map();
      const texOf = pgn => { const o = { setFilters() {}, setWraps() {}, dispose() {}, getImage() { return imgs[pgn]; } };
                             texImg.set(o, imgs[pgn]); return o; };
      const atlas = new spine.TextureAtlas(atlasTxt, texOf);
      const ofind = atlas.findRegion.bind(atlas);
      atlas.findRegion = n => { let r = ofind(n); if (r) return r; const s2 = ('' + n).trim(); return s2 !== n ? ofind(s2) : r; };
      const data = bytes[0] === 0x7B
        ? new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(new TextDecoder().decode(bytes))
        : new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);

      /* 区域像素统计。**不做"整页读进内存"**：本项目页贴图常见 4096×4096，
         getImageData 一次 67MB、一个 part 4 页就 268MB。改成把区域**缩采到 ≤64×64** 再读（16KB）——
         纯色板/落笔比例这类统计量对缩采不敏感。
         ⚠️ 图片只能从 `page.texture.getImage()` 拿：`page.name` 存的是 atlas 里那一行原文（带路径），
         与自己解析出的裸文件名不相等，按名字回查会拿到 undefined（实测第一轮就是这么废的）。
         ⚠️ 旋转区域打包矩形里的 width/height 是互换的（`reg.degrees===90`）。 */
      const b2 = {c: null, ctx: null};
      /* ⚠️ 必须把 slot 颜色乘进来再统计：实测 `yunlong_3` 的黑幕是**白色贴图 × rgb=0,0,0 乘数**，
         只看贴图它 nonBlack=1、lum=255，完全不像黑底；而 `1heidi`/`heimu` 是黑色贴图 × 白乘数。
         两种都渲染成纯黑 → 判据只能建立在"乘完之后实际落笔的颜色"上。 */
      const regionStats = (reg, col) => {
        if (!reg || !reg.page) return null;
        const pg = reg.page;
        const img = pg.texture && pg.texture.getImage ? pg.texture.getImage() : null;
        if (!img || !img.width) throw new Error('页图片缺失 page.name=' + pg.name + ' pageKeys=' + Object.keys(pg).join(','));
        let sw = reg.width, sh = reg.height;
        if (reg.degrees === 90 || reg.rotate) { const t = sw; sw = sh; sh = t; }
        if (!(sw > 0 && sh > 0)) return {rw: sw || 0, rh: sh || 0, ink: 0, nonBlack: 0, lum: 0, p95: 0, colors: 0, samples: 0};
        const n = Math.min(64, Math.max(4, sw)), m = Math.min(64, Math.max(4, sh));
        if (!b2.ctx) { b2.c = document.createElement('canvas'); b2.c.width = 64; b2.c.height = 64;
                       b2.ctx = b2.c.getContext('2d', {willReadFrequently: true}); }
        b2.ctx.clearRect(0, 0, 64, 64);
        b2.ctx.drawImage(img, reg.x, reg.y, sw, sh, 0, 0, n, m);
        const px = b2.ctx.getImageData(0, 0, n, m).data;
        const cr = col ? col.r : 1, cg = col ? col.g : 1, cb = col ? col.b : 1, ca = col ? col.a : 1;
        let ink = 0, nonBlack = 0; const hist = new Set(); const lums = [];
        for (let i = 0; i < n * m; i++) {
          const o = i * 4;
          const A = px[o + 3] * ca;
          if (A <= 8) continue;
          ink++;
          const r = px[o] * cr, g = px[o + 1] * cg, b = px[o + 2] * cb;
          if (Math.max(r, g, b) > 40) nonBlack++;
          lums.push(0.299 * r + 0.587 * g + 0.114 * b);
          hist.add(((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4));
        }
        lums.sort((p, q) => p - q);
        return {rw: sw, rh: sh, ink: +(ink / (n * m)).toFixed(3),
                nonBlack: +(nonBlack / Math.max(1, ink)).toFixed(3),
                lum: +(lums.reduce((a, c) => a + c, 0) / Math.max(1, lums.length)).toFixed(1),
                p95: lums.length ? lums[Math.min(lums.length - 1, Math.floor(lums.length * 0.95))].toFixed(0) : 0,
                colors: hist.size, samples: n * m};
      };

      /* 与画廊同一套 skin 选择规则 */
      const skinNames = (data.skins || []).map(k => k.name);
      let animNames = (data.animations || []).map(a => (a && a.name !== undefined) ? a.name : String(a)).filter(Boolean).slice(0, __MAXAN__);
      const cover = (sk) => { const ever = new Set(); const asd = new spine.AnimationStateData(data);
        for (const an of (animNames.length ? animNames : [null])) {
          const s2 = new spine.Skeleton(data); const st = new spine.AnimationState(asd);
          try { if (sk !== null) s2.setSkin(data.findSkin(sk)); s2.setSlotsToSetupPose(); s2.setBonesToSetupPose();
            if (an) st.setAnimation(0, an, true);
            for (const dt of [0.05, 0.5, 2.0]) { st.update(dt); st.apply(s2);
              for (const sl of s2.slots) if (sl.getAttachment()) ever.add(sl.data.name); } } catch (e) {} }
        return ever.size; };
      let best = null, bestCov = cover(null);
      for (const sn of skinNames) { const c = cover(sn); if (c > bestCov) { bestCov = c; best = sn; } }

      const sk = new spine.Skeleton(data);
      if (best !== null) sk.setSkin(data.findSkin(best));
      sk.setSlotsToSetupPose(); sk.setBonesToSetupPose(); sk.updateWorldTransform();
      const rows = []; let r = [1e9, 1e9, -1e9, -1e9];
      for (const sl of sk.slots) {
        const a = sl.getAttachment(); if (!a || !sl.bone || !sl.bone.active) continue;
        if (sl.data.color && sl.data.color.a <= 0.001) continue;      // 第一类已由画廊修掉
        let v, c;
        try {
          if (a instanceof spine.RegionAttachment) { v = spine.Utils.newFloatArray(8); c = 8; a.computeWorldVertices(sl.bone, v, 0, 2); }
          else if (a instanceof spine.MeshAttachment && a.worldVerticesLength) { c = a.worldVerticesLength; v = spine.Utils.newFloatArray(c); a.computeWorldVertices(sl, 0, c, v, 0, 2); }
          else continue;
        } catch (e) { continue; }
        let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
        for (let j = 0; j < c; j += 2) { if (v[j] < x0) x0 = v[j]; if (v[j] > x1) x1 = v[j];
                                         if (v[j+1] < y0) y0 = v[j+1]; if (v[j+1] > y1) y1 = v[j+1]; }
        if (x0 < r[0]) r[0] = x0; if (x1 > r[2]) r[2] = x1;
        if (y0 < r[1]) r[1] = y0; if (y1 > r[3]) r[3] = y1;
        rows.push({slot: sl.data.name, reg: (a.name || ''), world: [Math.round(x1 - x0), Math.round(y1 - y0)],
                   col: sl.data.color ? [+sl.data.color.r.toFixed(2), +sl.data.color.g.toFixed(2),
                                         +sl.data.color.b.toFixed(2), +sl.data.color.a.toFixed(2)] : null,
                   area: Math.round((x1 - x0) * (y1 - y0))});
      }
      rows.sort((p, q) => q.area - p.area);
      /* 同一区域+同一乘数会被几十个附件复用，缓存掉 */
      const statCache = new Map();
      const statsOf = (att, col) => {
        const k = (att.region ? att.region.name : '') + '|' + (att.region ? att.region.index : 0) + '|' +
                  (col ? [col.r, col.g, col.b, col.a].join(',') : '-');
        if (!statCache.has(k)) statCache.set(k, regionStats(att.region, col));
        return statCache.get(k);
      };
      for (const row of rows.slice(0, TOPN)) {
        const s = sk.slots.find(x => x.data.name === row.slot);
        row.rs = statsOf(s.getAttachment(), s.data.color);
        delete row.area;
      }
      rec.skin = best; rec.nAtt = rows.length;
      rec.box = r[0] > r[2] ? null : r.map(Math.round);
      rec.atts = rows;
      /* 判据候选：排除"乘完 slot 颜色后落笔里没有非近黑像素"的附件，看取景框会缩多少 */
      let r2 = [1e9, 1e9, -1e9, -1e9], dropped = [];
      for (const s of sk.slots) {
        const a = s.getAttachment(); if (!a || !s.bone || !s.bone.active) continue;
        if (s.data.color && s.data.color.a <= 0.001) continue;
        const rs = statsOf(a, s.data.color); if (!rs || rs.nonBlack < __CUT__) { dropped.push(s.data.name); continue; }
        let v, c;
        try {
          if (a instanceof spine.RegionAttachment) { v = spine.Utils.newFloatArray(8); c = 8; a.computeWorldVertices(s.bone, v, 0, 2); }
          else if (a instanceof spine.MeshAttachment && a.worldVerticesLength) { c = a.worldVerticesLength; v = spine.Utils.newFloatArray(c); a.computeWorldVertices(s, 0, c, v, 0, 2); }
          else continue;
        } catch (e) { continue; }
        for (let j = 0; j < c; j += 2) { if (v[j] < r2[0]) r2[0] = v[j]; if (v[j] > r2[2]) r2[2] = v[j];
                                         if (v[j+1] < r2[1]) r2[1] = v[j+1]; if (v[j+1] > r2[3]) r2[3] = v[j+1]; }
      }
      if (r2[0] <= r2[2]) {
        rec.boxInk = r2.map(Math.round);
        rec.nDroppedInk = dropped.length;
        const A = (b) => b ? Math.max(1, (b[2] - b[0]) * (b[3] - b[1])) : 1;
        rec.gainInk = +Math.sqrt(A(rec.box) / A(rec.boxInk)).toFixed(2);
        if (rec.gainInk > 1.3) rec.droppedInk = dropped.slice(0, 12);
      }
      rec.ms = Math.round(performance.now() - t0);
    } catch (e) { rec.err = String(e && e.message || e).slice(0, 140); }
    canvas.width = 0; canvas.height = 0;
    out.push(rec);
  }
  return JSON.stringify(out);
})
"""


def preflight():
    for path in ('/gallery_v2/index.html', '/gallery_v2/vendor/spine/spine-all.js'):
        try:
            code = urllib.request.urlopen('http://127.0.0.1:8777' + path, timeout=10).getcode()
        except Exception as e:
            sys.exit(f'[x] 本地服务器 8777 无响应（{path}: {e}）—— 先起服务：\n'
                     f'    py -3 scripts/diag/run_detached.py --log .diag/gallery_server.log '
                     f'-- py -3 "Output/gallery_v2/_gallery_server.py"')
        if code != 200:
            sys.exit(f'[x] 8777 对 {path} 返回 {code}')
    print('[i] 8777 就绪', flush=True)


def spawn():
    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}', '--remote-allow-origins=*',
        f'--user-data-dir={os.path.join(ROOT, ".diag", "chrome_ink_scan")}',
        '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader',
        '--use-angle=swiftshader', '--js-flags=--max-old-space-size=4096', '--window-size=1280,900', BASE,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(120):
        try:
            for tab in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
                if 'gallery_v2' in tab.get('url', '') and tab.get('webSocketDebuggerUrl'):
                    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=600)
                    ws.settimeout(600); break
            if ws:
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        kill(proc); raise RuntimeError('CDP 未就绪')
    _id = [0]

    def ev(expr, awaitp=False):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': 'Runtime.evaluate',
                            'params': {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp}}))
        deadline = time.time() + 600
        while True:
            if time.time() > deadline:
                raise RuntimeError('eval 600s 无响应')
            m = json.loads(ws.recv())
            if m.get('id') == _id[0]:
                if 'error' in m:
                    raise RuntimeError(json.dumps(m['error'])[:200])
                r = m.get('result', {})
                if r.get('exceptionDetails'):
                    return 'EVALERR ' + str(r['exceptionDetails'].get('exception', {}).get('description'))[:200]
                return r.get('result', {}).get('value')

    for _ in range(240):
        if ev('String(typeof loadScriptOnce==="function")') == 'true':
            break
        time.sleep(0.5)
    return proc, ev, (lambda: ws.close())


def kill(proc):
    subprocess.call(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


DUMP = r"""
(async (folder, part) => {
  const t = ms => new Promise(r => setTimeout(r, ms));
  if (typeof loadScriptOnce === 'function') { try { await loadScriptOnce('./vendor/spine/spine-all.js'); } catch (e) {} }
  for (let i = 0; i < 60; i++) { if (typeof spine !== 'undefined' && spine.webgl) break; await t(500); }
  if (typeof spine === 'undefined') return 'spine 未就绪';
  const imgs = {};
  const base = '../Spine_v2/' + folder + '/';
  const bytes = new Uint8Array(await (await fetch(base + part + '.skel')).arrayBuffer());
  const atlasTxt = await (await fetch(base + part + '.atlas')).text();
  const pageNames = [];
  for (const ln of atlasTxt.split('\n')) {
    const s = (ln || '').replace(/\r$/, '');
    if (/^[A-Za-z0-9_].*\.(png|jpg)$/i.test(s) && !ln.startsWith(' ') && !ln.startsWith('\t') && !s.includes(':')) pageNames.push(s);
  }
  for (const pgn of pageNames) {
    const img = new Image(); img.crossOrigin = 'anonymous';
    await new Promise((rs, rj) => { img.onload = rs; img.onerror = () => rj(new Error('tex')); img.src = base + pgn; });
    imgs[pgn] = img;
  }
  const loader = p => ({ name: p, setFilters() {}, setWraps() {}, dispose() {}, getImage() { return imgs[p] || imgs[pageNames[0]]; } });
  const atlas = new spine.TextureAtlas(atlasTxt, loader);
  const data = bytes[0] === 0x7B
    ? new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(new TextDecoder().decode(bytes))
    : new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);
  const sk = new spine.Skeleton(data); sk.setSlotsToSetupPose(); sk.updateWorldTransform();
  const K = o => o === undefined ? 'undefined' : (o === null ? 'null' : (Array.isArray(o) ? 'Array(' + o.length + ')' : Object.keys(o).join(',')));
  const rows = [];
  for (const s of sk.slots) {
    const a = s.getAttachment(); if (!a) continue;
    rows.push({slot: s.data.name, attCtor: a.constructor.name, attKeys: K(a),
               regionCtor: a.region ? a.region.constructor.name : String(a.region),
               regionKeys: K(a.region),
               pageCtor: a.region && a.region.page ? a.region.page.constructor.name : String(a.region && a.region.page),
               pageKeys: K(a.region && a.region.page),
               pageTexture: K(a.region && a.region.page && a.region.page.texture),
               pageW: a.region && a.region.page && a.region.page.width,
               pageH: a.region && a.region.page && a.region.page.height,
               regXy: [a.region && a.region.x, a.region && a.region.y, a.region && a.region.width, a.region && a.region.height,
                       a.region && a.region.degrees, a.region && a.region.rotate],
               regUV: [a.region && a.region.u, a.region && a.region.v, a.region && a.region.u2, a.region && a.region.v2]});
  }
  return JSON.stringify({pages: pageNames, n: rows.length, first3: rows.slice(0, 3),
                         atlasCtor: atlas.pages && atlas.pages[0] ? atlas.pages[0].constructor.name : '?',
                         atlasPageKeys: atlas.pages && atlas.pages[0] ? K(atlas.pages[0]) : '-',
                         atlasPageTex: atlas.pages && atlas.pages[0] ? K(atlas.pages[0].texture) : '-'}, null, 1);
})
"""


def run_dump(folder, part):
    proc, ev, close_fn = spawn()
    try:
        raw = ev(f'({DUMP})({json.dumps(folder)}, {json.dumps(part)})', True)
        print(raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False))
    finally:
        close_fn(); kill(proc)


def main():
    preflight()
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='')
    ap.add_argument('--topn', type=int, default=TOPN)
    ap.add_argument('--dump', default='', help='只打一个 part 的运行时结构，定位 region/page 字段用')
    ap.add_argument('--cut', type=float, default=0.05, help='nonBlack 占比低于此值 → 判为纯色板，不参与取景')
    args = ap.parse_args()
    if args.dump:
        f = args.dump.rsplit('/', 1)
        run_dump(f[0] if len(f) == 2 else f[-1], f[-1])
        return
    folders = sorted(d for d in os.listdir(SPINE_DIR)
                     if os.path.isdir(os.path.join(SPINE_DIR, d))
                     and any(f.endswith('.skel') for f in os.listdir(os.path.join(SPINE_DIR, d))))
    if args.only:
        want = set(x.strip() for x in args.only.split(',') if x.strip())
        folders = [f for f in folders if f in want]
    if args.limit:
        folders = folders[:args.limit]
    print(f'[i] 待扫目录 {len(folders)} 个', flush=True)

    allrec, proc, ev, close_fn = [], None, None, None
    t0 = time.time()
    try:
        for idx, folder in enumerate(folders):
            parts = sorted(f[:-5] for f in os.listdir(os.path.join(SPINE_DIR, folder)) if f.endswith('.skel'))
            if proc is None or idx % RESTART_EVERY == 0:
                if proc:
                    close_fn(); kill(proc); time.sleep(1.0)
                proc, ev, close_fn = spawn()
                print(f'[i] Chrome #{idx // RESTART_EVERY + 1} 起（{time.time()-t0:.0f}s）', flush=True)
            js = JS.replace('__MAXAN__', str(MAX_ANIMS)).replace('__CUT__', str(args.cut))
            raw = ev(f'({js})({json.dumps(folder)}, {json.dumps(parts)}, {args.topn})', True)
            try:
                recs = json.loads(raw)
            except Exception:
                print(f'[!] {folder}: 不可解析 → {str(raw)[:160]}', flush=True); continue
            if isinstance(recs, dict):
                print(f'[!] {folder}: {recs}', flush=True); continue
            for r in recs:
                allrec.append(r); print(json.dumps(r, ensure_ascii=False), flush=True)
            print(f'[i] {idx+1}/{len(folders)} {folder} 用时{time.time()-t0:.0f}s', flush=True)
    finally:
        if proc:
            close_fn(); kill(proc)

    ok = [r for r in allrec if r.get('atts')]
    print('SUMMARY ' + json.dumps({
        'parts': len(allrec), 'measured': len(ok),
        'err': [(r.get('part'), r.get('err')) for r in allrec if r.get('err')][:20],
        'cut': args.cut,
        '排除纯色板后取景会缩>1.3倍': sorted([(r['part'], r.get('gainInk')) for r in ok
                                       if (r.get('gainInk') or 1) > 1.3], key=lambda x: -x[1]),
        '排除到包围盒为空(必须回退)': [r['part'] for r in ok if r.get('nAtt') and not r.get('boxInk')],
        '零误伤核对(对照应恒 1.0)': len([r for r in ok if (r.get('gainInk') or 1) > 1.05]),
    }, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
