#!/usr/bin/env python3
"""gallery_src/ ↔ Output/gallery_v2/ 部署同步与漂移检查。

gallery_src/ 是画廊前端源码的唯一权威版本（纳入 Git）；
Output/gallery_v2/ 是运行目录（gitignore，含 index.json/index.js/thumbs/vendor 等生成物）。
两边同名文件默认是两个独立副本，本脚本负责让它们一致；--relink 后可变成硬链接（同一份数据）。
"""
"""三种模式：
  （默认）    逐文件比对，正本与运行目录副本不一致时用正本覆盖（修复用）
  --check     只比对不写盘，发现漂移即非零退出（提交前/回归前自查）
  --relink    把运行目录副本换成指向正本的硬链接 —— 同一份磁盘数据挂两个路径名，
              此后改正本即刻生效、不再有"忘部署"这类静默失败。
              换链前要求两边内容逐字节相同；正本有未提交改动（其它会话在写）的文件自动跳过。
"""
import sys, os, shutil, hashlib, subprocess
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SRC = os.path.join(ROOT, 'gallery_src')
DST = os.path.join(ROOT, 'Output', 'gallery_v2')
FILES = ['index.html', 'cg_export.html', '_gallery_server.py', '启动资产浏览器.bat']
MODE = next((a for a in sys.argv[1:] if a.startswith('--')), '')

def md5(p):
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

def same_inode(a, b):
    try:
        x, y = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (x.st_dev, x.st_ino) == (y.st_dev, y.st_ino)

def git_dirty(rel):
    return subprocess.run(['git', 'diff', '--quiet', 'HEAD', '--', rel],
                          cwd=ROOT, capture_output=True).returncode != 0

changed = drift = linked = skipped = 0
for f in FILES:
    s, d = os.path.join(SRC, f), os.path.join(DST, f)
    if not os.path.isfile(s):
        print(f'! 源文件缺失 {f}')
        drift += 1
        continue
    twin = same_inode(s, d)
    same = twin or (os.path.isfile(d) and md5(s) == md5(d))

    if MODE == '--check':
        if twin:
            print(f'= {f} 同一份数据（硬链）')
        elif same:
            print(f'= {f} 已一致（独立副本，可 --relink）')
        else:
            print(f'! {f} 漂移：运行目录副本 != 正本')
            drift += 1
        continue

    if MODE == '--relink':
        if not os.path.isfile(d):
            print(f'! {f} 运行目录缺件，先跑默认部署')
            drift += 1
        elif twin:
            print(f'= {f} 已是硬链')
        elif git_dirty(os.path.join('gallery_src', f)):
            print(f'~ {f} 正本有未提交改动（疑似其它会话在写），跳过换链')
            skipped += 1
        elif md5(s) != md5(d):
            print(f'! {f} 两边内容不同，拒绝换链（先跑默认部署把正本刷过去）')
            drift += 1
        else:
            os.remove(d)
            os.link(s, d)
            print(f'⇄ {f} 已换成硬链（nlink={os.stat(s).st_nlink}）')
            linked += 1
        continue

    if not same:
        shutil.copy2(s, d)
        print(f'→ 已同步 {f}')
        changed += 1
    else:
        print(f'= {f} 已一致' + ('（硬链）' if twin else ''))

if MODE == '--check':
    print(f'检查完成，漂移 {drift} 个' + ('' if drift == 0 else ' —— 运行 deploy_gallery.py 修复'))
    sys.exit(1 if drift else 0)
if MODE == '--relink':
    print(f'换链 {linked} 个，跳过 {skipped} 个，异常 {drift} 个，未处理（已是硬链或内容一致）若干')
    sys.exit(1 if drift else 0)
print(f'完成，同步 {changed} 个文件')
