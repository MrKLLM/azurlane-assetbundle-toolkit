# -*- coding: utf-8 -*-
"""Live2D 贴图完整性审计：源 bundle 的 Texture2D 清单 vs 磁盘 PNG 产物，逐模型对账。

存在的理由: `reconstruct_live2d.py` 的 `extract_textures()` 里是
    try: img = data.image
    except Exception: continue
——解码失败会**静默少一张**，产物结构仍然合法（只是少一索引），运行时不会报错，
只会让引用该索引的部件采样到别的图集。这类"丢东西但看起来成功"和 motion 层的
`"Curves": []` 空壳是同一类静默失败。

检查四件事（任一非 0 即退出码 1）:
  missing   源里有、磁盘没有            —— 解码被静默跳过
  extra     磁盘有、源里没有            —— 产物来源不明
  namered   贴图名不是 texture_%02d     —— 编号即索引的约定不再成立，排序修复的前提塌了
  noorder   源枚举序 ≠ 编号序           —— 只打印不判红（fix_model3.py 已会归一）

用法:
    py -3 scripts/diag/l2d_tex_completeness.py            # 全量
    py -3 scripts/diag/l2d_tex_completeness.py benningdun_2 sebao_2
"""
import sys, os, re, json

sys.stdout.reconfigure(encoding='utf-8')
import UnityPy
from UnityPy import config
config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BUNDLE_DIR = os.path.join(ROOT, 'files', 'AssetBundles', 'live2d')
LIVE2D = os.environ.get("L2D_OUT_DIR") or os.path.join(ROOT, 'Output', 'Live2D')


def bundle_tex_names(bundle_path):
    env = UnityPy.load(bundle_path)
    out = []
    for o in env.objects:
        if o.type.name != 'Texture2D':
            continue
        try:
            d = o.read()
            out.append(getattr(d, 'm_Name', '') or '')
        except Exception as e:
            out.append(f'<READFAIL {type(e).__name__}>')
    return out


def main():
    names = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not names:
        names = sorted(n for n in os.listdir(LIVE2D)
                       if os.path.isfile(os.path.join(LIVE2D, n, f'{n}.model3.json')))

    stats = {'missing': 0, 'extra': 0, 'namered': 0, 'noorder': 0, 'nobundle': 0, 'ok': 0}
    bad = []
    for i, name in enumerate(names, 1):
        d = os.path.join(LIVE2D, name)
        bundle = os.path.join(BUNDLE_DIR, name)
        pngs = sorted(f[:-4] for f in os.listdir(d) if f.endswith('.png'))
        if not os.path.isfile(bundle):
            stats['nobundle'] += 1
            bad.append((name, f'源 bundle 不存在（产物 {len(pngs)} 张无从对账）'))
            continue
        try:
            src = bundle_tex_names(bundle)
        except Exception as e:
            stats['nobundle'] += 1
            bad.append((name, f'源 bundle 读取失败 {type(e).__name__}: {e}'))
            continue

        src_set, png_set = set(src), set(pngs)
        miss = sorted(src_set - png_set)
        extra = sorted(png_set - src_set)
        noname = [s for s in src if not re.fullmatch(r'texture_\d{2}', s)]
        ordered = sorted(src, key=lambda f: int(re.search(r'\d+', f).group())
                         if re.search(r'\d+', f) else 10 ** 9)
        red = []
        if miss:
            stats['missing'] += len(miss)
            red.append(f'missing={miss}')
        if extra:
            stats['extra'] += len(extra)
            red.append(f'extra={extra}')
        if noname:
            stats['namered'] += len(noname)
            red.append(f'非 texture_%02d 命名={noname}')
        if src != ordered:
            stats['noorder'] += 1
            print(f'  [顺序] {name}: 源枚举序 {src} → 编号序 {ordered}', flush=True)
        if red:
            bad.append((name, '; '.join(red)))
        else:
            stats['ok'] += 1
        if i % 40 == 0:
            print(f'... {i}/{len(names)}', flush=True)

    print('\n' + '=' * 60)
    print(f'对账模型 {len(names)} | 全绿 {stats["ok"]} | 源缺失 {stats["nobundle"]}')
    for k in ('missing', 'extra', 'namered'):
        print(f'  {k:8s} = {stats[k]}')
    print(f'  noorder  = {stats["noorder"]}（仅提示，fix_model3.py 已归一）')
    for name, msg in bad:
        print(f'  ✗ {name}: {msg}')
    return 1 if (stats['missing'] or stats['extra'] or stats['namered'] or stats['nobundle']) else 0


if __name__ == '__main__':
    sys.exit(main())
