# -*- coding: utf-8 -*-
"""全库比对「画廊实际合成的 Spine 层」与「游戏 prefab 真正挂着的层」——只读，不动任何产物。

为什么需要：`build_gallery_index.py` 用 `glob('Output/Spine_v2/<目录>/*.skel')` 决定一张 Spine
立绘由哪几层合成，viewer 与 `cg_export.html` 共用这份列表。但**同一个导出目录里除了分层，
还躺着 `_hx`（和谐版）等变体的 skel**——它们不是层，是另一张画。实测 `spinepainting/buleisite_res`
包里有 `buleisite_B.skel` / `buleisite_T.skel` / `buleisite_T_hx.skel` 三个，而 `buleisite` 的 prefab
只挂前两个（`buleisite_hx` 的 prefab 挂 `_B` + `_T_hx`）。⇒ `_hx` 是**替换某一层**，不是多加一层。

权威来源（零猜测）：`spinepainting/<bundleID>` 这个 UI 容器里每个 `SkeletonGraphic` 组件
= 一个真实图层节点，它的 `skeletonDataAsset` 是跨包 PPtr，解析到的
`SkeletonDataAsset.m_Name` 形如 `<层名>_SkeletonData` ⇒ **剥后缀即得层名**，
不受"节点名 `buleisiteB` vs 文件名 `buleisite_B`"这类命名错配影响。
顺带读出每个节点该用的 `startingAnimation` / `initialSkinName` / 激活位 / RectTransform——
这几项画廊现在也一律没读（弹窗硬编码优先播 `normal`）。

用法:
  py -3 scripts/diag/spine_parts_prefab_diff.py                 # 全库（index.json 里有 spine 的目录）
  py -3 scripts/diag/spine_parts_prefab_diff.py --only buleisite,huajia_2
产物: .diag/spine_parts_<stamp>.tsv + 终端汇总
"""
import sys, os, re, json, io, time, argparse, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
TSV_HEAD = ('bundle\tprefab_layer\twhy\tin_export_dir\tactive\tnode_name\t'
            'startAnim\tinitSkin\tanchoredPos\tscale\trotZ\tglob_layers\n')
def skel_nodes(prefab_bundle):
    """薄封装：解析逻辑已抽到 compose_paintings_v2.skel_layers（谁写谁读只认一份）。

    这里只把它返回的结构转成本脚本 TSV 要的字面量形态。
    """
    out = []
    for nd in C.skel_layers(prefab_bundle):
        out.append(dict(node=nd['node'], layer=nd['layer'], why=nd['why'],
                        active=nd['active'], anim=nd['anim'], skin=nd['skin'],
                        ap='%.1f,%.1f' % tuple(nd['anchoredPosition']),
                        sc='%.3f,%.3f' % tuple(nd['localScale']),
                        rot='%.2f' % nd['rotZ']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stamp', default=time.strftime('%Y%m%d'))
    ap.add_argument('--only', default='')
    a = ap.parse_args()

    idx = json.load(io.open(os.path.join(ROOT, 'Output', 'gallery_v2', 'index.json'), encoding='utf-8'))
    folders = {}
    for s in idx['ships']:
        for sk in (s.get('skins') or []):
            sp = sk.get('spine')
            if sp and sp.get('folder'):
                folders.setdefault(sp['folder'], sp.get('parts') or [sp['folder']])
    if a.only:
        want = {x.strip() for x in a.only.split(',') if x.strip()}
        folders = {k: v for k, v in folders.items() if k in want}

    tsv = os.path.join(ROOT, '.diag', f'spine_parts_{a.stamp}.tsv')
    os.makedirs(os.path.dirname(tsv), exist_ok=True)
    w = open(tsv, 'w', encoding='utf-8', newline='\n')
    w.write(TSV_HEAD)

    n_over = n_under = n_nonident = n_anim = n_noprefab = n_missing = 0
    over_by = collections.Counter()
    anim_by = collections.Counter()
    bad = []
    for i, (f, globbed) in enumerate(sorted(folders.items()), 1):
        g = set(globbed or [])
        sd = os.path.join(ROOT, 'Output', 'Spine_v2', f)
        exp = {x[:-5] for x in os.listdir(sd) if x.endswith('.skel')} if os.path.isdir(sd) else set()
        nodes = skel_nodes(f'spinepainting/{f}')
        if not nodes:
            n_noprefab += 1
            print(f'  ! {f}: 读不到 spinepainting/{f} 或里面没有 SkeletonGraphic', flush=True)
            continue
        layers = {nd['layer'] for nd in nodes if nd['layer']}
        for nd in nodes:
            inv = 'Y' if nd['layer'] in exp else ('MISSING' if nd['layer'] else '-')
            if inv == 'MISSING':
                n_missing += 1
            w.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                f, nd['layer'], nd['why'], inv, nd['active'], nd['node'],
                nd['anim'], nd['skin'], nd['ap'], nd['sc'], nd['rot'], ','.join(sorted(g))))
        extra, miss = g - layers, layers - g
        if extra:
            n_over += 1
            for e in extra:
                over_by[e] += 1
        if miss:
            n_under += 1
        if any(abs(float(nd['rot'] or 0)) > 0.01 or
               (nd['sc'] and not all(abs(float(x) - 1) < 1e-3 for x in nd['sc'].split(',')))
               for nd in nodes):
            n_nonident += 1
        an = {nd['anim'] for nd in nodes if nd['anim']}
        if an and an != {'normal'}:
            n_anim += 1
            for x in an:
                anim_by[x] += 1
        if extra or miss:
            bad.append((f, sorted(extra), sorted(miss)))
        if i % 40 == 0:
            w.flush()
            print(f'  进度 {i}/{len(folders)} 多画 {n_over} 少画 {n_under} 非单位变换 {n_nonident} '
                  f'起始动画≠normal {n_anim} 无prefab {n_noprefab} 层文件缺失 {n_missing}', flush=True)
    w.close()

    print('=' * 78)
    print(f'比对 {len(folders)} 个 Spine 目录 -> {tsv}')
    print(f'  多画（glob 有、prefab 没挂）目录数     : {n_over}')
    print(f'  少画（prefab 挂了、glob 没有）目录数   : {n_under}')
    print(f'  prefab 指到的层在导出目录里找不到 的节点: {n_missing}')
    print(f'  含非单位变换（位移/缩放/旋转）的目录数   : {n_nonident}')
    print(f'  起始动画不是 normal 的目录数            : {n_anim}  （2026-09-29 起前端已按 parts.json 逐层播）')
    print(f'  读不到 prefab / 无 SkeletonGraphic 的目录: {n_noprefab}')
    if over_by:
        print('  被多画的那一层叫什么:', dict(over_by.most_common(12)))
    if anim_by:
        print('  prefab 写的起始动画分布:', dict(anim_by.most_common(8)))
    print(f'  有层差异的目录 {len(bad)} 个，前 20:')
    for f, e, m in bad[:20]:
        print(f'    {f:22s} 多画={e} 少画={m}')


if __name__ == '__main__':
    main()
