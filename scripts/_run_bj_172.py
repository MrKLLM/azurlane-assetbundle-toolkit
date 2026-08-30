# -*- coding: utf-8 -*-
# 临时脚本：把 172 个 bj 角色用 sprite-frame 修复全部合成到 FIXTEST/bj_172 供抽查
# 只读正式目录，不改动 Output/Paintings_Synthesized/
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from compose_paintings import compose_paintings

CSV = r"D:\Azur Lane Assets\Output\bj_screen_full.csv"
OUT = r"D:\Azur Lane Assets\Output\Paintings_Synthesized_FIXTEST\bj_172"

names = []
with open(CSV, encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if not row.get('skip', '').strip():
            names.append(row['bundle'])

print(f'共 {len(names)} 个 bj 角色 -> {OUT}', flush=True)

ok = fail = 0
failed_names = []
for i, n in enumerate(names):
    try:
        if compose_paintings(n, OUT):
            ok += 1
        else:
            fail += 1
            failed_names.append(n)
    except Exception as e:
        fail += 1
        failed_names.append(f'{n}({e})')
    if (i + 1) % 20 == 0:
        print(f'  进度 {i+1}/{len(names)}  成功={ok} 失败={fail}', flush=True)

print(f'完成: 成功 {ok}, 失败 {fail}', flush=True)
if failed_names:
    print('失败列表:', failed_names, flush=True)