# -*- coding: utf-8 -*-
"""从 AssetBundles 的 UI 图集里导出 Texture2D / Sprite，作为「按游戏风格做控件」的**取色参照**。

为什么要有这个工具：给画廊加"符合碧蓝航线风格"的按钮态时，不许凭印象画。
游戏自己的 HUD 按钮素材就在 `files/AssetBundles/ui/` 里（`commonui_atlas` 是共享图集、
`mainactbtntpl` 是主操作按钮模板），导出来直接看：切角形状、描边色、渐变方向、
按下/hover 是不是换亮度还是换描边——这些决定了 CSS 该怎么写。

  py -3 scripts/diag/export_ui_ref_textures.py ui/commonui_atlas ui/mainactbtntpl
  py -3 scripts/diag/export_ui_ref_textures.py --list ui | grep -i button   # 先找候选图集

输出 `.diag/ui_ref/<图集名>/`（临时区，不入库）。
"""
import os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')

import UnityPy                                   # noqa: E402
from UnityPy import config                       # noqa: E402
# 与 export_assets.py 保持一致：新版 bundle 的 unity_version 被伪装/缺失，不显式回退会加载失败
config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
import export_assets as EA                       # noqa: E402  复用它的 export_texture2d / export_sprite

AB = os.path.join(ROOT, 'files', 'AssetBundles')
OUT_ROOT = os.path.join(ROOT, '.diag', 'ui_ref')


def files_of(path):
    """图集目录里真正的 bundle 文件（AL 的目录名会再套一层同名文件）。"""
    if os.path.isfile(path):
        return [path]
    out = []
    for dp, _dn, fn in os.walk(path):
        for f in fn:
            p = os.path.join(dp, f)
            if os.path.splitext(f)[1].lower() in ('.assets', '.bundle', ''):
                out.append(p)
    return out


def dump(rel):
    src = os.path.join(AB, rel)
    if not os.path.exists(src):
        print(f'! 不存在 {rel}')
        return 0
    name = os.path.basename(rel.rstrip('/\\'))
    outdir = os.path.join(OUT_ROOT, name)
    os.makedirs(outdir, exist_ok=True)
    n_tex = n_spr = n_err = 0
    for bf in files_of(src):
        try:
            env = UnityPy.load(bf)
        except Exception as e:
            print(f'  ! 打不开 {os.path.basename(bf)}: {str(e)[:80]}')
            n_err += 1
            continue
        for obj in env.objects:
            if obj.type.name == 'Texture2D':
                ok, _, err = EA.export_texture2d(obj, outdir, f'tex_{obj.path_id}')
                n_tex += ok
                n_err += (not ok)
            elif obj.type.name == 'Sprite':
                ok, _, _ = EA.export_sprite(obj, outdir, f'spr_{obj.path_id}')
                n_spr += ok
    print(f'  {rel}: Texture2D {n_tex} 张 / Sprite {n_spr} 张  ->  {os.path.relpath(outdir, ROOT)}'
          + (f'  （失败 {n_err}）' if n_err else ''))
    return n_tex + n_spr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('targets', nargs='*', help='相对 files/AssetBundles 的图集路径，如 ui/commonui_atlas')
    ap.add_argument('--list', metavar='DIR', help='只列某个子目录下的图集名（配合 grep 找候选）')
    a = ap.parse_args()
    if a.list:
        for d in sorted(os.listdir(os.path.join(AB, a.list))):
            print(f'{a.list}/{d}')
        return
    if not a.targets:
        ap.error('给至少一个图集路径，或用 --list ui 先找候选')
    tot = 0
    for t in a.targets:
        tot += dump(t)
    print(f'合计导出 {tot} 张，落在 {os.path.relpath(OUT_ROOT, ROOT)}/')


main()
