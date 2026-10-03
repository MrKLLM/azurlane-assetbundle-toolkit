# -*- coding: utf-8 -*-
"""生成「皮肤标签换成游戏真名」的改前/改后对照表（人看的 .md + 可 grep 的 .tsv）。

为什么要它：`build_gallery_index.py` 的 `label` 一直是**从文件名推**的占位值
（`_2`→「皮肤2」、`_h`→直接印一个 `h`），而游戏给每套皮肤起的真名在权威皮肤表 `name` 字段里，
从来没被用过（2026-10-03 查明，见 docs/TROUBLESHOOTING.md §91 末段）。2783 条占位标签里
2731 条能换成真名——一次改 2731 个可见文案，必须能逐条查、且**可疑的要被自动挑出来**，
不能指望人把 2731 行读完。

自动挑出来的可疑档（只有这些需要人勾选，其余按规则放行）：
  · 名字塌了     改后名字 == 船名 ⇒ 那一行是"实体行"不是皮肤行（如 `haorenlichade_alter`→「好人理查德」）
  · 含占位符     名字里还有 `{namecode:NN}`（有 `name_code` 表可展开，展开后仍留占位的才可疑）
  · 像垃圾串     `？？？` / 纯十六进制 / 含 `▅▇■` 这类块字符——判据沿用 name_review 那一版，**不写例外名单**
  · 同船重名     同一艘船两张**不同**皮肤拿到同一个真名（画法变体同名是预期的，不算）
  · 改后为空     查到了行但 `name` 是空串
  · 无法换       表里查无该行 ⇒ 保留现标签（52 条）

用法:
  py -3 scripts/diag/skin_name_review.py [--md 路径] [--tsv 路径]
只读：不写 Output/、不改 index.json。
"""
import os, sys, re, json, argparse, collections

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import extract_cv_voice as E      # noqa: E402

GAL = os.path.join(ROOT, 'Output', 'gallery_v2')
GAMECFG = os.path.join(ROOT, 'inputs', 'gamecfg')
DEF_MD = os.path.join(ROOT, 'docs', 'skin_name_review_20261003.md')
DEF_TSV = os.path.join(ROOT, '.diag', 'skin_name_review.tsv')

VARMAP = {'hx': '和谐版', 'n': '无背景版', 'rw': '人物', 'bj': '背景', 'jz': '舰装'}
NAMECODE = re.compile(r'\{namecode:(\d+)\}')
# "像不像真名"的判据（沿用 2026-09-29 那版，按形状判、不按名字开例外）
JUNK = [(re.compile(r'^[?？]+$'), '全问号'),
        (re.compile(r'^[0-9A-Fa-f]{6,}$'), '像十六进制回显'),
        (re.compile(r'[▁▂▃▄▅▆▇█■□]'), '含块字符')]
PLACEHOLDER = re.compile(r'^皮肤\d+$|^[a-z]+$')


def art_marks(kl):
    """从皮肤名里逐层剥出的**画法后缀**（`_n`/`_hx`…）→ 中文标记，顺序与剥出顺序一致。"""
    out, cur = [], kl
    while True:
        m = E.ART_SUF.search(cur)
        if not m:
            return out
        out.append(VARMAP.get(m.group(1).strip('_'), m.group(1).strip('_')))
        cur = cur[:m.start()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--md', default=DEF_MD)
    ap.add_argument('--tsv', default=DEF_TSV)
    a = ap.parse_args()
    ix = json.load(open(os.path.join(GAL, 'index.json'), encoding='utf-8'))
    st = json.load(open(os.path.join(GAMECFG, 'ship_skin_template.json'), encoding='utf-8'))
    nc = json.load(open(os.path.join(GAMECFG, 'name_code.json'), encoding='utf-8'))
    name_by_id = {int(r['id']): (r.get('name') or '') for r in st.values()}
    rows = E.load_skin_rows()

    recs, by_ship_names = [], collections.defaultdict(list)
    for s in ix['ships']:
        for sk in s['skins']:
            key, lab = sk['key'], sk['label']
            rid = E.row_id_for(key.lower(), rows)
            raw = name_by_id.get(rid, '') if rid is not None else ''
            nm = NAMECODE.sub(lambda m: (nc.get(m.group(1)) or {}).get('name') or m.group(0), raw)
            marks = art_marks(key.lower())
            new = (nm + ('·' + '·'.join(marks) if marks else '')) if nm else ''
            # 基皮不换名：弹层已经是这艘船的界面，「默认立绘」传达的是"没换装的那张"，
            # 换成船名反而把"哪张是默认"这个信息弄丢。（漏了这条会连带把 1382 条基皮
            # 误判成"名字==船名"的可疑档——2026-10-03 第一版就是这么虚报了。）
            if lab == '默认立绘':
                new = lab
            # 基皮的画法变体（`X_n`/`X_hx`）没有自己的皮肤名——它剥掉画法后缀就是基皮那一行，
            # 拿到的"真名"必然 == 船名。这种**原样保留**现标签（「和谐版」「无背景版」），
            # 既不该变成「船名·和谐版」（船名在标题栏已经有了），也不该算成可疑。
            # 判据用"剥完画法后缀是否还是同一行"，不靠"名字==船名"这个结果去猜。
            elif nm and nm == (s.get('name') or '') and marks:
                if E.row_id_for(E.art_chain(key.lower())[-1], rows) == rid:
                    new = lab
            why = []
            if not nm:
                why.append('无法换' if rid is None else '名字为空')
            else:
                if nm == (s.get('name') or ''):
                    why.append('名字塌了(==船名)')
                if '{namecode' in nm:
                    why.append('含未展开占位符')
                for rx, tag in JUNK:
                    if rx.search(nm):
                        why.append('像垃圾串:' + tag)
                if len(nm) > 20:
                    why.append('长度异常')
            rec = dict(ship=s['id'], shipName=s.get('name') or '', key=key, old=lab,
                       new=new, rid=rid, why=why)
            recs.append(rec)
            if nm and not marks:
                by_ship_names[(s['id'], nm)].append(key)
    for (sid, nm), ks in by_ship_names.items():
        if len(ks) > 1:
            for r in recs:
                if r['ship'] == sid and r['new'] == nm:
                    r['why'].append('同船重名(%d)' % len(ks))

    chg = [r for r in recs if r['new'] and r['new'] != r['old']]
    same = [r for r in recs if r['new'] and r['new'] == r['old']]
    keep = [r for r in recs if not r['new'] and PLACEHOLDER.match(r['old'] or '')]
    sus = [r for r in chg if r['why']]
    print('皮肤条目 %d | 会变的 %d | 本来就一样的 %d | 换不了(保留占位标签) %d | 其中**可疑需人看** %d'
          % (len(recs), len(chg), len(same), len(keep), len(sus)))
    print('可疑分布:', collections.Counter(w for r in sus for w in r['why']).most_common())

    os.makedirs(os.path.dirname(a.tsv), exist_ok=True)
    with open(a.tsv, 'w', encoding='utf-8', newline='') as f:
        f.write('船id\t船名\t皮肤键\t改前\t改后\t表行id\t可疑\n')
        for r in sorted(recs, key=lambda x: (x['ship'], x['key'])):
            f.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\n'
                    % (r['ship'], r['shipName'], r['key'], r['old'], r['new'],
                       r['rid'] if r['rid'] is not None else '', '|'.join(r['why'])))

    def img(r):
        return 'Output/gallery_v2/thumbs/%s.webp' % r['key']

    L = ['# 皮肤标签换成游戏真名 —— 改前/改后对照（2026-10-03）', '',
         '> 生成：`py -3 scripts/diag/skin_name_review.py`（只读，不动 `Output/`）。',
         '> 数据：`Output/gallery_v2/index.json`（现标签）+ `inputs/gamecfg/ship_skin_template.json`（真名）',
         '> + `name_code.json`（占位符展开）。画法后缀（`_n`/`_hx`）保留成 `·无背景版` 等标记。',
         '',
         '**总账**：皮肤条目 %d | 会变 **%d** | 本来就一样 %d | 换不了、保留现标签 %d | 需人看的可疑 %d'
         % (len(recs), len(chg), len(same), len(keep), len(sus)),
         '',
         '可疑分布：' + '、'.join('%s %d' % (k, v) for k, v in
                                 collections.Counter(w for r in sus for w in r['why']).most_common()),
         '',
         '## 一、需要人勾选的（%d 条）' % len(sus), '',
         '勾选规则：把 `- [ ]` 改成 `- [x]` 表示**这条不许换**（保留现标签）；不勾 = 按对照表换。', '']
    for r in sorted(sus, key=lambda x: (x['why'][0], x['ship'])):
        L += ['### %s · `%s` — %s' % (r['shipName'] or r['ship'], r['key'], '|'.join(r['why'])), '',
              '改前 `%s` → 改后 `%s`' % (r['old'], r['new']), '',
              '![%s](%s)' % (r['key'], img(r)), '',
              '- [ ] 这条不换']
    L += ['', '## 二、全量对照（%d 条，按船分组，可直接 grep）' % len(chg), '',
          '| 船 | 皮肤键 | 改前 | 改后 |', '|---|---|---|---|']
    for r in sorted(chg, key=lambda x: (x['ship'], x['key'])):
        L.append('| %s | `%s` | %s | **%s**%s |' % (
            r['shipName'] or r['ship'], r['key'], r['old'], r['new'],
            ' ⚠' + ' '.join(r['why']) if r['why'] else ''))
    L += ['', '## 三、换不了的 %d 条（表里查无该行，保留现标签）' % len(keep), '',
          '| 船 | 皮肤键 | 现标签 |', '|---|---|---|']
    for r in sorted(keep, key=lambda x: x['key']):
        L.append('| %s | `%s` | %s |' % (r['shipName'] or r['ship'], r['key'], r['old']))
    os.makedirs(os.path.dirname(a.md), exist_ok=True)
    open(a.md, 'w', encoding='utf-8', newline='').write('\n'.join(L) + '\n')
    print('对照表: %s（%d 行）· 明细 tsv: %s' % (os.path.relpath(a.md, ROOT), len(L), os.path.relpath(a.tsv, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
