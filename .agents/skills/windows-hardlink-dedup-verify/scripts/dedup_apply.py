# -*- coding: utf-8 -*-
"""硬链接去重 步骤2/4：应用去重。

用法: python dedup_apply.py <N|all>   (默认 2，即前 N 组做小样本)

对 _dedup_plan.json 的组执行: 逐 dup 先真实字节复核 == canonical
-> os.remove + os.link -> 失败回退 shutil.copy2 -> 逐文件校验 nlink>=2 且 sha256 全等。
把成功应用的相对路径写入 _dedup_applied.txt（供 httpverify 逐路径 GET）。

配置(同 dedup_plan.py): DEDUP_ROOT / DEDUP_DIAG。
"""
import os, io, sys, json, hashlib, shutil

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DIAG = os.environ.get('DEDUP_DIAG') or os.path.join(ROOT, '.diag')
OUT = os.environ.get('DEDUP_ROOT') or 'Output'
OUT = OUT if os.path.isabs(OUT) else os.path.join(ROOT, OUT)

plan = json.load(io.open(os.path.join(DIAG, '_dedup_plan.json'), encoding='utf-8'))
arg = sys.argv[1] if len(sys.argv) > 1 else '2'
groups = plan if arg == 'all' else plan[:int(arg)]


def hb(x):
    for u in ['B', 'KB', 'MB', 'GB']:
        if x < 1024:
            return f'{x:.1f}{u}'
        x /= 1024
    return f'{x:.1f}TB'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def byte_equal(a, b):
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            ca, cb = fa.read(1 << 20), fb.read(1 << 20)
            if ca != cb:
                return False
            if not ca:
                return True


linked = 0
issues = []
fallback_copy = 0
applied = []
for g in groups:
    canon = os.path.join(OUT, g['canonical'])
    if not os.path.exists(canon):
        issues.append(f"canonical 缺失: {g['canonical']}")
        continue
    canon_sha = sha(canon)
    for dp in g['dups']:
        dup = os.path.join(OUT, dp)
        if not os.path.exists(dup):
            issues.append(f'dup 缺失: {dp}')
            continue
        # 建链前再次真实字节复核，绝不误链不同内容
        if not byte_equal(canon, dup):
            issues.append(f'字节不等，跳过: {dp}')
            continue
        try:
            before = os.stat(dup).st_nlink
            os.remove(dup)
            try:
                os.link(canon, dup)
            except OSError:
                # 跨卷/权限等：回退 copy（数据独立，非硬链），并计数以便排查
                shutil.copy2(canon, dup)
                fallback_copy += 1
                issues.append(f'os.link 失败，回退 copy: {dp}')
                continue
            after = os.stat(dup).st_nlink
            if after < 2 or sha(dup) != canon_sha:
                issues.append(f'校验失败 nlink={after} sha_ok={sha(dup)==canon_sha}: {dp}')
                continue
            linked += 1
            applied.append(dp)
        except OSError as e:
            issues.append(f'异常 {type(e).__name__}: {dp} {e}')

with io.open(os.path.join(DIAG, '_dedup_applied.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(applied) + ('\n' if applied else ''))

freed = sum(os.stat(os.path.join(OUT, r)).st_size for r in applied)
print(f'本次处理组数: {len(groups)}   建链文件: {linked}   回退copy: {fallback_copy}   问题: {len(issues)}')
print(f'累计已应用路径写入 _dedup_applied.txt ({len(applied)} 条)，freed≈{hb(freed)}')
for msg in issues[:40]:
    print('  ! ' + msg)
if fallback_copy:
    print('  (存在回退 copy：请检查是否跨卷/权限，这些文件未共享数据)')
