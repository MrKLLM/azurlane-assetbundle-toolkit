#!/usr/bin/env python3
"""§6 第5~6条：从 azurlane-data 社区缓存重建舰船元数据。

数据源（本机缓存，不入库）：
  .diag/azdata_ship_skin_template.json    皮肤：painting=磁盘拼音stem, name, ship_group, voice_actor, desc
  .diag/azdata_ship_data_statistics.json  舰船：name/english_name/nationality/rarity/type/skin_id
桥：磁盘stem --剥变体后缀--> 基painting --skin--> 基皮肤id --stats.skin_id--> 舰级字段
    （实测 stats.skin_id 命中皮肤 4118/4119；ship_group 不是 stats 外键，仅用于同舰皮肤分组）

--diag（默认）：只读，打印覆盖率分档 / 数值码经验映射 / 样本 / 残差，绝不写文件。
--write        ：产出 Output/ship_meta.json（需用户确认后）。
"""
import sys, os, re, json, glob, argparse, collections

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DIAG = os.path.join(ROOT, '.diag')
OUT = os.path.join(ROOT, 'Output')

# ---------- 变体后缀（磁盘 stem 上出现、但皮肤表 painting 用基名的情形）----------
DERIV = re.compile(
    r'_(n|hx|hei|alter|heihua|idolns|shophx|memory|wjz|doa|ex|gv|meta|asmr|rank'
    r'|s[123]|\d+|ii|iii|iv)$'
)

# 剧情角色 / NPC 命名前缀（拿不到舰级字段时用于分类）
STORY_PREFIX = re.compile(r'^(aijiang|linghangyuan|lingyangzhe|tansuozhe|npc|tb|linghang)')


def load():
    skin = json.load(open(os.path.join(DIAG, 'azdata_ship_skin_template.json'), encoding='utf-8'))
    stats = json.load(open(os.path.join(DIAG, 'azdata_ship_data_statistics.json'), encoding='utf-8'))
    wpath = os.path.join(OUT, 'WikiData', 'ship_data.json')
    wiki = json.load(open(wpath, encoding='utf-8')) if os.path.exists(wpath) else []
    return skin, stats, wiki


def build_indexes(skin, stats):
    painting2skin = {}
    for v in skin.values():
        p = v.get('painting')
        if p and p not in painting2skin:
            painting2skin[p] = v
    skinid2skin = {v['id']: v for v in skin.values() if 'id' in v}
    # 舰级字段按 ship_group 归并：stats.skin_id -> 该皮肤所属组 -> 组级舰信息
    # （变体皮肤 gin_2 的 id 不被 stats.skin_id 直接引用，但与其基皮肤同 ship_group）
    by_group = collections.defaultdict(list)
    for sv in stats.values():
        g = skinid2skin.get(sv.get('skin_id'), {}).get('ship_group')
        if g is not None:
            by_group[g].append(sv)
    stats_by_group = {k: min(v, key=lambda x: x['id']) for k, v in by_group.items()}
    return painting2skin, stats_by_group


def resolve_base(stem, painting2skin):
    """磁盘 stem -> (基painting, source)。source: painting 直命中 / suffix 剥后缀命中。"""
    s = stem
    for _ in range(8):
        if s in painting2skin:
            return s, ('painting' if s == stem else 'suffix')
        ns = DERIV.sub('', s)
        if ns == s:
            break
        s = ns
    return None, None


def bundle_ids():
    """画廊用到的全部磁盘 bundleID（立绘目录名为主，含 spine/live2d/cg 目录）。"""
    ids = set()
    for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')):
        ids.add(os.path.splitext(os.path.basename(p))[0])
    for sub in ('Spine_v2', 'Live2D', 'CG_v2'):
        for d in glob.glob(os.path.join(OUT, sub, '*')):
            if os.path.isdir(d):
                ids.add(os.path.basename(d))
    return ids


def build_meta(skin, stats, wiki, verbose=False):
    painting2skin, stats_by_group = build_indexes(skin, stats)
    wiki_by_name = {x['name']: x for x in wiki if x.get('name')}
    meta = {}
    for stem in sorted(bundle_ids()):
        base, source = resolve_base(stem, painting2skin)
        entry = {'cn': stem, 'en': '', 'faction': '', 'type': '', 'rarity': '',
                 'voice_actor': 0, 'category': 'story', 'base_painting': base, 'source': source or 'unresolved'}
        if base:
            sk = painting2skin[base]
            entry['cn'] = sk.get('name') or stem
            entry['voice_actor'] = sk.get('voice_actor', 0)
            sv = stats_by_group.get(sk.get('ship_group'))
            if sv:
                entry['en'] = sv.get('english_name', '')
                entry['nationality_code'] = sv.get('nationality')
                entry['rarity_code'] = sv.get('rarity')
                entry['type_code'] = sv.get('type')
                entry['category'] = 'ship'
        meta[stem] = entry
    return meta, painting2skin, stats_by_group, wiki_by_name


def derive_labels(meta, wiki_by_name):
    """用命中的中文维基标签，经验推导 nationality/rarity/type 数值码 -> 中文。"""
    # code -> Counter(中文标签)
    nat, rar, typ = (collections.defaultdict(collections.Counter) for _ in range(3))
    for e in meta.values():
        w = wiki_by_name.get(e['cn'])
        if not w:
            continue
        if 'nationality_code' in e:
            nat[e['nationality_code']][w.get('faction') or '?'] += 1
            rar[e['rarity_code']][w.get('rarity') or '?'] += 1
            typ[e['type_code']][w.get('ship_type') or '?'] += 1
    return nat, rar, typ


def print_diag(meta, wiki_by_name):
    n = len(meta)
    src = collections.Counter(e['source'] for e in meta.values())
    cat = collections.Counter(e['category'] for e in meta.values())
    res = cat.get('ship', 0)
    print('=' * 60)
    print(f'bundleID 总数: {n}')
    print('解析来源分档:', dict(src))
    print(f'舰船(ship): {res}   剧情/未解析(story): {n - res}')

    print('\n--- 数值码 -> 中文 经验映射（命中维基的投票，? = 维基缺该舰）---')
    nat, rar, typ = derive_labels(meta, wiki_by_name)
    for title, table in (('nationality', nat), ('rarity', rar), ('type', typ)):
        print(f'[{title}]')
        for code in sorted(table):
            top = table[code].most_common(4)
            tot = sum(table[code].values())
            print(f'    {code!s:>4} (n={tot:<4}) -> {top}')

    print('\n--- 样本 ---')
    for probe in ('kuersike_rw', 'kuersike', 'gin', 'gin_2', 'abuluqi_2_n_hx', 'aijiangcl', '2b', 'dahuangfengii_2'):
        e = meta.get(probe)
        if e:
            print(f'  {probe:20s} {json.dumps(e, ensure_ascii=False)}')

    print('\n--- 未解析残差（source=unresolved）样例 ---')
    un = [k for k, e in meta.items() if e['source'] == 'unresolved']
    print(f'共 {len(un)} 个:', un[:60])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', action='store_true', help='产出 Output/ship_meta.json（默认只读诊断）')
    args = ap.parse_args()

    skin, stats, wiki = load()
    meta, painting2skin, stats_by_group, wiki_by_name = build_meta(skin, stats, wiki)
    print_diag(meta, wiki_by_name)

    if args.write:
        path = os.path.join(OUT, 'ship_meta.json')
        json.dump(meta, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print(f'\n[WRITE] 已产出 {path}  ({len(meta)} 条) —— 需数值标签表确认后再回填 faction/type/rarity 中文')


if __name__ == '__main__':
    main()
