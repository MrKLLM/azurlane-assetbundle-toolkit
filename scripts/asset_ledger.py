# -*- coding: utf-8 -*-
"""资产台账：本机有哪些源包、每个产物是哪几个源包在什么时刻生成的，能不能删、删了怎么补。

为什么要有它（2026-10-01 用户提的场景）：源包 28.9GB 想上云后清本地，但直接删会连带
把 diff 弄坏 —— `mumu_sync` 比的是"设备侧路径+大小 vs 本地目录树"，删掉的包下次会被报成
**全部新增**，于是白下一遍。台账把"本地有没有"和"需不需要在本地"分开：

    sources.json   每个源包：相对路径 / 大小 / 所属类型        （只 stat，不读内容）
    artifacts.json 每个产物：大小 + md5 + 生成时刻 + 它由哪几个源包（大小+md5）生成
    pruned.json    被本工具**有意删除**的源包：路径 / 删除时大小 / 依据的产物

三条硬规矩（都是"删错了不可复原"换来的）：
  1. 「已还原」= 产物存在 **且** 台账记录的源包大小/哈希与盘上现状对得上。只"产物存在"不算。
  2. prune 默认 dry-run；`--apply` 还要 `--yes`。只删台账里**有产物依据**的包，
     不在台账里的一律当未知保留；`inputs/`、`dependencies`、`hashes*.csv` 永不删。
  3. 台账可导出/导入（换设备、重装系统后不必重拉）：`export` 出一个自包含 JSON，
     `import` 按"同路径取更新的记录"合并，并拒绝 schema 版本不明的文件。

    py -3 scripts/asset_ledger.py build                     # 扫源包目录（不读内容）
    py -3 scripts/asset_ledger.py record --stems a,b --type painting
    py -3 scripts/asset_ledger.py status
    py -3 scripts/asset_ledger.py prune [--apply --yes]
    py -3 scripts/asset_ledger.py export --out x.json ; import --in x.json
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P  # noqa: E402

SCHEMA = 1
LEDGER = os.path.join(P.ROOT, 'ledger')
SOURCES = os.path.join(LEDGER, 'sources.json')
ARTIFACTS = os.path.join(LEDGER, 'artifacts.json')
PRUNED = os.path.join(LEDGER, 'pruned.json')

# 永不删除：权威输入（不可复原，见 WF-15 白名单）+ 每次渲染都要读的公共依赖
# AB 根下的散包（ammo / channel …共 41 个）没有类型归属、消费方不明 ⇒ 一律不删，只登记
ROOT_KEY = '.'
# 永不删除：权威输入（不可复原，见 WF-15 白名单）+ 每次渲染都要读的公共依赖
NEVER_DELETE_TOPS = {'dependencies', ROOT_KEY}
NEVER_DELETE_NAMES = {'hashes.csv', 'hashes-painting.csv', 'hashes-cv.csv', 'hashes-dorm.csv',
                      'version'}

# 产物类型 → (产物目录, 产物通配)。台账只认这几类，别的类型删了也不影响产物。
ARTIFACT_OF = {
    'painting':      (P.PAINT_OUT,  '.png'),
    'spinepainting': (P.SPINE_OUT,  ''),      # 目录形态
    'live2d':        (P.LIVE2D_OUT, ''),
}


def log(m):
    print(m, flush=True)


def _now():
    return dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def _load(p, key):
    try:
        d = json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return {key: {}}
    if d.get('schema') != SCHEMA:
        raise SystemExit(f'{os.path.basename(p)} 的 schema={d.get("schema")} 与本工具({SCHEMA})不符，'
                         f'拒绝猜测其含义 —— 请核对来源或用 match 版本重新导出')
    return d


def _save(p, key, data):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as f:
        json.dump({'schema': SCHEMA, 'updated': _now(), key: data}, f,
                  ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    os.replace(tmp, p)        # 同盘 rename 是原子的：崩在半路也不会留下半截台账


def md5_of(p, limit=None):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        while True:
            b = f.read(1 << 20)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ───────────────────────────────────────────────────────────── sources（只 stat）
def cmd_build(a):
    """扫源包目录（**只 stat 不读内容**）。必须递归：`dorm3d/` 这类是多层结构，
    只扫第一层会少记 22501 个包（实测 70178 vs 全盘 92679），台账少记 = 将来 diff 误判。"""
    d = _load(SOURCES, 'sources')
    src = d['sources']
    tot = 0
    # AB 根下**直接放着**一批无后缀源包（ammo / channel / …共 41 个），它们不属于任何类型目录。
    # 只遍历子目录会把它们整批漏记 —— 台账少记 = 将来 diff 与 prune 都看不见它们。
    loose = [[f, os.stat(os.path.join(P.AB, f)).st_size]
             for f in sorted(os.listdir(P.AB)) if os.path.isfile(os.path.join(P.AB, f))]
    src[ROOT_KEY] = loose
    tot += len(loose)
    for top in sorted(os.listdir(P.AB)):
        p = os.path.join(P.AB, top)
        if not os.path.isdir(p):
            continue
        keep = []
        for dirpath, _dirnames, files in os.walk(p):
            rel_dir = os.path.relpath(dirpath, p).replace('\\', '/')
            for fn in sorted(files):
                fp = os.path.join(dirpath, fn)
                try:
                    st = os.stat(fp)
                except OSError:
                    continue
                keep.append([fn if rel_dir == '.' else rel_dir + '/' + fn, st.st_size])
        src[top] = keep
        tot += len(keep)
    _save(SOURCES, 'sources', src)
    gb = sum(x[1] for v in src.values() for x in v) / 2**30
    log(f'[OK] 源包台账已重建：{tot} 个文件 / {gb:.1f} GB，{len(src)} 个类型（只 stat，未读内容）')
    return 0



def load_sources():
    d = _load(SOURCES, 'sources')
    return {t: {x[0]: x[1] for x in v} for t, v in d['sources'].items()}


# ───────────────────────────────────────────────────────────── artifacts
def _src_bundles_for(stem, typ):
    """一个皮肤对应的源包集合：主包 + `<stem>_tex` + `<stem>_res`（存在才算）。"""
    if typ == ROOT_KEY:
        return []
    out = []
    for cand in (stem, stem + '_tex', stem + '_res'):
        fp = os.path.join(P.AB, typ, cand)
        if os.path.isfile(fp):
            st = os.stat(fp)
            out.append([cand, st.st_size, md5_of(fp)])
    return out


def cmd_record(a):
    """渲染完之后把"这个产物由这几个源包生成"记进台账（哈希此刻对得上，才有意义）。

    `--all-live` 是**一次性建账**用的：枚举正式产物目录，给每个还能找到源包的皮肤补上溯源。
    ⚠️ 它要读源包算哈希 —— 立绘全库约 7GB，实测得十几分钟，所以只在建账时跑，
    平时由 swap-in 之后按本次范围增量记录（几秒）。
    """
    d = _load(ARTIFACTS, 'artifacts')
    art = d['artifacts']
    typ = a.type
    adir, ext = ARTIFACT_OF.get(typ, (None, None))
    if not adir:
        log(f'[FAIL] 类型 {typ} 没有登记产物目录，无法记溯源')
        return 2
    if a.all_live:
        if ext:
            stems = sorted(os.path.basename(x)[:-len(ext)] for x in
                           glob.glob(os.path.join(adir, '*' + ext)))
        else:
            stems = sorted(x for x in os.listdir(adir) if os.path.isdir(os.path.join(adir, x)))
        if a.limit:
            stems = stems[:a.limit]
        log(f'  建账：{typ} 正式产物 {len(stems)} 个（要读源包算哈希，慢是预期的）')
    else:
        stems = [x for x in (a.stems or '').split(',') if x.strip()]
    if not stems:
        log('[FAIL] 没有要记录的皮肤（--stems 为空且没给 --all-live）')
        return 2
    hit = miss = 0
    for i, s in enumerate(stems, 1):
        ap = os.path.join(adir, s + ('.png' if ext else ''))
        exists = os.path.isfile(ap) if ext else os.path.isdir(ap)
        if not exists:
            miss += 1
            continue
        src = _src_bundles_for(s, typ)
        if not src:
            miss += 1                      # 源包都不在 = 无从核对，不能记成"已还原"
            continue
        rec = {'type': typ, 'produced_at': _now(), 'src': src}
        if ext:
            rec['art_size'] = os.path.getsize(ap)
            rec['art_md5'] = md5_of(ap)
        else:
            rec['art_dir'] = os.path.relpath(ap, P.ROOT).replace('\\', '/')
        art[s] = rec
        hit += 1
        if a.all_live and i % 200 == 0:
            log(f'  进度 {i}/{len(stems)} 已记 {hit}')
    _save(ARTIFACTS, 'artifacts', art)
    log(f'[OK] 溯源已记 {hit} 个（产物或源包缺失 {miss} 个）· 台账共 {len(art)} 条')
    return 0 if miss == 0 else 1



def load_artifacts():
    return _load(ARTIFACTS, 'artifacts')['artifacts']


def artifact_matches(stem, rec):
    """「已还原」的完整判据：产物在 **且** 台账里每个源包的大小/哈希都与盘上现状对得上。

    返回 (ok, 原因)。源包已经被删掉时**不能**判 ok —— 那正是"没依据"的状态。
    """
    typ = rec.get('type')
    adir, ext = ARTIFACT_OF.get(typ, (None, None))
    if not adir:
        return False, '类型未登记'
    ap = os.path.join(adir, stem + ('.png' if ext else ''))
    if ext:
        if not os.path.isfile(ap):
            return False, '产物文件不存在'
        if os.path.getsize(ap) != rec.get('art_size'):
            return False, '产物大小变了（被别的批次覆盖过）'
    elif not os.path.isdir(ap):
        return False, '产物目录不存在'
    for name, size, md5 in rec.get('src', []):
        base = P.AB if typ == ROOT_KEY else os.path.join(P.AB, typ)
        fp = os.path.join(base, name)
        if not os.path.isfile(fp):
            return False, f'源包 {name} 已不在盘上，无从核对'
        st = os.stat(fp)
        if st.st_size != size:
            return False, f'源包 {name} 大小变了 {size}→{st.st_size}'
        if md5_of(fp) != md5:
            return False, f'源包 {name} 内容变了（哈希不符）'
    return True, '产物在且源包与生成时一致'


# ───────────────────────────────────────────────────────────── prune
def prune_plan():
    """→ [(relpath, size, 依据)] ：只删"有产物依据且盘上仍对得上"的源包。"""
    art = load_artifacts()
    by_bundle = {}
    for stem, rec in art.items():
        ok, _why = artifact_matches(stem, rec)
        if not ok:
            continue
        for name, size, _md5 in rec.get('src', []):
            by_bundle[(rec['type'], name)] = stem
    plan = []
    for (typ, name), stem in sorted(by_bundle.items()):
        if typ in NEVER_DELETE_TOPS or name in NEVER_DELETE_NAMES:
            continue
        base = P.AB if typ == ROOT_KEY else os.path.join(P.AB, typ)
        fp = os.path.join(base, name)
        if not os.path.isfile(fp):
            continue
        # 主包、部件包、纹理包一视同仁：只有"产物在且生成依据的哈希对得上"才进这份计划
        rel = (f'AssetBundles/{name}' if typ == ROOT_KEY else f'AssetBundles/{typ}/{name}')
        plan.append([rel, os.path.getsize(fp), stem])
    return plan


def cmd_prune(a):
    plan = prune_plan()
    gb = sum(x[1] for x in plan) / 2**30
    if not a.apply:
        log(f'[dry-run] 可安全删除 {len(plan)} 个源包 / {gb:.2f} GB（都有产物依据且哈希对得上）')
        for rel, size, stem in plan[:15]:
            log(f'    {size/1048576:8.2f} MB  {rel}   ← 依据产物 {stem}')
        if len(plan) > 15:
            log(f'    …另 {len(plan)-15} 个')
        log('  加 --apply --yes 才会真删；删除会写 ledger/pruned.json，diff 据此不再报"新增"')
        return 0
    if not a.yes:
        log('[FAIL] --apply 必须同时给 --yes（这是不可逆动作，不接半句话）')
        return 2
    done, freed = [], 0
    for rel, size, stem in plan:
        # rel 一律是相对 `files/` 的路径（`AssetBundles/painting/2b`），从 P.FILES 拼最稳：
        fp = os.path.join(P.FILES, *rel.replace(chr(92), '/').split('/'))
        fp = os.path.join(P.AB, *rel.replace('\\', '/').split('/')[1:])
        try:
            os.remove(fp)
            done.append([rel, size, stem, _now()])
            freed += size
        except OSError as e:
            log(f'  ✗ 删不掉 {rel}: {e}')
    old = _load(PRUNED, 'pruned')['pruned']
    for rel, size, stem, at in done:
        old[rel] = [size, stem, at]
    _save(PRUNED, 'pruned', old)
    log(f'[OK] 已删 {len(done)} 个源包 / {freed/2**30:.2f} GB，台账 {len(old)} 条归档记录')
    return 0


def cmd_pruned_list(_a):
    d = _load(PRUNED, 'pruned')['pruned']
    print(json.dumps(d, ensure_ascii=False))
    return 0


# ───────────────────────────────────────────────────────────── 可迁移
def cmd_export(a):
    out = {'schema': SCHEMA, 'exported': _now(),
           'sources': _load(SOURCES, 'sources')['sources'],
           'artifacts': load_artifacts(),
           'pruned': _load(PRUNED, 'pruned')['pruned']}
    with open(a.out, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    log(f'[OK] 台账已导出 {a.out}（{os.path.getsize(a.out)/1048576:.1f} MB）'
        f'：源包 {sum(len(v) for v in out["sources"].values())} / 产物 {len(out["artifacts"])} / '
        f'归档 {len(out["pruned"])}')
    return 0


def cmd_import(a):
    src = json.load(open(a.file, encoding='utf-8'))
    if src.get('schema') != SCHEMA:
        log(f'[FAIL] 文件 schema={src.get("schema")} 与本机({SCHEMA})不符，拒绝合并')
        return 2
    cur_s = _load(SOURCES, 'sources')['sources']
    for t, v in (src.get('sources') or {}).items():
        m = {x[0]: x[1] for x in cur_s.get(t, [])}
        for name, size in v:
            m.setdefault(name, size)
        cur_s[t] = sorted([k, s] for k, s in m.items())
    cur_a = load_artifacts()
    for k, v in (src.get('artifacts') or {}).items():
        if k not in cur_a:
            cur_a[k] = v
    _save(SOURCES, 'sources', cur_s)
    _save(ARTIFACTS, 'artifacts', cur_a)
    cur_p = _load(PRUNED, 'pruned')['pruned']
    for k, v in (src.get('pruned') or {}).items():
        cur_p.setdefault(k, v)
    _save(PRUNED, 'pruned', cur_p)
    log(f'[OK] 已合并导入：源包 {sum(len(v) for v in cur_s.values())} / 产物 {len(cur_a)} / '
        f'归档 {len(cur_p)}（同路径保留本机较新的记录，不覆盖）')
    return 0


def cmd_status(_a):
    s = _load(SOURCES, 'sources')['sources']
    art = load_artifacts()
    p = _load(PRUNED, 'pruned')['pruned']
    log(f'源包台账 {sum(len(v) for v in s.values())} 个 / '
        f'{sum(x[1] for v in s.values() for x in v)/2**30:.1f} GB（{len(s)} 个类型）')
    log(f'产物溯源 {len(art)} 条；已归档（本地故意删除）{len(p)} 条 / '
        f'{sum(x[0] for x in p.values())/2**30:.2f} GB')
    plan = prune_plan()
    log(f'当前可安全删除：{len(plan)} 个源包 / {sum(x[1] for x in plan)/2**30:.2f} GB')
    on_disk = 0
    for t, v in s.items():
        d = os.path.join(P.AB, t)
        if os.path.isdir(d):
            on_disk += sum(1 for x in v if os.path.isfile(os.path.join(d, x[0])))
    log(f'台账里的源包当前在盘上：{on_disk} 个（差额=已归档或已手工删除）')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('build').set_defaults(func=cmd_build)
    r = sub.add_parser('record'); r.add_argument('--type', default='painting'); r.add_argument('--stems', default='')
    r.add_argument('--all-live', action='store_true', dest='all_live',
                   help='枚举正式产物目录做一次性建账（要读源包算哈希，慢）')
    r.add_argument('--limit', type=int, default=0, help='配 --all-live 只处理前 N 个')
    r.set_defaults(func=cmd_record)
    pr = sub.add_parser('prune'); pr.add_argument('--apply', action='store_true'); pr.add_argument('--yes', action='store_true')
    pr.set_defaults(func=cmd_prune)
    sub.add_parser('status').set_defaults(func=cmd_status)
    sub.add_parser('pruned-list').set_defaults(func=cmd_pruned_list)
    e = sub.add_parser('export'); e.add_argument('--out', default=os.path.join(P.WORK, 'ledger-export.json'))
    e.set_defaults(func=cmd_export)
    i = sub.add_parser('import'); i.add_argument('--file', required=True); i.set_defaults(func=cmd_import)
    a = ap.parse_args()
    return a.func(a) or 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
