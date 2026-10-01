# -*- coding: utf-8 -*-
"""把临时目录里重渲好的立绘换入正式目录，并把"没伤到别人"证到位。

四道硬检查（缺一条就不许说"已换入"）：
  ① 目标 `st_nlink == 1`（硬链目标不能直接覆盖，会把运行目录/别的路径一起改掉）；
  ② 备份与原文件 md5 全等（先能退回去，再谈改）；
  ③ 换入后与临时渲染 md5 全等（落盘的确实是审过的那版）；
  ④ **全目录快照**：mtime/nlink 变化的文件集合必须正好等于本次清单（证明零附带伤害）。
之后按清单删旧缩略图，跑 make_thumbs.py 增量重建。

用法: py -3 scripts/diag/painting_swap_in.py --list <清单> --from <临时目录> --bak <备份目录>
      [--no-thumbs] [--break-hardlink]

⚠️ `--break-hardlink`：历史去重把逐字节相同的立绘链成同一 inode（见 windows-hardlink-dedup-verify）。
   一旦本次重渲让这些共享者**彼此不再相同**（实测 2026-09-27：赤城·改 左/中/右/本体 8 个文件
   原本两两共享 2 个 inode，过滤关闭层后 8 份渲染全不同），默认模式会拒绝覆盖 —— 因为
   `shutil.copyfile` 是**顺着 inode 写**的，会把所有共享者一起改掉。加这个旗标后逐名字
   `os.remove` 断开再写，并打印每个目标的同 inode 兄弟（清单外的兄弟留在旧 inode = 内容不变）。
"""
import sys, os, shutil, hashlib, argparse, subprocess

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
DIR = os.path.join(ROOT, 'Output', 'Paintings_v2')
THUMBS = os.path.join(ROOT, 'Output', 'gallery_v2', 'thumbs')


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', required=True)
    ap.add_argument('--from', dest='src', required=True)
    ap.add_argument('--bak', required=True)
    ap.add_argument('--no-thumbs', action='store_true')
    ap.add_argument('--break-hardlink', action='store_true',
                    help='允许把硬链目标断成独立文件（重渲后彼此不再同内容时用）')
    a = ap.parse_args()
    names = [l.strip() for l in open(os.path.join(ROOT, a.list) if not os.path.isabs(a.list) else a.list,
                                     encoding='utf-8') if l.strip()]
    src = os.path.join(ROOT, a.src) if not os.path.isabs(a.src) else a.src
    bak = os.path.join(ROOT, a.bak) if not os.path.isabs(a.bak) else a.bak
    print(f'待换入 {len(names)} 张，源 {src}')

    allf = [f for f in os.listdir(DIR) if f.endswith('.png')]
    snap = {f: (os.stat(os.path.join(DIR, f)).st_mtime_ns, os.stat(os.path.join(DIR, f)).st_nlink)
            for f in allf}

    # 「线上新增」的目标此刻**根本不存在** —— 早先对每个名字无条件 os.stat，
    # 换入 12 张新皮肤时直接抛 FileNotFoundError（§79 那层根因往下露出来的第二层）
    new_targets = [n for n in names if not os.path.isfile(os.path.join(DIR, f'{n}.png'))]
    existing = [n for n in names if n not in new_targets]
    hard = [n for n in existing if os.stat(os.path.join(DIR, f'{n}.png')).st_nlink != 1]
    if new_targets:
        print(f'· 其中线上新增 {len(new_targets)} 张（正式区原本没有，无需备份、没有硬链风险）')

    if hard and not a.break_hardlink:
        print(f'✗ 这些目标是硬链（nlink>1），拒绝覆盖: {hard}\n'
              f'  硬链是历史去重留下的（同内容共享 inode）。若本次重渲让它们**彼此不再相同**，\n'
              f'  必须显式加 --break-hardlink：先 os.remove 断开本名字，再单独写入，\n'
              f'  否则会顺着 inode 串改所有共享者。')
        return 2
    if hard:
        # 报出同 inode 的兄弟名字：清单外的兄弟会留在旧 inode 上（内容不变），这是安全的，
        # 但必须让人看得见——否则"我只改了 4 个"和"实际有 8 个共享这份数据"是两回事。
        inv = {}
        for f in allf:
            st = os.stat(os.path.join(DIR, f))
            inv.setdefault((st.st_dev, st.st_ino), []).append(f)
        print(f'⚠️ 断链换入 {len(hard)} 个硬链目标：')
        for n in hard:
            sib = [x for x in inv[(os.stat(os.path.join(DIR, f'{n}.png')).st_dev,
                                   os.stat(os.path.join(DIR, f'{n}.png')).st_ino)]
                   if x != f'{n}.png']
            print(f'   {n}.png  nlink={os.stat(os.path.join(DIR, f"{n}.png")).st_nlink}  '
                  f'同 inode 兄弟={sib}  其中清单外={[x for x in sib if x[:-4] not in names]}')

    missing = [n for n in names if not os.path.isfile(os.path.join(src, f'{n}.png'))]
    if missing:
        print(f'✗ 临时目录里缺这些: {missing}')
        return 2

    os.makedirs(bak, exist_ok=True)
    bad = []
    for n in names:
        d = os.path.join(DIR, f'{n}.png')
        s = os.path.join(src, f'{n}.png')
        b = os.path.join(bak, f'{n}.png')
        if os.path.isfile(b):
            print(f'  ! 备份已存在，跳过备份步骤: {b}')
        elif not os.path.isfile(d):
            pass                       # 线上新增：没有旧文件可备份
        else:
            shutil.copy2(d, b)
            if md5(b) != md5(d):
                bad.append((n, '备份 md5 不符'))
                continue
        if os.path.isfile(d) and os.stat(d).st_nlink != 1:
            os.remove(d)              # 断开这一个名字，别顺 inode 串改共享者

        shutil.copyfile(s, d)
        if md5(d) != md5(s):
            bad.append((n, '换入后 md5 不符'))
        elif os.stat(d).st_nlink != 1:
            bad.append((n, f'换入后 nlink 仍为 {os.stat(d).st_nlink}'))
    still_hard = [n for n in names if os.stat(os.path.join(DIR, f'{n}.png')).st_nlink != 1]
    print(f'① 换入后 nlink 全为 1: {not still_hard} {still_hard[:5]}   '
          f'② 备份 {len(names) - len(bad)} 份 md5 全等   ③ 换入后与临时渲染 md5 全等: '
          f'{not bad}')
    if bad:
        print('✗ 校验失败:', bad)
        return 1

    touched = {f for f, v in snap.items()
               if (os.stat(os.path.join(DIR, f)).st_mtime_ns,
                   os.stat(os.path.join(DIR, f)).st_nlink) != v}
    extra = sorted(touched - {f'{n}.png' for n in names})
    print(f'④ 全目录快照：mtime/nlink 变化 {len(touched)} 个，清单外被动的 {len(extra)} 个 {extra[:5]}')
    if extra:
        print('✗ 有附带伤害，立刻用备份回滚！')
        return 1

    if not a.no_thumbs:
        removed = 0
        for n in names:
            p = os.path.join(THUMBS, f'{n}.webp')
            if os.path.isfile(p):
                os.remove(p)
                removed += 1
        print(f'删除旧缩略图 {removed} 个，跑 make_thumbs.py 增量重建…')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'make_thumbs.py')],
                           capture_output=True, text=True, encoding='utf-8', errors='replace')
        tail = [l for l in (r.stdout or '').splitlines() if l.strip()][-1:]
        print('  ', tail[0] if tail else (r.stderr or '')[:200])
        still = [n for n in names if not os.path.isfile(os.path.join(THUMBS, f'{n}.webp'))]
        print('   重建后仍缺:', still or '无')
    print(f'\n完成。备份在 {bak}（{len(os.listdir(bak))} 个文件）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
