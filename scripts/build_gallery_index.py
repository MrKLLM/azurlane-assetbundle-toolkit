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
GAL = os.path.join(OUT, 'gallery_v2')

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

# ---------- 收集 skins（key=完整stem）----------
skins = {}   # stem -> {key,label,base,image,spine_dir,live2d}
ships = {}   # base -> ship dict

def ship_of(base):
    if base in ships:
        return ships[base]
    cn = SHIP_NAME_MAP.get(base)
    meta = meta_by_cn.get(cn, {}) if cn else {}
    npc = bool(re.match(r'(npc|linghangyuan|lingyangzhe)', base))
    ships[base] = {
        'id': base, 'name': cn or base, 'hasCn': bool(cn), 'npc': npc,
        'type': meta.get('ship_type', '') or ('NPC' if npc else ''),
        'rarity': meta.get('rarity', ''), 'faction': meta.get('faction', ''),
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
