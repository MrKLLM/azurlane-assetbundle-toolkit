# -*- coding: utf-8 -*-
"""只读：扫描 Paintings_v2 / Paintingface / CG_v2 内逐字节相同的文件，生成硬链去重方案。
不写任何文件（除方案 json）。同 inode(已互为硬链)的跳过；每组做真实字节比对确认相同。"""
import os, io, json, glob, hashlib, collections
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'Output')
DIRS = ['Paintings_v2', 'Paintingface', 'CG_v2']

def hb(x):
    for u in ['B','KB','MB','GB']:
        if x < 1024: return f'{x:.1f}{u}'
        x /= 1024
    return f'{x:.1f}PB'

def sha(p, cap=None):
    h = hashlib.sha256()
    with open(p,'rb') as f:
        while True:
            b=f.read(1<<20)
            if not b: break
            h.update(b)
    return h.hexdigest()

plan = []
for d in DIRS:
    root = os.path.join(OUT, d)
    files = glob.glob(os.path.join(root,'**','*.png'),recursive=True)+glob.glob(os.path.join(root,'**','*.webp'),recursive=True)
    bysize = collections.defaultdict(list)
    for p in files:
        try: s=os.path.getsize(p)
        except: continue
        if s>0: bysize[s].append(p)
    for size, ps in bysize.items():
        if len(ps)<2: continue
        # 先按 sha256 精确分组（避免逐对比）
        byhash = collections.defaultdict(list)
        for p in ps:
            try: byhash[sha(p)].append(p)
            except: pass
        for h, g in byhash.items():
            if len(g)<2: continue
            # 同 inode 视为已链，去重：按 (st_dev,st_ino) 归并
            uniq = {}
            for p in g:
                st=os.stat(p); uniq.setdefault((st.st_dev,st.st_ino),[]).append(p)
            if len(uniq)<2:
                continue  # 全部已是同一硬链，无需处理
            canon = min(g, key=lambda p:(len(p),p))  # 选最短路径为 canonical
            stc=os.stat(canon)
            dups=[p for p in g if (os.stat(p).st_dev,os.stat(p).st_ino)!=(stc.st_dev,stc.st_ino)]
            # 真实字节比对：每个 dup 与 canonical 逐字节相等才纳入
            cb=open(canon,'rb').read()
            dups=[p for p in dups if open(p,'rb').read()==cb]
            if not dups: continue
            plan.append({'dir':d,'hash':h,'size':size,'canonical':os.path.relpath(canon,OUT),
                         'dups':[os.path.relpath(p,OUT) for p in dups],
                         'canon_nlink':stc.st_nlink})

json.dump(plan, io.open(os.path.join(ROOT,'.diag','_dedup_plan.json'),'w',encoding='utf-8'), ensure_ascii=False, indent=1)
bydir=collections.Counter(); save=collections.Counter(); ngroups=0; ndup=0
for e in plan:
    bydir[e['dir']]+=len(e['dups']); save[e['dir']]+=e['size']*len(e['dups']); ngroups+=1; ndup+=len(e['dups'])
lines=[f'去重组数 {ngroups}  可转硬链的重复文件 {ndup} 个']
for d in DIRS:
    lines.append(f'  {d:16s} 重复 {bydir.get(d,0):4d} 个 / 可省 {hb(save.get(d,0))}')
lines.append(f'  合计可省 {hb(sum(save.values()))}')
lines.append('')
lines.append('=== 前 12 组样例 (canonical <- dups) ===')
for e in plan[:12]:
    lines.append(f"  [{e['dir']}] {e['size']}B {hb(e['size'])}  {e['canonical']}  <- {e['dups']}")
io.open(os.path.join(ROOT,'.diag','_dedup_summary.txt'),'w',encoding='utf-8').write('\n'.join(lines))
print('PLAN groups=%d dups=%d save=%s' % (ngroups, ndup, hb(sum(save.values()))))
