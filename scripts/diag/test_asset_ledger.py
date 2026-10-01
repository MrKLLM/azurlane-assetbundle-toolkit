# -*- coding: utf-8 -*-
"""资产台账的闸门自测：prune 的判据、删完还能不能认出 diff、导出导入是否等价。

台账管的是**不可逆动作**（删源包），所以每条判据都按"会不会让人丢数据"来设计：
正向（该删的能删）好写，**反向（不该删的一个都不许进计划）才是重点**。

    py -3 scripts/diag/test_asset_ledger.py        # 退出码即结论

全部在临时目录里跑，绝不碰真的 files/ 与 Output/。
"""
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
ROOT = os.path.dirname(S)
sys.path.insert(0, S)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import paths as P          # noqa: E402
import asset_ledger as L   # noqa: E402

FAIL = []


def ck(name, cond, got=''):
    print(f'  {"PASS" if cond else "FAIL"}  {name}' + (f'  ← {got}' if got and not cond else ''))
    if not cond:
        FAIL.append(name)


def mk_world():
    """造一个假仓库：3 个皮肤（2b / x_ok / x_bad）+ 产物 + 台账目录。"""
    w = tempfile.mkdtemp(prefix='ledger_')
    ab = os.path.join(w, 'files', 'AssetBundles', 'painting')
    out = os.path.join(w, 'Output', 'Paintings_v2')
    os.makedirs(ab); os.makedirs(out); os.makedirs(os.path.join(w, 'ledger'))
    for stem in ('2b', 'x_ok', 'x_bad'):
        io.open(os.path.join(ab, stem), 'w', encoding='utf-8').write('SRC-' + stem)
        io.open(os.path.join(ab, stem + '_tex'), 'w', encoding='utf-8').write('TEX-' + stem)
        io.open(os.path.join(out, stem + '.png'), 'w', encoding='utf-8').write('PNG-' + stem)
    # 一个"产物根本没有"的皮肤：只有源包
    io.open(os.path.join(ab, 'orphan'), 'w', encoding='utf-8').write('SRC-orphan')
    # AB 根下的散包（真实仓库里有 41 个：ammo / channel …）+ 一个嵌套目录里的包

    # 一个 dependencies 包：就算有产物依据也永不删
    dep = os.path.join(w, 'files', 'AssetBundles', 'dependencies')
    os.makedirs(dep)
    io.open(os.path.join(dep, 'dependencies'), 'w', encoding='utf-8').write('DEP')

    # AB 根下的散包（真实仓库里有 41 个：ammo / channel …）+ 嵌套目录里的包
    ABx = os.path.join(w, 'files', 'AssetBundles')
    io.open(os.path.join(ABx, 'ammo'), 'w', encoding='utf-8').write('AMMO')
    os.makedirs(os.path.join(ab, 'sub'), exist_ok=True)
    io.open(os.path.join(ab, 'sub', 'deep'), 'w', encoding='utf-8').write('DEEP')
    P.AB = os.path.join(w, 'files', 'AssetBundles')
    P.ROOT = w
    P.PAINT_OUT = out
    L.LEDGER = os.path.join(w, 'ledger')
    L.SOURCES = os.path.join(L.LEDGER, 'sources.json')
    L.ARTIFACTS = os.path.join(L.LEDGER, 'artifacts.json')
    L.PRUNED = os.path.join(L.LEDGER, 'pruned.json')
    L.ARTIFACT_OF['painting'] = (out, '.png')
    return w, ab, out


class A:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def main():
    w, ab, out = mk_world()
    try:
        print('\n[1] build / record')
        rc = L.cmd_build(A())
        srcs = L.load_sources()
        ck('build 记全了：painting 7 个（含嵌套 sub/deep）+ dependencies + AB 根下散包',
           rc == 0 and len(srcs.get('painting', {})) == 8      # 7 个平铺 + sub/deep
           and 'dependencies' in srcs and 'sub/deep' in srcs['painting']
           and 'ammo' in srcs.get(L.ROOT_KEY, {}),
           str({k: len(v) for k, v in srcs.items()}))
        rc = L.cmd_record(A(type='painting', all_live=True, limit=0, stems=''))
        art = L.load_artifacts()
        ck('record --all-live 给有源包的产物建了溯源（orphan 不算）',
           set(art) == {'2b', 'x_ok', 'x_bad'}, str(sorted(art)))
        ck('每条溯源都带源包的大小+哈希', all(len(a['src']) == 2 and a['src'][0][2]
                                              for a in art.values()))

        print('\n[2] prune 计划：正向 + 两条反向')
        plan = {r for r, _s, _d in L.prune_plan()}
        ck('有产物依据的 6 个包进计划', len(plan) == 6, str(sorted(plan)))
        ck('AB 根下的散包与嵌套包永不进删除计划（消费方不明）',
           not any('ammo' in p or 'sub/deep' in p for p in plan), str(sorted(plan)))
        ck('没有产物的 orphan 源包不许进计划',
           not any('orphan' in p for p in plan), str(sorted(plan)))
        # 篡改 x_bad 的源包内容（**保持同长度**，这样先撞到的必须是哈希那道检查）
        io.open(os.path.join(ab, 'x_bad'), 'w', encoding='utf-8').write('SRC-x_baX')   # 同长度，只改内容
        plan2 = {r for r, _s, _d in L.prune_plan()}
        ck('源包被改过（哈希不符）⇒ 它的两个包都不许删',
           not any('x_bad' in p for p in plan2), str(sorted(plan2)))
        ok, why = L.artifact_matches('x_bad', L.load_artifacts()['x_bad'])
        ck('并且给出的是"哈希不符"这条原因，不是一句"不行"', '哈希' in why, why)
        # 两条原因要分得开：大小对不上时报大小（人才知道该去查什么）
        fake = dict(L.load_artifacts()['2b'], src=[['2b', 999999, 'deadbeef']])
        ok_sz, why_sz = L.artifact_matches('2b', fake)
        ck('大小对不上时报"大小变了"，与"哈希不符"是两条不同原因',
           (not ok_sz) and '大小' in why_sz, why_sz)
        # 产物被删 → 也不许删源包（没依据了）
        os.remove(os.path.join(out, 'x_ok.png'))
        plan3 = {r for r, _s, _d in L.prune_plan()}
        ck('产物不存在 ⇒ 源包不许删', not any('x_ok' in p for p in plan3), str(sorted(plan3)))
        ck('dependencies 永不进计划', not any('/dependencies' in p for p in plan3), str(sorted(plan3)))

        print('\n[3] prune 的动作闸门')
        rc = L.cmd_prune(A(apply=True, yes=False))
        ck('--apply 但没 --yes ⇒ 退出码 2 且一个文件都没删',
           rc == 2 and os.path.isfile(os.path.join(ab, '2b')), str(rc))
        rc = L.cmd_prune(A(apply=False, yes=False))
        ck('默认 dry-run 不删任何东西', rc == 0 and os.path.isfile(os.path.join(ab, '2b')))
        rc = L.cmd_prune(A(apply=True, yes=True))
        gone = not os.path.isfile(os.path.join(ab, '2b'))
        still = os.path.isfile(os.path.join(ab, 'x_bad'))
        ck('--apply --yes 才真删，且只删计划内的', rc == 0 and gone and still,
           f'gone={gone} x_bad还在={still}')
        pruned = L._load(L.PRUNED, 'pruned')['pruned']
        ck('删掉的每个都写进 pruned.json（路径→删除时大小）',
           all(p in pruned for p in ['AssetBundles/painting/2b', 'AssetBundles/painting/2b_tex']),
           str(sorted(pruned))[:80])

        print('\n[4] 删完之后 diff 还认得（这是用户最担心的那条）')
        import mumu_sync as M
        M.P.ROOT = w
        sz = os.path.getsize if False else 6               # 'TEX-2b' 归档时就是 6 字节
        r_files = {'AssetBundles/painting/2b': 999,        # 设备上又变了 ⇒ 不是"归档"，是真新版本
                   'AssetBundles/painting/2b_tex': sz,     # 与归档时一致 ⇒ 不重拉
                   'AssetBundles/painting/brand_new': 11}  # 台账里没有 ⇒ 正常新增
        l_files = {}          # 本地一个都没有（源包已上云删掉）⇒ 三个都进 added 再分流

        added = sorted(set(r_files) - set(l_files))
        keep, arch = M.split_archived(added, r_files, M.load_pruned())
        ck('台账里归档过、设备上大小没变 ⇒ 不再报"新增"',
           arch == ['AssetBundles/painting/2b_tex'], f'keep={keep} arch={arch}')
        ck('设备上大小变了 ⇒ 那是真新版本，必须回来重拉（不许被台账吞掉）',
           keep == ['AssetBundles/painting/2b', 'AssetBundles/painting/brand_new'], str(keep))
        ck('真正的新包照常算新增', 'AssetBundles/painting/brand_new' in keep, str(keep))
        ck('没有台账时 split_archived 一律不吞（保守）',
           M.split_archived(added, r_files, {}) == (added, []))

        print('\n[5] 导出 / 导入：换设备要等价')
        exp = os.path.join(w, 'exp.json')
        L.cmd_export(A(out=exp))
        a_before = json.dumps(L.load_artifacts(), sort_keys=True)
        for f in (L.SOURCES, L.ARTIFACTS, L.PRUNED):
            if os.path.isfile(f):
                os.remove(f)
        ck('清空本机台账后 status 归零', L.load_artifacts() == {})
        rc = L.cmd_import(A(file=exp))
        ck('import 之后溯源条数与导出前一致',
           rc == 0 and json.dumps(L.load_artifacts(), sort_keys=True) == a_before,
           f'{len(L.load_artifacts())}')
        pruned2 = L._load(L.PRUNED, 'pruned')['pruned']
        ck('归档记录也随台账回来了（否则 diff 又会把删过的报成新增）', len(pruned2) >= 2,
           str(len(pruned2)))
        bad = os.path.join(w, 'bad.json')
        io.open(bad, 'w', encoding='utf-8').write(json.dumps({'schema': 99, 'artifacts': {}}))
        ck('schema 对不上就拒绝合并，不猜', L.cmd_import(A(file=bad)) == 2)
    finally:
        shutil.rmtree(w, ignore_errors=True)
    print('\n' + (('[FAIL] ' + '；'.join(FAIL)) if FAIL else '[PASS] 资产台账闸门全绿'))
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
