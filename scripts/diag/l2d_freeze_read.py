# -*- coding: utf-8 -*-
"""读 Live2D「暂停」存档（.diag/l2d_freeze/*.json）：把一帧到底画了哪几片讲成人话。

为什么要有这个脚本：一条暂停存档是 30KB 的数组（532 个参数 × 423 片美术的包围盒），
手读读不出结论；用户念一个文件名给我，我要一条命令就答出「这一帧少了哪几片、哪几片被压成一个点」。

两种模式：
  单文件  py -3 scripts/diag/l2d_freeze_read.py 20261011-194707-gezi_2-idle.json
          → 头部信息（组 / 第几秒 / 取景 / 开关）+ 被压成点的片 + 面积最小的 15 片
  两文件  py -3 scripts/diag/l2d_freeze_read.py <坏帧> <对照帧>
          → 三张差集：只在对照帧亮着的（= 这一帧没画出来的，正是要查的那批）、
            只在坏帧亮着的、两边都亮但包围盒塌掉的。**必须有对照帧**：
            实测正常 idle 里就有 8 片是零面积（停放件），所以"有片塌着"本身不是症状，
            与一帧好画面的差集才是。对照帧可以同一次暂停连按两次取相邻两拍，
            也可以按 --good 直接拿某个已知好帧的存档。

文件名可以是裸文件名（自动到 .diag/l2d_freeze/ 里找）、相对路径或绝对路径。
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')      # 控制台默认 GBK，报告里全是中文与 ⇒/⚠️
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FDIR = os.path.join(ROOT, '.diag', 'l2d_freeze')


def locate(name):
    if os.path.isfile(name):
        return name
    p = os.path.join(FDIR, name if name.endswith('.json') else name + '.json')
    if os.path.isfile(p):
        return p
    if not name.endswith('.json'):
        name += '.json'
    hits = sorted(f for f in (os.listdir(FDIR) if os.path.isdir(FDIR) else []) if f.endswith(name))
    return os.path.join(FDIR, hits[-1]) if hits else None


def load(name):
    fp = locate(name)
    if not fp:
        sys.exit(f'[用法] 找不到存档：{name}（.diag/l2d_freeze/ 里也没有以 {name} 结尾的文件）')
    with io.open(fp, encoding='utf-8') as f:
        d = json.load(f)
    d['_file'] = os.path.basename(fp)
    return d


def lit_map(d):
    """{片名: (不透明度, 宽, 高, x0, y0)} —— art 行是 [name, opacity, w, h, x0, y0]"""
    return dict((a[0], (a[1], a[2], a[3], a[4], a[5])) for a in d.get('art') or [])


def head(d):
    c, v, fl, st = d.get('counts') or {}, d.get('view') or {}, d.get('flags') or {}, d.get('state') or {}
    print(f"  文件 {d['_file']}")
    print(f"  皮肤 {d.get('skin')} · 组 {d.get('group')} 第 {d.get('tInGroup')}s"
          f"（下拉选的是 {d.get('sel')}，暂停累计 {d.get('heldMs')}ms）")
    print(f"  上屏 {c.get('lit')}/{c.get('drawables')} 片 · 压成点的 {c.get('collapsed')} 片 · "
          f"参数 {c.get('params')} · 部件 {c.get('parts')}")
    print(f"  取景 {v.get('w')}x{v.get('h')} scale={v.get('scale')} 模型位 ({v.get('mx')},{v.get('my')}) "
          f"| 开关 noRest={fl.get('noRest')} ambOff={fl.get('ambOff')} snapOff={fl.get('snapOff')} "
          f"ambMask={fl.get('ambMask')} 回绕参数 {fl.get('phase')} 个")
    print(f"  动作状态 currentGroup={st.get('currentGroup')} index={st.get('currentIndex')} "
          f"priority={st.get('currentPriority')}")


def single(d):
    head(d)
    m = lit_map(d)
    zero = sorted(k for k, v in m.items() if v[1] < 0.02 or v[2] < 0.02)
    print(f"\n  被压成一个点的（{len(zero)}）：{', '.join(zero) or '无'}")
    small = sorted(m.items(), key=lambda kv: kv[1][1] * kv[1][2])[:15]
    print('\n  面积最小的 15 片（片名, 不透明度, 宽, 高, x0, y0）：')
    for k, v in small:
        print(f'    {k:<16} op={v[0]:<6} w={v[1]:<8} h={v[2]:<8} x0={v[3]:<9} y0={v[4]}')
    print('\n  ⚠️ 单看这一帧判不了"少画了什么"：零面积的片在好帧里也有一批（停放件）。'
          '\n     要结论就再给一帧对照：l2d_freeze_read.py <坏帧> <对照帧>')


def diff(bad, good):
    b, g = lit_map(bad), lit_map(good)
    head(bad)
    print('  —— 对照 ——')
    head(good)
    gone = sorted(set(g) - set(b))
    new = sorted(set(b) - set(g))
    both = set(b) & set(g)
    crushed = sorted(k for k in both
                     if (b[k][1] < 0.02 or b[k][2] < 0.02) and g[k][1] >= 0.02 and g[k][2] >= 0.02)
    grew = sorted((k for k in both if abs(b[k][1] - g[k][1]) > 1.0
                   or abs(b[k][2] - g[k][2]) > 1.0),
                  key=lambda k: -max(abs(b[k][1] - g[k][1]), abs(b[k][2] - g[k][2])))[:12]
    print(f"\n  只在对照帧亮着、坏帧整片不见了（{len(gone)}）：{', '.join(gone) or '无'}")
    print(f"  只在坏帧亮着（{len(new)}）：{', '.join(new) or '无'}")
    print(f"  两边都在、坏帧里被压成一个点（{len(crushed)}）：{', '.join(crushed) or '无'}")
    print(f"  包围盒变化最大的 12 片：{', '.join(grew) or '无'}")
    bp = dict(bad.get('parameters') or [])
    gp = dict(good.get('parameters') or [])
    dmax = sorted(((abs(bp[k] - gp.get(k, 0)), k) for k in bp if k in gp), reverse=True)[:12]
    print('  两帧差最大的参数（|Δ| , 名 , 坏帧值 ← 对照帧值）：')
    for dv, k in dmax:
        print(f'    {dv:<9.4f} {k:<26} {bp[k]} ← {gp.get(k)}')
    print('\n  读法：gone / crushed 就是"该画没画"的那批美术；再用探针臂 ㉔ 反查它们在画面上是哪一块，'
          '\n  用 ㉘ {restoreVec} 把坏帧的参数向量写回去就能原地复现这一帧。')


def main():
    a = sys.argv[1:]
    if not a:
        ls = sorted(f for f in (os.listdir(FDIR) if os.path.isdir(FDIR) else []))
        print(f'{FDIR} 里有 {len(ls)} 条存档：')
        for f in ls[-12:]:
            print('  ' + f)
        print('用法：l2d_freeze_read.py <坏帧> [对照帧]')
        return 0
    bad = load(a[0])
    if len(a) == 1:
        single(bad)
        return 0
    diff(bad, load(a[1]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
