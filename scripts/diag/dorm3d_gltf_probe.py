# -*- coding: utf-8 -*-
"""3D 宿舍 step 5 通路验收：dorm3d 蒙皮 GLB 进 three.js，用**两条独立来源的数值**判姿势与蒙皮，
再拍图交人目视。

为什么不写"加载没报错就算过"：three.js 报绿只能证明文件解析了，证明不了骨骼、权重、bind 矩阵
三者互相自洽。所以这里量两件不同来源的事：

1. **几何包围盒**（three.js `geometry.boundingBox`）vs Unity 网格里的 `m_LocalAABB`
   —— 一个是前端运行时算的，一个是源包 TypeTree 里的原始字段，逐轴比。对不上就是顶点数据搬错了。
2. **静止态蒙皮结果**（页面里**用 CPU 逐顶点重算** `Σ w·(bone.matrixWorld ∘ boneInverse)·v`
   再取包围盒）vs 同一个 `m_LocalAABB`。
   这条才是蒙皮的直接证据：骨骼在自己的层变换上、bind 矩阵正确时，蒙皮结果就该**等于绑定姿态**；
   bind 矩阵只要错（比如该共轭没共轭、该转置没转置），静止态就会把模型扯开，这个盒子立刻失衡。
   ⚠️ 不能用 `Box3.setFromObject(skinnedMesh)` 代替——它走 `geometry.boundingBox`，
   **根本不经过蒙皮**，蒙皮炸了它也不动，是条恒真判据。

反向对照三条（每条都要真的红，否则上面的 ✅ 不算数）：
  A. 故意把权重字节改坏的 glb ⇒ 第 2 条必须红；
  B. `--transpose-ibm` 版本 ⇒ 记录它是否让第 2 条变红（不变红就说明这个开关测不出这一维，如实报）；
  C. 请求一个不存在的 glb ⇒ harness 必须报 miss（证明"加载成功"这一判据不是白给的）。

    py -3 scripts/diag/dorm3d_gltf_probe.py                 # 全跑（含两张对照产物）
    py -3 scripts/diag/dorm3d_gltf_probe.py --keep-open      # 不关浏览器，人工看

产物与截图都落在 `.diag/dorm3d_gltf/`（临时区，未进 `Output/`）。
退出码 0 = 全部判据通过；1 = 有判据红；2 = 环境起不来（浏览器/服务器/文件缺失）。
"""
import argparse
import json
import os
import struct
import subprocess
import sys
import threading
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'gallery_src'))

import UnityPy                                   # noqa: E402
import cdp_slot                                  # noqa: E402
import chrome_tree                               # noqa: E402
import paths as P                                # noqa: E402
import _gallery_server as GS                     # noqa: E402

UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

CHAR = os.path.join('files', 'AssetBundles', 'dorm3d', 'character', 'tianlangxing_db')
RES = os.path.join(ROOT, CHAR, 'res', 'tianlangxing_noshoes')
PREFAB = os.path.join(ROOT, CHAR, 'prefabs', 'tianlangxing_noshoes')
WORK = os.path.join(ROOT, '.diag', 'dorm3d_gltf')
CHROME = P.tool('AL_CHROME', 'chrome', r'C:/Program Files/Google/Chrome/Application/chrome.exe',
                r'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
PORT, PROFILE = cdp_slot.slot(ROOT, 'd3dglb')
FAIL = []


def say(cond, msg):
    print(('  PASS  ' if cond else '  FAIL  ') + msg)
    if not cond:
        FAIL.append(msg)


def unity_truth():
    """从**源包**取每个网格的 m_LocalAABB 与三角数（与前端那条路完全独立）。"""
    env = UnityPy.load(RES)
    out = {}
    for o in env.objects:
        if o.type.name != 'Mesh':
            continue
        m = o.read()
        bb = m.m_LocalAABB
        c, ex = bb.m_Center, bb.m_Extent
        idx = bytes(m.m_IndexBuffer or b"")
        nv = m.m_VertexData.m_VertexCount
        tris = None
        for w, code in ((2, 'H'), (4, 'I')):
            if len(idx) % w:
                continue
            cnt = len(idx) // w
            if cnt % 3:
                continue
            ii = list(struct.unpack('<%d%s' % (cnt, code), idx))
            if ii and max(ii) < nv:
                tris = cnt // 3
                break
        if tris is None:
            tris = len(idx) // 2 // 3
        out[m.m_Name] = dict(center=[float(c.x), float(c.y), float(c.z)],
                             size=[2 * float(ex.x), 2 * float(ex.y), 2 * float(ex.z)],
                             verts=nv, tris=tris)
    return out


HARNESS = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<script type="importmap">{"imports":{"three":"/three/three.module.min.js"}}</script>
</head><body style="margin:0;background:#101418">
<div id="log" style="position:fixed;left:8px;top:6px;color:#cfe3f2;font:12px monospace;z-index:9"></div>
<canvas id="c"></canvas>
<script type="module">
import * as THREE from '/three/three.module.min.js';
import { GLTFLoader } from '/three/jsm/loaders/GLTFLoader.js';
const log = s => { document.getElementById('log').textContent = s; };
const url = new URL(location.href).searchParams.get('m') || '/dorm3d_gltf/tianlangxing.glb';
const expectUrl = new URL(location.href).searchParams.get('e') || '/dorm3d_gltf/expect.json';
window.__DONE = false; window.__RESULT = null; window.__ERR = null;
window.__shot = (deg, wire) => {
  const r = window.__r;
  const d = r.camera.position.distanceTo(r.center);
  const a = deg * Math.PI / 180;
  r.camera.position.set(r.center.x + d * Math.cos(a), r.center.y + d * 0.30,
                        r.center.z + d * Math.sin(a));
  r.camera.lookAt(r.center);
  r.meshes.forEach(m => { m.material.wireframe = !!wire; });
  r.renderer.render(r.scene, r.camera);
  return r.renderer.domElement.toDataURL('image/png');
};
try {
  const expect = await (await fetch(expectUrl)).json();
  const gltf = await new GLTFLoader().loadAsync(url);
  const scene = gltf.scene;
  const canvas = document.getElementById('c');
  canvas.width = 1200; canvas.height = 1200;
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
  renderer.setSize(1200, 1200, false);
  const sc = new THREE.Scene();
  sc.background = new THREE.Color(0x101418);
  sc.add(new THREE.HemisphereLight(0xffffff, 0x404850, 1.1));
  const dl = new THREE.DirectionalLight(0xffffff, 1.0); dl.position.set(2, 4, 3); sc.add(dl);
  sc.add(scene);
  scene.traverse(o => { if (o.isMesh) o.frustumCulled = false; });
  sc.updateMatrixWorld(true);
  const meshes = [];
  scene.traverse(o => { if (o.isSkinnedMesh) meshes.push(o); });
  const V = new THREE.Vector4(), v = new THREE.Vector3(), out3 = new THREE.Vector3();
  const rep = {};
  for (const m of meshes) {
    const key = m.name.replace(/_mesh$/, '');
    try {
    const sk = m.skeleton;
    const pos = m.geometry.attributes.position;
    const ji = m.geometry.attributes.skinIndex, wj = m.geometry.attributes.skinWeight;
    if (!sk || !pos || !ji || !wj) {
      rep[key] = { error: '缺字段: skeleton=' + !!sk + ' position=' + !!pos +
                 ' skinIndex=' + !!ji + ' skinWeight=' + !!wj +
                 ' attrs=' + Object.keys(m.geometry.attributes).join(',') };
      continue;
    }
    const M = sk.bones.map(b => new THREE.Matrix4().multiplyMatrices(b.matrixWorld, sk.boneInverses[sk.bones.indexOf(b)]));
    let mn = [1e30, 1e30, 1e30], mx = [-1e30, -1e30, -1e30];
    const P = new Float32Array(pos.count * 3);
    let wmin = 9, wmax = 0;
    for (let i = 0; i < pos.count; i++) {
      v.fromBufferAttribute(pos, i);
      out3.set(0, 0, 0);
      let s2 = 0;
      for (let k = 0; k < 4; k++) {
        const w = wj.getComponent(i, k);
        if (!w) continue;
        const mm = M[ji.getComponent(i, k)];
        if (!mm) continue;
        V.set(v.x, v.y, v.z, 1).applyMatrix4(mm);
        out3.x += V.x * w; out3.y += V.y * w; out3.z += V.z * w;
        s2 += w;
      }
      wmin = Math.min(wmin, s2); wmax = Math.max(wmax, s2);
      P[i * 3] = out3.x; P[i * 3 + 1] = out3.y; P[i * 3 + 2] = out3.z;
      for (let a = 0; a < 3; a++) {
        const q = [out3.x, out3.y, out3.z][a];
        mn[a] = Math.min(mn[a], q); mx[a] = Math.max(mx[a], q);
      }
    }
    let maxE = 0;
    const ix = m.geometry.index;
    if (!ix) {
      rep[key] = { error: 'geometry.index 为空（装配器应当输出带索引的 primitive）' };
      continue;
    }
    for (let t = 0; t < ix.count; t += 3) {
      const A = [ix.getX(t), ix.getX(t + 1), ix.getX(t + 2)];
      for (let e = 0; e < 3; e++) {
        const p = A[e], q = A[(e + 1) % 3];
        const d = Math.hypot(P[p * 3] - P[q * 3], P[p * 3 + 1] - P[q * 3 + 1], P[p * 3 + 2] - P[q * 3 + 2]);
        if (d > maxE) maxE = d;
      }
    }
    const size = [mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2]];
    const diag = Math.hypot(size[0], size[1], size[2]) || 1e-9;
    m.geometry.computeBoundingBox();
    const gb = m.geometry.boundingBox;
    rep[key] = {
      verts: pos.count, joints: sk.bones.length, weightSum: [wmin, wmax],
      geomSize: [gb.max.x - gb.min.x, gb.max.y - gb.min.y, gb.max.z - gb.min.z],
      skinSize: size, skinCenter: [(mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2],
      maxEdgeOverDiag: maxE / diag,
    };
    } catch (e) {
      rep[key] = { error: String(e && e.message || e).slice(0, 160) };
    }
  }
  const box = new THREE.Box3().setFromObject(scene);
  const center = box.getCenter(new THREE.Vector3());
  const span = box.getSize(new THREE.Vector3()).length() * 1.7 || 1;
  const cam = new THREE.PerspectiveCamera(38, 1, 0.01, span * 30);
  cam.position.set(center.x + span, center.y + span * 0.25, center.z);
  cam.lookAt(center);
  renderer.render(sc, cam);
  window.__r = { scene: sc, camera: cam, renderer, meshes, center };
  window.__RESULT = { meshes: rep, expect, skinnedCount: meshes.length,
                      sceneBox: [box.min.toArray(), box.max.toArray()],
                      drawCalls: renderer.info.render.calls,
                      renderedTris: renderer.info.render.triangles,
                      totalTris: Object.values(rep).reduce((a, x) => a + x.verts, 0) };
  log('done: ' + meshes.length + ' skinned meshes');
} catch (e) {
  window.__ERR = String((e && (e.stack || e.message)) || e).slice(0, 700);
  log('ERROR ' + window.__ERR);
}
window.__DONE = true;
</script></body></html>
"""


def write_harness():
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, 'harness.html')
    with open(p, 'w', encoding='utf-8', newline='\n') as f:
        f.write(HARNESS)
    return p


def build_variants():
    """正常版 + 两种坏版（都放 .diag，不动正式区）。"""
    import dorm3d_to_gltf as G
    outs = {}
    outs['good'] = os.path.join(WORK, 'tianlangxing.glb')
    if not os.path.isfile(outs['good']):
        die_need_build(outs['good'])
    outs['transpose'] = os.path.join(WORK, 'variant_transpose.glb')
    G.build(RES, None, outs['transpose'], False, transpose_ibm=True, prefab_path=PREFAB)
    raw = bytearray(open(outs['good'], 'rb').read())
    jlen = int.from_bytes(raw[12:16], 'little')
    g = json.loads(raw[20:20 + jlen].decode('utf-8'))
    acc = g['accessors'][g['meshes'][0]['primitives'][0]['attributes']['WEIGHTS_0']]
    off = 20 + jlen + 8 + g['bufferViews'][acc['bufferView']]['byteOffset']
    raw[off] = 0
    raw[off + 4] = 0
    raw[off + 8] = 0
    outs['badweights'] = os.path.join(WORK, 'variant_badweights.glb')
    open(outs['badweights'], 'wb').write(bytes(raw))
    return outs


def die_need_build(path):
    print('  正常版 glb 不存在，先装配一份 …')
    import dorm3d_to_gltf as G
    G.build(RES, None, path, False, prefab_path=PREFAB)


def rel(a, b):
    d = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / d


def compare(good, expect, label):
    print("\n== %s ==" % label)
    ok_all = True
    for name, exp in sorted(expect.items()):
        got = good.get(name)
        if not got:
            say(False, '%s: three.js 里没有这个网格' % name)
            ok_all = False
            continue
        if got.get('error'):
            say(False, '%s: 前端量不出来 —— %s' % (name, got['error']))
            ok_all = False
            continue
        # Unity 是左手系、glTF 镜像了 X ⇒ 尺寸逐轴应相等、中心 x 反号
        gs, ss = got['geomSize'], got['skinSize']
        e = exp['size']
        d_ok = all(rel(gs[i], e[i]) < 1e-3 for i in range(3))
        s_ok = all(rel(ss[i], e[i]) < 5e-2 for i in range(3))
        c_ok = rel(abs(got['skinCenter'][0]), abs(exp['center'][0])) < 5e-2 and \
            rel(got['skinCenter'][1], exp['center'][1]) < 5e-2 and \
            rel(got['skinCenter'][2], exp['center'][2]) < 5e-2
        w_ok = abs(got['weightSum'][1] - 1.0) < 1e-3 and abs(got['weightSum'][0] - 1.0) < 1e-3
        tris_ok = got['verts'] == exp['verts']
        say(d_ok, '%-13s 几何盒逐轴 vs m_LocalAABB: three=%s unity=%s' %
            (name, ['%.4f' % x for x in gs], ['%.4f' % x for x in e]))
        say(s_ok and c_ok, '%-13s 静止态蒙皮盒 vs m_LocalAABB: size=%s center=%s（权重和 %.4f~%.4f）' %
            (name, ['%.4f' % x for x in ss], ['%.4f' % x for x in got['skinCenter']],
             got['weightSum'][0], got['weightSum'][1]))
        say(tris_ok, '%-13s 顶点数 vs 源包: %d vs %d' % (name, got['verts'], exp['verts']))
        if not (d_ok and s_ok and tris_ok):
            ok_all = False
    return ok_all



def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--keep-open', action='store_true')
    ap.add_argument('--no-controls', action='store_true', help='跳过两条坏版对照（调试用，正式判定不许跳）')
    a = ap.parse_args()
    if not os.path.isfile(RES) or not os.path.isfile(PREFAB):
        print('[FAIL] 靶子不在盘上：%s / %s —— 先跑 step 2 的拉取' % (RES, PREFAB))
        return 2
    if not CHROME:
        print('[FAIL] 找不到 Chrome/Edge（设 AL_CHROME）')
        return 2
    for f in ('three.module.min.js',):
        if not os.path.isfile(os.path.join(ROOT, '.diag', 'three', f)):
            print('[FAIL] .diag/three/%s 不存在 —— three.js 没取到' % f)
            return 2
    expect = unity_truth()
    os.makedirs(WORK, exist_ok=True)
    with open(os.path.join(WORK, 'expect.json'), 'w', encoding='utf-8') as f:
        json.dump(expect, f)
    print("Unity 侧真值（源包 m_LocalAABB）: %s" %
          {k: ['%.4f' % x for x in v['size']] for k, v in expect.items()})
    variants = build_variants()
    write_harness()

    srv_port = None
    with __import__('socket').socket() as s:
        s.bind(('127.0.0.1', 0)); srv_port = s.getsockname()[1]
    httpd = GS.make_server(port=srv_port, root=os.path.join(ROOT, '.diag'))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:%d/' % srv_port

    proc = subprocess.Popen([CHROME, '--headless=new', '--remote-debugging-port=%d' % PORT,
                             '--remote-allow-origins=*', '--user-data-dir=%s' % PROFILE,
                             '--no-first-run', '--no-default-browser-check',
                             '--disable-background-timer-throttling', '--use-angle=swiftshader',
                             '--allow-file-access-from-files',
                             '--window-size=1240,1260',
                             base + 'dorm3d_gltf/harness.html?m=' + base + 'dorm3d_gltf/tianlangxing.glb'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(proc)
    ws = None
    try:
        import websocket
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen('http://127.0.0.1:%d/json' % PORT, timeout=5))
                u = [t['webSocketDebuggerUrl'] for t in tabs
                     if 'harness.html' in t.get('url', '') and t.get('webSocketDebuggerUrl')]
                if u:
                    ws = websocket.create_connection(u[0], timeout=180, max_size=None)
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if ws is None:
            print('[FAIL] 连不上浏览器')
            return 2
        _id = [0]
        console_errs = []

        def cmd(m, p=None):
            _id[0] += 1
            ws.send(json.dumps({'id': _id[0], 'method': m, 'params': p or {}}))
            ws.settimeout(180)
            while True:
                r = json.loads(ws.recv())
                if r.get('method') == 'Log.entryAdded':
                    e = r['params']['entry']
                    if e.get('level') == 'error':
                        console_errs.append('%s | %s' % ((e.get('text') or '')[:150],
                                                         (e.get('url') or '')[-90:]))
                    continue
                if r.get('method') == 'Runtime.consoleAPICalled' and r['params'].get('type') == 'error':
                    console_errs.append(' '.join(str(x.get('value', '')) for x in
                                                 r['params'].get('args', []))[:200])
                    continue
                if r.get('id') == _id[0]:
                    if 'error' in r:
                        raise RuntimeError(json.dumps(r['error'])[:200])
                    return r.get('result', {})

        def ev(e):
            r = cmd('Runtime.evaluate', {'expression': e, 'awaitPromise': True, 'returnPointer': False})
            if r.get('exceptionDetails'):
                return {'__err': str(r['exceptionDetails'].get('text'))[:220]}
            return r.get('result', {}).get('value')
        cmd('Runtime.enable'); cmd('Log.enable'); cmd('Page.enable')

        for _ in range(240):
            if ev('window.__DONE === true'):
                break
            time.sleep(0.5)
        else:
            print('[FAIL] 120 秒内 harness 没跑完（等 __DONE 超时）')

        res = ev('JSON.stringify(window.__RESULT)')
        res = json.loads(res) if isinstance(res, str) else res
        if not res:
            say(False, 'harness 没产出结果; 页面报错=%s console=%s'
                % (str(ev('window.__ERR'))[:700], console_errs[:3]))
            return 1
        say(len([x for x in console_errs if 'favicon' not in x]) == 0,
            '浏览器 console 零 error（实得 %d 条: %s）' % (len(console_errs), console_errs[:2]))
        say(res['skinnedCount'] == len(expect),
            'three.js 里 SkinnedMesh 数 == Unity 网格数: %d == %d' % (res['skinnedCount'], len(expect)))
        exp = res['expect']
        compare(res['meshes'], exp, '正常版：前端读数 vs 源包真值')
        tot_tris = sum(v['tris'] for v in exp.values())
        say(res['renderedTris'] >= tot_tris * 0.2,
            '真的落笔了: renderer 画了 %d 个三角（源包共 %d，被背面剔除属正常，但必须是正数）'
            % (res['renderedTris'], tot_tris))
        ratios = {k: round(v['maxEdgeOverDiag'], 4) for k, v in res['meshes'].items()
                  if 'maxEdgeOverDiag' in v}
        if not ratios:
            say(False, '最长三角边 / 包围盒对角线：没有任何网格可量（上面已判红）')
        else:
            say(max(ratios.values()) < 0.35,
                '最长三角边 / 包围盒对角线 < 0.35（蒙皮没把面扯飞）: %s' % ratios)

        shots = []
        for name, deg, wire in (('front', 0.0, False), ('side', 90.0, False),
                                ('back', 180.0, False), ('wire', 45.0, True)):
            data = ev('window.__shot(%s,%s)' % (deg, 'true' if wire else 'false'))
            if isinstance(data, str) and data.startswith('data:image/png;base64,'):
                p = os.path.join(WORK, 'shot_%s.png' % name)
                with open(p, 'wb') as f:
                    import base64
                    f.write(base64.b64decode(data.split(',', 1)[1]))
                shots.append((name, p, os.path.getsize(p)))
        for name, p, sz in shots:
            print('  截图 %-6s %s (%.0f KB)' % (name, os.path.relpath(p, ROOT), sz / 1024))
        say(len(shots) == 4, '四张角度截图都落盘（拍不出来说明画面是空的）')

        if not a.no_controls:
            print("\n== 反向对照（这两条必须红，否则上面的 ✅ 不算数）==")
            # C：不存在的模型
            ev("window.__DONE=false;window.__RESULT=null;window.__ERR=null")
            r = ev("location.href='%s'" % (base + 'dorm3d_gltf/harness.html?m=/dorm3d_gltf/no_such.glb'))
            got = None
            for _ in range(60):
                time.sleep(0.5)
                got = ev('JSON.stringify({done:window.__DONE,err:window.__ERR})')
                if got and json.loads(got).get('done'):
                    break
            g = json.loads(got) if isinstance(got, str) else got
            say(bool(g and g.get('err')), '请求不存在的 glb ⇒ harness 报错（%s）'
                % (str((g or {}).get('err'))[:70]))
            r = ev("location.href='%s'" % (base + 'dorm3d_gltf/harness.html?m=' +
                                           base + 'dorm3d_gltf/tianlangxing.glb'))
            for _ in range(120):
                time.sleep(0.5)
                if ev('window.__DONE === true'):
                    break
            # A：权重被改坏
            for tag, path in (('坏权重版', variants['badweights']), ('转置版', variants['transpose'])):
                ev("window.__DONE=false;window.__RESULT=null;window.__ERR=null")
                ev("location.href='%s'" % (base + 'dorm3d_gltf/harness.html?m=' +
                                           base + 'dorm3d_gltf/' + os.path.basename(path)))
                done = False
                for _ in range(160):
                    time.sleep(0.5)
                    if ev('window.__DONE === true'):
                        done = True
                        break
                rr = ev('JSON.stringify(window.__RESULT)')
                rr = json.loads(rr) if isinstance(rr, str) else rr
                if not rr:
                    say(True, '%s ⇒ harness 直接失败（%s），也算咬住了' %
                        (tag, str(ev('window.__ERR'))[:60]))
                    continue
                bad = [k for k, v in rr['meshes'].items()
                       if 'skinSize' not in v or
                       not all(rel(v['skinSize'][i], exp[k]['size'][i]) < 5e-2 for i in range(3))]
                if not rr['meshes']:
                    say(True, '%s 一个网格都没蒙皮成功 —— 也算咬住' % tag)
                    continue
                es = [v['maxEdgeOverDiag'] for v in rr['meshes'].values() if 'maxEdgeOverDiag' in v]
                if not es:
                    say(True, '%s 全部网格读不出边长比 —— 也算咬住' % tag)
                    continue
                edge = max(es)
                w = [v['weightSum'] for v in rr['meshes'].values()]
                print('     %s: 失衡网格=%s 最长边/对角=%.4f 权重和范围=%s'
                      % (tag, bad or '无', edge, [round(max(x[0], 0), 3) for x in w][:3]))
                say(bool(bad) or edge > 0.35,
                    '%s 让"静止态蒙皮盒/边长比"判据变红（失衡 %s，边长比 %.3f）' % (tag, bad or '无', edge))
            r = ev("location.href='%s'" % (base + 'dorm3d_gltf/harness.html?m=' +
                                           base + 'dorm3d_gltf/tianlangxing.glb'))
        print("\n退出判据: FAIL=%d" % len(FAIL))
        for f in FAIL:
            print('  ! ' + f)
        return 0 if not FAIL else 1
    finally:
        if ws:
            try:
                ws.close()
            except Exception:
                pass
        if not a.keep_open:
            try:
                proc.terminate(); proc.wait(timeout=10)
            except Exception:
                proc.kill()
            httpd.shutdown()


if __name__ == '__main__':
    sys.exit(main())
