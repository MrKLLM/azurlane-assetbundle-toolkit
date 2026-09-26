# -*- coding: utf-8 -*-
"""探针：Spine 骨架在浏览器里到底画了哪些槽位——用于定位"缺下半身"这类整块丢失。

手法：用页面里已加载好的 spine 运行时（切到 Spine 标签后即存在）自己 fetch skel+atlas
建一份骨架，然后逐槽报告 setup 附件 / 当前附件 / 所属图集页 / 颜色 alpha / 骨骼 active。
不依赖画廊内部变量（spState 只存 {cancelled, raf}，拿不到 layers）。
"""
import sys, os, json, time, subprocess, urllib.request

sys.stdout.reconfigure(encoding='utf-8')
import websocket

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHROME = r'C:/Program Files/Google/Chrome/Application/chrome.exe'
PORT = 9345
DEBUG_DIR = os.path.join(ROOT, '.diag', 'chrome_spine_probe')
FOLDER = sys.argv[1] if len(sys.argv) > 1 else 'aluomangshi_2'
MATCH = sys.argv[2] if len(sys.argv) > 2 else 'datui'
BASE = 'http://127.0.0.1:8777/gallery_v2/index.html'

proc = subprocess.Popen([
    CHROME, '--headless=new', f'--remote-debugging-port={PORT}',
    '--remote-allow-origins=*', f'--user-data-dir={DEBUG_DIR}',
    '--no-first-run', '--no-default-browser-check', '--enable-unsafe-swiftshader',
    '--use-angle=swiftshader', '--window-size=1280,900', BASE,
], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

ws = None
for _ in range(80):
    try:
        for t in json.load(urllib.request.urlopen(f'http://127.0.0.1:{PORT}/json')):
            if t.get('webSocketDebuggerUrl'):
                ws = websocket.create_connection(t['webSocketDebuggerUrl'], timeout=300)
                ws.settimeout(300)
                break
        if ws: break
    except Exception:
        pass
    time.sleep(0.5)
else:
    raise SystemExit('CDP 未就绪')

_id = 0
def cmd(method, params=None):
    global _id
    _id += 1
    ws.send(json.dumps({'id': _id, 'method': method, 'params': params or {}}))
    deadline = time.time() + 300
    while True:
        if time.time() > deadline:
            raise RuntimeError(f'{method} 无响应（300s 内没等到匹配 id={_id} 的响应）')
        try:
            m = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            raise RuntimeError(f'{method} recv 超时')
        if m.get('id') == _id:
            if 'error' in m:
                if 'id' not in m:      # 无 id 的是事件通知（Execution context destroyed 等），继续等
                    continue
                raise RuntimeError(json.dumps(m['error'])[:200])
            return m.get('result', {})

def ev(expr, awaitp=False):
    r = cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True, 'awaitPromise': awaitp})
    if r.get('exceptionDetails'):
        return 'EVALERR ' + str(r['exceptionDetails'].get('exception', {}).get('description')
                                 or r['exceptionDetails'].get('text'))[:400]
    return r.get('result', {}).get('value')

cmd('Page.enable')
# 直接以 BASE 启动时，连上的第一个上下文会在文档提交时被销毁 → 先轮询到 evaluate 能稳定返回
for _ in range(120):
    try:
        if cmd('Runtime.evaluate', {'expression': '1', 'returnByValue': True})['result'].get('value') == 1:
            break
    except Exception:
        pass
    time.sleep(0.5)

JS = r"""
(async () => {
  const t = ms => new Promise(r => setTimeout(r, ms));
  for (let i = 0; i < 240; i++) { if (typeof GALLERY !== 'undefined' && Array.isArray(GALLERY.ships) && GALLERY.ships.length) break; await t(500); }
  // spine-all.js 是切到 Spine 标签才动态加载的，先走页面真实入口把它拉起来
  let ship = null, sk = null;
  for (const s of GALLERY.ships) { const k = s.skins.find(x => x.key === __FOLDER__);
    if (k && (k.spine || s.spineSkins && s.spineSkins.includes(__FOLDER__))) { ship = s; sk = k; break; } }
  if (sk) { openShip(ship); setSkin(sk); buildSkinList(ship); tab = 'spine'; renderView(); }
  for (let i = 0; i < 60; i++) { if (typeof spine !== 'undefined' && spine.webgl) break; await t(500); }
  if (typeof spine === 'undefined' || !spine.webgl) return JSON.stringify({err: 'spine 运行时未就绪', openedSkin: !!sk});
  const base = '../Spine_v2/' + __FOLDER__ + '/';
  const skelR = await fetch(base + __FOLDER__ + '.skel'); if (!skelR.ok) return 'skel 404';
  const bytes = new Uint8Array(await skelR.arrayBuffer());
  const atlasTxt = await (await fetch(base + __FOLDER__ + '.atlas')).text();

  // 区域名 -> 所属图集页（按 atlas 文本自己切页，不依赖运行时内部结构）
  const pageOf = {}, pages = [];
  let cur = null;
  for (const raw of atlasTxt.split('\n')) {
    const ln = raw.replace(/\r$/, '');
    if (!ln.trim()) continue;
    if (/^[A-Za-z0-9_].*\.(png|jpg)$/i.test(ln.trim()) && !raw.startsWith(' ') && !raw.startsWith('\t') && !ln.includes(':')) {
      cur = ln.trim(); pages.push(cur); pageOf[cur] = {}; continue;
    }
    if (cur && !raw.startsWith(' ') && !ln.includes(':')) pageOf[cur][ln.trim()] = 1;
  }
  const regionPage = {};
  for (const p in pageOf) for (const rg in pageOf[p]) regionPage[rg] = p;

  // 用 gallery 同款方式建 atlas（贴图这里不需要，只查结构）
  // 只查结构，不需要真贴图；但 loader 返回 null 会让 TextureAtlas.load 炸（它要 setFilters）
  const fakeTex = () => ({ setFilters() {}, setWraps() {}, dispose() {},
                           getImage() { return { width: 1, height: 1 }; } });
  const atlas = new spine.TextureAtlas(atlasTxt, fakeTex);
  const data = bytes[0] === 0x7B
    ? new spine.SkeletonJson(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(new TextDecoder().decode(bytes))
    : new spine.SkeletonBinary(new spine.AtlasAttachmentLoader(atlas)).readSkeletonData(bytes);

  const s = new spine.Skeleton(data);
  s.setSlotsToSetupPose(); s.setBonesToSetupPose();

  // 逐个 skin 设上、并把动画跑到若干时刻后数"有附件的槽位"。
  // 关键：skin 专属附件是在 AnimationState.apply 里经 Skeleton.setAttachment→skin.getAttachment
  // 才解析的，只做 setSlotsToSetupPose() 数出来必然偏少。
  const animNames = (data.animations || []).map(a => a && (a.name !== undefined ? a.name : String(a))).filter(Boolean);
  const skinNames = (data.skins || []).map(k => k.name);
  const sweep = [];
  for (const sk of [null, ...skinNames]) {
    for (const an of (animNames.length ? animNames.slice(0, 2) : [null])) {
      const t2 = new spine.Skeleton(data);
      const as = new spine.AnimationState(new spine.AnimationStateData(data));
      try {
        if (sk !== null) t2.setSkin(data.findSkin(sk));   // 必须传 Skin 对象，传字符串会炸
        t2.setSlotsToSetupPose(); t2.setBonesToSetupPose();
        if (an) { as.setAnimation(0, an, true); }
        for (const dt of [0.05, 0.5, 1.5, 3.0]) { as.update(dt); as.apply(t2); }
      } catch (e) { sweep.push({ skin: sk, anim: an, err: String(e).slice(0, 70) }); continue; }
      let withAtt = 0, datui = 0;
      for (const sl of t2.slots) {
        const a = sl.getAttachment();
        if (a) { withAtt++; const nm = (a.name || '') + '|' + (sl.data.name || '');
                 if (/datui/i.test(nm)) datui++; }
      }
      sweep.push({ skin: sk, anim: an, attached: withAtt, of: t2.slots.length, datuiAttached: datui });
    }
  }

  const hit = new RegExp(__MATCH__, 'i');
  const slots = [];
  for (const sl of s.slots) {
    const a = sl.getAttachment();
    const nm = a ? (a.name || a.path || '') : '';
    const parent = sl.data.name || '';
    if (!hit.test(nm) && !hit.test(parent)) continue;
    slots.push({slot: parent, setup: (sl.data.attachmentName || null),
                attach: nm || null, kind: a ? (a.constructor && a.constructor.name) : null,
                page: regionPage[nm] || regionPage[parent] || null,
                alpha: +(sl.data.color === undefined ? 1 : 1).toFixed(2),
                bone: sl.bone && sl.bone.data ? sl.bone.data.name : null,
                boneActive: sl.bone ? !!sl.bone.active : null,
                x: a && a.x !== undefined ? a.x : null, y: a && a.y !== undefined ? a.y : null,
                w: a && a.width ? a.width : null, h: a && a.height ? a.height : null});
  }
  const snap = (sk, an) => { const t2 = new spine.Skeleton(data); const m = {};
    try { if (sk !== null) t2.setSkin(data.findSkin(sk));
          t2.setSlotsToSetupPose(); t2.setBonesToSetupPose();
          const as = new spine.AnimationState(new spine.AnimationStateData(data));
          if (an) as.setAnimation(0, an, true);
          for (const dt of [0.05, 0.5, 1.5, 3.0]) { as.update(dt); as.apply(t2); } } catch (e) {}
    for (const sl of t2.slots) { const a = sl.getAttachment(); m[sl.data.name] = a ? (a.name || '<?>') : null; }
    return m; };
  const AN = animNames.includes('normal') ? 'normal' : (animNames[0] || null);
  const snapNull = snap(null, AN), snapS1 = snap(skinNames.includes('1') ? '1' : skinNames[0], AN);
  const gained = Object.keys(snapS1).filter(k => !snapNull[k] && snapS1[k]).map(k => k + ' -> ' + snapS1[k]);
  const datuiRows = Object.keys(snapS1).filter(k => /datui/i.test(k))
      .map(k => ({ slot: k, none: snapNull[k], skin: snapS1[k] }));

  return JSON.stringify({
    totalSlots: s.slots.length, totalBones: s.bones.length,
    pages: pages, skins: (data.skins || []).map(k => k.name),
    skinSweep: sweep, animNames: animNames, skinNames: skinNames, usedAnim: AN,
    gainedCount: gained.length, gained: gained.slice(0, 30),
    datuiRows: datuiRows,
    matched: slots.length, slots: slots.slice(0, 40)
  });
})()
""".replace('__FOLDER__', json.dumps(FOLDER)).replace('__MATCH__', json.dumps(MATCH))

print(ev(JS, True))
ws.close(); proc.terminate()
