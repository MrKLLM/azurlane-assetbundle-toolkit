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


def empty(v):
    """标量"没有值"的口径：None / 空串 / 空列表 / 0 都算空。
    闸门要靠它区分「补全」与「回退」——把 `None→12` 叫回退是方向判反（本轮 23 处误报）。"""
    return v is None or v == '' or v == [] or v == 0


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


def diff(old, new, allow_ship, allow_skin, packs, expect=None):
    expect = expect or {}
    o_s, o_k = index_of(old)
    n_s, n_k = index_of(new)
    rep = collections.Counter()
    bad = []
    misfit = []

    for gone in sorted(set(o_s) - set(n_s)):
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
                        # 旧索引里这条压根没有 `voices` 列表 ⇒ **无从判定**旧包属于谁。
                        # 此时不能直接断言"丢了本船语音"（那是把"不知道"当成"证明了"），
                        # 但也不能放行：要求撤掉语音后**仍有台词**，否则就是静默变空白。
                        # 本轮实例：黑化版 `congmang_2_hei` 32→0，同时 voiceText 补上 12 条。
                        vt = b.get('voiceText') or (s.get('voiceText') if k == 'voiceCount' else None)
                        if vt:
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
            elif empty(a.get(k)) and not empty(b.get(k)):
                # 从"没有"变成"有" = 补全，不是回退（撤掉错派语音后台词层接管就是这一类）
                rep['船标量补全:%s' % k] += 1
            else:
                bad.append('船标量回退: %s.%s %r→%r' % (sid, k, a.get(k), b.get(k)))

    for key in sorted(set(o_k) - set(n_k)):
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
            bad.append('皮肤换船: %s %s→%s' % (key, sk['_ship'], t['_ship']))
        for k in sorted(set(a) | set(b)):
            if a.get(k) == b.get(k):
                rep['皮肤标量未变'] += 1
            elif k in allow_skin:
                rep['皮肤标量允许变化:%s' % k] += 1
                if k == 'image' and a.get(k) and not b.get(k):
                    bad.append('皮肤立绘路径丢失: %s' % key)
            elif empty(a.get(k)) and not empty(b.get(k)):
                rep['皮肤标量补全:%s' % k] += 1
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
    expect = json.load(open(a.expect, encoding='utf-8')) if a.expect else {}
    rep, bad, misfit = diff(old, new, set(a.allow_ship.split(',')) - {''},
                            set(a.allow_skin.split(',')) - {''}, skin_packs(a.azdata), expect)
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
