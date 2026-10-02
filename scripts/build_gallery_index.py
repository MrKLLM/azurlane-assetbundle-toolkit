#!/usr/bin/env python3
"""构建资产浏览器索引 index.json（v2 合并逻辑）。
所有资产按「归一化基ID → 完整皮肤stem」挂载，Spine/Live2D 绑定到对应 skin。
"""
import sys, os, re, json, glob
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import skin_table  # 皮肤表唯一读取口（azdata 快照 + 设备侧权威表逐字段合并）
from ship_name_map import SHIP_NAME_MAP

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
OUT = os.path.join(ROOT, 'Output')
# 支持 GALLERY_OUT_DIR 环境变量把产物写到临时目录，供改造后小规模比对，默认写正式 gallery_v2
GAL = os.environ.get('GALLERY_OUT_DIR') or os.path.join(OUT, 'gallery_v2')

# ---------- 语音/台词权威源：skin_voice.json（scripts/extract_cv_voice.py 从 cue/cv-*.b 导出）----------
# 旧口径是「社区 CV_MAP(719 条) → 中文名 → 拼音」归并 Output/Audio/CV/*.wav，
# 结果 740/1008 组船显示「语音 0」而其中 590 组其实有语音（docs/TROUBLESHOOTING.md §47）。
SKIN_VOICE = {}
_sv_path = os.path.join(OUT, 'gallery_v2', 'skin_voice.json')
if os.path.exists(_sv_path):
    SKIN_VOICE = json.load(open(_sv_path, encoding='utf-8'))

# 台词正文（scripts/build_skin_words.py）：给「有表行但主包没下发」的皮肤补 voiceText，
# 少这一步就是 44 张明明有台词却在语音页整页空白（§57 / §6 第 16 条）。缺文件不许静默当 0。
_sw_path = os.environ.get('GALLERY_WORDS_PATH') or os.path.join(OUT, 'gallery_v2', 'skin_words.json')
if not os.path.exists(_sw_path) and not os.environ.get('GALLERY_ALLOW_NO_WORDS'):
    raise SystemExit('缺 %s —— 先跑 py -3 scripts/build_skin_words.py 再建索引；'
                     '确实不需要台词字段时用 GALLERY_ALLOW_NO_WORDS=1 显式放行' % _sw_path)
SKIN_WORDS = json.load(open(_sw_path, encoding='utf-8')) if os.path.exists(_sw_path) else {'m': {}, 'w': {}}

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
# 配置表里有一类值**根本不是名字**：游戏自己用遮蔽块字符（▅▇■ 等 U+2580–U+259F）表示被和谐掉的
# 字，还有一整串问号、以及长的拼音/十六进制回显。一旦当组名用，卡片上就会出现
# `▅海▊▇洛▅■芬特▇▆`（实测组 hierophant）或 `？？？`（实测 dosair / unknown1）。
# 判据按「像不像一个真名」写，**不按组名开例外名单**。
# ⚠️ 纯 ASCII 那条只挡**长串**：`2B` / `A2` 是尼尔联动角色的真名（实测被误杀过一次），
#    而 `544845544F574552`、`ladyE` 这类才是回显 —— 用长度 5 分开这两类。
NOT_A_NAME = re.compile(r'^[\s？?！!。，,、\-—·]*$|[\u2580-\u259f]|^[A-Za-z0-9_\-\.\s]{5,}$')
def _derived(cn, e):
    """这个名字能撑起的三项字段（配置优先、Wiki 按中文名兜底）。"""
    m = meta_by_cn.get(cn, {}) if cn else {}
    return (bool(e.get('faction') or m.get('faction', '')),
            bool(e.get('type') or m.get('ship_type', '') or m.get('type', '')),
            bool(e.get('rarity') or m.get('rarity', '')))


def _emptier(a, b):
    """a 是否比 b 少撑起至少一项、且一项都没多起来。"""
    return any((not x) and y for x, y in zip(a, b)) and not any(x and not y for x, y in zip(a, b))


def _clean_cn(v):
    """占位符/空/不像真名的 cn 视为无有效名；首尾空白先去掉再判
    （实测 `仲裁者·英普拉·IV ` 带一个尾空格 —— 那是真名，不该和占位符一起被挡）。"""
    v = (v or '').strip()
    return '' if (not v or PLACEH.search(v) or NOT_A_NAME.search(v)) else v

# 社区快照/拼音表译名与游戏官方中文名差异修正（与 build_ship_meta 保持一致，兜底路径也生效）
NAME_FIX = {'贾斯科涅': '加斯科涅'}

PINS = set(SHIP_NAME_MAP.keys())
ROMAN = {'ii': '改', 'iii': '改三', 'iv': '改四'}
# 后缀真实语义（用户 2026-09-20 确认）：_hx 是和谐处理版立绘（非调色变体），_n 是不显示背景的立绘（非夜战场景）
VARMAP = {'hx': '和谐版', 'n': '无背景版', 'g': 'G', 'meta': 'META', 'asmr': 'ASMR', 'gv': '改造'}
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

# 能当组名用的来源档：走通配置桥（含大小写不敏感回退）、或从 NPC 立绘表/同族前缀查到，
# 以及人工核验过的 manual。不含 fallback（手抄表，另有更高优先级通道）与 unresolved。
AUTHORITATIVE_CN = {'painting', 'suffix', 'painting_ci', 'suffix_ci',
                    'npc_table', 'npc_suffix', 'npc_family', 'family', 'manual'}

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
    # 同 base 兄弟上的配置权威名：base 是**合成前缀**（`linghangyuan1`/`nabulesi` 这类不是任何
    # stem 的组键）、或组键自己那条没解析出阵营时，兄弟里可能恰恰带着干净的真名。
    # 要求该条目的 source 属于「从表里查到」的档，否则 cn 可能只是未被解析的拼音回显。
    sib_name = ''
    if e.get('source') in AUTHORITATIVE_CN:
        s = _clean_cn(e.get('cn') or '')
        sib_name = '' if s == base else s
    # ⚠️ 2026-09-29 用户拍板：兜底顺序改成**配置优先**，含已知错名的手抄表 SHIP_NAME_MAP 退到最后
    # （旧顺序下 80 个组显示的是手抄表名而配置里另有真名，如 missr R小姐→好人理查德、
    #   aijiang 海酱→绊爱、strength 力量→仲裁者·司特莲库斯·VIII）。
    # 配置名要先过 `_clean_cn` 那道"像不像真名"的闸——挡掉 `？？？`/遮蔽块/纯 ASCII 之后，
    # 这些组**保留手抄表名**，因为换了就是把占位符摆到卡片上。
    cn = name_meta or sib_name or SHIP_NAME_MAP.get(base) or ''
    cn = NAME_FIX.get(cn, cn)   # 官方译名修正（兜底路径也生效）
    # ⚠️ 零回退不变式：**改名不得让阵营/舰种/稀有度变得比原来更空**。
    #    这三项是「配置优先，Wiki 按中文名兜底」，所以换一个名字会连带换掉 Wiki 那一跳的命中——
    #    实测 kelei 从手抄表的「可畏」换成配置的「柯蕾」后，皇家/航母/超稀有 全掉、
    #    category 从 ship 翻成 story。这类"名字更权威但字段塌了"的配置名一律不用。
    hand = NAME_FIX.get(SHIP_NAME_MAP.get(base) or '', SHIP_NAME_MAP.get(base) or '')
    if cn and hand and cn != hand and _emptier(_derived(cn, e), _derived(hand, e)):
        cn = hand
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
        'skins': [], 'spineSkins': [], 'live2dSkins': [],
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
SPINE_NO_PARTS = []      # 有 .skel 却没有 parts.json 的目录 —— 攒起来末尾非零退出
for d in glob.glob(os.path.join(OUT, 'Spine_v2', '*')):
    if not os.path.isdir(d): continue
    stem = os.path.basename(d)
    if not glob.glob(os.path.join(d, '*.skel')):
        continue          # 空壳目录（如 fulangxisike_2 只有一个散 PNG），本来就没有可合成的层
    # 分层只认 prefab 权威清单，**不再按目录 glob 猜**：同目录里除了真分层还躺着
    # `_hx`（和谐版）等变体的 skel，它们不是层、是另一张画 —— 实测 30 个目录被多画、
    # 15 对本体/_hx 的 CG 因此逐像素完全相同（docs/TROUBLESHOOTING.md §58）。
    pj = os.path.join(d, 'parts.json')
    if not os.path.isfile(pj):
        # 刻意不回落到 glob：回落等于把这个 bug 换个地方留着，只是没人再看得见。
        # 由 `extract_spine_v2.py --parts-only` 补齐后再来。
        SPINE_NO_PARTS.append(stem)
        continue
    layers = json.load(open(pj, encoding='utf-8'))['layers']
    # 维持原有的绘制序（B<M<T、bg 最底）——本轮只改「有哪几层」，不动「层的先后」，
    # 免得一次改动混进两个视觉变量。active 过滤当前是全 true 的 no-op，留着表达意图。
    parts = sorted((l['layer'] for l in layers if l.get('active') is not False),
                   key=layer_order)
    base = normalize(stem)
    sk = skins.get(stem)
    if sk is None:
        add_skin(stem, '')
        sk = skins[stem]
    sk['spine'] = {'folder': stem, 'parts': parts}
    ship_of(base)['spineSkins'].append(stem)
if SPINE_NO_PARTS:
    print(f"! {len(SPINE_NO_PARTS)} 个 Spine 目录有 .skel 但没有 parts.json —— "
          f"分层的权威清单缺失，拒绝猜。先跑 `py -3 scripts/extract_spine_v2.py --parts-only`。"
          f"\n  清单: {SPINE_NO_PARTS[:20]}")
    sys.exit(1)

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

# 皮肤级语音计数：skin_voice.json 的键就是画廊 bundleID，逐皮肤挂条数与「可点击出声」标记
VOICE_ORPHAN = 0
for stem, e in SKIN_VOICE.items():
    sk = skins.get(stem)
    if sk is None:
        VOICE_ORPHAN += 1          # 测试残留(22/33/unknown3)等 JUNK 皮肤不进索引
        continue
    files = {l.get('f') for l in (e.get('lines') or []) if l.get('f')}
    sk['voiceCount'] = len(files)
    sk['voiceTap'] = bool(e.get('tap'))

# ---------- 变体包语音（主包本地缺失时盘上仅剩的 -gift / -battle 导出）----------
# 包号来自游戏自己的皮肤表（painting → 皮肤行 id // 10），不再走社区 CV_MAP 那条归并链。
# 一个 painting 若同时属于两个发声实体（如 lafei 既是舰船 10117 也是剧情角色 90024），
# 就把这一档**整体放弃**——按 §47 的教训，派错声比留空更糟。
SKIN_ROWS = {}
for _r in skin_table.load().values():
    if isinstance(_r, dict):
        _p = str(_r.get('painting') or '').strip().lower()
        if _p:
            SKIN_ROWS.setdefault(_p, set()).add(int(_r.get('id') or 0) // 10)
VARIANT_PACK = {}
for _f in glob.glob(os.path.join(OUT, 'Audio', 'CV', 'cv-*.wav')):
    _m = re.match(r'cv-(\d+)-(\w+)\.wav$', os.path.basename(_f))
    if _m:
        VARIANT_PACK.setdefault(int(_m.group(1)), []).append('Audio/CV/' + _m.group(0))
VAR_TAIL = re.compile(r'(_hx|_n|_rw|_bj|_jz|_alter|_heihei|_hei)+$')
VOICE_EXTRA = 0
for stem, sk in skins.items():
    if sk.get('voiceCount'):
        continue
    cands = {stem.lower(), VAR_TAIL.sub('', stem.lower())}
    packs = set()
    for c in cands:
        packs |= SKIN_ROWS.get(c, set())
    hits = sorted({f for p in packs for f in VARIANT_PACK.get(p, [])})
    # 「歧义」的判据是**命中的包号**而不是候选包号：lafei 同名有舰船(10117)与剧情角色(90024)两行，
    # 但盘上只有 cv-10117-gift.wav ⇒ 唯一命中，归属没有二义；两个号都有变体包时才放弃。
    if len({p for p in packs if p in VARIANT_PACK}) == 1:
        sk['voiceExtra'] = hits
        VOICE_EXTRA += 1

# ---------- 「只有台词、没有音频」的那批皮肤 ----------
# 判据与 build_skin_words.py 的第二趟同源：语音表里没这条皮肤、词表 m 里有 ⇒ 台词能显示、不能播。
# voiceCount 语义不变（仍= 可播音频条数），只加一个新字段，前端据此放行语音标签。
_W_M = SKIN_WORDS.get('m') or {}
_W_W = SKIN_WORDS.get('w') or {}
VOICE_TEXT_ONLY = 0
for stem, sk in skins.items():
    if sk.get('voiceCount'):
        continue
    sid = _W_M.get(stem)
    n = len(_W_W.get(sid) or {}) if sid else 0
    if n:
        sk['voiceText'] = n
        VOICE_TEXT_ONLY += 1


def ship_voice_text(sh):
    """船级「台词条数（无可播音频的那些皮肤）」——语音标签能不能放行要看这个 + voiceCount。"""
    return sum(sk.get('voiceText') or 0 for sk in sh['skins'] if not sk.get('voiceCount'))


def ship_voice_count(sh):
    """船级「语音 N 条」= 该船全部皮肤去重后的音频文件数（同一包同一条台词只算一次）。"""
    files = set()
    for sk in sh['skins']:
        e = SKIN_VOICE.get(sk['key'])
        if e:
            files |= {l.get('f') for l in (e.get('lines') or []) if l.get('f')}
        files |= set(sk.get('voiceExtra') or [])
    return len(files)

# ---------- 舰船/剧情角色 分层重分类（收集完成后，按皮肤标记+阵营+维基+塞壬覆盖综合判定）----------
# 单一字段不可靠：塞壬 unknown* 带 900000+ 假 stats（误判 ship）；联动可玩船(hdn/DOA/海王星/NieR)缺 stats（误判 story）。
SIREN_PREFIX = re.compile(r'^(unknown|sairen|error|npc|linghangyuan|lingyangzhe|tansuozhe|aijiang|tbniang|congmang|missd|missr|magician)')
COLLAB_SKIN = re.compile(r'(_doa|_tolove|_idol|_idolns)')   # 联动/偶像皮肤只出现在可玩船上 → 判舰船
# 用户确认的可玩船(Bon Homme Richard，仅 _alter 皮肤) + story_review.md 勾选的 31 条自机（2026-09-20）
EXTRA_SHIP = {'haorenlichade',
    'lafeiii','i404','tansuozhe','2b','a2','suweiaitongmengnew','linghangyuan3','lingyangzhe3',
    'i13','i168','i19','i25','i26','i56','i58','hdn101','hdn102','lanliii','congmang',
    'aijiang','aijiangbb','aijiangcl','aijiangcv','aijiangdd',
    'vtuber_aqua_wjz','vtuber_ayame_wjz','vtuber_fubuki_wjz','vtuber_matsuri_wjz',
    'vtuber_mio_wjz','vtuber_shion_wjz','vtuber_sora_wjz'}
WIKI_NAMES = set(meta_by_cn.keys())
def reclassify():
    for s in ships.values():
        k = s['id']; name = s['name']
        if k in EXTRA_SHIP:                                    # 用户勾选确认的自机：舰船 + 保留 ship_meta 属性
            s['category'] = 'ship'
        elif ('？' in name) or SIREN_PREFIX.match(k):          # 塞壬/BOSS/NPC：剧情角色 + 清空战斗属性
            s['category'] = 'story'; s['faction'] = ''; s['type'] = ''; s['rarity'] = ''
        elif s['faction'] or name in WIKI_NAMES or any(COLLAB_SKIN.search(sk['key']) for sk in s['skins']):
            s['category'] = 'ship'
        else:
            s['category'] = 'story'
reclassify()

# 每船 skins 排序（默认在前，皮肤号升序）
def skin_sort(s):
    return (s['label'] != '默认立绘', s['key'])
for sh in ships.values():
    sh['skins'].sort(key=skin_sort)
    sh['voiceCount'] = ship_voice_count(sh)
    vt = ship_voice_text(sh)
    if vt:
        sh['voiceText'] = vt          # 只在有值时写，避免给 964 组船凭空加一个 0

ship_list = sorted(ships.values(),
                   key=lambda s: (s['npc'], not s['hasCn'], s['faction'], s['type'], s['name']))

cnt = {
    'ships': len(ship_list), 'with_cn': sum(1 for s in ship_list if s['hasCn']),
    'skins': sum(len(s['skins']) for s in ship_list),
    'spine': len(skins and [k for k,v in skins.items() if v['spine']]),
    'live2d': sum(1 for v in skins.values() if v['live2d']),
    'with_voice': sum(1 for s in ship_list if s['voiceCount']),
    'voice_skins': sum(1 for v in skins.values() if v.get('voiceCount')),
    'voice_text_skins': VOICE_TEXT_ONLY,        # 只有台词、没有可播音频的皮肤（§6 第 16 条）
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
lines = [f"统计 {cnt}",
         f"语音源未命中索引的皮肤 {VOICE_ORPHAN}（JUNK/未导出目录），"
         f"skin_voice 共 {len(SKIN_VOICE)} 皮肤",
         f"非NPC未映射 ({len(unmapped)}): {unmapped[:60]}", "样例:"]
for s in ship_list[:6]:
    lines.append(f"  {s['id']}->{s['name']} 皮肤{len(s['skins'])} spine{len(s['spineSkins'])} l2d{len(s['live2dSkins'])} 语音{s['voiceCount']}")
open(os.path.join(GAL, '_build_report.txt'), 'w', encoding='utf-8').write('\n'.join(lines))
print('DONE', cnt)
