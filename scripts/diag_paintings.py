#!/usr/bin/env python3
"""诊断立绘合成：统计 face 部件解析失败(缺脸)与疑似投影层(阴影)的皮肤。"""
import sys, os, glob
import numpy as np
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(__file__))
import compose_paintings_v2 as C

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Output'))
stems = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')))
# 跳过 _face 差分与明显变体后缀，只测基础皮肤
stems = [s for s in stems if '_face' not in s]
N = int(sys.argv[1]) if len(sys.argv) > 1 else 150
stems = stems[:N]

def is_shadow(arr):
    """大面积、暗、低饱和、半透明的层 -> 疑似脚下投影"""
    a = arr[..., 3]
    vis = a > 20
    if vis.sum() < 400:
        return False
    rgb = arr[..., :3].astype(np.int16)[vis]
    mx = rgb.max(axis=1); mn = rgb.min(axis=1)
    sat = (mx - mn)
    dark = (mx < 120)                      # 偏暗
    lowsat = (sat < 40)                    # 低饱和(灰黑)
    frac_dark = (dark & lowsat).mean()
    alpha = a[vis].mean()
    return frac_dark > 0.6 and 20 < alpha < 200

face_missing = []   # 有 face 部件但 build_part 返回 None
face_present = 0
has_shadow = []     # 含疑似投影层
no_parts = []
err = []
for s in stems:
    try:
        C._env_cache.clear(); C._obj_cache.clear(); C._img_cache.clear()
        rects, go_names, father_map, children_map, parts, deps = C.parse_painting(s)
    except Exception as e:
        err.append((s, str(e)[:50])); continue
    if not parts:
        no_parts.append(s); continue
    shadow_names = []
    for p in parts:
        try:
            res = C.build_part(dict(p))
        except Exception:
            res = None
        if p.get('name') == 'face':
            if res is None:
                face_missing.append(s)
            else:
                face_present += 1
        if res is not None:
            arr, bbox, frame = res
            if is_shadow(arr):
                shadow_names.append(p.get('name') or str(p.get('rect_pid')))
    if shadow_names:
        has_shadow.append((s, shadow_names))

print(f"样本 {len(stems)} 个基础皮肤")
print(f"有face且解析成功: {face_present}")
print(f"有face但缺脸(解析失败): {len(face_missing)}  例: {face_missing[:20]}")
print(f"含疑似投影层: {len(has_shadow)}  例: {has_shadow[:20]}")
print(f"无部件: {len(no_parts)}  解析异常: {len(err)}")
# 统计部件名分布，看脸/阴影的命名
from collections import Counter
names=Counter()
for s in stems[:60]:
    try:
        _,_,_,_,parts,_=C.parse_painting(s)
        for p in parts: names[p.get('name') or '(非名)']+=1
    except: pass
print("部件名Top:", names.most_common(25))
