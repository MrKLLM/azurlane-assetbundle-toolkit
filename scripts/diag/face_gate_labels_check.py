# -*- coding: utf-8 -*-
"""叠脸门控的带标签回归闸门：只读渲染一批人工目视裁定过的皮肤，断言新判据不改变它们的裁定。

标签来源：2026-09-27 在 48 张带标签样本 + 24 张抽样目视上核对（§48）。
  HOLE = 底图在脸槽处不是这张脸（透明洞 / 平涂灰块 / 缺整张头），必须叠脸
  BAKE = 底图已烤好一张完整脸（哪怕淡色低饱和），叠脸=把好脸换成另一表情，必须不叠

用法：py -3 scripts/diag/face_gate_labels_check.py     # 退出码 0 = 全部符合标签
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import compose_paintings_v2 as C

# 透明洞（旧判据一直在管的那一类）
HOLE_TRANSPARENT = ['i168_2', 'dunkeerke_3', 'chuixue_6', 'xukufu_2', 'haerxibaoweier', 'beiqi',
                    'botelan_2', 'qifeng', 'ajiakesi_2', 'wenqinzuojiaobeidi', 'gezi_2',
                    'shidifenbote', 'gelunbiya', 'makeboluo', 'missd', 'feiteliedadi',
                    'haerxibaoweier_3', 'dunkeerke', 'daleike', 'ouruola_h']
# 不透明但画的不是这张脸（§14 的 sat 判据管不住、本轮新查出的那一类）
HOLE_BLOCK = ['moermansike_2', 'xipeier_idol', 'bangkeshan_2']
# 底图已烤好完整脸：全部来自「当前(§14) sat 判据误判成洞」的抽样，逐张目视确认
BAKED = ['antu', 'leiniya_wjz', 'moermansike', 'moermansike_3', 'hongseshanmai',
         'beierfasite_7', 'canglong_g', 'chicheng_idol', 'dafeng_h', 'dulianglai',
         'jialimaoxian', 'jiluofu_2', 'jiyi', 'kaxin_2', 'kewei_4', 'lieren_alter',
         'lingyangzhe1_2', 'luao_2', 'lvzuofu_h', 'mayebuleize', 'nubiyaren', 'qibolin_3',
         'ruifeng_2', 'sanli_5']
# 不断言：z43 —— §14 目视判过「淡化半脸」要叠，但它 MAD=2.6（底图与脸谱几乎同一张画），
# 叠与不叠产物无可见差异，两侧都不算错，故不入断言集。
NEUTRAL = ['z43']

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))


def main():
    bad = []
    print(f'{"bundle":22s} {"期望":6s} {"op":>5s} {"MAD":>6s} {"sat判据":>7s} {"新判据":>6s}  结论')
    for want, lst in [('洞', HOLE_TRANSPARENT + HOLE_BLOCK), ('好脸', BAKED),
                      ('—', NEUTRAL)]:
        for b in lst:
            if not os.path.isfile(os.path.join(ROOT, 'files', 'AssetBundles', 'painting', b)):
                print(f'{b:22s} {want:6s}  包不存在，跳过')
                continue
            C.FACE_GATE.pop(b, None)
            try:
                C.compose(b, os.path.join(ROOT, '.diag', 'face_gate_check_tmp'), save=False)
            except Exception as e:
                print(f'{b:22s} {want:6s}  ERR {e}')
                bad.append(b)
                continue
            g = C.FACE_GATE.get(b)
            if not g:
                print(f'{b:22s} {want:6s}  未参与判定（无脸槽/无脸谱）')
                bad.append(b)
                continue
            got = '洞' if g['hole'] else '好脸'
            old = '洞' if g['frac_realart'] < 0.5 else '好脸'
            ok = True if want == '—' else got == want
            if not ok:
                bad.append(b)
            mad = g['mad']
            print(f'{b:22s} {want:6s} {g["frac_opaque"]:5.2f} '
                  f'{(f"{mad:6.1f}" if mad is not None else "   n/a")} {old:>7s} {got:>6s}  '
                  f'{"OK" if ok else "★ 不符"}')
    print(f'\n断言：{len(HOLE_TRANSPARENT) + len(HOLE_BLOCK) + len(BAKED)} 个标签样本，'
          f'不符 {len(bad)}' + ('' if not bad else f' -> {bad}'))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
