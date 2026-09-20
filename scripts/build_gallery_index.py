#!/usr/bin/env python3
"""构建资产浏览器索引 index.json（v2 合并逻辑）。
所有资产按「归一化基ID → 完整皮肤stem」挂载，Spine/Live2D 绑定到对应 skin。
"""
import sys, os, re, json, glob
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ship_name_map import SHIP_NAME_MAP

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'Output')
# 支持 GALLERY_OUT_DIR 环境变量把产物写到临时目录，供改造后小规模比对，默认写正式 gallery_v2
GAL = os.environ.get('GALLERY_OUT_DIR') or os.path.join(OUT, 'gallery_v2')

# ---------- CV_MAP ----------
cv_src = open(os.path.join(ROOT, 'scripts', 'generate_audio_doc.py'), encoding='utf-8').read()
mm = re.search(r'CV_MAP\s*=\s*\{(.*?)\n\}', cv_src, re.S)
CV_MAP = {int(k): v for k, v in re.findall(r'(\d+)\s*:\s*"([^"]+)"', mm.group(1))}

# ---------- 中文名 → 拼音（仅唯一映射）----------
CN2PIN = {}
for pin, cn in SHIP_NAME_MAP.items():
    CN2PIN[cn] = pin if cn not in CN2PIN or CN2PIN[cn] == pin else CN2PIN[cn]
dup_cn = {}
for pin, cn in SHIP_NAME_MAP.items():
    dup_cn.setdefault(cn, []).append(pin)

# ---------- 元数据 ----------
meta_by_cn = {}
for s in json.load(open(os.path.join(OUT, 'WikiData', 'ship_data.json'), encoding='utf-8')):
    meta_by_cn[s['name']] = s

# ---------- 新权威元数据源：ship_meta.json（旧 SHIP_NAME_MAP + Wiki meta_by_cn 降级兜底）----------
# 键=完整 bundle stem，值含 cn(皮肤名)/faction/type/rarity/category(舰级，经 ship_group 归并)
# ⚠️ cn 可能含 {namecode:XX} 本地化占位符(§6#8)，故「舰名」优先用干净的 SHIP_NAME_MAP，
#    仅当 SHIP_NAME_MAP 缺失且 cn 为真实名时才用 cn；「阵营/舰种/稀有度」则以 ship_meta 为主(Wiki 覆盖仅 445 太低)。
SHIP_META = {}
_sm_path = os.path.join(OUT, 'ship_meta.json')
if os.path.exists(_sm_path):
    try:
        SHIP_META = json.load(open(_sm_path, encoding='utf-8'))
    except Exception:
        SHIP_META = {}
PLACEH = re.compile(r'\{namecode:\d+\}')
def _clean_cn(v):
    """占位符/空/等于 stem 本身的 cn 视为无有效名。"""
    return '' if (not v or PLACEH.search(v)) else v

# 社区快照/拼音表译名与游戏官方中文名差异修正（与 build_ship_meta 保持一致，兜底路径也生效）
NAME_FIX = {'贾斯科涅': '加斯科涅'}

PINS = set(SHIP_NAME_MAP.keys())
ROMAN = {'ii': '改', 'iii': '改三', 'iv': '改四'}
VARMAP = {'hx': '换色', 'n': '夜战', 'g': 'G', 'meta': 'META', 'asmr': 'ASMR', 'gv': '改造'}
JUNK = {'22', '33', 'unknown3'}  # 明显测试残留

def normalize(stem):
    """返回 (base, extra_label_tokens)。剥离尾部变体标记直到命中拼音表或无可剥。"""
    toks = stem.split('_')
    # 从尾部剥离变体标记（数字/hx/n/g/meta/asmr/罗马数字等）
    while len(toks) > 1:
        if '_'.join(toks) in PINS:
            break
        t = toks[-1]
        if re.fullmatch(r'\d+', t) or t in VARMAP or t in ROMAN or t in ('s1','s2','s3'):
            toks.pop()
        else:
            break
    base = '_'.join(toks)
    # 命中表 或 base 本身即在表 → base；否则若首段在表则用首段
    if base not in PINS and len(toks) > 1 and toks[0] in PINS:
        # META/灰烬舰(异格,_alter 形态)不并入本体船——独立成卡才能显示 faction=META。
        # 仅当该 _alter 基名在 ship_meta 里确为 META 阵营时才独立;非 META 的 alter 仍折叠。
        if base.endswith('_alter') and SHIP_META.get(base, {}).get('faction') == 'META':
            return base
        base = toks[0]
    return base

def variant_label(stem, base):
    tail = stem[len(base):].strip('_')
    if not tail:
        return '默认立绘'
    parts = []
    for t in tail.split('_'):
        if re.fullmatch(r'\d+', t):
            parts.append(f'皮肤{t}')
        elif t in ROMAN:
            parts.append(ROMAN[t])
        elif t in VARMAP:
            parts.append(VARMAP[t])
        elif t in ('s1','s2','s3'):
            parts.append('SP'+t[-1])
        else:
            parts.append(t)
    return '·'.join(parts)

# ---------- ship_meta 反查：base → 代表性条目（同 base 多 stem 中挑 cn 干净/ship/有阵营 的最优）----------
_base2stems = {}
for _stem in SHIP_META:
    _base2stems.setdefault(normalize(_stem), []).append(_stem)

def ship_meta_entry(base):
    """舰级字段(faction/type/rarity/category/en)来源：优先基皮肤自身条目，其次同 base 兄弟。"""
    if base in SHIP_META:
        return SHIP_META[base]
    best = None
    for s in sorted(_base2stems.get(base, [])):
        if s in SHIP_META:
            e = SHIP_META[s]
            score = (1 if e.get('category') == 'ship' else 0,
                     1 if e.get('faction') else 0,
                     1 if e.get('type') else 0,
                     1 if e.get('rarity') else 0)
            if best is None or score > best[0]:
                best = (score, e)
    return best[1] if best else {}

# ---------- 收集 skins（key=完整stem）----------
skins = {}   # stem -> {key,label,base,image,spine_dir,live2d}
ships = {}   # base -> ship dict

def ship_of(base):
    if base in ships:
        return ships[base]
    e = ship_meta_entry(base)
    # 舰名：ship_meta 为权威（解密配置+en 交叉印证，如 beianpudun=北安普敦而非旧表错的"贝尔法斯特"），
    # SHIP_NAME_MAP 是含已知错误的手写猜测表，降为兜底。
    # 但仅当 meta 条目「已解析出阵营」(resolved) 时才信它的 cn——未解析条目(如 kelei→柯蕾/空阵营)
    # 的 cn 可能是皮肤名或错值，此时回落 SHIP_NAME_MAP(可畏)+Wiki。
    # ⚠️ 只认「基皮肤自身」的 cn 作舰名（变体皮肤 cn 是皮肤标题，不能当舰名）；{namecode}占位符视为无名(§6#8)。
    resolved = bool(e.get('faction'))
    name_meta = _clean_cn(SHIP_META[base].get('cn')) if (resolved and base in SHIP_META) else ''
    cn = name_meta or SHIP_NAME_MAP.get(base) or ''
    cn = NAME_FIX.get(cn, cn)   # 官方译名修正（兜底路径也生效）
    meta = meta_by_cn.get(cn, {}) if cn else {}
    npc = bool(re.match(r'(npc|linghangyuan|lingyangzhe)', base))
    # 阵营/舰种/稀有度：ship_meta 主，Wiki meta_by_cn 兜底（Wiki 覆盖仅 445，且须舰名先正确才可信）
    faction = e.get('faction') or meta.get('faction', '')
    stype = e.get('type') or meta.get('ship_type', '') or ('NPC' if npc else '')
    rarity = e.get('rarity') or meta.get('rarity', '')
    category = e.get('category') or ('story' if (npc or not cn) else 'ship')
    ships[base] = {
        'id': base, 'name': cn or base, 'hasCn': bool(cn), 'npc': npc,
        'type': stype, 'rarity': rarity, 'faction': faction, 'category': category,
        'skins': [], 'voices': [], 'spineSkins': [], 'live2dSkins': [],
    }
    return ships[base]

def add_skin(stem, rel_image):
    if stem in JUNK:
        return
    base = normalize(stem)
    sh = ship_of(base)
    sk = skins.get(stem)
    if sk is None:
        sk = {'key': stem, 'label': variant_label(stem, base), 'image': rel_image,
              'spine': False, 'live2d': ''}
        skins[stem] = sk
        sh['skins'].append(sk)
    elif rel_image and not sk['image']:
        sk['image'] = rel_image

# 立绘
for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')):
    stem = os.path.splitext(os.path.basename(p))[0]
    add_skin(stem, 'Paintings_v2/' + os.path.basename(p))

# Spine（目录名即某 skin 的 stem；内含 1..N 个部件 .skel 需合成）
def layer_order(name):
    # B(身体)<M(脸)<T(头发/装饰) 参考原 viewer 图层序，bg 最底
    if '_bg' in name or name.endswith('bg'): return 0
    if name.endswith('B') or 'B_' in name: return 1
    if name.endswith('M') or 'M_' in name: return 2
    if name.endswith('T') or 'T_' in name: return 3
    return 2
for d in glob.glob(os.path.join(OUT, 'Spine_v2', '*')):
    if not os.path.isdir(d): continue
    stem = os.path.basename(d)
    parts = sorted((os.path.basename(f)[:-5] for f in glob.glob(os.path.join(d, '*.skel'))),
                   key=layer_order)
    if not parts:  # 空目录（导出缺失），跳过
        continue
    base = normalize(stem)
    sk = skins.get(stem)
    if sk is None:
        add_skin(stem, '')
        sk = skins[stem]
    sk['spine'] = {'folder': stem, 'parts': parts}
    ship_of(base)['spineSkins'].append(stem)

# Spine setup-pose 全屏 CG（cg_export.html 导出到 CG_v2/，目录名=皮肤 stem）
for p in glob.glob(os.path.join(OUT, 'CG_v2', '*.png')):
    stem = os.path.splitext(os.path.basename(p))[0]
    sk = skins.get(stem)
    if sk is None:
        add_skin(stem, '')
        sk = skins[stem]
    sk['cg'] = 'CG_v2/' + os.path.basename(p)

# Live2D
for d in glob.glob(os.path.join(OUT, 'Live2D', '*')):
    if not os.path.isdir(d): continue
    if not glob.glob(os.path.join(d, '*.model3.json')): continue
    stem = os.path.basename(d)
    base = normalize(stem)
    sk = skins.get(stem)
    if sk is None:
        add_skin(stem, '')
        sk = skins[stem]
    sk['live2d'] = 'Live2D/' + stem
    sk['live2dBase'] = stem
    ship_of(base)['live2dSkins'].append(stem)

# 语音按中文名归到 ship
for f in glob.glob(os.path.join(OUT, 'Audio', 'CV', 'cv-*.wav')):
    fn = os.path.basename(f)
    m2 = re.match(r'cv-(\d+)(-[\w]+)?\.wav', fn)
    if not m2: continue
    name = CV_MAP.get(int(m2.group(1)))
    if not name: continue
    cn = name.split('-')[0]
    base = CN2PIN.get(cn)
    if base and base in ships:
        ships[base]['voices'].append('Audio/CV/' + fn)

# ---------- 舰船/剧情角色 分层重分类（收集完成后，按皮肤标记+阵营+维基+塞壬覆盖综合判定）----------
# 单一字段不可靠：塞壬 unknown* 带 900000+ 假 stats（误判 ship）；联动可玩船(hdn/DOA/海王星/NieR)缺 stats（误判 story）。
SIREN_PREFIX = re.compile(r'^(unknown|sairen|error|npc|linghangyuan|lingyangzhe|tansuozhe|aijiang|tbniang|congmang|missd|missr|magician)')
COLLAB_SKIN = re.compile(r'(_doa|_tolove|_idol|_idolns)')   # 联动/偶像皮肤只出现在可玩船上 → 判舰船
EXTRA_SHIP = {'haorenlichade'}                               # 用户确认的可玩船(Bon Homme Richard，仅 _alter 皮肤)
WIKI_NAMES = set(meta_by_cn.keys())
def reclassify():
    for s in ships.values():
        k = s['id']; name = s['name']
        if ('？' in name) or SIREN_PREFIX.match(k):          # 塞壬/BOSS/NPC：剧情角色 + 清空战斗属性
            s['category'] = 'story'; s['faction'] = ''; s['type'] = ''; s['rarity'] = ''
        elif s['faction'] or name in WIKI_NAMES or any(COLLAB_SKIN.search(sk['key']) for sk in s['skins']) or k in EXTRA_SHIP:
            s['category'] = 'ship'
        else:
            s['category'] = 'story'
reclassify()

# 每船 skins 排序（默认在前，皮肤号升序）
def skin_sort(s):
    return (s['label'] != '默认立绘', s['key'])
for sh in ships.values():
    sh['skins'].sort(key=skin_sort)
    sh['voiceCount'] = len(sh['voices'])

ship_list = sorted(ships.values(),
                   key=lambda s: (s['npc'], not s['hasCn'], s['faction'], s['type'], s['name']))

cnt = {
    'ships': len(ship_list), 'with_cn': sum(1 for s in ship_list if s['hasCn']),
    'skins': sum(len(s['skins']) for s in ship_list),
    'spine': len(skins and [k for k,v in skins.items() if v['spine']]),
    'live2d': sum(1 for v in skins.values() if v['live2d']),
    'with_voice': sum(1 for s in ship_list if s['voices']),
    'npc': sum(1 for s in ship_list if s['npc']),
    'with_faction': sum(1 for s in ship_list if s['faction']),
    'ship': sum(1 for s in ship_list if s['category'] == 'ship'),
    'story': sum(1 for s in ship_list if s['category'] == 'story'),
}
index = {'generated': 'v2', 'counts': cnt, 'ships': ship_list}
os.makedirs(GAL, exist_ok=True)
json.dump(index, open(os.path.join(GAL, 'index.json'), 'w', encoding='utf-8'),
          ensure_ascii=False)
# 同时输出 index.js，令 index.html 可直接以 file:// 双击打开时也能读到数据
js = json.dumps(index, ensure_ascii=False, separators=(',', ':'))
open(os.path.join(GAL, 'index.js'), 'w', encoding='utf-8').write('window.GALLERY=' + js + ';')

unmapped = [s['id'] for s in ship_list if not s['hasCn'] and not s['npc']]
lines = [f"统计 {cnt}", f"非NPC未映射 ({len(unmapped)}): {unmapped[:60]}", "样例:"]
for s in ship_list[:6]:
    lines.append(f"  {s['id']}->{s['name']} 皮肤{len(s['skins'])} spine{len(s['spineSkins'])} l2d{len(s['live2dSkins'])} 语音{s['voiceCount']}")
open(os.path.join(GAL, '_build_report.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
print('DONE', cnt)
