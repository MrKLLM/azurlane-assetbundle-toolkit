# -*- coding: utf-8 -*-
"""全库普查「prefab 里 GameObject 处于关闭态、却被我们画进成品」的部件 —— 只读出清单，不动产物。

背景：用户报宁海/平海/飞龙/纽卡斯尔/让·巴尔/敦刻尔克/水星纪念·META 头部整片发黑。
逐层拆开后发现是一层名为 `shadow` 的压暗剪影（436×305、不透明处 mean RGB≈(68,57,63)）
被叠在角色正上方；而该节点 `GameObject.m_IsActive = False`，游戏里根本没开。
compose_paintings_v2 的 parse_painting 从不读激活位 ⇒ 凡是带关闭节点的皮肤都会多画一层。

判据：**由渲染侧给出**——`compose_paintings_v2.parse_painting` 把激活位算在部件的 `active` 字段上
  有效激活 = 自身 `GameObject.m_IsActive` AND 沿 `RectTransform.m_Father` 全链激活
  （Unity 语义：父节点关闭则整棵子树不渲染）
本脚本只读这个字段，不另算一遍 —— 扫描与产物同源，否则清单和实际会变的图对不上。
例外：名为 `face` 的槽**不计入**——它在 prefab 里恒为关闭，游戏运行时才激活来显示表情差分，
      正是 compose 里 paintingface 叠层逻辑要用的那个槽（见 §14 / §48），豁免表 `C.FACE_SLOT_EXEMPT`。

用法:
  py -3 scripts/diag/painting_inactive_scan.py                 # 全库（Paintings_v2 stems）
  py -3 scripts/diag/painting_inactive_scan.py --only ninghai,pinghai
产物: .diag/inactive_<stamp>.tsv  每行 stem<TAB>部件名<TAB>纹理包<TAB>画布框
"""
import sys, os, glob, time, argparse, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
DIR = os.path.join(ROOT, 'Output', 'Paintings_v2')
TSV_HEAD = 'stem\tgo_name\ttex_bundle\tcanvas_box\n'


def scan(stem):
    """返回该皮肤里「关闭却被画」的部件清单 [(go_name, tex_bundle, box)]。
    激活判定直接读 parse_painting 落在部件上的 `active` 位 —— **与渲染侧同源**，
    不在这里另算一遍（另算极易和真实渲染路径不一致 → 假清单，见 §46 那条教训）。"""
    rects, go_names, father_map, children_map, parts, deps = C.parse_painting(stem)
    boxes, mirrors, roots = C.layout_all(rects, father_map, children_map)
    allb = list(boxes.values())
    ch = int(max(b[1] + b[3] for b in allb)) if allb else 0
    hits = []
    for p in parts:
        if p.get('active', True) or p['name'] in C.FACE_SLOT_EXEMPT:
            continue
        b = boxes.get(p['rect_pid'])
        box = '' if b is None else f'{int(round(b[0]))},{int(round(ch - (b[1] + b[3])))},{int(round(b[2]))}x{int(round(b[3]))}'
        hits.append((p['name'] or str(p['rect_pid']),
                     p['spr_bundle'].replace('painting/', ''), box))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--stamp', default=time.strftime('%Y%m%d'))
    ap.add_argument('--only', default='')
    ap.add_argument('--limit', type=int, default=0)
    a = ap.parse_args()

    if a.only:
        stems = [s.strip() for s in a.only.split(',') if s.strip()]
    else:
        stems = sorted(os.path.splitext(os.path.basename(p))[0]
                       for p in glob.glob(os.path.join(DIR, '*.png')))
    if a.limit:
        stems = stems[:a.limit]

    tsv = os.path.join(ROOT, '.diag', f'inactive_{a.stamp}.tsv')
    os.makedirs(os.path.dirname(tsv), exist_ok=True)
    rf = open(tsv, 'w', encoding='utf-8', newline='\n')
    rf.write(TSV_HEAD)

    by_name = collections.Counter()
    stems_hit = []
    other_names = collections.Counter()
    t0 = time.time()
    n_err = 0
    for i, s in enumerate(stems, 1):
        try:
            hits = scan(s)
        except Exception as e:
            n_err += 1
            if n_err <= 10:
                print(f'  ERR {s}: {str(e)[:120]}', flush=True)
            continue
        if hits:
            stems_hit.append(s)
            for nm, tb, box in hits:
                by_name[nm] += 1
                if nm != 'shadow':
                    other_names[nm] += 1
                rf.write(f'{s}\t{nm}\t{tb}\t{box}\n')
        if i % 200 == 0:
            rf.flush()
            dt = time.time() - t0
            print(f'  进度 {i}/{len(stems)}  命中 {len(stems_hit)}  err {n_err}  '
                  f'用时 {dt:.0f}s  预计还需 {dt / i * (len(stems) - i) / 60:.1f} 分钟', flush=True)
    rf.close()

    print('=' * 70)
    print(f'扫描 {len(stems)} 张，命中 {len(stems_hit)} 张，err {n_err}')
    print(f'按部件名统计: {dict(by_name)}')
    if other_names:
        print(f'⚠️ 非 shadow 的关闭部件（需逐个裁定）: {dict(other_names)}')
    print(f'清单 -> {tsv}')
    if stems_hit:
        print('前 40 个命中皮肤:', ', '.join(stems_hit[:40]))


if __name__ == '__main__':
    main()
