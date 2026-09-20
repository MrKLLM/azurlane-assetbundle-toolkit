# -*- coding: utf-8 -*-
"""硬链接去重 步骤1：只读扫描，生成去重方案。

按 size 分组 -> 同尺寸算 sha256 -> 组内真实字节比对确认逐字节相同
-> 跳过已互为硬链(同 st_ino) -> 每组选 canonical -> 输出方案 json + 人类汇总。
不改动任何资产文件（只写 _dedup_plan.json / _dedup_summary.txt）。

配置（改这里或用环境变量）：
  DEDUP_ROOT      产物根目录，默认 "Output"（相对项目根）
  DEDUP_DIRS      逗号分隔的子目录名，默认 "Paintings_v2,Paintingface,CG_v2"
  DEDUP_EXT       逗号分隔的扩展名，默认 ".png,.jpg,.jpeg,.webp"
"""
import os, io, json, glob, hashlib, collections

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
# 允许脚本被复制到项目 .diag 下运行时也能找到根：优先环境变量
DIAG = os.environ.get('DEDUP_DIAG') or os.path.join(ROOT, '.diag')
OUT = os.environ.get('DEDUP_ROOT') or 'Output'
OUT = OUT if os.path.isabs(OUT) else os.path.join(ROOT, OUT)
DIRS = [d.strip() for d in (os.environ.get('DEDUP_DIRS') or 'Paintings_v2,Paintingface,CG_v2').split(',') if d.strip()]
EXTS = tuple(e.strip() for e in (os.environ.get('DEDUP_EXT') or '.png,.jpg,.jpeg,.webp').split(',') if e.strip())

os.makedirs(DIAG, exist_ok=True)


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
    """真实字节比对，避免只信哈希。"""
    with open(a, 'rb') as fa, open(b, 'rb') as fb:
        while True:
            ca = fa.read(1 << 20)
            cb = fb.read(1 << 20)
            if ca != cb:
                return False
            if not ca:
                return True


# 1) 收集文件并按 size 分组
by_size = collections.defaultdict(list)
total_files = 0
for d in DIRS:
    for ext in EXTS:
        for p in glob.glob(os.path.join(OUT, d, '**', '*' + ext), recursive=True):
            try:
                st = os.stat(p)
            except OSError:
                continue
            if not st.st_size:
                continue
            total_files += 1
            by_size[st.st_size].append(p)

# 2) 同尺寸内按 sha256 再分组，命中后做真实字节比对确认
groups = []
savings = 0
for size, files in by_size.items():
    if len(files) < 2:
        continue
    by_hash = collections.defaultdict(list)
    for p in files:
        by_hash[sha(p)].append(p)
    for _h, cand in by_hash.items():
        if len(cand) < 2:
            continue
        # 真实字节复核 + 同 inode 去重（已互为硬链的归一组内不算重复）
        verified = []
        seen_inode = set()
        for p in cand:
            st = os.stat(p)
            if st.st_ino in seen_inode:
                continue
            # 与已确认列表逐个字节比
            if not verified or byte_equal(verified[0], p):
                verified.append(p)
                seen_inode.add(st.st_ino)
        if len(verified) >= 2:
            canonical = verified[0]
            dups = verified[1:]
            groups.append({
                'canonical': os.path.relpath(canonical, OUT).replace('\\', '/'),
                'size': size,
                'dups': [os.path.relpath(x, OUT).replace('\\', '/') for x in dups],
            })
            savings += size * len(dups)

groups.sort(key=lambda g: -g['size'] * len(g['dups']))

plan_path = os.path.join(DIAG, '_dedup_plan.json')
io.open(plan_path, 'w', encoding='utf-8').write(json.dumps(groups, ensure_ascii=False, indent=1))

n_dup = sum(len(g['dups']) for g in groups)
lines = [
    f'扫描目录: {DIRS}  根: {OUT}',
    f'扫描文件数: {total_files}',
    f'同内容组数: {len(groups)}   重复文件数: {n_dup}   预估可省: {hb(savings)}',
    '',
    '== 前 20 组样例 (可省从大到小) ==',
]
for g in groups[:20]:
    lines.append(f"  {hb(g['size']):>9} x{len(g['dups'])+1}  canonical={g['canonical']}")
    for dp in g['dups'][:4]:
        lines.append(f'                dup = {dp}')
summary = '\n'.join(lines)
io.open(os.path.join(DIAG, '_dedup_summary.txt'), 'w', encoding='utf-8').write(summary)
print(summary)
print(f'\n方案已写入: {plan_path}')
