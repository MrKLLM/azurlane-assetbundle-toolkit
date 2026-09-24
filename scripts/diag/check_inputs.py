#!/usr/bin/env python3
"""check_inputs.py — 校验 inputs/ 下权威外部输入的完整性（只读，不写任何文件）。

用法:
  py -3 scripts/diag/check_inputs.py            # 校验全部 inputs/*/MANIFEST.json
  py -3 scripts/diag/check_inputs.py azdata     # 只校验某个台账

退出码: 0 全部一致 / 1 有缺失或 sha256 漂移 / 2 台账本身读不了。
"""
import os, sys, json, hashlib, glob

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def check_one(manifest):
    print(f"== {os.path.relpath(manifest, ROOT)} ==")
    m = json.load(open(manifest, encoding='utf-8'))
    d = os.path.dirname(manifest)
    bad = 0
    for e in m.get('files', []):
        # 相对台账所在目录写，避免同一份数据换根目录时整本台账要改
        p = e['path'] if os.path.isabs(e['path']) else os.path.normpath(os.path.join(d, e['path']))
        disp = os.path.relpath(p, ROOT).replace('\\', '/')
        if not os.path.isfile(p):
            print(f"  [MISSING] {disp}")
            bad += 1
            continue
        size = os.path.getsize(p)
        digest = sha256(p)
        ok_size = size == e.get('bytes')
        ok_hash = digest == e.get('sha256')
        flag = 'OK ' if ok_size and ok_hash else 'DRIFT'
        print(f"  [{flag}] {os.path.basename(disp)}  {size}B  sha256={digest[:12]}")
        if not ok_size:
            print(f"         期望 bytes={e.get('bytes')} 实际={size}")
        if not ok_hash:
            print(f"         期望 sha256={e.get('sha256')}")
        bad += 0 if (ok_size and ok_hash) else 1
    print(f"  {'全部一致' if not bad else f'{bad} 项异常'}\n")
    return bad


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    manifests = sorted(glob.glob(os.path.join(ROOT, 'inputs', '*', 'MANIFEST.json')))
    if only:
        manifests = [p for p in manifests if os.path.basename(os.path.dirname(p)) == only]
    if not manifests:
        print('[ERROR] 没找到 inputs/*/MANIFEST.json')
        return 2
    total = 0
    for mf in manifests:
        total += check_one(mf)
    if total:
        print(f"[FAIL] {total} 项权威输入缺失或漂移 —— 先恢复再继续跑依赖它们的管线")
        return 1
    print(f"[PASS] {len(manifests)} 个台账全部一致")
    return 0


if __name__ == '__main__':
    sys.exit(main())
