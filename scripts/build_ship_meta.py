#!/usr/bin/env python3
"""§6 第5~6条：从 azurlane-data 社区缓存重建舰船元数据。

数据源（本机权威快照，不入库，台账见 inputs/azdata/MANIFEST.json）：
  inputs/azdata/azdata_ship_skin_template.json    皮肤：painting=磁盘拼音stem, name, ship_group, voice_actor, desc
  inputs/azdata/azdata_ship_data_statistics.json  舰船：name/english_name/nationality/rarity/type/skin_id
  inputs/gamecfg/voice_actor_cn.json             声优：voice_actor 码 -> 中文姓名（游戏本体解出，525 条）
桥：磁盘stem --剥变体后缀--> 基painting --skin--> 基皮肤id --stats.skin_id--> 舰级字段
    （实测 stats.skin_id 命中皮肤 4118/4119；ship_group 不是 stats 外键，仅用于同舰皮肤分组）

--diag（默认）：只读，打印覆盖率分档 / 数值码经验映射 / 样本 / 残差，绝不写文件。
--write        ：产出 Output/ship_meta.json（需用户确认后）。
"""
import sys, os, re, json, glob, argparse, collections

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
AZDATA = os.path.join(ROOT, 'inputs', 'azdata')   # 权威快照，台账 inputs/azdata/MANIFEST.json
OUT = os.path.join(ROOT, 'Output')

# ---------- 变体后缀（磁盘 stem 上出现、但皮肤表 painting 用基名的情形）----------
DERIV = re.compile(
    r'_(n|hx|hei|alter|heihua|idolns|shophx|memory|wjz|doa|ex|gv|meta|asmr|rank'
    r'|s[123]|\d+|ii|iii|iv)$'
    r'|(?:_?)(ii|iii|iv)$'   # 罗马数字紧跟无下划线：beianpudunii -> beianpudun
)

# 剧情角色 / NPC 命名前缀（拿不到舰级字段时用于分类）
STORY_PREFIX = re.compile(r'^(aijiang|linghangyuan|lingyangzhe|tansuozhe|npc|tb|linghang)')

# ---------- 数值码 -> 中文（维基一致投票 + english_name 前缀 IJN/KMS 佐证；对齐游戏内筛选词表）----------
NATIONALITY = {
    1: '白鹰', 2: '皇家', 3: '重樱', 4: '铁血', 5: '东煌', 6: '撒丁帝国', 7: '北方联合',
    8: '自由鸢尾', 9: '维希教廷', 11: '郁金王国',
    96: '飓风', 97: 'META', 98: '其他',   # 98=布里系(UNIV)无阵营，归其他；游戏"晶环联盟"本快照无对应码
    12: '晶环联盟',        # 2026-09-25 用户按舰名认定：该码旗下只有「瓦尔帕莱索」(战列/海上传奇)
    99: '塞壬',            # 2026-09-25 用户认定：构建者、仲裁者·提尔瑞特·VII
    101: '联动-超次元游戏海王星', 104: '联动-KizunaAI', 117: '联动-尼尔：自动再述',   # 按舰名+gametip 文案号(1204/1210)对齐
    102: '联动-Bilibili', 103: '联动-传颂之物', 105: '联动-Hololive', 106: '联动-死或生',
    107: '联动-偶像大师', 108: '联动-SSSS', 109: '联动-莱莎的炼金工房', 110: '联动-闪乱神乐',
    111: '联动-出包王女', 112: '联动-黑岩射手', 113: '联动-蕾斯莱莉娅娜的炼金工房',
    114: '联动-在地下城寻求邂逅', 115: '联动-约会大作战',
}
RARITY = {2: '普通', 3: '稀有', 4: '精锐', 5: '超稀有', 6: '海上传奇', 18: '超稀有'}
TYPE = {
    1: '驱逐', 2: '轻巡', 3: '重巡', 4: '战巡', 5: '战列', 6: '轻航', 7: '航母', 8: '潜艇',
    10: '航战', 12: '维修', 13: '重炮', 18: '超巡', 19: '运输', 21: '轻巡', 22: '风帆', 23: '风帆', 24: '风帆',
}

# 快照里查不到、但画廊有实体的怪例（下架联动舰等）；painting 与 ship_name_map 兜底都覆盖不到时用它
MANUAL = {'2b': '2B', 'a2': 'A2'}

# 社区快照译名与游戏官方中文名的差异修正（cn 命中左侧即替换为右侧官方名）
NAME_FIX = {'贾斯科涅': '加斯科涅'}

try:
    from ship_name_map import SHIP_NAME_MAP
except Exception:
    SHIP_NAME_MAP = {}

# 声优码 -> 中文名：从游戏本体 sharecfg 容器解出（tools/sharecfg_re/42 发布，台账 inputs/gamecfg/MANIFEST.json）
GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
try:
    VOICE_ACTOR = json.load(open(os.path.join(GAMECFG, 'voice_actor_cn.json'), encoding='utf-8'))
except Exception:
    VOICE_ACTOR = {}
    print('!! 缺 inputs/gamecfg/voice_actor_cn.json，voice_actor_name 将全为空'
          '（跑 py -3 tools/sharecfg_re/42_publish_gamecfg.py 重新生成）', file=sys.stderr)

# 秘书舰 NPC 立绘名：指挥室换装立绘不是舰皮肤，桥走不到，只能靠这张表（tools/sharecfg_re/45 发布）
try:
    NPC_PAINTING = json.load(open(os.path.join(GAMECFG, 'npc_painting_name.json'), encoding='utf-8'))
except Exception:
    NPC_PAINTING = {}
    print('!! 缺 inputs/gamecfg/npc_painting_name.json，36 个秘书舰 NPC 立绘将显示为拼音目录名'
          '（跑 py -3 tools/sharecfg_re/45_publish_npc_painting.py 重新生成）', file=sys.stderr)


def load():
    skin = json.load(open(os.path.join(AZDATA, 'azdata_ship_skin_template.json'), encoding='utf-8'))
    stats = json.load(open(os.path.join(AZDATA, 'azdata_ship_data_statistics.json'), encoding='utf-8'))
    wpath = os.path.join(OUT, 'WikiData', 'ship_data.json')
    wiki = json.load(open(wpath, encoding='utf-8')) if os.path.exists(wpath) else []
    return skin, stats, wiki


def build_indexes(skin, stats):
    painting2skin = {}
    spell = collections.defaultdict(set)
    for v in skin.values():
        p = v.get('painting')
        if p:
            painting2skin.setdefault(p, v)
            spell[str(p).lower()].add(p)
    # 大小写不敏感索引：配置里写 `2B_2`/`aijiangDD`/`npclafeiII_4`/`suweiaitongmengNew`，
    # 而磁盘 bundle 目录名一律小写 -> 精确比对会把这些整批判成"无源"（实测 27 个）。
    # 只收"该小写键全表只有一种拼法"的，避免 U556/u556 这类同键多拼法被猜错。
    painting_ci = {k: v for k, v in
                   ((k, painting2skin[min(s, key=str)])
                    for k, s in spell.items() if len(s) == 1)}
    skinid2skin = {v['id']: v for v in skin.values() if 'id' in v}
    # 舰级字段按 ship_group 归并：stats.skin_id -> 该皮肤所属组 -> 组级舰信息
    # （变体皮肤 gin_2 的 id 不被 stats.skin_id 直接引用，但与其基皮肤同 ship_group）
    by_group = collections.defaultdict(list)
    for sv in stats.values():
        g = skinid2skin.get(sv.get('skin_id'), {}).get('ship_group')
        if g is not None:
            by_group[g].append(sv)
    stats_by_group = {k: min(v, key=lambda x: x['id']) for k, v in by_group.items()}
    return painting2skin, painting_ci, stats_by_group


def _walk(stem, table, fold=False):
    """逐层剥变体后缀在 table 里找；返回 (命中层数 0/1, 键, 行) 或 None。"""
    s = stem
    for depth in range(8):
        k = s.lower() if fold else s
        if k in table:
            return depth, k, table[k]
        ns = DERIV.sub('', s)
        if ns == s:
            break
        s = ns
    return None


def resolve_base(stem, painting2skin, painting_ci):
    """磁盘 stem -> (基painting, source, 皮肤行)。

    先按原逻辑**精确**匹配（大小写敏感、逐层剥后缀），命中即返回，保证既有条目一字不改；
    只有精确匹配整轮走完都没命中，才走大小写不敏感回退（source 带 _ci 标记，可事后单独审）。
    """
    hit = _walk(stem, painting2skin)
    if hit:
        depth, key, row = hit
        return key, ('painting' if depth == 0 else 'suffix'), row
    hit = _walk(stem, painting_ci, fold=True)
    if hit:
        depth, key, row = hit
        return (row.get('painting') or key, 'painting_ci' if depth == 0 else 'suffix_ci', row)
    return None, None, None


NPC_PREFIX = re.compile(r'^npc(?=[a-z])', re.I)


def resolve_story_fallback(stem, painting_ci):
    """立绘桥走空后的两级兜底，名字仍取自表，不猜。

    -> (名字前缀, source, 皮肤行或 None, 表里的中文名或 None)；皮肤行交调用方去取舰级字段。
      npc_table/npc_suffix：秘书舰 NPC 换装立绘（secretary_special_ship 的 head/painting）
      npc_family：`npc<已知立绘名>` —— 剧情里当杂兵用的该舰复制体
      family：去掉最后一个 `_段` 后等于已知立绘名 —— 同一实体的另一张资源（图纸/贴图/和谐版）
    """
    s = stem
    for _ in range(8):
        rec = NPC_PAINTING.get(s.lower())
        if rec:
            return '', (s == stem and 'npc_table' or 'npc_suffix'), None, rec['cn']
        base = NPC_PREFIX.sub('', s)
        if base != s and base.lower() in painting_ci:
            return 'NPC', 'npc_family', painting_ci[base.lower()], None
        parts = s.rsplit('_', 1)
        if len(parts) == 2 and len(parts[0]) >= 4 and parts[0] in painting_ci:
            return '', 'family', painting_ci[parts[0]], None
        ns = DERIV.sub('', s)
        if ns == s:
            break
        s = ns
    return None, None, None, None


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
    painting2skin, painting_ci, stats_by_group = build_indexes(skin, stats)
    wiki_by_name = {x['name']: x for x in wiki if x.get('name')}
    meta = {}
    for stem in sorted(bundle_ids()):
        base, source, sk_row = resolve_base(stem, painting2skin, painting_ci)
        entry = {'cn': stem, 'en': '', 'faction': '', 'type': '', 'rarity': '',
                 'voice_actor': 0, 'category': 'story', 'base_painting': base, 'source': source or 'unresolved'}
        if base:
            sk = sk_row
            entry['voice_actor'] = sk.get('voice_actor', 0)
            entry['voice_actor_name'] = VOICE_ACTOR.get(str(entry['voice_actor']), '')
            # skin_template.name 是「皮肤名」(常含 {namecode} 占位符，或是皮肤主题标题如"午夜的瑰色电梯")，
            # 不能当舰名；另存 skin_name 备用。舰名取自 statistics.name(0 占位符，实测 4119/4119 皆真名)。
            entry['skin_name'] = sk.get('name') or stem
            sv = stats_by_group.get(sk.get('ship_group'))
            if sv:
                entry['cn'] = sv.get('name') or sk.get('name') or stem
                entry['en'] = sv.get('english_name', '')
                entry['faction'] = NATIONALITY.get(sv.get('nationality'), '其他')
                entry['rarity'] = RARITY.get(sv.get('rarity'), '')
                entry['type'] = TYPE.get(sv.get('type'), '')
                entry['nationality_code'] = sv.get('nationality')
                entry['rarity_code'] = sv.get('rarity')
                entry['type_code'] = sv.get('type')
                entry['category'] = 'ship'
            else:
                entry['cn'] = sk.get('name') or stem
        else:
            # painting 未命中 -> 秘书舰 NPC 表 / 同族前缀 -> ship_name_map 兜底 -> manual 怪例表
            pfx, src, row, npc_cn = resolve_story_fallback(stem, painting_ci)
            if src:
                entry['source'] = src
                sv = stats_by_group.get((row or {}).get('ship_group'))
                name = (sv or {}).get('name') or (row or {}).get('name') or npc_cn
                entry['cn'] = pfx + (name or stem)
                if sv:   # 舰级字段属于同一实体，可以带；但仍是剧情资源，不进"舰船"筛选
                    entry['en'] = sv.get('english_name', '')
                    entry['faction'] = NATIONALITY.get(sv.get('nationality'), '其他')
                    entry['rarity'] = RARITY.get(sv.get('rarity'), '')
                    entry['type'] = TYPE.get(sv.get('type'), '')
                    entry['nationality_code'] = sv.get('nationality')
                    entry['rarity_code'] = sv.get('rarity')
                    entry['type_code'] = sv.get('type')
            else:
                s = stem
                for _ in range(8):
                    if s in SHIP_NAME_MAP:
                        entry['cn'] = SHIP_NAME_MAP[s]
                        entry['source'] = 'fallback'
                        break
                    ns = DERIV.sub('', s)
                    if ns == s:
                        break
                    s = ns
            if entry['source'] == 'unresolved' and stem in MANUAL:
                entry['cn'] = MANUAL[stem]
                entry['source'] = 'manual'
        if entry.get('cn') in NAME_FIX:
            entry['cn'] = NAME_FIX[entry['cn']]
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
        print(f'\n[WRITE] 已产出 {path}  ({len(meta)} 条)')


if __name__ == '__main__':
    main()
