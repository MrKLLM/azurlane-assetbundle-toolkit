#!/usr/bin/env python3
"""l2d_voice_inventory.py — 语音产物的只读体检：映射表 / 磁盘 ogg / 模型目录三方对齐。

回答的问题是「语音要不要备份」：
  * 引用的 ogg 全在 → 产物完整；
  * 有 ogg 没被引用（孤儿）→ 换入过多余台词或映射表被截断；
  * 有模型没语音 → 与 --report 的「270 皮肤 / 无 ACB 17」对上即为预期。
本脚本不写任何文件。

用法: py -3 scripts/diag/l2d_voice_inventory.py [--verbose]
退出码: 0 一致 / 1 有缺失引用（映射表说有、磁盘没有）
"""
import os, sys, json, argparse, collections

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUTPUT = os.path.join(ROOT, 'Output')
MAP = os.path.join(OUTPUT, 'gallery_v2', 'l2d_voice.json')
AUDIO_ROOT = os.path.join(OUTPUT, 'Audio', 'L2D')
MODEL_ROOT = os.path.join(OUTPUT, 'Live2D')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true', help='列出全部缺失/孤儿明细')
    args = ap.parse_args()

    if not os.path.isfile(MAP):
        print(f'[ERROR] 映射表不存在: {MAP}\n'
              f'        重跑: L2D_VOICE_ALL=1 py -3 scripts/extract_live2d_voice.py')
        return 1
    m = json.load(open(MAP, encoding='utf-8'))

    referenced, groups = set(), 0
    for key, gmap in m.items():
        for g, paths in gmap.items():
            groups += 1
            for p in paths:
                referenced.add(p)
    missing = [p for p in sorted(referenced) if not os.path.isfile(os.path.join(OUTPUT, p))]

    on_disk = set()
    if os.path.isdir(AUDIO_ROOT):
        for dirpath, _, names in os.walk(AUDIO_ROOT):
            for n in names:
                if n.lower().endswith(('.ogg', '.wav', '.mp3')):
                    on_disk.add(os.path.relpath(os.path.join(dirpath, n), OUTPUT).replace('\\', '/'))
    orphans = sorted(on_disk - referenced)

    models = {d for d in os.listdir(MODEL_ROOT)
              if os.path.isdir(os.path.join(MODEL_ROOT, d)) and not d.startswith('_')}
    no_voice = sorted(models - set(m))

    print(f'映射表: {MAP}')
    print(f'  皮肤 {len(m)} | 动作组条目 {groups} | 引用音频 {len(referenced)} 条')
    print(f'磁盘:   {AUDIO_ROOT} 下 {len(on_disk)} 个音频文件')
    print(f'  缺失引用（表里有、磁盘没有）: {len(missing)}')
    print(f'  孤儿（磁盘有、表里没引用）  : {len(orphans)}')
    print(f'模型目录 {MODEL_ROOT} 共 {len(models)} 个，其中 {len(no_voice)} 个无语音映射')
    if args.verbose:
        for p in missing:
            print(f'  [MISSING] {p}')
        for p in orphans:
            print(f'  [ORPHAN]  {p}')
    elif missing or orphans:
        print('  （加 --verbose 看明细）')
    if no_voice:
        print(f'  无语音样例: {no_voice[:8]}{" ..." if len(no_voice) > 8 else ""}')

    if missing:
        print('\n[FAIL] 映射表引用的音频有缺失 → 说明上次导出被中断或 Audio 目录被动过。'
              '\n       可重跑：L2D_VOICE_ALL=1 py -3 scripts/extract_live2d_voice.py'
              '\n       （映射表由 scripts/ 里已入库的脚本 + files/AssetBundles/cue + '
              'inputs/azdata 确定性再生产，产物本身无需单独备份）')
        return 1
    print('\n[PASS] 三方对齐，无缺失引用。'
          + ('' if not orphans else f'（{len(orphans)} 个孤儿音频：导出的全集，映射表只挂动作组命中的那些，属预期）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
