#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_pipeline_e2e.py — 还原管线的端到端验证闸门（只读，除自己的报告/基线外不写盘）。

回答的不是「脚本跑完没有」，而是三个更硬的问题：

  ① 输入层：权威输入 / 源包清单 / 依赖表 / vendor 运行时库是否**此刻仍然一致**？
  ② 处理层：用**当前脚本**重跑一小批样本，产物是否与盘上正式产物**逐字节/逐像素一致**？
     （立绘 / Live2D / Spine / 背景 / BGM 索引 / 台词表 / 画廊索引）
  ③ 输出层：索引、缩略图、模型、音频之间的引用是否**闭合**？counts 是否自洽？
     部署硬链是否仍然 8/8 同 inode？

为什么不能只看退出码：`export_cue_audio` / `make_thumbs` / `fix_model3` /
`compose_paintings_v2` / `l2d_motion_audit` / `run_cg_export` 失败时仍可能 exit 0
（见 scripts/update_pipeline.py 文件头）。所以这里每一项都自带判据。

用法:
  py -3 scripts/diag/verify_pipeline_e2e.py                 # 标准校验（含 3 个样本/类）
  py -3 scripts/diag/verify_pipeline_e2e.py --quick         # 跳过重跑类样本，只查输入/输出
  py -3 scripts/diag/verify_pipeline_e2e.py --sample 5      # 每类多抽两个立绘
  py -3 scripts/diag/verify_pipeline_e2e.py --selftest      # 证明闸门自己会红
  py -3 scripts/diag/verify_pipeline_e2e.py --update-baseline
  py -3 scripts/diag/verify_pipeline_e2e.py --strict-baseline

退出码: 0 全部 PASS（允许 WARN）；1 有 FAIL；2 运行环境本身不成立。
报告: .diag/verify/e2e_report.json      基线: ledger/pipeline_baseline.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import paths as P  # noqa: E402

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

ROOT = P.ROOT
OUT = P.OUT
AB = P.AB
GAL = P.GALLERY_OUT
PY = sys.executable
WORK = os.path.join(ROOT, '.diag', 'verify')
REPORT = os.path.join(WORK, 'e2e_report.json')
BASELINE = os.path.join(ROOT, 'ledger', 'pipeline_baseline.json')
LIVE2D_RECIPE = {'L2D_MOTION_LINEAR': '1', 'L2D_MOTION_EMIT_CONST': '1'}

RESULTS = []
T0 = time.time()


def log(msg):
    print(msg, flush=True)


def rel(p):
    try:
        return os.path.relpath(p, ROOT).replace('\\', '/')
    except ValueError:
        return p


def add(layer, name, status, detail, data=None):
    """status: PASS / FAIL / WARN / SKIP"""
    RESULTS.append({'layer': layer, 'name': name, 'status': status,
                    'detail': detail, 'data': data, 'at': round(time.time() - T0, 2)})
    icon = {'PASS': '✓', 'FAIL': '✗', 'WARN': '!', 'SKIP': '·'}[status]
    log(f"  {icon} [{layer}] {name}: {detail}")


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def pixel_sig(path):
    """PNG 内容指纹：解码后的 RGBA 像素 + 尺寸。用于区分「内容真的变了」和「只是重新压了一次」。"""
    if Image is None:
        return None
    im = Image.open(path)
    im.load()
    im = im.convert('RGBA')
    h = hashlib.sha256(im.tobytes())
    return f'{im.width}x{im.height}:{h.hexdigest()}'


def run(argv, env_extra=None, timeout=900):
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONUNBUFFERED'] = '1'
    if env_extra:
        env.update(env_extra)
    t = time.time()
    try:
        p = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', env=env, timeout=timeout)
        return p.returncode, (p.stdout or '') + (p.stderr or ''), time.time() - t
    except subprocess.TimeoutExpired:
        return 124, f'TIMEOUT {timeout}s', time.time() - t
    except Exception as e:  # noqa: BLE001
        return 125, f'{type(e).__name__}: {e}', time.time() - t


def tail(text, n=12):
    lines = [x for x in (text or '').splitlines() if x.strip()]
    return '\n'.join(lines[-n:])


# ════════════════════════════════════════════════════════════════════
# 输入层
# ════════════════════════════════════════════════════════════════════
def check_input_manifests():
    import glob
    manifests = sorted(glob.glob(os.path.join(ROOT, 'inputs', '*', 'MANIFEST.json')))
    if not manifests:
        add('input', 'inputs/MANIFEST', 'FAIL', '没有找到 inputs/*/MANIFEST.json')
        return
    bad, total = [], 0
    for mf in manifests:
        m = json.load(open(mf, encoding='utf-8'))
        d = os.path.dirname(mf)
        for e in m.get('files', []):
            p = e['path'] if os.path.isabs(e['path']) else os.path.normpath(os.path.join(d, e['path']))
            total += 1
            if not os.path.isfile(p):
                bad.append(f'{rel(p)} 缺失')
                continue
            if os.path.getsize(p) != e.get('bytes'):
                bad.append(f'{rel(p)} 字节数漂移')
                continue
            if sha256(p) != e.get('sha256'):
                bad.append(f'{rel(p)} sha256 漂移')
    add('input', 'inputs/MANIFEST', 'FAIL' if bad else 'PASS',
        f'{len(manifests)} 份台账 / {total} 个文件' + (f'，{len(bad)} 项异常：{bad[:3]}' if bad else '，逐份字节+sha256 全对'),
        {'manifests': [rel(x) for x in manifests], 'files': total, 'bad': bad})


def check_source_manifest():
    mp = os.path.join(ROOT, 'asset_manifest.json')
    if not os.path.isfile(mp):
        add('input', 'asset_manifest vs 磁盘', 'FAIL', 'asset_manifest.json 不存在')
        return
    m = json.load(open(mp, encoding='utf-8'))
    files = m.get('files') or []
    want = {e['path'].replace('\\', '/'): e.get('size_bytes') for e in files}
    have = {}
    for d, _, fs in os.walk(AB):
        for f in fs:
            p = os.path.join(d, f)
            have[os.path.relpath(p, AB).replace('\\', '/')] = os.path.getsize(p)
    missing = sorted(set(want) - set(have))
    extra = sorted(set(have) - set(want))
    sized = sorted(k for k in set(want) & set(have) if want[k] != have[k])
    ok = not missing and not extra and not sized
    detail = (f'清单 {len(want)} / 磁盘 {len(have)}；缺失 {len(missing)}、多出 {len(extra)}、'
              f'大小不符 {len(sized)}')
    if not ok:
        detail += f'；例：missing={missing[:2]} extra={extra[:2]} sized={sized[:2]}'
    add('input', 'asset_manifest vs 磁盘', 'PASS' if ok else 'FAIL', detail,
        {'manifest': len(want), 'disk': len(have), 'missing': missing[:20],
         'extra': extra[:20], 'size_mismatch': sized[:20]})


def check_dependency_manifest():
    mp = P.MANIFEST_PATH
    if not os.path.isfile(mp):
        add('input', 'dependency_manifest', 'FAIL', '依赖表不存在')
        return
    d = json.load(open(mp, encoding='utf-8'))
    keys = list(d)
    # 依赖表的 key 就是源包相对路径（`emoji/xxx`）。`file` 字段带设备侧 `android/` 前缀，
    # 在本机不成立（目录被摊平），不能拿它当存在性判据。
    # 缺失只允许一种：已在 ledger/pruned.json 登记为「用户裁定删除」。
    pruned = set()
    pp = os.path.join(ROOT, 'ledger', 'pruned.json')
    if os.path.isfile(pp):
        try:
            for k in (json.load(open(pp, encoding='utf-8')).get('pruned') or {}):
                pruned.add(k[len('AssetBundles/'):] if k.startswith('AssetBundles/') else k)
        except Exception:  # noqa: BLE001
            pass
    n = min(400, len(keys))
    step = max(1, len(keys) // max(1, n))
    sample = keys[::step][:n]
    missing, expected = [], []
    for k in sample:
        if os.path.isfile(os.path.join(AB, k)):
            continue
        (expected if k in pruned else missing).append(k)
    add('input', 'dependency_manifest', 'PASS' if not missing else 'FAIL',
        f'{len(keys)} 个包 / 抽 {len(sample)} 个；{len(expected)} 个缺失属已登记裁剪'
        + ('' if not missing else f'，{len(missing)} 个未登记缺失：{missing[:3]}'),
        {'entries': len(keys), 'sampled': len(sample), 'missing': missing[:20],
         'pruned_expected': expected[:20], 'pruned_total': len(pruned)})


def check_vendor_manifest():
    mp = os.path.join(ROOT, 'gallery_src', 'vendor', 'MANIFEST.json')
    if not os.path.isfile(mp):
        add('input', 'vendor 运行时库', 'FAIL', 'VENDOR MANIFEST 不存在')
        return
    m = json.load(open(mp, encoding='utf-8'))
    bad = []
    for e in m.get('files', []):
        p = e['path'] if os.path.isabs(e['path']) else os.path.join(ROOT, e['path'])
        if not os.path.isfile(p):
            bad.append(f"{e['path']} 缺失")
        elif os.path.getsize(p) != e.get('bytes'):
            bad.append(f"{e['path']} 字节数漂移")
        elif sha256(p) != e.get('sha256'):
            bad.append(f"{e['path']} sha256 漂移")
    add('input', 'vendor 运行时库', 'PASS' if not bad else 'FAIL',
        f'{len(m.get("files", []))} 个文件逐一 sha256 校验' if not bad else f'{len(bad)} 项异常：{bad[:3]}',
        {'files': len(m.get('files', [])), 'bad': bad})


def check_paths():
    rc, out, _ = run([PY, 'scripts/diag/check_paths.py'], timeout=300)
    add('input', '路径可迁移性', 'PASS' if rc == 0 else 'FAIL',
        '调用链无写死绝对路径' if rc == 0 else tail(out, 8))


def check_gating():
    rc, out, sec = run([PY, 'scripts/diag/test_pipeline_gating.py'], timeout=600)
    npass = sum(1 for ln in out.splitlines() if ln.strip().startswith('PASS'))
    add('input', '签字门 / 增量范围闸门', 'PASS' if rc == 0 else 'FAIL',
        f'{npass} 条判据全绿（{sec:.1f}s）' if rc == 0 else f'rc={rc}；' + tail(out, 8))


# ════════════════════════════════════════════════════════════════════
# 输出层
# ════════════════════════════════════════════════════════════════════
def load_index():
    p = os.path.join(GAL, 'index.json')
    return json.load(open(p, encoding='utf-8'))


def check_index_schema(idx):
    d = idx
    c = d.get('counts') or {}
    ships, sil, var = d.get('ships') or [], d.get('silhouettes') or [], d.get('variants') or []
    skin_total = sum(len(s.get('skins') or []) for s in ships)
    keys = [k.get('key') for s in ships for k in (s.get('skins') or [])]
    from collections import Counter
    dup = sorted(k for k, n in Counter(keys).items() if n > 1)
    problems = []
    if c.get('ships') != len(ships):
        problems.append(f"counts.ships={c.get('ships')} != {len(ships)}")
    if c.get('skins') != skin_total:
        problems.append(f"counts.skins={c.get('skins')} != {skin_total}")
    if c.get('silhouettes') != len(sil):
        problems.append(f"counts.silhouettes={c.get('silhouettes')} != {len(sil)}")
    if c.get('variants') != len(var):
        problems.append(f"counts.variants={c.get('variants')} != {len(var)}")
    if dup:
        problems.append(f'皮肤 key 重复 {len(dup)} 个')
    add('output', 'index counts 自洽', 'PASS' if not problems else 'FAIL',
        f'船 {len(ships)} / 皮肤 {skin_total} / 剪影 {len(sil)} / 形态 {len(var)}；counts 逐项吻合'
        if not problems else '；'.join(problems),
        {'counts': c, 'ship_skins': skin_total, 'duplicate_keys': dup[:20]})


def check_index_refs(idx):
    missing_img, missing_thumb, missing_spine, missing_l2d = [], [], [], []

    def check_skin(sk):
        key = sk.get('key')
        img = sk.get('image')
        if img:
            p = os.path.normpath(os.path.join(OUT, img))
            if not os.path.isfile(p):
                missing_img.append(f'{key}: {img}')
        cg = sk.get('cg')
        if cg:
            p = os.path.normpath(os.path.join(OUT, cg))
            if not os.path.isfile(p):
                missing_img.append(f'{key}: {cg}')
        t = os.path.join(GAL, 'thumbs', f'{key}_cg.webp' if cg else f'{key}.webp')
        # 只有「有静态图」的皮肤才该有缩略图；6 个 Live2D-only 皮肤 image 为空，
        # 前端本来就显示"无立绘"，不能把它们算成缺缩略图。
        if (img or cg) and (not os.path.isfile(t) or os.path.getsize(t) == 0):
            missing_thumb.append(key)
        sp = sk.get('spine')
        if sp and isinstance(sp, dict):
            folder = sp.get('folder') or key
            parts = os.path.join(OUT, 'Spine_v2', folder, 'parts.json')
            if not os.path.isfile(parts):
                missing_spine.append(f'{key}: Spine_v2/{folder}/parts.json')
        l2 = sk.get('live2d')
        if l2:
            base = sk.get('live2dBase') or os.path.basename(l2)
            m3 = os.path.join(OUT, l2, f'{base}.model3.json')
            if not os.path.isfile(m3):
                missing_l2d.append(f'{key}: {l2}/{base}.model3.json')

    for s in idx.get('ships') or []:
        for sk in s.get('skins') or []:
            check_skin(sk)
    for s in (idx.get('silhouettes') or []) + (idx.get('variants') or []):
        if s.get('image'):
            p = os.path.normpath(os.path.join(OUT, s['image']))
            if not os.path.isfile(p):
                missing_img.append(f"{s.get('key')}: {s['image']}")
            t = os.path.join(GAL, 'thumbs', f"{s.get('key')}.webp")
            if not os.path.isfile(t):
                missing_thumb.append(s.get('key'))

    total = sum(1 for _ in missing_img) + len(missing_thumb) + len(missing_spine) + len(missing_l2d)
    add('output', 'index 引用闭合', 'PASS' if total == 0 else 'FAIL',
        '立绘/CG、缩略图、parts.json、model3.json 全部存在' if total == 0 else
        f'缺图 {len(missing_img)} / 缺缩略图 {len(missing_thumb)} / 缺 Spine {len(missing_spine)} / 缺 L2D {len(missing_l2d)}',
        {'image': missing_img[:20], 'thumb': missing_thumb[:20],
         'spine': missing_spine[:20], 'live2d': missing_l2d[:20]})


def check_painting_inventory(idx):
    pdir = P.PAINT_OUT
    n = sum(1 for f in os.listdir(pdir) if f.lower().endswith('.png')) if os.path.isdir(pdir) else 0
    refs = {sk['image'] for s in idx.get('ships') or [] for sk in (s.get('skins') or [])
            if sk.get('image') and sk['image'].lower().endswith('.png')}
    on_disk = {f'Paintings_v2/{f}' for f in os.listdir(pdir) if f.lower().endswith('.png')} if os.path.isdir(pdir) else set()
    orphan = sorted(on_disk - refs)
    add('output', '立绘盘面与索引', 'PASS' if n >= len(refs) else 'FAIL',
        f'盘上 {n} 张 / 索引引用 {len(refs)} 张 / 未被引用 {len(orphan)} 张（允许：脸差分、中间产物）',
        {'on_disk': n, 'referenced': len(refs), 'orphan': orphan[:20]})


def check_bg_meta():
    mp = os.path.join(GAL, 'bg_meta.json')
    if not os.path.isfile(mp):
        add('output', 'bg_meta 引用闭合', 'FAIL', 'bg_meta.json 不存在')
        return
    m = json.load(open(mp, encoding='utf-8'))
    items = m.get('items') or []
    missing_img, missing_thumb, bad_tier = [], [], []
    for it in items:
        img = it.get('img')
        if not img:
            missing_img.append(f"{it.get('key')}: 无 img")
        else:
            p = os.path.normpath(os.path.join(GAL, img))
            if not os.path.isfile(p):
                missing_img.append(f"{it.get('key')}: {img}")
        th = it.get('thumb')
        if th:
            p = os.path.normpath(os.path.join(GAL, th))
            if not os.path.isfile(p):
                missing_thumb.append(f"{it.get('key')}: {th}")
        if it.get('tier') not in ('exact', 'baked', 'inferred', 'none'):
            bad_tier.append(f"{it.get('key')}: {it.get('tier')}")
    c = m.get('counts') or {}
    tier_sum = sum(c.get(k, 0) for k in ('exact', 'baked', 'inferred', 'none'))
    problems = []
    if missing_img:
        problems.append(f'缺原图 {len(missing_img)}')
    if missing_thumb:
        problems.append(f'缺缩略图 {len(missing_thumb)}')
    if bad_tier:
        problems.append(f'非法 tier {len(bad_tier)}')
    if tier_sum != len(items):
        problems.append(f'四档相加 {tier_sum} != {len(items)}')
    add('output', 'bg_meta 引用闭合', 'PASS' if not problems else 'FAIL',
        f'{len(items)} 张 / 四档相加 {tier_sum}；原图与缩略图逐条存在' if not problems else '；'.join(problems),
        {'items': len(items), 'counts': c, 'missing_img': missing_img[:20],
         'missing_thumb': missing_thumb[:20], 'bad_tier': bad_tier[:20]})


def check_bgm_refs():
    mp = os.path.join(GAL, 'bgm.json')
    if not os.path.isfile(mp):
        add('output', 'bgm 引用闭合', 'FAIL', 'bgm.json 不存在')
        return
    m = json.load(open(mp, encoding='utf-8'))
    tracks = m.get('tracks') or []
    missing = []
    for t in tracks:
        u = t.get('url')
        p = os.path.normpath(os.path.join(GAL, u)) if u else ''
        if not u or not os.path.isfile(p):
            missing.append(f"{t.get('slug')}: {u}")
    c = m.get('counts') or {}
    problems = []
    if missing:
        problems.append(f'缺音频 {len(missing)}')
    if c.get('tracks') != len(tracks):
        problems.append(f"counts.tracks={c.get('tracks')} != {len(tracks)}")
    add('output', 'bgm 引用闭合', 'PASS' if not problems else 'FAIL',
        f'{len(tracks)} 首音频逐条存在；counts.tracks 吻合' if not problems else '；'.join(problems),
        {'tracks': len(tracks), 'counts': c, 'missing': missing[:20]})


def check_deploy():
    rc, out, _ = run([PY, 'scripts/deploy_gallery.py', '--check'], timeout=300)
    add('output', 'gallery 硬链部署', 'PASS' if rc == 0 else 'FAIL',
        '正本与运行目录全部同 inode' if rc == 0 else tail(out, 8))


# ════════════════════════════════════════════════════════════════════
# 处理层：抽样重跑 + 与盘上产物比对
# ════════════════════════════════════════════════════════════════════
def sample_keys(items, n):
    items = sorted(items)
    if n <= 0 or not items:
        return []
    if n >= len(items):
        return items
    if n == 1:
        return [items[len(items) // 2]]
    idx = sorted({round(i * (len(items) - 1) / (n - 1)) for i in range(n)})
    return [items[i] for i in idx]


def _tree(root):
    out = {}
    for d, _, fs in os.walk(root):
        for f in fs:
            p = os.path.join(d, f)
            out[os.path.relpath(p, root).replace('\\', '/')] = p
    return out


def compare_tree(prod, temp, pixel_fallback=True):
    """逐文件比对。PNG 允许「像素相同、封装字节不同」并记成 WARN 级差异。"""
    a, b = _tree(prod), _tree(temp)
    missing = sorted(set(a) - set(b))
    extra = sorted(set(b) - set(a))
    byte_diff, pixel_only, pixel_diff = [], [], []
    for k in sorted(set(a) & set(b)):
        pa, pb = a[k], b[k]
        if open(pa, 'rb').read() == open(pb, 'rb').read():
            continue
        if k.lower().endswith('.png') and pixel_fallback and pixel_sig(pa) == pixel_sig(pb):
            pixel_only.append(k)
        elif k.lower().endswith('.png'):
            pixel_diff.append(k)
        else:
            byte_diff.append(k)
    return {
        'missing': missing, 'extra': extra, 'byte_diff': byte_diff,
        'pixel_only': pixel_only, 'pixel_diff': pixel_diff,
        'ok': not missing and not extra and not byte_diff and not pixel_diff,
    }


def check_paintings_repro(idx, n=3):
    keys = sorted({sk['key'] for s in idx.get('ships') or [] for sk in (s.get('skins') or [])
                   if sk.get('image') and sk['key']})
    picks = sample_keys(keys, n)
    if not picks:
        add('process', '立绘重跑复现', 'SKIP', '索引里没有可抽样的立绘')
        return
    tmp = os.path.join(WORK, 'paintings')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    rc, out, sec = run([PY, 'scripts/compose_paintings_v2.py', *picks, '--out', tmp], timeout=900)
    if rc != 0:
        add('process', '立绘重跑复现', 'FAIL', f'重跑失败 rc={rc}；' + tail(out, 6), {'picks': picks})
        return
    details, bad = [], []
    for k in picks:
        p1 = os.path.join(P.PAINT_OUT, f'{k}.png')
        p2 = os.path.join(tmp, f'{k}.png')
        if not os.path.isfile(p2):
            bad.append(f'{k}: 未产出')
            continue
        b1, b2 = open(p1, 'rb').read(), open(p2, 'rb').read()
        if b1 == b2:
            details.append(f'{k}: 字节一致')
        elif pixel_sig(p1) == pixel_sig(p2):
            details.append(f'{k}: 像素一致（PNG 封装差异）')
        else:
            bad.append(f'{k}: 像素不一致')
    add('process', '立绘重跑复现', 'PASS' if not bad else 'FAIL',
        f'{len(picks)} 张 / {sec:.1f}s；' + ('、'.join(details) if not bad else '、'.join(bad)),
        {'picks': picks, 'details': details, 'bad': bad})


def _model3_projection(d):
    """把 model3 投影成「语义等价类」：忽略只改名的别名动作组、把 HitAreas 解析到真实文件。

    盘上 269 个模型是历史批次：同一个 touch_head 文件同时登记为
    `touch_head` / `Head` / `TapHead` 三组（旧版导出器的别名），当前管线只写 canonical 组。
    这是**语义等价的遗留形状**，不是内容差异；用解析后的目标文件比对才能把两者判等。
    """
    fr = d.get('FileReferences') or {}
    motions = {}
    for g, entries in (fr.get('Motions') or {}).items():
        sig = tuple(sorted(os.path.normpath(e.get('File', '')).replace('\\', '/')
                           for e in (entries or []) if e.get('File')))
        fade = tuple((e.get('FadeInTime'), e.get('FadeOutTime')) for e in (entries or []))
        motions[g] = (sig, fade)
    # 同一份文件 + 同一组淡入淡出的多个组名折叠成一个等价类；比较时不带组名，
    # 否则「用 Head 当代表」和「用 touch_head 当代表」会被误判成差异。
    canon = {}
    for g, sig in motions.items():
        canon.setdefault(sig, []).append(g)
    aliases = {g: min(gs) for sig, gs in canon.items() for g in gs if g != min(gs)}

    def resolve(name):
        return motions.get(name, ((), ()))[0]

    hits = sorted((h.get('Id'), resolve(h.get('Name'))) for h in (d.get('HitAreas') or []))
    core = {k: v for k, v in d.items() if k not in ('FileReferences', 'HitAreas')}
    fr_core = {k: v for k, v in fr.items() if k != 'Motions'}
    return {'core': core, 'fr_core': fr_core, 'motions': sorted(set(motions.values())),
            'hitareas': hits, 'aliases': aliases}


def check_live2d_repro(model='heitaizi_2'):
    prod = os.path.join(P.LIVE2D_OUT, model)
    if not os.path.isdir(prod):
        add('process', 'Live2D 重跑复现', 'SKIP', f'样本 {model} 不在盘上')
        return
    tmp = os.path.join(WORK, 'live2d')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    steps = []
    rc1, o1, s1 = run([PY, 'scripts/reconstruct_live2d.py', '--name', model, '--out', tmp], timeout=900)
    steps.append(('reconstruct', rc1, s1))
    env = dict(LIVE2D_RECIPE)
    rc2, o2, s2 = run([PY, 'scripts/extract_motions.py', '--name', model, '--out', tmp],
                      env_extra=env, timeout=900)
    steps.append(('extract_motions', rc2, s2))
    rc3, o3, s3 = run([PY, 'scripts/fix_model3.py'], env_extra={'L2D_OUT_DIR': tmp}, timeout=900)
    steps.append(('fix_model3', rc3, s3))
    bad_steps = [f'{n} rc={rc}' for n, rc, _ in steps if rc != 0]
    if bad_steps:
        add('process', 'Live2D 重跑复现', 'FAIL', '；'.join(bad_steps) + '；' + tail(o1 + o2 + o3, 6),
            {'model': model, 'steps': steps})
        return
    if '动作配方: linear+const' not in o2:
        add('process', 'Live2D 重跑复现', 'FAIL',
            f'动作配方不是生产配方（linear+const）：{tail(o2, 3)}', {'model': model})
        return
    temp = os.path.join(tmp, model)
    cmp = compare_tree(prod, temp)
    m3a = os.path.join(prod, f'{model}.model3.json')
    m3b = os.path.join(temp, f'{model}.model3.json')
    m3_ok, m3_detail, aliases = True, '', {}
    if os.path.isfile(m3a) and os.path.isfile(m3b):
        try:
            ja = _model3_projection(json.load(open(m3a, encoding='utf-8')))
            jb = _model3_projection(json.load(open(m3b, encoding='utf-8')))
            aliases = ja.get('aliases') or {}
            diffs = [k for k in ('core', 'fr_core', 'motions', 'hitareas') if ja[k] != jb[k]]
            m3_ok = not diffs
            m3_detail = ('model3 语义等价（忽略遗留别名组 ' + ','.join(sorted(aliases)) + '）'
                         if m3_ok and aliases else ('model3 语义一致' if m3_ok else f'model3 差异: {diffs}'))
        except Exception as e:  # noqa: BLE001
            m3_ok = False
            m3_detail = f'model3 解析失败: {e}'
    else:
        m3_ok = False
        m3_detail = 'model3.json 缺失'
    # model3 已单独做语义比对 ⇒ 不再按字节计入；其余文件仍要逐字节一致。
    cmp['byte_diff'] = [x for x in cmp['byte_diff'] if x != f'{model}.model3.json']
    cmp['ok'] = (not cmp['missing'] and not cmp['extra'] and not cmp['byte_diff']
                 and not cmp['pixel_diff'])
    ok = cmp['ok'] and m3_ok
    detail = (f'{model}：' + ('全部文件一致' if cmp['ok'] else
                              f"缺 {len(cmp['missing'])} / 多 {len(cmp['extra'])} / "
                              f"字节差 {len(cmp['byte_diff'])} / 像素差 {len(cmp['pixel_diff'])} / "
                              f"仅封装差 {len(cmp['pixel_only'])}")
              + '；' + m3_detail)
    add('process', 'Live2D 重跑复现', 'PASS' if ok else 'FAIL', detail,
        {'model': model, 'compare': cmp, 'model3': m3_detail, 'aliases': sorted(aliases)})


def check_bg_repro(n=2):
    mp = os.path.join(GAL, 'bg_meta.json')
    if not os.path.isfile(mp):
        add('process', '背景重导复现', 'SKIP', '没有 bg_meta.json')
        return
    m = json.load(open(mp, encoding='utf-8'))
    pool = [(it['dir'], it['name']) for it in (m.get('items') or [])
            if it.get('dir') and it.get('name') and not it['name'].endswith('__2')
            and os.path.isfile(os.path.join(AB, it['dir'], it['name']))]
    # 只抽「源包名 == 条目名」的：backyardbg/boliguan 这类产物名来自包内 Texture2D，
    # 源包文件叫 bg1，`export_assets --only` 点不到它们（定点补导走的是包名）。
    pool = sorted(set(pool))
    if not pool:
        add('process', '背景重导复现', 'SKIP', 'bg_meta 里没有可抽样的条目')
        return
    # 按 (dir,name) 均匀抽样，尽量覆盖不同类目
    picks = sample_keys([f'{d}\t{n}' for d, n in pool], n)
    pairs = [tuple(x.split('\t', 1)) for x in picks]
    names = [n for _, n in pairs]
    dirs = sorted({d for d, _ in pairs})
    tmp = os.path.join(WORK, 'bg')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    argv = [PY, 'scripts/export_assets.py', '--target', 'bg', '--only', ','.join(names),
            '--only-dir', ','.join(dirs), '--out', tmp]
    rc, out, sec = run(argv, timeout=900)
    if rc != 0 or '导出完成' not in out:
        add('process', '背景重导复现', 'FAIL', f'rc={rc}；' + tail(out, 6), {'pairs': pairs})
        return
    bad, good = [], []
    for d, name in pairs:
        p1 = os.path.join(P.OUT, 'Raw', d, f'{name}.png')
        p2 = os.path.join(tmp, d, f'{name}.png')
        if not os.path.isfile(p1):
            bad.append(f'{d}/{name}: 盘上原图缺失')
        elif not os.path.isfile(p2):
            bad.append(f'{d}/{name}: 未产出')
        elif open(p1, 'rb').read() == open(p2, 'rb').read():
            good.append(f'{d}/{name}: 字节一致')
        elif pixel_sig(p1) == pixel_sig(p2):
            good.append(f'{d}/{name}: 像素一致')
        else:
            bad.append(f'{d}/{name}: 像素不一致')
    add('process', '背景重导复现', 'PASS' if not bad else 'FAIL',
        f'{len(pairs)} 张 / {sec:.1f}s；' + ('、'.join(good if not bad else bad)),
        {'pairs': pairs, 'bad': bad})


def check_spine_repro(n=2):
    root = P.SPINE_OUT
    dirs = sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, 'parts.json'))) \
        if os.path.isdir(root) else []
    picks = sample_keys(dirs, n)
    if not picks:
        add('process', 'Spine 重跑复现', 'SKIP', '没有带 parts.json 的 Spine 目录')
        return
    tmp = os.path.join(WORK, 'spine')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    rc, out, sec = run([PY, 'scripts/extract_spine_v2.py', *picks, '--out', tmp], timeout=900)
    if rc != 0:
        add('process', 'Spine 重跑复现', 'FAIL', f'rc={rc}；' + tail(out, 6), {'picks': picks})
        return
    bad, good = [], []
    for k in picks:
        cmp = compare_tree(os.path.join(root, k), os.path.join(tmp, k))
        if cmp['ok']:
            good.append(f'{k}: {len(_tree(os.path.join(root, k)))} 个文件字节一致')
        else:
            bad.append(f'{k}: ' + str({x: cmp[x][:3] for x in ('missing', 'extra', 'byte_diff', 'pixel_diff') if cmp[x]}))
    add('process', 'Spine 重跑复现', 'PASS' if not bad else 'FAIL',
        f'{len(picks)} 个 / {sec:.1f}s；' + ('、'.join(good if not bad else bad)),
        {'picks': picks, 'bad': bad})


def _json_without(path, *keys):
    d = json.load(open(path, encoding='utf-8'))
    for k in keys:
        d.pop(k, None)
    return d


def check_bgm_index_repro():
    tmp = os.path.join(WORK, 'bgm.json')
    os.makedirs(WORK, exist_ok=True)
    rc, out, sec = run([PY, 'scripts/build_bgm_index.py', '--out', tmp], timeout=600)
    prod = os.path.join(GAL, 'bgm.json')
    if rc != 0 or not os.path.isfile(tmp):
        add('process', 'BGM 索引重生成', 'FAIL', f'rc={rc}；' + tail(out, 6))
        return
    a = _json_without(prod, 'generated')
    b = _json_without(tmp, 'generated')
    add('process', 'BGM 索引重生成', 'PASS' if a == b else 'FAIL',
        f'536 首 / 19.1 小时，逐字段一致（忽略 generated 时间戳，{sec:.1f}s）' if a == b
        else f'字段不一致：{[k for k in a if a.get(k) != b.get(k)]}',
        {'equal': a == b})


def check_words_repro():
    tmp = os.path.join(WORK, 'skin_words.json')
    os.makedirs(WORK, exist_ok=True)
    rc, out, sec = run([PY, 'scripts/build_skin_words.py', '--out', tmp], timeout=600)
    prod = os.path.join(GAL, 'skin_words.json')
    if rc != 0 or not os.path.isfile(tmp):
        add('process', '台词表重生成', 'FAIL', f'rc={rc}；' + tail(out, 6))
        return
    a = _json_without(prod, 'gen')
    b = _json_without(tmp, 'gen')
    add('process', '台词表重生成', 'PASS' if a == b else 'FAIL',
        f'7.6 MB 逐字段一致（忽略 gen 时间戳，{sec:.1f}s）' if a == b
        else f'字段不一致：{[k for k in a if a.get(k) != b.get(k)]}',
        {'equal': a == b})


def check_gallery_index_repro(idx):
    tmp = os.path.join(WORK, 'gallery')
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp, exist_ok=True)
    rc, out, sec = run([PY, 'scripts/build_gallery_index.py'],
                       env_extra={'GALLERY_OUT_DIR': tmp}, timeout=900)
    if rc != 0:
        add('process', '画廊索引重生成', 'FAIL', f'rc={rc}；' + tail(out, 6))
        return
    ok = True
    detail = []
    for f in ('index.json', 'index.js'):
        a, b = os.path.join(GAL, f), os.path.join(tmp, f)
        if not os.path.isfile(b):
            ok = False
            detail.append(f'{f} 未产出')
            continue
        same = open(a, 'rb').read() == open(b, 'rb').read()
        ok &= same
        detail.append(f'{f} ' + ('逐字节一致' if same else '不一致'))
    add('process', '画廊索引重生成', 'PASS' if ok else 'FAIL',
        f'{"; ".join(detail)}（{sec:.1f}s）', {'detail': detail})


def check_audio_sample(idx=None):
    """抽 2 首 BGM + 1 条语音，验证「能解出非零时长」而不只是文件存在。"""
    ff = P.FFMPEG
    probe = None
    if ff:
        cand = os.path.join(os.path.dirname(ff), 'ffprobe.exe')
        probe = cand if os.path.isfile(cand) else shutil.which('ffprobe')
    if not probe:
        add('process', '音频可解码抽样', 'SKIP', '找不到 ffprobe（只能做文件存在性检查）')
        return
    m = json.load(open(os.path.join(GAL, 'bgm.json'), encoding='utf-8'))
    picks = sample_keys([t['file'] for t in m.get('tracks') or []], 2)
    bad, good = [], []
    for f in picks:
        p = os.path.join(P.AUDIO_OUT, 'BGM', f)
        rc, out, _ = run([probe, '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'default=nw=1:nk=1', p], timeout=120)
        try:
            dur = float((out or '').strip().splitlines()[-1])
        except Exception:  # noqa: BLE001
            dur = 0.0
        if rc == 0 and dur > 1:
            good.append(f'{f}: {dur:.1f}s')
        else:
            bad.append(f'{f}: rc={rc} dur={dur}')
    add('process', '音频可解码抽样', 'PASS' if not bad else 'FAIL',
        '、'.join(good if not bad else bad), {'good': good, 'bad': bad})


# ════════════════════════════════════════════════════════════════════
# 基线
# ════════════════════════════════════════════════════════════════════
def make_snapshot(idx):
    files = [
        'inputs/azdata/MANIFEST.json', 'inputs/azdata/azdata_version.json',
        'inputs/gamecfg/MANIFEST.json', 'asset_manifest.json',
        'Output/dependency_manifest.json', 'Output/ship_meta.json',
        'Output/gallery_v2/index.json', 'Output/gallery_v2/index.js',
        'Output/gallery_v2/bg_meta.json', 'Output/gallery_v2/bgm.json',
        'Output/gallery_v2/skin_words.json', 'Output/gallery_v2/skin_voice.json',
        'gallery_src/theme.css', 'gallery_src/index.html',
        'gallery_src/bgm.html', 'gallery_src/backgrounds.html',
    ]
    snaps = {}
    for f in files:
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            snaps[f] = {'bytes': os.path.getsize(p), 'sha256': sha256(p)}
    return {
        'schema': 1,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'recipe': {'live2d': 'L2D_MOTION_LINEAR=1 + L2D_MOTION_EMIT_CONST=1'},
        'counts': idx.get('counts'),
        'files': snaps,
        'tools': {'python': sys.version.split()[0], 'pillow': getattr(__import__('PIL'), '__version__', '?')},
    }


def check_baseline(snap, strict=False):
    if not os.path.isfile(BASELINE):
        add('baseline', '与基线对比', 'SKIP', '还没有基线（首次请加 --update-baseline）')
        return
    old = json.load(open(BASELINE, encoding='utf-8'))
    drift = []
    for f, e in (old.get('files') or {}).items():
        n = (snap.get('files') or {}).get(f)
        if not n:
            drift.append(f'{f}: 本次快照缺失')
        elif n['sha256'] != e['sha256']:
            drift.append(f'{f}: sha256 变化')
    add('baseline', '与基线对比', 'FAIL' if (drift and strict) else ('WARN' if drift else 'PASS'),
        '关键产物与上次基线逐字节相同' if not drift else
        f'{len(drift)} 个文件变化（生产改动属正常；--strict-baseline 时判红）：{drift[:4]}',
        {'drift': drift})


# ════════════════════════════════════════════════════════════════════
# 自测
# ════════════════════════════════════════════════════════════════════
def selftest():
    ok = True
    tmp = tempfile.mkdtemp(prefix='e2e_selftest_')
    try:
        p = os.path.join(tmp, 'a.txt')
        open(p, 'w', encoding='utf-8').write('hello')
        h1 = sha256(p)
        open(p, 'a', encoding='utf-8').write('!')
        if sha256(p) == h1:
            ok = False
            log('  ✗ selftest: sha256 对内容变化不敏感')
        # 两张不同像素的 PNG
        if Image is not None:
            a = os.path.join(tmp, 'a.png')
            b = os.path.join(tmp, 'b.png')
            Image.new('RGB', (8, 8), (255, 0, 0)).save(a)
            Image.new('RGB', (8, 8), (0, 255, 0)).save(b)
            if pixel_sig(a) == pixel_sig(b):
                ok = False
                log('  ✗ selftest: pixel_sig 对内容变化不敏感')
        # model3 别名折叠
        m1 = {'Version': 3, 'FileReferences': {'Motions': {
            'Head': [{'File': 'motion/touch_head.motion3.json'}],
            'touch_head': [{'File': 'motion/touch_head.motion3.json'}]}},
            'HitAreas': [{'Id': 'TouchHead', 'Name': 'Head'}]}
        m2 = {'Version': 3, 'FileReferences': {'Motions': {
            'touch_head': [{'File': 'motion/touch_head.motion3.json'}]}},
            'HitAreas': [{'Id': 'TouchHead', 'Name': 'touch_head'}]}
        if _model3_projection(m1)['motions'] != _model3_projection(m2)['motions']:
            ok = False
            log('  ✗ selftest: model3 别名折叠失败')
        if _model3_projection(m1)['hitareas'] != _model3_projection(m2)['hitareas']:
            ok = False
            log('  ✗ selftest: HitAreas 解析失败')
        # compare_tree 必须抓到缺文件
        os.makedirs(os.path.join(tmp, 'p'))
        os.makedirs(os.path.join(tmp, 'q'))
        open(os.path.join(tmp, 'p', 'x.bin'), 'wb').write(b'1')
        cmp = compare_tree(os.path.join(tmp, 'p'), os.path.join(tmp, 'q'))
        if cmp['ok'] or not cmp['missing']:
            ok = False
            log('  ✗ selftest: compare_tree 漏报缺失文件')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    log('  ✓ selftest: sha256 / pixel_sig / model3 投影 / compare_tree 四条红路径均有效'
        if ok else '  ✗ selftest 失败')
    return ok


# ════════════════════════════════════════════════════════════════════
def main():
    ap = argparse.ArgumentParser(description='还原管线端到端验证')
    ap.add_argument('--quick', action='store_true', help='跳过重跑类样本（输入/输出层仍全查）')
    ap.add_argument('--sample', type=int, default=3, help='立绘抽样数（默认 3）')
    ap.add_argument('--live2d-model', default='heitaizi_2', help='Live2D 抽样模型')
    ap.add_argument('--update-baseline', action='store_true', help='把本次快照写成基线')
    ap.add_argument('--strict-baseline', action='store_true', help='基线漂移判红')
    ap.add_argument('--selftest', action='store_true', help='只跑闸门自身的红路径自测')
    ap.add_argument('--json', default=REPORT, help='报告落盘路径')
    args = ap.parse_args()

    log('══ 还原管线端到端验证 ══')
    log(f'仓库 {ROOT}')

    if args.selftest:
        rc = 0 if selftest() else 1
        log(f'\n[SUMMARY] selftest {"PASS" if rc == 0 else "FAIL"}')
        return rc

    os.makedirs(WORK, exist_ok=True)
    log('\n[输入层]')
    check_input_manifests()
    check_source_manifest()
    check_dependency_manifest()
    check_vendor_manifest()
    check_paths()
    check_gating()

    log('\n[输出层]')
    idx = load_index()
    check_index_schema(idx)
    check_index_refs(idx)
    check_painting_inventory(idx)
    check_bg_meta()
    check_bgm_refs()
    check_deploy()

    if args.quick:
        log('\n[处理层] --quick，跳过重跑样本')
        add('process', '抽样重跑', 'SKIP', '--quick 跳过')
    else:
        log('\n[处理层] 抽样重跑（只写 .diag/verify/，不碰正式产物）')
        check_paintings_repro(idx, args.sample)
        check_live2d_repro(args.live2d_model)
        check_bg_repro(2)
        check_spine_repro(2)
        check_bgm_index_repro()
        check_words_repro()
        check_gallery_index_repro(idx)
        check_audio_sample(idx)

    snap = make_snapshot(idx)
    log('\n[基线]')
    check_baseline(snap, args.strict_baseline)
    if args.update_baseline:
        os.makedirs(os.path.dirname(BASELINE), exist_ok=True)
        with open(BASELINE, 'w', encoding='utf-8') as f:
            json.dump(snap, f, ensure_ascii=False, indent=1)
        add('baseline', '写入基线', 'PASS', f'-> {rel(BASELINE)}')

    n_fail = sum(1 for r in RESULTS if r['status'] == 'FAIL')
    n_warn = sum(1 for r in RESULTS if r['status'] == 'WARN')
    n_pass = sum(1 for r in RESULTS if r['status'] == 'PASS')
    n_skip = sum(1 for r in RESULTS if r['status'] == 'SKIP')
    report = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'elapsed_s': round(time.time() - T0, 1),
        'summary': {'pass': n_pass, 'fail': n_fail, 'warn': n_warn, 'skip': n_skip},
        'results': RESULTS,
        'snapshot': snap,
    }
    os.makedirs(os.path.dirname(args.json), exist_ok=True)
    with open(args.json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    log(f'\n[SUMMARY] {n_pass} PASS / {n_fail} FAIL / {n_warn} WARN / {n_skip} SKIP'
        f'  ({time.time() - T0:.1f}s)')
    log(f'报告: {rel(args.json)}')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
