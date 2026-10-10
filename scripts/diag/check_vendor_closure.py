# -*- coding: utf-8 -*-
"""画廊 vendor 的 **import 闭包**闸门：台账列全了 ≠ 页面能跑。

真实起因（2026-10-10）：把 three.js 的 14 个文件按**名字**挑进 vendor/，MANIFEST 逐条 sha256
对拍全绿，`fetch_gallery_vendor.py --check` 报 18/18 就位 —— 但 `GLTFLoader.js` 第 1 行就是
`import ... from '../utils/BufferGeometryUtils.js'`，那个文件没拿。ES module 缺一个相对 import
⇒ **整个 module 不执行**，页面连自建的钩子对象都不会定义，症状长得像"钩子没写"或"模型加载失败"，
完全看不出是缺一个 31 KB 的工具文件。

判据为什么必须是"闭包"而不是"清单"：
  · 台账是**人写的名词表**，漏一个名字不会让台账自相矛盾 —— 生成器与校验器共享了同一个错假设。
  · 闭包从**文件内容**反推需求：每条 `import … './x.js'` 的解析目标必须在盘上存在；
    每个裸模块名（`from 'three'`）必须被页面的 importmap 映射，且映射目标在盘上存在。
    它不依赖"我以为该有哪些文件"，所以不会被我的挑选错误污染。

两道口径分开跑，因为它们的失效方向不同：
  · 运行目录 Output/gallery_v2/ —— 页面真正被服务的位子，**一律不许缺**（无豁免）。
  · 正本 gallery_src/ —— vendor 的 JS 不进 git，由 fetch_gallery_vendor.py 补进运行目录，
    所以这里允许"盘上没有但台账里有"，但**台账里也没有**就是真缺件（漏登记 = 换机器装不回来）。

⚠️ 只认 `import` 关键字开头的规格符：three.module.min.js 是自包含压缩包，
   用宽松的 `from '…'` 正则会从字符串常量里凭空造出裸模块名（实测捏出过 'srgb-linear'）。

反向对照（必须判红，否则这条闸是死的）：
    py -3 scripts/diag/check_vendor_closure.py --break-demo
用法：
    py -3 scripts/diag/check_vendor_closure.py
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SRC = os.path.join(ROOT, 'gallery_src')
RUN = os.path.join(ROOT, 'Output', 'gallery_v2')
MANIFEST = os.path.join(SRC, 'vendor', 'MANIFEST.json')
# `import x from '…'` / `import '…'` / `import('…')`，都要求出现 import 关键字。
# ⚠️ 还必须排除 CSS 的 `@import 'theme.css'`（上一版就是把它读成了 ES 依赖，
#    于是页面明明能跑、闸门却报"裸模块 theme.css 无映射"）与压缩包里的字符串常量。
IMP_RE = re.compile(
    r"""(?<![@\w$.])import\s*(?:[^'";()]*?\bfrom\s*)?['"]([^'"]+)['"]"""
    r"""|(?<![@\w$.])import\s*\(\s*['"]([^'"]+)['"]""")
MAP_RE = re.compile(r'<script\s+type="importmap"\s*>(.*?)</script>', re.S)


def manifest_allows(rel_from_root):
    """台账登记过 ⇒ "盘上没有但已登记"可豁免（正本的 vendor JS 不进 git，由 fetch 补进运行目录）。

    ⚠️ 台账记的是**运行目录**那个路径名，而这一侧解析出来的是 `gallery_src/vendor/...`，
    逐字比对会永远不命中、豁免形同虚设 ⇒ 按 `vendor/` 之后的相对段比。
    """
    n = rel_from_root.replace('\\', '/')
    i = n.find('vendor/')
    tail = (n[i:] if i >= 0 else n).rstrip('/')
    # importmap 的目录型映射（`three/addons/` → `./vendor/three/jsm/`）落在**目录**上，
    # 而台账登记的是文件、且登记名带 `Output/gallery_v2/` 前缀 ⇒ 按 `/tail/` 命中段判登记
    return any(p.endswith(tail) or ('/' + tail + '/') in p for p in MANIFEST_PATHS)


def declared_paths():
    try:
        d = json.load(open(MANIFEST, encoding='utf-8'))
    except Exception as e:
        print(f'  ! 台账读不到/不是合法 JSON：{e}')
        return None
    return set(str(f.get('path', '')).replace('\\', '/') for f in d.get('files', []))


MANIFEST_PATHS = None


def js_files(base):
    out = []
    for dirpath, _dirs, files in os.walk(base):
        for f in files:
            if f.endswith(('.js', '.mjs')):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def page_files(base):
    return sorted(os.path.join(dp, f) for dp, _d, fs in os.walk(base)
                  for f in fs if f.endswith('.html'))


def spec_of(path):
    try:
        txt = open(path, encoding='utf-8', errors='replace').read()
    except OSError:
        return [], ''
    specs = set()
    for m in IMP_RE.finditer(txt):
        specs.add(m.group(1) or m.group(2))
    return sorted(specs), txt


def check_tree(base, label, allow_absent):
    """返回缺件列表。allow_absent=True 时，"盘上没有但台账登记过"不算缺（正本侧口径）。"""
    rel_root = os.path.relpath(base, ROOT)
    missing, bare = [], set()
    njs = 0
    for f in js_files(base):
        if os.sep + 'vendor' + os.sep not in f:
            continue          # 只核对第三方库自己，页面脚本另说
        njs += 1
        specs, _ = spec_of(f)
        for spec in specs:
            if spec.startswith(('http://', 'https://', 'data:', 'blob:')):
                continue
            if spec.startswith('.'):
                tgt = os.path.normpath(os.path.join(os.path.dirname(f), spec))
                rel = os.path.relpath(tgt, ROOT)
                if not os.path.isfile(tgt) and not (allow_absent and manifest_allows(rel)):
                    missing.append((rel_root, os.path.relpath(f, base), spec, rel))
            else:
                bare.add(spec)
    # 页面的 importmap：映射目标必须在盘上（或台账登记过），且每个裸名都得有映射
    maps = {}
    for p in page_files(base):
        specs, txt = spec_of(p)
        for m in MAP_RE.finditer(txt):
            try:
                imports = json.loads(m.group(1)).get('imports', {})
            except Exception as e:
                missing.append((rel_root, os.path.basename(p), 'importmap 不是合法 JSON', str(e)[:80]))
                continue
            for k, v in imports.items():
                maps[k] = v
                if not v.startswith(('.', '/')):
                    continue
                tgt = os.path.normpath(os.path.join(os.path.dirname(p), v))
                rel = os.path.relpath(tgt, ROOT)
                good = os.path.isdir(tgt) if v.endswith('/') else os.path.isfile(tgt)
                if not good and not (allow_absent and manifest_allows(rel)):
                    missing.append((rel_root, os.path.relpath(p, base), f'importmap[{k}]', rel))
        for spec in specs:
            if spec.startswith(('.', '/', 'http')):
                continue
            if not any(k == spec or (k.endswith('/') and spec.startswith(k)) for k in maps):
                missing.append((rel_root, os.path.relpath(p, base), f'裸模块 {spec}', '无 importmap 映射'))
    print(f'  {label}：JS {njs} 个 · 裸模块名 {sorted(bare)} · importmap {sorted(maps)}')
    for b in sorted(bare):
        if not any(k == b or (k.endswith('/') and b.startswith(k)) for k in maps):
            missing.append((rel_root, '<被依赖的裸名>', b, '没有任何页面 importmap 映射它'))
    return missing


def main():
    global MANIFEST_PATHS
    MANIFEST_PATHS = declared_paths()
    if MANIFEST_PATHS is None:
        return 2
    print('== vendor import 闭包 ==')
    print(f'  台账登记 {len(MANIFEST_PATHS)} 个路径')
    miss_run = check_tree(RUN, '运行目录（真被服务的位子，无豁免）', False)
    miss_src = check_tree(SRC, '正本 gallery_src（允许"盘上没有但台账有"）', True)
    if '--break-demo' in sys.argv:
        victim = os.path.join(RUN, 'vendor', 'three', 'jsm', 'utils', 'BufferGeometryUtils.js')
        if not os.path.isfile(victim):
            print('  ! 反向对照没处下手：运行目录里没有 BufferGeometryUtils.js')
            return 2
        os.rename(victim, victim + '.bak_probe')
        try:
            demo = check_tree(RUN, '反向对照（故意抽掉一个被依赖文件）', False)
        finally:
            os.rename(victim + '.bak_probe', victim)
        hit = [x for x in demo if 'BufferGeometryUtils' in x[2] or 'BufferGeometryUtils' in x[3]]
        if hit:
            print(f'  PASS  反向对照命中，闸门确实拦得住：{hit[0][2]} → {hit[0][3]}')
            return 0
        print('  FAIL  反向对照没命中 ⇒ 这条闸是死的，别看它平时绿')
        return 1
    for tag, lst in (('运行', miss_run), ('正本', miss_src)):
        for x in lst:
            print(f'  MISSING [{tag}] {x[0]}/{x[1]} → "{x[2]}" 解析到 {x[3]}')
    if not miss_run and not miss_src:
        print('  PASS  闭包完整：每条相对 import 都在盘上（或已登记），裸模块名都有 importmap 映射')
        return 0
    print(f'  FAIL  缺件 {len(miss_run) + len(miss_src)} 处 ⇒ 页面会**整块不初始化**（不是少一个功能）')
    return 1


if __name__ == '__main__':
    sys.exit(main())
