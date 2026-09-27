# -*- coding: utf-8 -*-
"""扫描所有「有 paintingface 包」的立绘皮肤，用门控渲染判定哪些是脸洞(需叠脸)。
渲染不落盘(save=False)，逐条把结果追加到：
  .diag/face_holes_<stamp>.txt   触发叠脸（=脸洞）的皮肤清单
  .diag/face_scan_<stamp>.tsv    门控实际读到的数（frac_opaque / frac_realart / mad）

为什么必须**全库重扫**而不是只复核已知清单：换判据 = 换分类器，旧清单是新判据的因变量；
只在旧清单上回归等于没回归（§14 的 sat 判据就是这么留下隐形漏检、还把 49% 判成过叠，见 §48）。

用法：py -3 scripts/diag/scan_faces.py [--stamp 20260927] [--limit N] [--resume]
长跑中断过就加 --resume：已在册的跳过，产物文件续写不覆盖。
"""
import sys, os, gc, glob, time, argparse
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'scripts'))
sys.stdout.reconfigure(encoding='utf-8')
import compose_paintings_v2 as C

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', '..'))
OUT = os.path.join(ROOT, 'Output')
TSV_HEAD = 'stem\tstate\tn_foot\tfrac_opaque\tfrac_realart\tmad\n'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='只扫前 N 个（小规模试跑）')
    ap.add_argument('--stamp', default=time.strftime('%Y%m%d'), help='产物文件名日期戳')
    ap.add_argument('--resume', action='store_true', help='跳过已在 TSV 里的皮肤，续写')
    a = ap.parse_args()

    pf = set(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, 'files', 'AssetBundles', 'paintingface', '*')) if os.path.isfile(p))
    stems = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(OUT, 'Paintings_v2', '*.png')))
    cands = [s for s in stems if s in pf]
    if a.limit:
        cands = cands[:a.limit]

    tmp = os.path.join(ROOT, '.diag', 'face_scan_tmp')
    os.makedirs(tmp, exist_ok=True)
    hp = os.path.join(ROOT, '.diag', f'face_holes_{a.stamp}.txt')
    rp = os.path.join(ROOT, '.diag', f'face_scan_{a.stamp}.tsv')

    done, holes = set(), []
    if a.resume and os.path.isfile(rp):
        with open(rp, encoding='utf-8') as f:
            for line in f:
                c = line.rstrip('\n').split('\t')
                if len(c) >= 2 and c[0] != 'stem':
                    done.add(c[0])
                    if c[1] == 'hole':
                        holes.append(c[0])
        print(f'续跑：已在册 {len(done)} 个（其中脸洞 {len(holes)}），跳过', flush=True)
    cands = [s for s in cands if s not in done]
    print(f'本次待扫 {len(cands)} 个', flush=True)

    # 进度**逐条落盘**：长跑随时可能被打断（实测在 600/2221 静默死过一次，机器只剩 0.9GB 空闲），
    # 攒到最后一次性写会把 17 分钟工作全丢掉。
    anew = not (a.resume and os.path.isfile(rp))
    rf = open(rp, 'w' if anew else 'a', encoding='utf-8', newline='\n')
    hf = open(hp, 'w' if anew else 'a', encoding='utf-8', newline='\n')
    if anew:
        rf.write(TSV_HEAD)
    errs = nogate = 0
    t0 = time.time()
    try:
        for i, s in enumerate(cands, 1):
            C.FACE_GATE.pop(s, None)
            C.FACE_APPLIED.pop(s, None)
            try:
                C.compose(s, tmp, save=False)
                g = C.FACE_GATE.get(s)
                if g:
                    mad = -1 if g['mad'] is None else round(g['mad'], 2)
                    rf.write(f'{s}\t{"hole" if g["hole"] else "ok"}\t{g["n_foot"]}\t'
                             f'{g["frac_opaque"]:.4f}\t{g["frac_realart"]:.4f}\t{mad}\n')
                    if g['hole']:
                        holes.append(s)
                        hf.write(s + '\n')
                        print(f'  洞 {s}: op={g["frac_opaque"]:.2f} mad={mad}', flush=True)
                else:
                    nogate += 1
                    rf.write(f'{s}\tnogate\t0\t-1\t-1\t-1\n')
            except Exception as e:
                errs += 1
                rf.write(f'{s}\terr\t0\t-1\t-1\t-1\n')
                if errs <= 20:
                    print(f'  ERR {s}: {e}', flush=True)
            if i % 20 == 0:
                rf.flush(); hf.flush()
                gc.collect()          # UnityPy 的原生解码缓存要靠 gc 收，长跑必须主动催
            if i % 100 == 0:
                dt = time.time() - t0
                print(f'  进度 {i}/{len(cands)}  脸洞 {len(holes)}  nogate {nogate}  err {errs}  '
                      f'用时 {dt:.0f}s  预计还需 {dt/i*(len(cands)-i)/60:.1f} 分钟', flush=True)
    finally:
        rf.flush(); rf.close(); hf.flush(); hf.close()
    print(f'完成：本次扫 {len(cands)}，脸洞累计 {len(holes)}，未参与判定 {nogate}，'
          f'err {errs}，总用时 {time.time()-t0:.0f}s', flush=True)
    print(f'脸洞清单 -> {hp}')
    print(f'门控读数 -> {rp}')


if __name__ == '__main__':
    main()
