# -*- coding: utf-8 -*-
"""l2d_curve_shape.py — 把某皮肤全部 motion3.json 里匹配正则的参数曲线按**正确的 Segment 步长**
解出来，逐 clip 打印：键数 / 贝塞尔段数 / 复位(下降)次数 / min…max / 是否越界以及"越界后多久被钳"。

为什么需要它：判断「这条曲线是刻意写的循环相位，还是美术/导出写错了」不能靠肉眼读 JSON。
`Segments` 的正确布局是 **[t0,v0,ty0, (贝塞尔再跟 4 个控制点) t1,v1,ty1, … , tn,vn]**——
最后一个键只有 (time,value) 没有 curveType，所以总长是 3n-1；按固定步长 3 整除去解会 IndexError
或把控制点误当键值，得到"曲线超出量程"的假结论（本项目就这么错过一次）。

配套的量程/repeat 标志表由 `l2d_param_meta_probe.py` 从运行时读回并落盘
（`.diag/_param_meta_<key>.json`，元素为 [min,max,default,repeat]）；缺该文件时退回
`_param_ranges_<key>.json`（[min,max,default]），此时不报 repeat。

用法: py -3 scripts/diag/l2d_curve_shape.py gezi_2 '^MB_wutixialuo'
      ONLY_MOVING=1 py -3 scripts/diag/l2d_curve_shape.py gezi_2 '^MB'
判据：
  - 「越界 + repeat=1」⇒ 运行时必须按量程取模回绕，否则动作后半段冻住（§123）。
  - 「越界 + repeat=0」⇒ 才怀疑导出或美术；本项目 gezi_2 实测这种是 **0 条**。
  - 斜率(末值/时长)在多 clip 上完全相同 ⇒ 曲线是"每单位时间推进固定量"的循环相位。
"""
import sys, os, json, glob, re

sys.stdout.reconfigure(encoding="utf-8")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

KEY = sys.argv[1] if len(sys.argv) > 1 else 'gezi_2'
PARAM = sys.argv[2] if len(sys.argv) > 2 else 'MB_wutixialuoxunhuangz'
ONLY_MOVING = os.environ.get('ONLY_MOVING') == '1'
rx = re.compile(PARAM)

ranges_all = {}
for nm in (f'_param_meta_{KEY}.json', f'_param_ranges_{KEY}.json'):
    fp = os.path.join(ROOT, '.diag', nm)
    if os.path.exists(fp):
        d = json.load(open(fp, encoding='utf-8'))
        ranges_all = d.get('meta') or d.get('ranges') or {}
        break

MOTION_DIRS = [os.path.join(ROOT, 'Output', 'Live2D', KEY, 'motion'),
               os.path.join(ROOT, '.diag', 'bez_test', KEY, 'motion')]
mdir = next((p for p in MOTION_DIRS if os.path.isdir(p)), None)
if not mdir:
    print(f'找不到 {KEY} 的 motion 目录'); raise SystemExit(2)
files = sorted(glob.glob(os.path.join(mdir, '*.motion3.json')))

clips = {}
for f in files:
    j = json.load(open(f, encoding='utf-8'))
    name = os.path.basename(f)[:-len('.motion3.json')]
    clips[name] = ({c['Id']: c for c in j.get('Curves', [])
                    if c.get('Target') == 'Parameter'}, j.get('Meta', {}).get('Duration'))
assert len(files) == len(clips), f'clip 名冲突：{len(files)} 文件 → {len(clips)} 条'
print(f'dir={mdir}  clips={len(clips)}  param~/{PARAM}/  标志表={"有" if ranges_all else "缺"}\n')


def parse(curve):
    """返回 (keys, types)。末键无 curveType；贝塞尔(type 2/3) 在 type 后跟 4 个控制点。"""
    s = curve.get('Segments', [])
    keys, types = [], []
    i = 0
    while i + 1 < len(s):
        keys.append((s[i], s[i + 1]))
        if i + 2 < len(s):
            ty = int(s[i + 2])
            types.append(ty)
            i += 3 + (4 if ty in (2, 3) else 0)
        else:
            i += 2
    assert i >= len(s), f'segment stride mismatch: consumed {i} of {len(s)}'
    return keys, types


matched = sorted({pid for cur in clips.values() for pid in cur[0] if rx.search(pid)})
print(f'匹配到 {len(matched)} 个参数\n')
tot_ov_rep = tot_ov_norm = 0
for pid in matched:
    rng = ranges_all.get(pid)
    rs = ('量程[%s, %s] 默认=%s repeat=%s' % tuple(rng[:3] + [rng[3] if len(rng) > 3 else '?'])) \
        if rng and len(rng) >= 3 else '[无标志表]'
    print(f'### {pid}  {rs}')
    n_moved = n_absent = 0
    for name in sorted(clips):
        cur, dur = clips[name]
        c = cur.get(pid)
        if c is None:
            n_absent += 1
            continue
        keys, types = parse(c)
        vals = [v for _, v in keys]
        moving = max(vals) - min(vals) > 1e-6
        if moving:
            n_moved += 1
        elif ONLY_MOVING:
            continue
        resets = sum(1 for k in range(1, len(vals)) if vals[k] < vals[k - 1] - 1e-6)
        flag = ''
        if rng and moving and (max(vals) > rng[1] + 1e-6 or min(vals) < rng[0] - 1e-6):
            slope = (vals[-1] - vals[0]) / max(1e-9, keys[-1][0] - keys[0][0])
            over_t = keys[0][0] + (rng[1] - vals[0]) / slope if slope > 0 else -1
            rep = rng[3] if len(rng) > 3 else None
            tot_ov_rep += 1 if rep else 0
            tot_ov_norm += 0 if rep else 1
            flag = ('  <<< 越界 → t≈%.1fs 起被钳到 %s（clip 长 %.1fs）%s'
                    % (over_t, rng[1], dur or 0,
                       '' if rep else '   ⚠ repeat=0，越界无解释'))
        print(f'  {name:<18} dur={dur or 0:>7.2f}s keys={len(keys):>3} '
              f'bez={sum(1 for t in types if t):>3} 复位={resets:>2}  '
              f'{min(vals):.3f}…{max(vals):.3f}{flag}')
    print(f'  —— 会驱动 {n_moved} 条 / 曲线缺失 {n_absent} 条\n')
if ranges_all:
    print(f'合计：越界曲线中 repeat=1 的 {tot_ov_rep} 条、repeat=0 的 {tot_ov_norm} 条'
          f'（后者不为 0 说明不是运行时语义问题）')
