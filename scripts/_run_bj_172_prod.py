# -*- coding: utf-8 -*-
# 生产落地：只重跑 172 个含 bj 层的角色，写入正式目录 Output/Paintings_Synthesized
# 步骤：备份被覆盖的旧图 -> 重跑 compose_paintings -> 输出统计
import csv
import os
import sys
import shutil

sys.path.insert(0, os.path.dirname(__file__))
from compose_paintings import compose_paintings

CSV = r"D:\Azur Lane Assets\Output\bj_screen_full.csv"
PROD = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"
BAK = r"D:\Azur Lane Assets\Output\_OLD_bak\bj_172_full_20260828"

names = []
with open(CSV, encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        if not row.get('skip', '').strip():
            names.append(row['bundle'])

print(f'共 {len(names)} 个 bj 角色', flush=True)

# 1. 备份将被覆盖的旧图
os.makedirs(BAK, exist_ok=True)
backed = 0
for n in names:
    src = os.path.join(PROD, n + '.png')
    if os.path.exists(src):
        shutil.copy2(src, os.path.join(BAK, n + '.png'))
        backed += 1
print(f'已备份 {backed} 张旧图 -> {BAK}', flush=True)

# 2. 重跑
ok = fail = 0
failed_names = []
for i, n in enumerate(names):
    try:
        if compose_paintings(n, PROD):
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