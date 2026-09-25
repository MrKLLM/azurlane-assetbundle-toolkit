# -*- coding: utf-8 -*-
"""Live2D 贴图索引顺序闸门（可选 --apply 就地修正）。

moc3 只按**索引**引用贴图，不含任何贴图名，所以 model3.json 的 `Textures`
数组第 i 项必须是 moc3 索引 i 对应的那张贴图；碧蓝的命名约定是 `texture_%02d.png`
且编号即索引。reconstruct_live2d.py 按 UnityPy 对象枚举顺序落清单，枚举序 ≠ 索引序时
模型会渲染成部件堆叠的碎片（2026-09-22 换入的 9 个 bundle 里有 5 个中招）。

用法:
    py -3 scripts/diag/l2d_texorder_check.py            # 只检查，乱序则退出码 1
    py -3 scripts/diag/l2d_texorder_check.py --apply    # 修正乱序文件（改前打印前后对比）
环境变量 L2D_OUT_DIR 可覆盖扫描目录。
"""
import sys, os, re, json

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIVE2D = os.environ.get("L2D_OUT_DIR") or os.path.join(ROOT, 'Output', 'Live2D')
APPLY = '--apply' in sys.argv


def sort_key(fname):
    """按贴图名里的编号排；无编号者排在数字之后并按名称字典序。"""
    m = re.search(r'(\d+)', os.path.basename(fname))
    return (0, int(m.group(1)), '') if m else (1, 0, fname)


def scan():
    bad = []
    for name in sorted(os.listdir(LIVE2D)):
        d = os.path.join(LIVE2D, name)
        if not os.path.isdir(d):
            continue
        p = os.path.join(d, f'{name}.model3.json')
        if not os.path.isfile(p):
            continue
        try:
            model = json.load(open(p, encoding='utf-8'))
        except Exception as e:
            bad.append((name, p, None, None, f'读取失败 {e}'))
            continue
        tex = (model.get('FileReferences') or {}).get('Textures') or []
        want = sorted(tex, key=sort_key)
        if want != tex:
            bad.append((name, p, tex, want, ''))
    return bad


def main():
    if not os.path.isdir(LIVE2D):
        print(f'[ERROR] 目录不存在: {LIVE2D}')
        return 2
    bad = scan()
    total = sum(1 for n in os.listdir(LIVE2D)
                if os.path.isfile(os.path.join(LIVE2D, n, f'{n}.model3.json')))
    for name, p, tex, want, err in bad:
        if err:
            print(f'  ✗ {name}: {err}')
        else:
            print(f'  ✗ {name}: {tex} → {want}')

    if not APPLY:
        print(f'贴图顺序闸门: {total - len(bad)}/{total} 升序，乱序 {len(bad)}')
        return 1 if bad else 0

    fixed = 0
    for name, p, tex, want, err in bad:
        if err or tex is None:
            continue
        model = json.load(open(p, encoding='utf-8'))
        model['FileReferences']['Textures'] = want
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        fixed += 1
    left = len(scan())
    print(f'贴图顺序修正: 改写 {fixed} 个，剩余乱序 {left}（应为 0）')
    return 1 if left else 0


if __name__ == '__main__':
    sys.exit(main())
