#!/usr/bin/env python3
"""gallery_src/ → Output/gallery_v2/ 部署同步。

gallery_src/ 是画廊前端源码的唯一权威版本（纳入 Git）；
Output/gallery_v2/ 是运行目录（gitignore，含 index.json/index.js/thumbs/vendor 等生成物）。
改完 gallery_src/ 里的文件后运行本脚本同步，再刷新浏览器即可。
"""
import sys, os, shutil, hashlib
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'gallery_src')
DST = os.path.join(ROOT, 'Output', 'gallery_v2')
FILES = ['index.html', 'cg_export.html', '_gallery_server.py', '启动资产浏览器.bat']

def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

changed = 0
for f in FILES:
    s, d = os.path.join(SRC, f), os.path.join(DST, f)
    if not os.path.isfile(s):
        print(f'! 源文件缺失 {f}'); continue
    if os.path.isfile(d) and md5(s) == md5(d):
        print(f'= {f} 已一致'); continue
    shutil.copy2(s, d)
    print(f'→ 已同步 {f}')
    changed += 1
print(f'完成，同步 {changed} 个文件')
