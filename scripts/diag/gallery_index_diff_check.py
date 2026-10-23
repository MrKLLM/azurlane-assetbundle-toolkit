#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gallery_index_diff_check.py — 画廊索引重建前后的**零回退闸门**（只读，退出码即结论）。

为什么需要：`build_gallery_index.py` 一次写出 1008 组船 / 4491 皮肤，改口径时最容易
"顺手把别的字段也改了"或"某类船整块掉出去"，而这两类错都**不会报错**。
本闸门把两份 index.json 逐船逐皮肤比标量，并把「允许变化的字段」写成显式白名单：
白名单之外的任何差异 = 回退 = 非零退出。

`voiceCount` 归零要分两种，且**不许写船名例外名单**，用游戏自己的皮肤表判：
  · 旧口径那些 `Audio/CV/cv-<N>-*.wav` 的包号 N，在该船任何皮肤的游戏表行（painting → id//10）
    里**一个都不出现** ⇒ 旧语音本就是别人的（如 可畏 cv-20705 被社区 CV_MAP 派给 柯蕾）
    ⇒ 归零属**修正**，只计数不判红；
  · 只要有一个包号对得上 ⇒ 这个包是这艘船自己的，归零就是**丢了声音** ⇒ 判红。

用法:
  py -3 scripts/diag/gallery_index_diff_check.py <旧 index.json> <新 index.json> [--allow voiceCount]
退出码: 0 通过 / 1 有白名单外的差异 / 2 参数或文件读不了。
"""
import os, sys, re, json, argparse, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEF_AZDATA = os.path.join(ROOT, 'inputs', 'azdata', 'azdata_ship_skin_template.json')
VAR_TAIL = re.compile(r'(_hx|_n|_rw|_bj|_jz|_alter|_heihei|_hei)+$')
# 黑化后缀 = 独立发声实体（2026-10-02 用户裁定，见 docs/TROUBLESHOOTING.md §84）
HEI_TAIL = re.compile(r'(_heihei|_hei)$')
# 「其他」档判据取索引器的唯一正本（同一套语义写两份 = §85 那批错派的成因）
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from gallery_buckets import is_other      # noqa: E402


def empty(v):
    """标量"没有值"的口径：None / 空串 / 空列表 / 0 都算空。
    闸门要靠它区分「补全」与「回退」——把 `None→12` 叫回退是方向判反（本轮 23 处误报）。"""
    return v is None or v == '' or v == [] or v == 0


# 索引里的船级标量 ←→ `ship_meta.json` 的字段名对照
META_FIELD_FOR = {'name': 'cn', 'faction': 'faction', 'type': 'type', 'rarity': 'rarity'}


def meta_blessed_ship(sid, k, a, b, mo, mn):
    """这处船级标量变化必须**两头都对上元数据**：旧值 == 旧 ship_meta，新值 == 新 ship_meta。

    为什么要求两头：只对新值的话，"索引自己漂到新值"和"索引跟着元数据改"分不开；
    旧值也对不上就说明这条改动不是从元数据派生的（索引器漂移），必须判红。
    元数据本身能改什么由 `ship_meta_authority_diff` 的方向性判据把关，这里只做同源核对。
    """
    if not mn or k not in META_FIELD_FOR:
        return False
    f = META_FIELD_FOR[k]
    ov = str((mo.get(sid) or {}).get(f, '') or '')
    nv = str((mn.get(sid) or {}).get(f, '') or '')
    return ov == str(a.get(k) or '') and nv == str(b.get(k) or '') and ov != nv


def meta_blessed_skin(key, av, bv, mo, mn):
    """皮肤 label 的变化必须能由**该皮肤自己那行元数据的舰名变化**逐字推导出来。

    例：`xiafei_hx.label` 「霞飞-战斗天使·和谐版」→「霞飞·和谐版」，
    正好等于把旧 label 里的旧 `cn` 换成新 `cn`。推不出来就是索引器自己改的字，判红。
    """
    if not mn or av is None or bv is None:
        return False
    o, n = mo.get(key) or {}, mn.get(key) or {}
    if o == n:
        return False
    oc, nc = str(o.get('cn') or ''), str(n.get('cn') or '')
    return bool(oc) and bool(nc) and oc != nc and str(bv) == str(av).replace(oc, nc)


def skin_packs(azdata):
    """painting(小写) → 该立绘所属语音包号集合（皮肤行 id // 10）。"""
    d = json.load(open(azdata, encoding='utf-8'))
    out = collections.defaultdict(set)
    for r in d.values():
        if not isinstance(r, dict):
            continue
        p = str(r.get('painting') or '').strip().lower()
        if p:
            out[p].add(int(r.get('id') or 0) // 10)
    return out


def old_pack_of(path):
    m = re.search(r'cv-(\d+)', os.path.basename(path))
    return int(m.group(1)) if m else None


def scalars(d, skip):
    """只滤掉结构性字段（列表/字典另比），**允许变化的字段必须仍参与比较**——
    早版在这里把白名单字段一起剔掉，于是「voiceCount 归零」那条判据永远走不到 = 假绿灯。"""
    return {k: v for k, v in d.items() if k not in skip and not isinstance(v, (list, dict))}


def index_of(doc):
    ships = {s['id']: s for s in doc['ships']}
    skins = {}
    for s in doc['ships']:
        for sk in s['skins']:
            skins[sk['key']] = dict(sk, _ship=s['id'])
    return ships, skins


def diff(old, new, allow_ship, allow_skin, packs, expect=None, meta=None):
    expect = expect or {}
    mo, mn = meta or ({}, {})
    o_s, o_k = index_of(old)
    n_s, n_k = index_of(new)
    # 皮肤级声明：--expect 传 {"<皮肤key>": {...}} 时按皮肤 key 取，{"<船id>": {...}} 时按船取。
    # ⚠️ 键空间**可能重叠**（`kelaimengsuo` 既是船 id 也是皮肤 key），靠 `k in o_k` 单判会
    # 让它只走皮肤那条、船级声明永不被检查（实测：篡改船名后报的是皮肤的错）。
    # ⇒ 用 `label` / `name` 这种**字段名**区分两套语义，而不是靠键本身。
    expect_skin = {k: v for k, v in expect.items()
                   if k in o_k and 'label' in v}
    rep = collections.Counter()
    bad = []
    misfit = []

    # 「掉出索引」只有一种是合法外迁：这条确实搬进了 `new['silhouettes']`（§88：`_hei` 是剧情黑脸
    # 剪影，不是皮肤，2026-10-03 用户拍板移出皮肤区）。放行是**双向可核**的——条目必须真的出现在
    # 新版剪影清单里，且键满足黑化后缀，还不得同时留在皮肤区里；所以这不是按名字开的例外名单，
    # 拿它掩盖一次真删除会在下面三条断言里撞车。
    sil = {s.get('key') for s in (new.get('silhouettes') or []) if s.get('key')}
    # 剪影区现在住两类东西（用户 2026-10-03 / 10-04 两次拍板）：
    #   ① `_hei`/`_heihei` 黑脸剪影（§88/§90）
    #   ② 探索者连线关卡 NPC（`tansuozhe*`/`lingyangzhe*`/`linghangyuan*`，§93）——
    #      权威表里一行都没有，不是任何舰船的皮肤。
    # ⚠️ 原来这里只认 `_hei`，探索者 NPC 一进来就报「混进了非 _hei 条目」；
    #   连带它们原来那张卡（linghangyuan1 等 19 艘）在下面被报「船掉出索引」。
    # 判据按"键形态"写死，不按名字开例外清单。
    EXPLORER = re.compile(r'^(?:npc)?(?:tansuozhe|lingyangzhe|linghangyuan)\d*(?:_\d+)*(?:_n)?$')
    not_sil_kind = sorted(k for k in sil
                          if not HEI_TAIL.search(k.lower()) and not EXPLORER.match(k.lower()))
    if not_sil_kind:
        bad.append('剪影清单里有既非 `_hei` 也非探索者 NPC 的条目: %s' % not_sil_kind[:5])
    still = sorted(k for k in sil if k in n_k)
    if still:
        bad.append('剪影条目同时还在皮肤区里（外迁没做干净）: %s' % still[:5])
    # ⚠️ 旧版把「不在**皮肤区**」当成「两边都不认识」，于是**一直待在剪影区**的条目
    # （如 aerjiliya_hei）每轮都报 ghost——实测剪影数 16→16 零变化，它却红了。
    # 判据必须是「两边皮肤区都没有、**且旧剪影区也没有**」才是真幽灵。
    old_sil = {s.get('key') for s in (old.get('silhouettes') or []) if s.get('key')}
    # 新增剪影（本批新 `_hei` / 新剧情剪影）是**增量**，不是零回退。旧版把「不在旧剪影区、
    # 也不在两边皮肤区」的条目当 ghost：第一次 derive 必红，第二次因为 index.prev 已带上它才绿
    # ——判据依赖运行次数，是假回退（2026-10-23 changshehao_hei / nichao_hei 实测）。
    # 真正的零回退是「旧剪影区有、新版没有」⇒ lost_sil。
    lost_sil = sorted(old_sil - sil)
    if lost_sil:
        bad.append('剪影清单里丢了旧条目: %s' % lost_sil[:5])

    for gone in sorted(set(o_s) - set(n_s)):
        if gone in sil:
            rep['船外迁为剪影'] += 1
            continue
        # ⚠️ 还有一种合法消失：**卡上所有皮肤都搬进了剪影**（探索者连线 NPC，§93），
        # 那这张卡自己也就没有皮肤可显示了 ⇒ 整张卡从主网格摘掉（与 §90「只剩剪影的船
        # 从主网格摘掉」同一条规则）。判据：它至少有一条皮肤确实进了新版剪影清单。
        # 这不是按名字开例外——`gone in sil or 有皮肤在 sil 里` 双向可核。
        if any(sk.get('key') in sil for sk in (o_s[gone].get('skins') or ())):
            rep['船因皮肤全部外迁而摘掉'] += 1
            continue
        # ⚠️ 2026-10-04 修：另一种合法消失 —— **假组键**。
        # `normalize()` 原先不剥 `_tolove`/`_doa`/`_wjz`，造出 `gushouchuan_tolove`、
        # `na_doa` 这种"表里不存在的实体 id"当组键 ⇒ 一个角色被拆成多张同名卡片。
        # 修好后这些假 id 消失、其皮肤并回真船。判据：该假 id 的**皮肤全部还在**，
        # 且都已挂到别的船上（双向可核），不是真删除。
        if gone in o_k and all(k in n_k for k in
                              [x['key'] for x in (o_s[gone].get('skins') or ())]):
            rep['假组键消失(皮肤已并回真船)'] += 1
            continue
        bad.append('船掉出索引: %s' % gone)
    for add in sorted(set(n_s) - set(o_s)):
        rep['船新增'] += 1

    for sid, s in o_s.items():
        t = n_s.get(sid)
        if not t:
            continue
        lost = set(s) - set(t)
        if lost - allow_ship:
            bad.append('船字段消失: %s %s' % (sid, sorted(lost - allow_ship)))
        a, b = scalars(s, {'skins'}), scalars(t, {'skins'})
        for k in sorted(set(a) | set(b)):
            if a.get(k) == b.get(k):
                rep['船标量未变'] += 1
                continue
            if k in allow_ship:
                rep['船标量允许变化:%s' % k] += 1
                if k == 'voiceCount':
                    rep['voiceCount 变好(0→有)' if not a.get(k) and b.get(k)
                        else 'voiceCount 数值变动' if b.get(k)
                        else 'voiceCount 归零'] += 1
                if k == 'voiceCount' and a.get(k) and not b.get(k):
                    # 归零分两种：旧语音本来属于别人的包（修正）vs 这艘船自己的包没了（回退）
                    olds = {old_pack_of(v) for v in (s.get('voices') or [])} - {None}
                    mine = set()
                    for sk in (s.get('skins') or []):
                        key = str(sk.get('key') or '').lower()
                        mine |= packs.get(key, set())
                        # 黑化版是**独立发声实体**（2026-10-02 用户裁定，见 §84）：
                        # 它"本船的包"只算它自己那一行的，基础皮肤那套是**另一个实体**的台词，
                        # 拿掉属修正。旧口径按船算，会把"错派给黑化版的本体台词"当成"丢了本船语音"判红。
                        if not HEI_TAIL.search(key):
                            mine |= packs.get(VAR_TAIL.sub('', key), set())
                    if olds and not (olds & mine):
                        rep['voiceCount 归零=旧语音本属他船(修正)'] += 1
                        misfit.append('  %s: 旧包 %s 不在其皮肤的游戏表包号 %s 内'
                                      % (sid, sorted(olds), sorted(mine)))
                    elif not olds:
                        # 旧索引里这条压根没有 `voices` 列表 ⇒ 旧包归属**无从判定**。
                        # 不能断言"丢了本船语音"（那是把"不知道"当成"证明了"），也不能直接放行。
                        # ⚠️ 替代证据不能写"还有台词"：本轮实测台词层有同一份错派（黑化键的
                        #    voiceText 指向本体的行），那等于让错数据给自己的存在作证（§85）。
                        vt = b.get('voiceText') or s.get('voiceText') or 0
                        if HEI_TAIL.search(sid):
                            # 黑化版按裁定不得借用任何非自己那一行的数据 ⇒ 归零属预期，点名即可
                            rep['voiceCount 归零=黑化版撤错派(需人看)'] += 1
                            misfit.append('  %s: 黑化版（独立发声实体）语音归零，'
                                          '旧索引无 voices 列表无从核对旧包；台词 %s 条'
                                          % (sid, vt if isinstance(vt, int) else len(vt)))
                        elif vt:
                            rep['voiceCount 归零=旧包无从判定但台词已在(需人看)'] += 1
                            misfit.append('  %s: 旧索引无 voices 列表，无法判定旧包归属；'
                                          '现 voiceCount=%s 但台词 %s 条已在（须人确认这确实是撤错派）'
                                          % (sid, b.get(k), vt if isinstance(vt, int) else len(vt)))
                        else:
                            bad.append('voiceCount 归零且无台词兜底(旧包无从判定): %s %s→%s'
                                       % (sid, a.get(k), b.get(k)))
                    else:
                        bad.append('voiceCount 归零(丢了这艘船自己的语音): %s %s→%s 旧包=%s 本船包号=%s'
                                   % (sid, a.get(k), b.get(k), sorted(olds), sorted(mine)))
            elif k in expect.get(sid, {}):
                # 声明过的期望变化：**值必须正好等于声明的那个**，否则照样红。
                # 比"按字段放行"强得多 —— 按字段放行 name 等于从此任何误改名都不再报，
                # 而这里清单外的组改名仍然判回退。
                if b.get(k) == expect[sid][k]:
                    rep['船标量按声明变化:%s' % k] += 1
                else:
                    bad.append('船标量变化与声明不符: %s.%s 期望 %r 实得 %r'
                               % (sid, k, expect[sid][k], b.get(k)))
            elif HEI_TAIL.search(str(sid)) and empty(b.get(k)):
                rep['船标量撤错派(黑化):%s' % k] += 1
                misfit.append('  船 %s.%s %r→%r（黑化版撤掉属于本体的错派）'
                              % (sid, k, a.get(k), b.get(k)))
            elif empty(a.get(k)) and not empty(b.get(k)):
                # 从"没有"变成"有" = 补全，不是回退（撤掉错派语音后台词层接管就是这一类）
                rep['船标量补全:%s' % k] += 1
            elif k == 'category' and (a.get(k), b.get(k)) == ('story', 'other') and is_other(sid):
                # 三档制改判（2026-10-05 用户定档）：只有**满足「其他」判据**的卡才许从剧情角色
                # 挪进其他；反向（other→story）与 ship→other 一律判红。判据与索引器同源，
                # 不是按名字放行——按名字放行等于从此任何误改类别都不再报。
                rep['船改判为其他档'] += 1
            elif meta_blessed_ship(sid, k, a, b, mo, mn):
                rep['船标量随元数据变化:%s' % k] += 1
            else:
                bad.append('船标量回退: %s.%s %r→%r' % (sid, k, a.get(k), b.get(k)))

    for key in sorted(set(o_k) - set(n_k)):
        if key in sil:
            rep['皮肤外迁为剪影'] += 1
            continue
        bad.append('皮肤掉出索引: %s' % key)
    for key in sorted(set(n_k) - set(o_k)):
        rep['皮肤新增'] += 1
    for key, sk in o_k.items():
        t = n_k.get(key)
        if not t:
            continue
        lost = set(sk) - set(t)
        if lost - allow_skin:
            bad.append('皮肤字段消失: %s %s' % (key, sorted(lost - allow_skin)))
        a, b = scalars(sk, {'_ship'}), scalars(t, {'_ship'})
        if sk['_ship'] != t['_ship']:
            # ⚠️ 2026-10-04：假组键被合并时，同一张皮肤会**换船**。合法形态有两种：
            #   ① 两边指向**同一实体**（舰名相同）—— `na_doa`→`na`；
            #   ② **新船 id 是旧船 id 的前缀或反之**（同一艘船的两张卡被合并，舰名可能不同）——
            #      `zi_shanluan_ex` 从 `zi`（三浦 梓）挪回 `zi_shanluan`（紫）。用 id 判比
            #      用舰名判准（舰名互不为子串：「三浦 梓」vs「紫」）。
            # 判据仍双向可核：**皮肤本身没变、只换了归属**，且两船 id 有前缀关系。
            old_id, new_id = sk['_ship'], t['_ship']
            if old_id == new_id or old_id.startswith(new_id) or new_id.startswith(old_id):
                rep['皮肤随假组键并回同一实体'] += 1
            else:
                bad.append('皮肤换船: %s %s→%s' % (key, old_id, new_id))
        for k in sorted(set(a) | set(b)):
            if a.get(k) == b.get(k):
                rep['皮肤标量未变'] += 1
            elif k in allow_skin:
                rep['皮肤标量允许变化:%s' % k] += 1
                if k == 'image' and a.get(k) and not b.get(k):
                    bad.append('皮肤立绘路径丢失: %s' % key)
            elif HEI_TAIL.search(key) and empty(b.get(k)):
                # 黑化版（独立发声实体）的标量清空 = 撤掉错派，不是回退。
                # 与语音侧同一条规则：台词层原来也把本体的台词派给了 12 个黑化键（§85），
                # 撤掉时方向是"有→空"，不点名就会被当成丢数据。仍然报出来给人看。
                rep['皮肤标量撤错派(黑化):%s' % k] += 1
                misfit.append('  皮肤 %s.%s %r→%r（黑化版撤掉属于本体的错派）'
                              % (key, k, a.get(k), b.get(k)))
            elif empty(a.get(k)) and not empty(b.get(k)):
                rep['皮肤标量补全:%s' % k] += 1
            elif expect_skin and k in expect_skin.get(key, {}):
                # 声明过的期望变化：**值必须正好等于声明的那个**（与船级 expect 同机制）。
                # 本轮用它承载「皮肤名从「皮肤N」换成游戏真名」这 3891 条有意变化：
                # 清单外的改名照样判回退，声明了却没换成照样红。
                if b.get(k) == expect_skin[key][k]:
                    rep['皮肤标量按声明变化:%s' % k] += 1
                else:
                    bad.append('皮肤标量变化与声明不符: %s.%s 期望 %r 实得 %r'
                               % (key, k, expect_skin[key][k], b.get(k)))
            elif meta_blessed_skin(key, a.get(k), b.get(k), mo, mn):
                rep['皮肤标量随元数据变化:%s' % k] += 1
            else:
                bad.append('皮肤标量回退: %s.%s %r→%r' % (key, k, a.get(k), b.get(k)))
    return rep, bad, misfit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('old'); ap.add_argument('new')
    ap.add_argument('--allow-ship', default='voiceCount,voices')
    ap.add_argument('--allow-skin', default='voiceCount,voiceTap,voiceExtra')
    ap.add_argument('--azdata', default=DEF_AZDATA, help='判「归零是修正还是回退」要用的游戏皮肤表')
    ap.add_argument('--expect', default='',
                    help='JSON：{组键: {字段: 期望新值}}。本次**有意**的改名写在这里，'
                         '值对不上或清单外的改名照样判红（比按字段放行强：那只等于关掉这项检查）')
    ap.add_argument('--meta-old', default='',
                    help='改前的 ship_meta.json；与 --meta-new 一起给出时，船级 name/faction/type/rarity '
                         '与皮肤 label 的变化必须**两头都对上元数据**才放行（不是按字段放行，那等于关掉检查）')
    ap.add_argument('--meta-new', default='', help='改后的 ship_meta.json')
    a = ap.parse_args()
    for p in (a.old, a.new):
        if not os.path.isfile(p):
            print('[ERROR] 读不到 %s' % p)
            return 2
    old = json.load(open(a.old, encoding='utf-8'))
    new = json.load(open(a.new, encoding='utf-8'))
    if not os.path.isfile(a.azdata):
        print('[ERROR] 读不到皮肤表 %s —— 没有它无法区分「归零是修正还是回退」，拒绝放行' % a.azdata)
        return 2
    if bool(a.meta_old) != bool(a.meta_new):
        print('[ERROR] --meta-old / --meta-new 必须同时给（只给一头就没法判方向）')
        return 2
    expect = json.load(open(a.expect, encoding='utf-8')) if a.expect else {}
    meta = (json.load(open(a.meta_old, encoding='utf-8')),
            json.load(open(a.meta_new, encoding='utf-8'))) if a.meta_old else None
    rep, bad, misfit = diff(old, new, set(a.allow_ship.split(',')) - {''},
                            set(a.allow_skin.split(',')) - {''}, skin_packs(a.azdata), expect, meta)
    if meta:
        print('[i] 元数据同源核对已开：%s ↔ %s' % (a.meta_old, a.meta_new))
    if expect:
        print('[i] --expect 声明 %d 组；未变红的声明项按「有意变化」计数' % len(expect))
    for k in sorted(rep):
        print('  %-34s %d' % (k, rep[k]))
    print('  旧 counts: %s' % old.get('counts'))
    print('  新 counts: %s' % new.get('counts'))
    if misfit:
        print('\n  以下归零判为**修正**（旧口径把别船的包派给了它）:')
        for m in misfit:
            print('   *' + m)
    if bad:
        print('\n[FAIL] %d 处白名单外的差异：' % len(bad))
        for b in bad[:40]:
            print('   - %s' % b)
        return 1
    print('\n[PASS] 白名单(%s / %s)之外零差异，且无掉船/掉皮肤/丢本船语音'
          % (a.allow_ship, a.allow_skin))
    return 0


if __name__ == '__main__':
    sys.exit(main())
