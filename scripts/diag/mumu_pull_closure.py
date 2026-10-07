"""按**依赖闭包**定向拉 AssetBundle 到本地，并逐包 md5 校验。

用途：只想拉某个房间/某个角色那一小撮包时，不必重开 `pruned.json` 的归档闸
（`mumu_sync sync --only <前缀>` 走的是台账闸，被归档的类目拉不回来，见 WF-28「撤销归档闸」）。
这里直接用 `adb pull`，**不读也不写台账**，所以归档闸保持关闭。

    py -3 scripts/diag/mumu_pull_closure.py --seed dorm3d/scenesres/scenes/tianlangxing_db/siriushostel/map_siriushostel_01_scene \
        --seed .../_base_scene --include dorm3d/scenesres --include dorm3d/effect --dry
    # 去掉 --dry 才真拉

三类结果分开计，**不许混成一个"成功"**：
  - `md5 全等` 才算拉到；
  - 设备侧 `stat=0` 的记为**幻影包**（游戏更新自己删掉的，台账里还挂着登记 —— 实测 dorm3d 有 8 个）；
  - 清单里没有该路径的记为**无校验依据**（不能算验过）。
退出码：0 = 无 md5 不符；1 = 有不符/拉失败；2 = 环境或参数问题。
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))

import mumu_sync as M                                # noqa: E402

DEPS = os.path.join(ROOT, 'Output', 'dependency_manifest.json')
HASHES = os.path.join(ROOT, 'files', 'hashes-dorm.csv')
LEDGER = os.path.join(ROOT, 'ledger', 'pruned.json')
BAK = os.path.join(ROOT, '.diag', 'pruned_backup_step1_20261007', 'pruned.json')


def load_sizes():
    """路径 -> 字节数。台账被撤销过的类目，从当场备份里补（备份不在就退回台账）。"""
    sizes = {}
    for p in (BAK, LEDGER):
        if not os.path.isfile(p):
            continue
        d = json.load(open(p, encoding='utf-8'))
        for k, v in (d.get('pruned') or {}).items():
            sizes.setdefault(k[len('AssetBundles/'):], v[0])
    return sizes


def load_md5():
    if not os.path.isfile(HASHES):
        return {}
    return {r[0]: r[2] for r in csv.reader(open(HASHES, encoding='utf-8')) if len(r) >= 3}


def closure(seeds):
    m = json.load(open(DEPS, encoding='utf-8'))
    seen = set(seeds)
    q = list(seeds)
    while q:
        x = q.pop()
        for d in (m.get(x) or {}).get('deps') or []:
            if d != 'custom_builtin' and d not in seen:
                seen.add(d)
                q.append(d)
    return seen


def main():
    ap = argparse.ArgumentParser(description='按依赖闭包定向拉包（不碰归档闸）')
    ap.add_argument('--seed', action='append', required=True, help='闭包起点（AB 相对路径，可重复）')
    ap.add_argument('--include', action='append', default=[],
                    help='只拉这些前缀的包（如 dorm3d/scenesres）；不传=闭包全拉')
    ap.add_argument('--exclude', action='append', default=[], help='排除这些前缀')
    ap.add_argument('--dry', action='store_true', help='只列清单与体量，不拉')
    a = ap.parse_args()

    sizes = load_sizes()
    md5 = load_md5()
    for s in a.seed:
        if s not in sizes and s not in md5:
            print('[FAIL] 起点不在清单里，先确认路径：%s' % s)
            return 2
    want = closure(a.seed)
    if a.include:
        want = {x for x in want if any(x.startswith(p) for p in a.include)}
    for p in a.exclude:
        want = {x for x in want if not x.startswith(p)}
    todo = sorted(x for x in want if not os.path.exists(os.path.join(M.LOCAL_ROOT, 'AssetBundles',
                                                                     x.replace('/', os.sep))))
    print('闭包 %d 个；过滤后 %d 个；本地已有 %d 个；待拉 %d 个 / %.1f MB' % (
        len(closure(a.seed)), len(want), len(want) - len(todo), len(todo),
        sum(sizes.get(x, 0) for x in todo) / 2 ** 20))
    if a.dry:
        for x in todo[:15]:
            print('   %9s  %s' % ('%d B' % sizes.get(x, 0) if x in sizes else '未知', x))
        if len(todo) > 15:
            print('   ... 还有 %d 个' % (len(todo) - 15))
        print('[--dry] 未拉取')
        return 0
    if not M.connect():
        print('[FAIL] 连不上模拟器（MuMu 要开着）')
        return 2

    ok = phantom = nomd5 = bad = failed = 0
    t0 = time.time()
    for i, rel in enumerate(todo, 1):
        loc = os.path.join(M.LOCAL_ROOT, 'AssetBundles', rel.replace('/', os.sep))
        if M.stat_remote('AssetBundles/' + rel) == 0:
            phantom += 1
            print('  ! 幻影包（设备侧不存在）%s' % rel)
            continue
        os.makedirs(os.path.dirname(loc), exist_ok=True)
        rc, _, err = M.run(['pull', '-a', M.REMOTE_ROOT + '/AssetBundles/' + rel, loc], timeout=900)
        if rc != 0:
            failed += 1
            print('  ! 拉失败 %s: %s' % (rel, (err or '').strip()[:80]))
            continue
        got = hashlib.md5(open(loc, 'rb').read()).hexdigest()
        exp = md5.get(rel)
        if exp is None:
            nomd5 += 1
            print('  ? 清单里没有该路径，无校验依据: %s' % rel)
        elif got.lower() == exp.lower():
            ok += 1
        else:
            bad += 1
            print('  ✗ md5 不符 %s 本地 %s 清单 %s' % (rel, got[:12], exp[:12]))
        if i % 50 == 0 or i == len(todo):
            print('  进度 %d/%d  ok=%d 不符=%d 幻影=%d 无依据=%d 失败=%d  %.1f 文件/秒'
                  % (i, len(todo), ok, bad, phantom, nomd5, failed, i / max(time.time() - t0, .01)))
    print('\n合计: md5 全等 %d | 不符 %d | 幻影包 %d | 无校验依据 %d | 拉失败 %d | 耗时 %.1fs'
          % (ok, bad, phantom, nomd5, failed, time.time() - t0))
    if bad or failed:
        print('[FAIL] 有包没对上，先别往下走')
        return 1
    if nomd5:
        print('⚠️ %d 个包没有 md5 依据 ⇒ 只能说"拉到了"，不能说"验过了"' % nomd5)
    return 0


if __name__ == '__main__':
    sys.exit(main())
