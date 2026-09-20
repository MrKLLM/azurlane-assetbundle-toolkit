# -*- coding: utf-8 -*-
"""应用硬链去重：python dedup_apply.py <N|all>
对 _dedup_plan.json 的前 N 组(或全部)执行 remove+link，逐文件校验。"""
import os, io, sys, json, hashlib, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'Output')
plan = json.load(io.open(os.path.join(ROOT,'.diag','_dedup_plan.json'), encoding='utf-8'))
arg = sys.argv[1] if len(sys.argv) > 1 else '2'
groups = plan if arg == 'all' else plan[:int(arg)]

def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1<<20), b''): h.update(b)
    return h.hexdigest()

applied=[]; ok=0; fail=[]; freed=0
for e in groups:
    canon=os.path.join(OUT, e['canonical'])
    cb=open(canon,'rb').read()
    for d in e['dups']:
        dp=os.path.join(OUT, d)
        try:
            if open(dp,'rb').read()!=cb:
                fail.append((d,'bytes differ, skip')); continue
            before=os.stat(canon).st_nlink
            os.remove(dp)
            try:
                os.link(canon, dp)
            except OSError:
                shutil.copyfile(canon, dp)   # 回退：复制(仍保住路径与内容)
                fail.append((d,'link failed->copied'))
            # 校验
            st=os.stat(dp)
            assert os.path.exists(dp) and open(dp,'rb').read()==cb, 'post verify failed'
            if st.st_nlink>before: freed+=e['size']
            applied.append(d); ok+=1
        except Exception as ex:
            fail.append((d, str(ex)))

io.open(os.path.join(ROOT,'.diag','_dedup_applied.txt'),'w',encoding='utf-8').write('\n'.join(applied))
print(f'groups={len(groups)} linked={ok} freed~{freed/1048576:.1f}MB issues={len(fail)}')
for d,m in fail[:20]: print('  ISSUE', d, '::', m)
