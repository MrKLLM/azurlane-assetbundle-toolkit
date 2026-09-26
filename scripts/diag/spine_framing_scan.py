# -*- coding: utf-8 -*-
"""Spine 取景影响面扫描（只读）：量化「恒不渲染的巨幕把包围盒撑爆」波及多少 part。

背景：画廊弹窗的 `fit()` 用顶点包围盒取景（`boundsOf` 只看"槽位挂了附件"，
不看这个附件**是否会被画出来**）。实测三类把包围盒撑大的部件：
  - `siwanshi_4` 的 `hei`/`bai`/`k`/`wlk`：21879×18909 单位，setup 与整条 21s 动画
    的 41 个采样点上 **alpha 恒为 0** → 一个像素都不画，却把取景撑到全屏 → 画面只剩中间 1.2%。
  - `fage_2` 的 `Layer 267`：32967×29970，同样恒 alpha 0 → 2.3%。
  - `aluomangshi_2` 的 `hei2`：只在 12/41 个采样点可见（瞬时闪黑），`hei1` 恒 0。

判据（可观测）：对每个 part，先按画廊的规则选出覆盖最多的 skin，再算三个包围盒：
  boxAll   = 当前行为（setup pose 下所有挂了附件的槽位）
  boxSetup = 同上，但排除 **setup 时刻 alpha≤0.001** 的槽位（= 此刻根本不渲染）
  boxEver  = 同上，但排除"沿**所有**动画采样 alpha 恒≤0.001"的槽位（= 从来没亮过）
`gain = sqrt(areaAll/area)` = 修好后画面能放大多少倍（1.0 即不受影响）。
⚠️ ever 版在阳性对照上会漏（`siwanshi_4` gain=1.0）：闪黑幕只要在某条特殊动画里亮一下
   就算"曾可见"，而弹窗取景发生在 setup 时刻 —— 取景判据必须与"取景那一刻是否渲染"一致。

用法（>8 分钟，务必走分离进程）:
  py -3 scripts/diag/run_detached.py --log .diag/spine_framing_scan.log -- py -3 scripts/diag/spine_framing_scan.py
  py -3 scripts/diag/spine_framing_scan.py --limit 5      # 小样本先看形状
  py -3 scripts/diag/spine_framing_scan.py --only siwanshi_4,fage_2,2b_2   # 阳性对照 + 阴性对照
输出：stdout 每 part 一行 JSON，末尾 `SUMMARY {...}` 一行。
"""
import sys, os, json, time, subprocess, urllib.request, argparse

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
SPINE_DIR = os.path.join(ROOT, 'Output', 'Spine_v2')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
PORT = 9351
MAX_ANIMS = 12
FRAMES = [0.03, 0.2, 0.5, 1.0, 2.0, 3.0]
RESTART_EVERY = 20
ALPHA_EPS = 0.001

JS = r"""
(async (folder, parts) => {
  const t = ms => new Promise(r => setTimeout(r, ms));
  if (typeof loadScriptOnce === 'function') {
    try { await loadScriptOnce('./vendor/spine/spine-all.js'); } catch (e) {}
  }
  for (let i = 0; i < 60; i++) { if (typeof spine !== 'undefined' && spine.webgl) break; await t(500); }
  if (typeof spine === 'undefined') return JSON.stringify({err: 'spine 运行时未就绪'});

  const fakeTex = () => ({ setFilters() {}, setWraps() {}, dispose() {},
                           getImage() { return { width: 1, height: 1 }; } });
  const EPS = __EPS__;
  const out = [];
  for (const part of parts) {
    const rec = {folder, part};
    const t0 = performance.now();
    try {
      const base = '../Spine_v2/' + folder + '/';
      const sr = await fetch(base + part + '.skel'); if (!sr.ok) throw new Error('skel ' + sr.status);
      const bytes = new Uint8Array(await sr.arrayBuffer());
      const ar = await fetch(base + part + '.atlas'); if (!ar.ok) throw new Error('atlas ' + ar.status);
      const atlas = new spine.TextureAtlas(await ar.text(), fakeTex);
      const data = bytes[0] === 0x7B
        ? new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(new TextDecoder().decode(bytes))
        : new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);

      const skinNames = (data.skins || []).map(k => k.name);
      let animNames = (data.animations || []).map(a => (a && a.name !== undefined) ? a.name : String(a)).filter(Boolean);
      const capped = animNames.length > __MAXAN__;
      if (capped) { rec.animsCapped = true; animNames = animNames.slice(0, __MAXAN__); }
      const FR = __FRAMES__;

      /* 与画廊 loadPart 同一套 skin 选择规则：推进动画后"曾挂上附件"的槽位数最多者 */
      const cover = (skinName) => {
        const ever = new Set();
        const asd = new spine.AnimationStateData(data);
        for (const an of (animNames.length ? animNames : [null])) {
          const s = new spine.Skeleton(data); const st = new spine.AnimationState(asd);
          try {
            if (skinName !== null) s.setSkin(data.findSkin(skinName));
            s.setSlotsToSetupPose(); s.setBonesToSetupPose();
            if (an) st.setAnimation(0, an, true);
            for (const dt of FR) { st.update(dt); st.apply(s);
              for (const sl of s.slots) if (sl.getAttachment()) ever.add(sl.data.name); }
          } catch (e) { rec.applyErr = String(e).slice(0, 90); }
        }
        if (!animNames.length) {
          const s = new spine.Skeleton(data);
          try { if (skinName !== null) s.setSkin(data.findSkin(skinName)); s.setSlotsToSetupPose(); } catch (e) {}
          for (const sl of s.slots) if (sl.getAttachment()) ever.add(sl.data.name);
        }
        return ever;
      };
      let best = null, bestCov = cover(null).size;
      for (const sn of skinNames) { const c = cover(sn).size; if (c > bestCov) { bestCov = c; best = sn; } }
      rec.skin = best;

      /* 槽位可见性两版：setup 时刻的 alpha、以及沿所有动画采样的最大 alpha */
      const aSetup = {}, aEver = {};
      {
        const s0 = new spine.Skeleton(data);
        if (best !== null) s0.setSkin(data.findSkin(best));
        s0.setSlotsToSetupPose(); s0.setBonesToSetupPose();
        for (const sl of s0.slots) { const a = sl.color ? sl.color.a : 1; aSetup[sl.data.name] = a; aEver[sl.data.name] = a; }
      }
      const asd = new spine.AnimationStateData(data);
      for (const an of animNames) {
        const s = new spine.Skeleton(data); const st = new spine.AnimationState(asd);
        if (best !== null) s.setSkin(data.findSkin(best));
        s.setSlotsToSetupPose(); s.setBonesToSetupPose();
        try {
          st.setAnimation(0, an, true);
          for (const dt of FR) { st.update(dt); st.apply(s);
            for (const sl of s.slots) { const a = sl.color ? sl.color.a : 1;
              if (a > aEver[sl.data.name]) aEver[sl.data.name] = a; } }
        } catch (e) {}
      }

      /* 三个包围盒：当前行为 / 排除 setup 不可见 / 排除"任何动画里都没亮过" */
      const sk = new spine.Skeleton(data);
      if (best !== null) sk.setSkin(data.findSkin(best));
      sk.setSlotsToSetupPose(); sk.setBonesToSetupPose(); sk.updateWorldTransform();
      const box = (mode) => {
        let r = [1e9, 1e9, -1e9, -1e9], n = 0, dom = null, domArea = -1;
        const rows = [];
        const tbl = mode === 'setup' ? aSetup : aEver;
        for (const sl of sk.slots) {
          const a = sl.getAttachment(); if (!a || !sl.bone || !sl.bone.active) continue;
          const ma = tbl[sl.data.name] === undefined ? 1 : tbl[sl.data.name];
          if (mode !== 'all' && ma <= EPS) continue;
          let v, c;
          try {
            if (a instanceof spine.RegionAttachment) { v = spine.Utils.newFloatArray(8); c = 8; a.computeWorldVertices(sl.bone, v, 0, 2); }
            else if (a instanceof spine.MeshAttachment && a.worldVerticesLength) { c = a.worldVerticesLength; v = spine.Utils.newFloatArray(c); a.computeWorldVertices(sl, 0, c, v, 0, 2); }
            else continue;
          } catch (e) { continue; }
          let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9;
          for (let j = 0; j < c; j += 2) { if (v[j] < x0) x0 = v[j]; if (v[j] > x1) x1 = v[j];
                                           if (v[j+1] < y0) y0 = v[j+1]; if (v[j+1] > y1) y1 = v[j+1]; }
          n++;
          const area = (x1 - x0) * (y1 - y0);
          if (area > domArea) { domArea = area; dom = sl.data.name; }
          rows.push({slot: sl.data.name, w: Math.round(x1 - x0), h: Math.round(y1 - y0),
                     sa: +(aSetup[sl.data.name] || 0).toFixed(2), ea: +ma.toFixed(2),
                     c: sl.data.color ? [sl.data.color.r, sl.data.color.g, sl.data.color.b].map(v => +v.toFixed(2)) : null,
                     area: Math.round(area)});
          if (x0 < r[0]) r[0] = x0; if (x1 > r[2]) r[2] = x1;
          if (y0 < r[1]) r[1] = y0; if (y1 > r[3]) r[3] = y1;
        }
        if (r[0] > r[2]) return {n: 0, box: null, dom: null, top: []};
        rows.sort((p, q) => q.area - p.area);
        return {n, box: r.map(Math.round), dom, top: rows.slice(0, 4)};
      };
      const A = box('all'), S = box('setup'), E = box('ever');
      if (!A.box && A.n) throw new Error('包围盒计算失败');
      rec.slots = data.slots.length; rec.anims = animNames.length; rec.bytes = bytes.length;
      rec.nAll = A.n; rec.nSetup = S.n; rec.nEver = E.n;
      rec.boxAll = A.box; rec.boxSetup = S.box; rec.boxEver = E.box;
      const area = (b) => b ? Math.max(1, (b[2] - b[0]) * (b[3] - b[1])) : 0;
      const gain = (b) => +Math.sqrt(area(A.box) / Math.max(1, area(b))).toFixed(2);
      /* 美术在 Spine 编辑器里声明的舞台边界（setup image bounds）——候选的取景权威依据 */
      rec.sb = [data.x, data.y, data.width, data.height].map(Math.round);
      rec.gainSb = (data.width > 0 && data.height > 0)
        ? +Math.sqrt(area(A.box) / Math.max(1, data.width * data.height)).toFixed(2) : null;
      rec.gainSetup = S.box ? gain(S.box) : null;
      rec.gainEver = E.box ? gain(E.box) : null;
      rec.dropSetup = A.n - S.n; rec.dropEver = A.n - E.n;
      rec.dropped = A.top.filter(r => r.sa <= EPS)
        .map(r => r.slot + '(' + r.w + 'x' + r.h + ',setup' + r.sa + '/ever' + r.ea + ')');
      /* 面积前三的附件及其 setup 颜色：判断"纯黑乘数巨幕"能否确定性排除 */
      rec.big = A.top.slice(0, 3).map(r => r.slot + ' ' + r.w + 'x' + r.h + ' rgb=' + (r.c ? r.c.join(',') : '?') + ' a=' + r.sa);
      rec.ms = Math.round(performance.now() - t0);
    } catch (e) { rec.err = String(e && e.message || e).slice(0, 140); rec.ms = Math.round(performance.now() - t0); }
    out.push(rec);
  }
  return JSON.stringify(out);
})
"""


def spawn():
    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
        '--remote-allow-origins=*',
        f'--user-data-dir={os.path.join(ROOT, ".diag", "chrome_framing_scan")}',
        '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader',
        '--use-angle=swiftshader', '--js-flags=--max-old-space-size=4096',
        '--window-size=1280,900', BASE,
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    ws = None
    for _ in range(120):
        try:
            for tab in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
                if 'gallery_v2' in tab.get('url', '') and tab.get('webSocketDebuggerUrl'):
                    ws = websocket.create_connection(tab['webSocketDebuggerUrl'], timeout=600)
                    ws.settimeout(600)
                    break
            if ws:
                break
        except Exception:
            pass
        time.sleep(0.5)
    if not ws:
        subprocess.call(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise RuntimeError('CDP 未就绪')
    _id = [0]

    def cmd(method, params=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params or {}}))
        deadline = time.time() + 600
        while True:
            if time.time() > deadline:
                raise RuntimeError(f'{method} 600s 无匹配响应')
            m = json.loads(ws.recv())
            if m.get('id') == _id[0]:
                if 'error' in m:
                    raise RuntimeError(json.dumps(m['error'])[:200])
                return m.get('result', {})

    def ev(expr, awaitp=False):
        r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
        if r.get('exceptionDetails'):
            return 'EVALERR ' + str(r['exceptionDetails'].get('exception', {}).get('description')
                                     or r['exceptionDetails'].get('text'))[:200]
        return r.get('result', {}).get('value')

    for _ in range(240):
        if ev('String(typeof loadScriptOnce==="function")') == 'true':
            break
        time.sleep(0.5)

    def close():
        try:
            ws.close()
        except Exception:
            pass
    return proc, cmd, ev, close


def kill(proc):
    subprocess.call(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def preflight():
    """8777 会静默死掉（无 traceback）。服务器没了这个扫描会对着空页面刷几百行
    "spine 运行时未就绪"，看着像扫描的 bug。开跑前先确认它活着。"""
    for path in ('/gallery_v2/index.html', '/gallery_v2/vendor/spine/spine-all.js'):
        try:
            code = urllib.request.urlopen('http://127.0.0.1:8777' + path, timeout=10).getcode()
        except Exception as e:
            sys.exit(f'[x] 本地服务器 8777 无响应（{path}: {e}）—— 先起服务：\n'
                     f'    py -3 scripts/diag/run_detached.py --log .diag/gallery_server.log '
                     f'-- py -3 "Output/gallery_v2/_gallery_server.py"')
        if code != 200:
            sys.exit(f'[x] 8777 对 {path} 返回 {code}，不是 200 —— 先修服务器再扫')
    print('[i] 8777 就绪', flush=True)


def main():
    preflight()
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='', help='逗号分隔目录名（阳性/阴性对照）')
    args = ap.parse_args()

    folders = sorted(d for d in os.listdir(SPINE_DIR)
                     if os.path.isdir(os.path.join(SPINE_DIR, d))
                     and any(f.endswith('.skel') for f in os.listdir(os.path.join(SPINE_DIR, d))))
    if args.only:
        want = set(x.strip() for x in args.only.split(',') if x.strip())
        folders = [f for f in folders if f in want]
    if args.limit:
        folders = folders[:args.limit]
    print(f'[i] 待扫目录 {len(folders)} 个', flush=True)

    allrec = []
    proc = ev = close_fn = None
    t_start = time.time()
    try:
        for idx, folder in enumerate(folders):
            parts = sorted(f[:-5] for f in os.listdir(os.path.join(SPINE_DIR, folder)) if f.endswith('.skel'))
            if proc is None or idx % RESTART_EVERY == 0:
                if proc:
                    close_fn(); kill(proc); time.sleep(1.0)
                proc, _c, ev, close_fn = spawn()
                print(f'[i] Chrome #{idx // RESTART_EVERY + 1} 起（{time.time()-t_start:.0f}s）', flush=True)
            js = (JS.replace('__MAXAN__', str(MAX_ANIMS)).replace('__FRAMES__', json.dumps(FRAMES))
                    .replace('__EPS__', str(ALPHA_EPS)))
            raw = ev(f'({js})({json.dumps(folder)}, {json.dumps(parts)})', True)
            try:
                recs = json.loads(raw)
            except Exception:
                print(f'[!] {folder}: 返回不可解析 → {str(raw)[:160]}', flush=True)
                continue
            if isinstance(recs, dict):
                if recs.get('err', '').startswith('spine 运行时'):
                    dead += 1
                    if dead >= 3:
                        sys.exit(f'[x] 连续 {dead} 个目录拿不到 spine 运行时 —— 8777 多半又静默死了，'
                                 f'已中止（避免刷出几百行假故障）')
                print(f'[!] {folder}: {recs}', flush=True)
                continue
            dead = 0
            for r in recs:
                allrec.append(r)
                print(json.dumps(r, ensure_ascii=False), flush=True)
            print(f'[i] {idx+1}/{len(folders)} {folder} 累计{len(allrec)} part 用时{time.time()-t_start:.0f}s', flush=True)
    finally:
        if proc:
            close_fn(); kill(proc)

    ok = [r for r in allrec if 'gainSetup' in r]
    err = [r for r in allrec if 'err' in r]
    cnt = lambda key, th: len([r for r in ok if (r.get(key) or 0) > th])
    worst = sorted([r for r in ok if (r.get('gainSetup') or 0) > 1.05],
                   key=lambda x: -x['gainSetup'])[:20]
    print('SUMMARY ' + json.dumps({
        'parts': len(allrec), 'measured': len(ok), 'err': len(err),
        'setup规则 affected(>1.05x)': cnt('gainSetup', 1.05),
        'setup规则 affected(>1.5x)': cnt('gainSetup', 1.5),
        'setup规则 affected(>3x)': cnt('gainSetup', 3),
        'ever规则 affected(>1.05x)': cnt('gainEver', 1.05),
        '两规则不一致(>1.05x 只差一个)': len([r for r in ok
                                            if ((r.get('gainSetup') or 0) > 1.05) != ((r.get('gainEver') or 0) > 1.05)]),
        'maxGainSetup': max([r['gainSetup'] or 0 for r in ok], default=0),
        'worst': [{'k': r['part'], 'setup': r['gainSetup'], 'ever': r['gainEver'],
                   'dropSetup': r.get('dropSetup'), 'boxAll': r.get('boxAll'),
                   'boxSetup': r.get('boxSetup'), 'dropped': r.get('dropped')} for r in worst],
        'errList': [(r.get('part'), r.get('err')) for r in err][:20],
    }, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
