# -*- coding: utf-8 -*-
"""比对两份 `skin_words.json`：逐皮肤逐槽位算 gained / changed / lost，并判方向。

为什么要有它：台词钥匙（`build_skin_words.py`）改了之后，"改好了"和"改坏了"在统计行上
长得一样 —— 正文字条数 ±几百都可能是修对（补全）或修坏（把对的台词弄没）。
⇒ 必须落到**每个皮肤每一句**上比，并把三种方向分开数：
  · `lost`    旧有新无 = **回退**，闸门判红（除非它旧的那句本来就派自别的实体）
  · `gained`  旧新无   = 补全
  · `changed` 两边都有且不同 = 改派，必须能说出"旧的是谁的台词"

用法:
  py -3 scripts/diag/voice_words_diff.py                     # 现网 vs .diag/_cv 里的新版
  py -3 scripts/diag/voice_words_diff.py --a X --b Y [--tsv out.tsv]
退出码: 0 = 零回退；1 = 有回退（列出来给人看）。
"""
import os, sys, json, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import skin_table                 # noqa: E402      皮肤表唯一读取口（行 id → painting）
import extract_cv_voice as E      # noqa: E402      与台词层同一份归属口径，判"旧行是谁的"

GAL = os.path.join(ROOT, 'Output', 'gallery_v2')


def flat(blob):
    """→ {皮肤: {槽位: 正文}}（把 m/w 两层展平，前端读的就是这个视图）。"""
    out = {}
    for skin, sid in blob['m'].items():
        out[skin] = dict((blob['w'].get(sid) or {}))
    return out


def owner(sid, rows_by_id):
    """皮肤行 id → 那一行属于哪个实体（`painting`）。查不到 = 表里根本没这行。"""
    r = rows_by_id.get(str(sid))
    return (r.get('painting') or '?') if r else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--a', default=os.path.join(GAL, 'skin_words.json'))
    ap.add_argument('--b', default=os.path.join(ROOT, '.diag', '_cv', 'skin_words_new.json'))
    ap.add_argument('--tsv', default=os.path.join(ROOT, '.diag', '_cv', 'words_diff.tsv'))
    ap.add_argument('--voice-a', default=os.path.join(GAL, 'skin_voice.json'))
    ap.add_argument('--voice-b', default=os.path.join(ROOT, '.diag', '_cv', 'skin_voice_new.json'))
    a = ap.parse_args()
    A, B = json.load(open(a.a, encoding='utf-8')), json.load(open(a.b, encoding='utf-8'))
    VA, VB = json.load(open(a.voice_a, encoding='utf-8')), json.load(open(a.voice_b, encoding='utf-8'))
    fa, fb = flat(A), flat(B)
    rows_by_id = skin_table.load()

    def renders(vmap, skin, name):
        """这一格正文**画不画得出来**：语音页是按 `lines` 逐行渲染的（`w[l.cat]`），
        没有对应音频行的正文键 = 不可见；反过来，「有表行、主包没下发」那批是把全部正文键
        当行渲染的（`!lines.length` 那条路），所以它们的每个键都算可见。"""
        e = vmap.get(skin)
        if not e:
            return False
        cats = {l['cat'] for l in e.get('lines', [])}
        return name in cats if cats else True

    rows = E.load_skin_rows()

    def own_rows(skin):
        """这条皮肤「本该是它的行」= 候选名在表里的**全部**行 + 本体行的全部行（黑化不含本体）。
        多行同名（META/联动另开一档，如 `aerjiliya` 同时有 900419/903020）时不能只取第一行，
        否则会把"它自己的另一行"判成别人的行。"""
        s = set()
        for cand in E.row_candidates(skin.lower()):
            if rows.get(cand):
                s |= {str(sid) for _pack, _tier, sid in rows[cand]}
        if not E.HEI_SUF.search(E.art_chain(skin.lower())[-1]):
            s |= {str(sid) for _pack, _tier, sid in rows.get(E.ship_stem(skin.lower()), [])}
        return s

    def audio_moved(skin):
        """这条皮肤的**音频**归属本轮是否变了档（A0 的效果，与台词钥匙无关）。"""
        a, b = VA.get(skin), VB.get(skin)
        return bool(a and b and (a['cv'], a['idx']) != (b['cv'], b['idx']))

    gained = changed = lost = misfiled = invis = moved = 0
    lost_rows, chg_rows, gain_rows, mis_rows, invis_rows, moved_rows = [], [], [], [], [], []
    for skin in sorted(set(fa) | set(fb)):
        oa, ob = fa.get(skin, {}), fb.get(skin, {})
        for name in sorted(set(oa) | set(ob)):
            x, y = oa.get(name, ''), ob.get(name, '')
            if x == y:
                continue
            sid_a, sid_b = A['m'].get(skin), B['m'].get(skin)
            who_a, who_b = owner(sid_a, rows_by_id), owner(sid_b, rows_by_id)
            if x and not y:
                # 「旧有新无」有两种，方向完全相反：
                #   旧行本来就是这条皮肤（或它本体）的行 → 真回退，改坏了，闸门必须红；
                #   旧行是**别的实体**（算术式撞进去的隔壁船）→ 错派回收，正是本次要修的东西。
                if sid_a not in own_rows(skin):
                    misfiled += 1
                    mis_rows.append((skin, name, sid_a, who_a, x[:40]))
                elif not (renders(VA, skin, name) and renders(VB, skin, name)):
                    invis += 1
                    invis_rows.append((skin, name, sid_a, who_a, x[:40]))
                elif audio_moved(skin):
                    # 音频这一轮被改了档（`assign_pending_idx` 不再让画法变体占档）⇒
                    # 新音频那一档表里没写词，正文只能空着。这是"宁缺勿错派"，不是钥匙改坏。
                    moved += 1
                    moved_rows.append((skin, name, sid_a, who_a, x[:40]))
                else:
                    lost += 1
                    lost_rows.append((skin, name, sid_a, who_a, x[:40]))
            elif y and not x:
                gained += 1
                gain_rows.append((skin, name, sid_b, who_b, y[:40]))
            else:
                changed += 1
                chg_rows.append((skin, name, sid_a, who_a, x[:34], sid_b, who_b, y[:34]))
    print('比对 %s → %s' % (os.path.relpath(a.a, ROOT), os.path.relpath(a.b, ROOT)))
    print('皮肤 %d → %d | 补全 %d | 改派 %d | 错派回收 %d | 不可见回收 %d | 音频改档待补 %d | 真回退 %d'
          % (len(fa), len(fb), gained, changed, misfiled, invis, moved, lost))
    print('  （改派=两边都有内容不同；错派回收=旧行属别的实体，删掉才对；'
          '不可见回收=新旧都不渲染那一格；音频改档待补=A0 把音频换成本皮肤档、那一档表里没词）')
    print('\n── 改派明细（前 40）：旧钥匙是谁的台词 → 新钥匙是谁的 ──')
    for t in chg_rows[:40]:
        print('   %-20s %-14s %s(%s)「%s」→ %s(%s)「%s」' % t)
    if lost_rows:
        print('\n── ⚠️ 真回退 %d 条（音频没动、这一格照样渲染、正文却没了）──' % len(lost_rows))
        for t in lost_rows[:40]:
            print('   %-20s %-14s 旧 %s(%s)「%s」' % t)
    if moved_rows:
        print('\n── 音频改档·正文待补 %d 条（前 12）──' % len(moved_rows))
        for t in moved_rows[:12]:
            print('   %-20s %-14s 旧 %s(%s)「%s」' % t)
    if mis_rows:
        print('\n── 错派回收 %d 条（前 12：旧行属**别的实体**，删掉才对）──' % len(mis_rows))
        for t in mis_rows[:12]:
            print('   %-20s %-14s 旧 %s(%s)「%s」' % t)
    if gain_rows:
        print('\n── 补全 %d 条（前 20）──' % len(gain_rows))
        for t in gain_rows[:20]:
            print('   %-20s %-14s 新 %s(%s)「%s」' % t)
    os.makedirs(os.path.dirname(a.tsv), exist_ok=True)
    with open(a.tsv, 'w', encoding='utf-8', newline='') as f:
        f.write('皮肤\t槽位\t处置\t旧行id\t旧归属\t旧正文\t新行id\t新归属\t新正文\n')
        for s, n, sa, wa, x, sb, wb, y in chg_rows:
            f.write('%s\t%s\t改派\t%s\t%s\t%s\t%s\t%s\t%s\n' % (s, n, sa, wa, x, sb, wb, y))
        for s, n, sa, wa, x in lost_rows:
            f.write('%s\t%s\t真回退\t%s\t%s\t%s\t\t\t\n' % (s, n, sa, wa, x))
        for s, n, sa, wa, x in moved_rows:
            f.write('%s\t%s\t音频改档待补\t%s\t%s\t%s\t\t\t\n' % (s, n, sa, wa, x))
        for s, n, sa, wa, x in mis_rows:
            f.write('%s\t%s\t错派回收\t%s\t%s\t%s\t\t\t\n' % (s, n, sa, wa, x))
        for s, n, sa, wa, x in invis_rows:
            f.write('%s\t%s\t不可见回收\t%s\t%s\t%s\t\t\t\n' % (s, n, sa, wa, x))
        for s, n, sb, wb, y in gain_rows:
            f.write('%s\t%s\t补全\t\t\t\t%s\t%s\t%s\n' % (s, n, sb, wb, y))
    print('\n明细: %s（改派 %d / 错派回收 %d / 不可见回收 %d / 待补 %d / 真回退 %d / 补全 %d）'
          % (a.tsv, changed, misfiled, invis, moved, lost, gained))
    if lost:
        print('[FAIL] 有真回退：钥匙改动不得让「本来就是这条皮肤自己的」台词消失')
        return 1
    print('[OK] 零真回退（改派与回收都能说出旧行是谁的）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
