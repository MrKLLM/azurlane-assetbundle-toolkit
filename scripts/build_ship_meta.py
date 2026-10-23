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
import skin_table   # 皮肤表唯一读取口（azdata 快照 + 设备侧权威表逐字段合并）
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


# META 补桥表：游戏配置里「有船行、没有皮肤行」的 META 实体（tools/sharecfg_re/48 发布，§108）。
# 桥的起点是皮肤行，所以这类实体在 `painting2skin` 里根本不存在 —— 不补这一步，
# 她的立绘会被 `DERIV` 剥掉 `_alter` 折进**本体船**（实测显示成「灵敏 / 北方联合 / 精锐」）。
try:
    META_BRIDGE = json.load(open(os.path.join(GAMECFG, 'meta_group_bridge.json'), encoding='utf-8'))
except Exception:
    META_BRIDGE = {}


def load():
    # 皮肤表走唯一读取口：设备侧权威表能补出 azdata 快照缺的行（如 aierdeliqi_9 / mile_3）
    skin = skin_table.load()
    stats = json.load(open(os.path.join(AZDATA, 'azdata_ship_data_statistics.json'), encoding='utf-8'))
    # 舰船统计也走设备侧优先：社区快照对新船滞后（2026-10-23 实测 960017~960021 五组不在快照里），
    # 设备侧 4146 行含这些行；缺少时自动退回快照，不影响旧机器。
    dev_stats = os.path.join(GAMECFG, 'ship_data_statistics.json')
    if os.path.isfile(dev_stats):
        dv = json.load(open(dev_stats, encoding='utf-8'))
        skin_by_id = {int(v['id']): v for v in skin.values()
                      if isinstance(v, dict) and v.get('id') is not None}
        for k, v in dv.items():
            # 已有 azdata 行的一律保留旧值：stats 只补「社区快照完全没有」的新行，
            # 避免把受保护档的旧字段（尤其 META）改掉、让权威闸门判红。
            if k in stats:
                continue
            sid = v.get('skin_id')
            sk = skin_by_id.get(int(sid)) if sid is not None else None
            grp = int((sk or {}).get('ship_group') or 0)
            # META 组（970xxx）由 meta_group_bridge 负责；stats 不补，保持旧行为（§108/§176）。
            if 970000 <= grp <= 979999:
                continue
            stats[k] = v
    wpath = os.path.join(OUT, 'WikiData', 'ship_data.json')
    wiki = json.load(open(wpath, encoding='utf-8')) if os.path.exists(wpath) else []
    return skin, stats, wiki


PLACEHOLDER_EN = ('', 'simulation')


def pick_stats_row(cand, base_skin_id=None):
    """组内候选 stats 行 -> 代表行（选行规则的唯一正本，探针必须 import 这一份）。

    两级：① `(nationality, type, rarity)` 众数族；② 族内先避开占位英文名
    （`english_name` 为空或 `simulation`，全表 44 行），再优先「`id == 基皮肤 id`」的
    **配对行**，没有配对行才退回 `min(id)`。
    """
    tup = lambda r: (r.get('nationality'), r.get('type'), r.get('rarity'))
    modal = collections.Counter(tup(r) for r in cand).most_common(1)[0][0]
    reps = [r for r in cand if tup(r) == modal] or list(cand)
    clean = [r for r in reps if str(r.get('english_name') or '').strip().lower()
             not in PLACEHOLDER_EN] or reps
    paired = [r for r in clean if r.get('id') == base_skin_id]
    return min(paired or clean, key=lambda x: x['id'])


def build_indexes(skin, stats):
    skinid2skin = {v['id']: v for v in skin.values() if 'id' in v}
    # 舰级字段按 ship_group 归并：stats.skin_id -> 该皮肤所属组 -> 组级舰信息
    # （变体皮肤 gin_2 的 id 不被 stats.skin_id 直接引用，但与其基皮肤同 ship_group）
    by_group = collections.defaultdict(list)
    for sv in stats.values():
        g = skinid2skin.get(sv.get('skin_id'), {}).get('ship_group')
        if g is not None:
            by_group[g].append(sv)

    # 同一 painting 有 142 组多行（实测 2026-10-05，涉及 309 行）：剧情/NPC 那行先出现，
    # 而自机化时游戏**新增**一行同 painting 的行（带真 voice_actor + 能查到 stats 的 ship_group）。
    # 原先 `setdefault` 让首行胜出 ⇒ 17 张已自机化的卡（11 张 META + 霞飞/阿尔及利亚/不屈/
    # 沃克兰/弗兰德尔/加斯科涅）显示「无阵营 + 无语音」，而游戏里她们有 CV。
    # 判据只认「配音与舰级信息同时从无到有」这一种改判，并列一律维持首行：
    # ⚠️ 不能加"id 取大"当 tie-break——`qiye_dark`(企业→？？？？？)、`linghangyuan1_5`
    #    (超级AI-TC→？？)、`unknown5`(构建者→仲裁者) 都是**不同实体复用同一 painting**，
    #    号段大小不代表哪行是该目录的归属。判据与影响面由 diag/painting_dup_probe.py 复核。
    def _row_rank(r):
        good = (r.get('voice_actor') or -1) > 0 and r.get('ship_group') in by_group
        return 0 if good else 1

    painting2skin = {}
    spell = collections.defaultdict(set)
    for v in skin.values():
        p = v.get('painting')
        if not p:
            continue
        old = painting2skin.get(p)
        if old is None or _row_rank(v) < _row_rank(old):
            painting2skin[p] = v
        spell[str(p).lower()].add(p)
    # 大小写不敏感索引：配置里写 `2B_2`/`aijiangDD`/`npclafeiII_4`/`suweiaitongmengNew`，
    # 而磁盘 bundle 目录名一律小写 -> 精确比对会把这些整批判成"无源"（实测 27 个）。
    # 只收"该小写键全表只有一种拼法"的，避免 U556/u556 这类同键多拼法被猜错。
    painting_ci = {k: v for k, v in
                   ((k, painting2skin[min(s, key=str)])
                    for k, s in spell.items() if len(s) == 1)}
    # 组内基皮肤 = 该组 id 最小的皮肤行（默认立绘那一行）。选 stats 行时**先要求它的
    # skin_id 正是这个基皮肤**，再在候选里取最小 id。
    # 只按 min(stats.id) 选会被脏行打穿：`ship_data_statistics` 里有一行 id=900106，
    # name 写着「敦刻尔克」而 english_name 是 HMS Vampire、nationality=2 皇家、type=1 驱逐，
    # 它的 skin_id=904011 指向敦刻尔克的**皮肤2**（不是基皮肤 904010），于是被归进同一组，
    # 又因为 900106 < 904011 压过了正确的 4 行 ⇒ 画廊把敦刻尔克显示成「皇家·驱逐」，
    # 而游戏自己的表是「维希教廷·战巡」。全库 970 组里只有这一组改判。
    base_skin_of_group = {}
    for v in skin.values():
        g = v.get('ship_group')
        if g in by_group and (g not in base_skin_of_group or v['id'] < base_skin_of_group[g]):
            base_skin_of_group[g] = v['id']
    stats_by_group = {}
    # 代表行的选法抽成模块级 `pick_stats_row()`（探针必须 import 同一份，判据不许各写一份）。
    # 三轮判据演进（每轮都是上一轮被某种脏行打穿）：
    #  · 只按 min(stats.id)：id=900106 的脏行（name 写「敦刻尔克」而 english_name 是
    #    HMS Vampire、nationality=2 皇家、type=1 驱逐，skin_id=904011 指向敦刻尔克的**皮肤2**）
    #    压掉正确的 4 行 ⇒ 画廊把 敦刻尔克 显示成「皇家·驱逐」，游戏自己的表是「维希·战巡」。
    #  · 加「先要求 skin_id == 基皮肤」：脏行**可以本身就是基皮肤行**——id=900399 把 加斯科涅
    #    的 nationality 写成 2(皇家)、900398 把 弗兰德尔 的 type 写成 18(超巡)，同组其余 5 行
    #    都是 9(维希)/5(战列) ⇒ 再加「(阵营,舰种,稀有度) 众数族」。全库 969 组只有 11 组分歧。
    #  · 众数**并列**时 min(id) 会把别的实体的行端上来：组 900550 里 id=900406 写「埃塞克斯·META」、
    #    id=900550 写「萨拉托加·META」，三列全同而前者 id 更小 ⇒ 埃塞克斯·META 的名字被顶在
    #    `npcsalatuojia_alter.png` 上（那张与 `salatuojia_alter.png` **md5 逐字节相同**）。
    #    `stats.id == 基皮肤 id` 是游戏自己的配对信号，并列时优先它。实测全库只有这 1 组改判。
    # 影响面与反向对照：diag/stats_majority_probe.py。
    for g, vs in by_group.items():
        b = base_skin_of_group.get(g)
        cand = [s for s in vs if s.get('skin_id') == b] or vs
        stats_by_group[g] = pick_stats_row(cand, b)

    # 配对救援：皮肤行所在 ship_group 一条 stats 都查不到时，认「stats.id == 该皮肤行 id
    # 且清洗后同名」那一行。900xxx 段的游戏约定本来就是 stats.id 与 skin.id 同号
    # （`qiye_dark` 两侧都是 900072/900135），这里只是把写歪的交叉引用认回来，不是推断。
    # 实测全表只补回 2 条：`aisaikesi_alter`（埃塞克斯·META，nationality=97 ⇒ 独立成 META 卡）、
    # `nina_wjz`（妮娜·弗里德，联动战列，仍折在 nina 卡下）。影响面探针：diag/meta_idpair_probe.py。
    stats_by_skinid = {}
    for sv in stats.values():
        sk = skinid2skin.get(sv.get('id'))
        if not sk or sk.get('ship_group') in stats_by_group or not sv.get('nationality'):
            continue
        n1 = clean_ship_name(sv.get('name') or '')
        if not n1 or n1 != clean_ship_name(sk.get('name') or ''):
            continue
        stats_by_skinid[sk['id']] = sv

    return painting2skin, painting_ci, stats_by_group, stats_by_skinid


# 舰名尾缀清洗（2026-10-04，§93）
# ① `ship_data_statistics` 里有 10 个 NPC 行的**官方名自带方位标注**：
#    「（后排）」`BLACK★ROCK SHOOTER（后排）`/`基洛夫·META（后排）`/`拉斐尔`/`抚顺.改`/
#    `朴茨茅斯冒险号`/`云仙`/`虎`/`马可波罗（后排 原皮）`，
#    「（前排）」`比叡·META（前排）`/`克莱蒙梭（前排）`。
#    同一行的 `english_name` 是干净的（`BLACK★ROCK SHOOTER`）⇒ 去掉不丢信息。
#    `ship_skin_template` 那侧本来就没有这个后缀 ⇒ **两边不一致**才让旧产物看起来像"脏值"。
# ② 另有 7 个舰名在**源表里自带尾空格**（`宝多六花 ` / `筑紫 ` / `格里芬 ` / `焦苏埃·卡尔杜齐 ` /
#    `帕萨迪纳 ` / `新条茜 ` / `托里拆利 ` / `尼科洛索·达雷科 ` / `迪盖·特鲁因 `）。
#    ⚠️ 尾空格不是"错"——`仲裁者·英普拉·IV ` 也带尾空格且是真名。首尾空白对任何名字都不是
#    有效字符，顺带 strip 是安全的；但**别把它记成"表里有脏数据"**，源表就是这么写的。
# 用户 2026-10-04 裁定去掉方位标注。
#
# ⚠️ 判据必须收窄在「尾部 + 成对括号 + 括号内只含已知方位词」，否则会剥掉真名里的括号：
#    `克利夫兰(μ兵装)`（实测 26 个条目）、`泛用型强化武装(工作用)`、`Vow mode（誓言模式）`、
#    `Liebestrank（迷魂酒/爱情魔药）` 全部必须原样保留。实测 14 例正反对照全过。
_NAV_SUF = re.compile(r'[（(]\s*(?:后排|前排)(?:\s*原皮)?\s*[)）]\s*$')
def clean_ship_name(v):
    """去掉舰名尾部的「（后排）」「（前排）」「（后排 原皮）」这类方位标注，并 strip 首尾空白。"""
    prev = None
    v = (v or '').strip()
    while prev != v:
        prev = v
        v = _NAV_SUF.sub('', v).strip()
    return v


def resolve_base(stem, painting2skin, painting_ci, stats_by_group=None, bridge=None):
    """磁盘 stem -> (基painting, source, 皮肤行)。

    ⚠️ `bridge`（META 补桥表）的优先级排在**皮肤表命中之后、继续剥后缀之前**：
    补桥表里的键（`lingmin_alter`）在游戏表里确实没有皮肤行，但它是**该实体自己的资源名**
    （出处是剧情行 900549 的 `prefab` 列）。如果先剥到 `lingmin`，就把 META 实体并进了本体船。
    命中时第三个返回值不是皮肤行，而是那条补桥记录 —— 调用方按 `source` 以 `bridge` 开头分流。

    逐层剥后缀，**每一层都先精确、后大小写不敏感**（不是"精确走完再回退"）。
    根因：`DERIV` 把 `ii|iii|iv` 当变体后缀，于是 `dahuangfengii` 剥一层就撞上基船
    `dahuangfeng`，而表里明明有它自己那行 `dahuangfengII` —— 实体名里的罗马数字被
    当成了"第二套皮肤"，船名于是丢了 `II`。整名能在 ci 索引里命中，说明表里就有
    这个资源名（只差大小写），它比"剥出来的另一个名字"更接近正身。
    ci 命中还要**该行的 ship_group 有舰级统计**才算终，否则继续剥：`xia_DOA_wjz` 整名
    确实命中一行(900302)，但那是没有舰级字段的剧情资源行，剥一层得到的 `xia_DOA`
    才是同一实体带舰级字段的那行。走完都没有，才用第一个 ci 命中兜底。
    """
    s = stem
    ci_fb = None
    for depth in range(8):
        if s in painting2skin:
            return s, ('painting' if depth == 0 else 'suffix'), painting2skin[s]
        k = s.lower()
        r = painting_ci.get(k)
        if r is not None:
            ent = (r.get('painting') or k, ('painting_ci' if depth == 0 else 'suffix_ci'), r)
            if stats_by_group is None or r.get('ship_group') in stats_by_group:
                return ent
            if ci_fb is None:
                ci_fb = ent
        if bridge:
            bk = s.lower()
            if bk in bridge:
                return bk, ('bridge' if depth == 0 else 'bridge_suffix'), bridge[bk]
        ns = DERIV.sub('', s)
        if ns == s:
            break
        s = ns
    if ci_fb is not None:
        return ci_fb
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


def bundle_ids(work=None):
    """画廊用到的全部磁盘 bundleID（立绘目录名为主，含 spine/live2d/cg 目录）。

    `work` = `.diag/pipeline`：本轮新皮肤在换入前只存在于临时区，不扫它就会漏掉
    （2026-10-23 实测：meta 跑在 paintings 换入之前，36 个新 stem 一个都没进 ship_meta）。
    """
    ids = set()
    for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')):
        ids.add(os.path.splitext(os.path.basename(p))[0])
    for sub in ('Spine_v2', 'Live2D', 'CG_v2'):
        for d in glob.glob(os.path.join(OUT, sub, '*')):
            if os.path.isdir(d):
                ids.add(os.path.basename(d))
    if work:
        for p in glob.glob(os.path.join(work, 'Paintings_v2', '*.png')):
            ids.add(os.path.splitext(os.path.basename(p))[0])
        for sub in ('Spine_v2', 'Live2D'):
            for d in glob.glob(os.path.join(work, sub, '*')):
                if os.path.isdir(d):
                    ids.add(os.path.basename(d))
    return ids


def build_meta(skin, stats, wiki, verbose=False, work=None):
    painting2skin, painting_ci, stats_by_group, stats_by_skinid = build_indexes(skin, stats)
    wiki_by_name = {x['name']: x for x in wiki if x.get('name')}
    meta = {}
    for stem in sorted(bundle_ids(work)):
        base, source, sk_row = resolve_base(stem, painting2skin, painting_ci, stats_by_group,
                                            META_BRIDGE)
        entry = {'cn': stem, 'en': '', 'faction': '', 'type': '', 'rarity': '',
                 'voice_actor': 0, 'category': 'story', 'base_painting': base, 'source': source or 'unresolved'}
        if source and source.startswith('bridge'):
            # META 补桥：舰级取自 `ship_data_group`（阵营/舰种），稀有度**表里没有 ⇒ 留空**。
            # ⚠️ 不要按 `cn` 去维基兜底 —— 那个名字去掉「·META」就是本体船（灵敏=北方联合/精锐），
            #      兜底会把 META 实体的阵营改成本体，正是 §101 那条「零回退不变式」要拦的方向。
            b = sk_row
            va = b.get('voice_actor', -1)
            entry.update({'cn': b['cn'], 'faction': b['faction'], 'type': b['type'],
                          'rarity': b['rarity'], 'category': 'ship', 'voice_actor': va,
                          'voice_actor_name': VOICE_ACTOR.get(str(va), ''),
                          'skin_name': b['cn'], 'nationality_code': b['nationality_code'],
                          'type_code': b['type_code'], 'meta_group': b['group'],
                          'voice_bank': b['bank'], 'meta_via': b['via']})
            if 'rarity_code' in b:      # 只在补桥表**显式声明过**时才写（稀有度配置侧没有字段）
                entry['rarity_code'] = b['rarity_code']
            if b.get('confirmed_via'):
                entry['confirmed_via'] = b['confirmed_via']
            meta[stem] = entry
            continue
        if base:
            sk = sk_row
            entry['voice_actor'] = sk.get('voice_actor', 0)
            entry['voice_actor_name'] = VOICE_ACTOR.get(str(entry['voice_actor']), '')
            # skin_template.name 是「皮肤名」(常含 {namecode} 占位符，或是皮肤主题标题如"午夜的瑰色电梯")，
            # 不能当舰名；另存 skin_name 备用。舰名取自 statistics.name(0 占位符，实测 4119/4119 皆真名)。
            entry['skin_name'] = sk.get('name') or stem
            sv = stats_by_group.get(sk.get('ship_group')) or stats_by_skinid.get(sk.get('id'))
            # 新船的 stats 行常常只有 `_2` 皮肤那一行（skin_id 指向本体），本体行不在表里；
            # 直接查 sk.id 会落空。补一次「按基 painting 的本体 id 查」。
            if sv is None and base:
                base_row = painting2skin.get(base) or {}
                base_id = base_row.get('id')
                if base_id is not None:
                    sv = stats_by_skinid.get(base_id)
            if sv is not None and sk.get('ship_group') not in stats_by_group:
                # 走的是「stats.id == 皮肤行 id 且同名」配对救援，记下来源便于逐条回查
                entry['stats_via'] = 'id_pair:%s' % sv.get('id')
            if sv:
                entry['cn'] = clean_ship_name(sv.get('name')) or sk.get('name') or stem
                entry['en'] = sv.get('english_name', '')
                entry['faction'] = NATIONALITY.get(sv.get('nationality'), '其他')
                entry['rarity'] = RARITY.get(sv.get('rarity'), '')
                entry['type'] = TYPE.get(sv.get('type'), '')
                entry['nationality_code'] = sv.get('nationality')
                entry['rarity_code'] = sv.get('rarity')
                entry['type_code'] = sv.get('type')
                entry['category'] = 'ship'
            else:
                # 皮肤行没有对应舰级行时，`name` 是**皮肤标题**（如"超级AI-TC""入浴的小恶魔"），不是实体名。
                # 若这张立绘同时是指挥室秘书舰 NPC 的换装（在 secretary 表里），实体名取表内 name，
                # 皮肤标题保留在 skin_name；两边都是配置里的原文，不做任何推断。
                rec = (NPC_PAINTING.get(str(sk.get('painting') or '').lower())
                       or NPC_PAINTING.get(stem.lower()))
                entry['cn'] = (rec or {}).get('cn') or sk.get('name') or stem
                if rec:
                    # 记下命中的表键（变体皮肤 `_n` 等的基资源名），便于事后逐条回查
                    key = (str(sk.get('painting') or '').lower()
                           if str(sk.get('painting') or '').lower() in NPC_PAINTING else stem.lower())
                    entry['name_via'] = 'npc_table:' + key
        else:
            # painting 未命中 -> 秘书舰 NPC 表 / 同族前缀 -> ship_name_map 兜底 -> manual 怪例表
            pfx, src, row, npc_cn = resolve_story_fallback(stem, painting_ci)
            if src:
                entry['source'] = src
                sv = stats_by_group.get((row or {}).get('ship_group'))
                name = clean_ship_name((sv or {}).get('name')) or (row or {}).get('name') or npc_cn
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
    ap.add_argument('--out', default=None,
                    help='配合 --write 指定落盘目录（临时目录比对用），默认 Output/')
    ap.add_argument('--work', default=None,
                    help='额外扫描的临时区（如 .diag/pipeline；换入前的新皮肤只在这里）')
    args = ap.parse_args()

    skin, stats, wiki = load()
    meta, painting2skin, stats_by_group, wiki_by_name = build_meta(
        skin, stats, wiki, work=args.work)
    print_diag(meta, wiki_by_name)

    if args.write:
        path = os.path.join(args.out or OUT, 'ship_meta.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        json.dump(meta, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        print(f'\n[WRITE] 已产出 {path}  ({len(meta)} 条)')


if __name__ == '__main__':
    main()
