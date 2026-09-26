# -*- coding: utf-8 -*-
"""Spine skin 影响面扫描（只读）：量化「画廊/CG 导出从不设 Spine skin」到底让多少部件画不出来。

背景：spine-ts 3.8 里，只有**当前 skin** 能提供动画所引用的附件
（`Skeleton.setAttachment` → `skin.getAttachment(slotIndex, name)`）。
`gallery_src/index.html` 与 `cg_export.html` 全程不调 `setSkin`，
于是凡把部件放进命名 skin 的骨架就整块不显示（2026-09-26 用户报阿罗芒什缺下半身即此）。

判据（可观测）：对每个 part，分别在「不设 skin」和「每个命名 skin」下，
把每条动画推进若干时刻，统计**曾经挂上附件的槽位数**。
`gain = best - none`，gain>0 即该 part 当前有部件画不出来。

用法（>8 分钟，务必走分离进程）:
  py -3 scripts/diag/run_detached.py --log .diag/spine_skin_scan.log -- py -3 scripts/diag/spine_skin_scan.py
  py -3 scripts/diag/spine_skin_scan.py --limit 5      # 小样本先看形状
输出：stdout 每 part 一行 JSON，末尾 `SUMMARY {...}` 一行。
"""
import sys, os, json, time, subprocess, urllib.request, argparse

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
SPINE_DIR = os.path.join(ROOT, 'Output', 'Spine_v2')
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'
PORT = 9348
MAX_ANIMS = 12          # 每条动画都跑满太贵；12 条足够覆盖附件时间线的并集（超限会记 animsCapped）
FRAMES = [0.03, 0.2, 0.5, 1.0, 2.0, 3.0]  # 每条动画推进这些时刻
RESTART_EVERY = 20      # 每 20 个目录换一个新 Chrome，防 SkeletonData 堆积

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
      rec.slots = data.slots.length; rec.bones = data.bones.length;
      rec.skinNames = skinNames; rec.anims = animNames.length; rec.bytes = bytes.length;
      const capped = animNames.length > __MAXAN__;
      if (capped) { rec.animsCapped = true; animNames = animNames.slice(0, __MAXAN__); }

      const FR = __FRAMES__;
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
        // ⚠️ 不要把"纯 setup pose"的并集也并进来：setup 附件走 slotData.attachmentName，
        // 与 skin 无关（实测 aluomangshi_2 每个 skin 都是 145），并进来会把 skin 之间的差值抹平，
        // 阳性对照当场翻车。只有在**一条动画都没有**时才退回 setup pose。
        if (!animNames.length) {
          const s = new spine.Skeleton(data);
          try { if (skinName !== null) s.setSkin(data.findSkin(skinName));
                s.setSlotsToSetupPose(); } catch (e) {}
          for (const sl of s.slots) if (sl.getAttachment()) ever.add(sl.data.name);
        }
        return ever;
      };
      const sets = {};
      sets['\u2205'] = cover(null);
      for (const sn of skinNames) sets[sn] = cover(sn);
      rec.cov = {}; for (const k in sets) rec.cov[k] = sets[k].size;
      let best = '\u2205';
      for (const k in sets) if (sets[k].size > sets[best].size) best = k;
      rec.best = best; rec.gain = sets[best].size - sets['\u2205'].size;
      if (rec.gain > 0) rec.gainedSlots = [...sets[best]].filter(x => !sets['\u2205'].has(x)).slice(0, 14);
      rec.ms = Math.round(performance.now() - t0);
    } catch (e) { rec.err = String(e && e.message || e).slice(0, 120); rec.ms = Math.round(performance.now() - t0); }
    out.push(rec);
  }
  return JSON.stringify(out);
})
"""


def spawn():
    proc = subprocess.Popen([
        CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
        '--remote-allow-origins=*', f'--user-data-dir={os.path.join(ROOT, ".diag", "chrome_spine_scan")}',
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
        proc.terminate()
        raise RuntimeError('CDP 未就绪')
    _id = [0]

    def cmd(method, params=None):
        _id[0] += 1
        ws.send(json.dumps({'id': _id[0], 'method': method, 'params': params or {}}))
        deadline = time.time() + 600
        while True:
            if time.time() > deadline:
                raise RuntimeError(f'{method} 600s 无匹配响应')
            try:
                m = json.loads(ws.recv())
            except websocket.WebSocketTimeoutException:
                raise RuntimeError(f'{method} recv 超时')
            if m.get('id') == _id[0]:
                if 'error' in m:
                    raise RuntimeError(json.dumps(m['error'])[:200])
                return m.get('result', {})
        return None

    def ev(expr, awaitp=False):
        r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
        if r.get('exceptionDetails'):
            return 'EVALERR ' + str(r['exceptionDetails'].get('exception', {}).get('description')
                                     or r['exceptionDetails'].get('text'))[:200]
        return r.get('result', {}).get('value')

    # 等页面就绪（GALLERY 由 index.js 赋值，函数在内联脚本后段）
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--only', default='', help='逗号分隔的目录名，跑阳性对照/复验用')
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
    proc = cmd = ev = close_fn = None
    t_start = time.time()
    for idx, folder in enumerate(folders):
        parts = sorted(f[:-5] for f in os.listdir(os.path.join(SPINE_DIR, folder)) if f.endswith('.skel'))
        if proc is None or idx % RESTART_EVERY == 0:
            if proc:
                close_fn()
                proc.terminate()
                time.sleep(1.0)
            proc, cmd, ev, close_fn = spawn()
            print(f'[i] Chrome #{idx // RESTART_EVERY + 1} 起（{time.time()-t_start:.0f}s）', flush=True)
        expr = f'({JS.replace("__MAXAN__", str(MAX_ANIMS)).replace("__FRAMES__", json.dumps(FRAMES))})({json.dumps(folder)}, {json.dumps(parts)})'
        try:
            raw = ev(expr, True)
        except Exception as e:
            raw = f'EVALERR driver {type(e).__name__}: {e}'
        if isinstance(raw, str) and raw.startswith('EVALERR'):
            print(json.dumps({'folder': folder, 'err': raw[:180]}, ensure_ascii=False), flush=True)
            allrec.append({'folder': folder, 'err': raw[:180]})
            close_fn(); proc.terminate(); proc = None   # 上下文可能被销毁，换新实例
            continue
        try:
            recs = json.loads(raw)
        except Exception as e:
            print(json.dumps({'folder': folder, 'err': f'解析 {e}'}, ensure_ascii=False), flush=True)
            close_fn(); proc.terminate(); proc = None
            continue
        if isinstance(recs, dict) and recs.get('err'):
            print(json.dumps({'folder': folder, 'err': recs['err']}, ensure_ascii=False), flush=True)
            close_fn(); proc.terminate(); proc = None
            continue
        for r in recs:
            print(json.dumps(r, ensure_ascii=False), flush=True)
            allrec.append(r)

    # 汇总
    ok = [r for r in allrec if 'cov' in r]
    aff = [r for r in ok if r.get('gain', 0) > 0]
    errs = [r for r in allrec if r.get('err')]
    summ = {
        'parts_total': len(allrec), 'parts_ok': len(ok), 'parts_err': len(errs),
        'parts_affected': len(aff),
        'affected_pct': round(100 * len(aff) / max(1, len(ok)), 1),
        'gain_sum_slots': sum(r.get('gain', 0) for r in aff),
        'gain_max': max([r.get('gain', 0) for r in aff] or [0]),
        'worst': sorted([{'p': r['folder'] + '/' + r['part'], 'gain': r['gain'],
                          'best': r['best'], 'none': r['cov'].get('\u2205')}
                         for r in aff], key=lambda x: -x['gain'])[:15],
        'no_skin_parts': len([r for r in ok if not r.get('skinNames')]),
        'elapsed_s': round(time.time() - t_start, 1),
    }
    print('SUMMARY ' + json.dumps(summ, ensure_ascii=False), flush=True)
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
