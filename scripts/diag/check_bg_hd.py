#!/usr/bin/env python3
"""check_bg_hd.py — 独立复核 `Output/Raw_hd/` 超分层（不采信 upscale_bg_hd.py 自己打的汇总行）。

为什么单独一个只读校验器：批处理脚本的"完成 N / 失败 0"是**它自己数自己的进度**，
数错、跳过判据放水、产物被别的会话中途删掉，它都照样报绿。消费方（索引、页面）
要的是盘上事实，所以这里从**索引**独立算出应有哪些张，再逐张回盘比。

四条判据：
  1. 覆盖：目标子集（宽 <=1280 ∧（有角色 ∨ 登录/加载））每张都有 HD 文件。
  2. 尺寸：HD 逐张正好是对应原图的 4 倍（宽和高各自相等）。
  3. 完整：尾部 IEND 在位（断电留下的半截文件尺寸头是合法的，只看尺寸会漏）。
  4. 无孤儿：HD 里每个文件都能回到一张目标集内的 Raw 图（顺手挡掉"给源头已 1920
     的图做超分"这类越界产物）。

用法: py -3 scripts/diag/check_bg_hd.py        退出码 0 = 四条全过
"""
import json
import os
import struct
import sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
RAW = os.path.join(ROOT, 'Output', 'Raw')
HD = os.path.join(ROOT, 'Output', 'Raw_hd')
META = os.path.join(ROOT, 'Output', 'gallery_v2', 'bg_meta.json')
SCALE = 4
MAXW = 1280
LOADING = ('loadingbg', 'loadingbg_hx')


def png(path):
    """-> ((w, h) 或 None, 尾部 IEND 是否完整)。"""
    try:
        with open(path, 'rb') as f:
            head = f.read(24)
            if head[:8] != b'\x89PNG\r\n\x1a\n':
                return None, False
            f.seek(-8, os.SEEK_END)      # IEND = 最后 8 字节（读在 -12 会永远 False）
            complete = f.read(8) == b'IEND\xaeB`\x82'
        return struct.unpack('>II', head[16:24]), complete
    except Exception:
        return None, False


def p_of(base, key):
    return os.path.join(base, key.replace('/', os.sep) + '.png')


def selftest():
    """判据自身的双向对照：完整文件必须判 True、故意截断的必须判 False。
    少了这一步，"偏移读错导致永远 False"这种缺陷会让四条判据全红却看不出是判据坏了
    （本轮真实踩过：IEND 是最后 8 字节，读在 [-12:-4] 会永远 False）。"""
    src = None
    for d in sorted(os.listdir(HD)) if os.path.isdir(HD) else []:
        p = os.path.join(HD, d)
        fs = [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.endswith('.png')]
        if fs:
            src = fs[0]
            break
    if not src:
        print('FAIL 判据自测：Raw_hd 里一张都没有，无从对照')
        return False
    tmp = os.path.join(ROOT, '.diag', 'hd_test', '_trunc_probe.png')
    os.makedirs(os.path.dirname(tmp), exist_ok=True)
    data = open(src, 'rb').read()
    with open(tmp, 'wb') as f:
        f.write(data[:len(data) // 2])
    good_sz, good_c = png(src)
    bad_sz, bad_c = png(tmp)
    os.remove(tmp)
    ok = bool(good_sz) and good_c and not bad_c
    print('%s 判据自测：完整文件判完整=%s（尺寸 %s）/ 截断文件判完整=%s'
          % ('OK  ' if ok else 'FAIL', good_c, good_sz, bad_c))
    return ok


def main():
    if not selftest():
        print('结论：红 —— 完整性判据自身失效，后面的数字都不可信')
        return 2
    items = json.load(open(META, encoding='utf-8'))['items']
    want = {}
    for it in items:
        rp = p_of(RAW, it['key'])
        sz, _c = png(rp)
        if not sz:
            continue
        if sz[0] <= MAXW and (it.get('has_char') == 1 or it['dir'] in LOADING):
            want[it['key']] = sz
    print('索引条目 %d / 目标集 %d 张' % (len(items), len(want)))

    missing, truncated, wrong_size, ok = [], [], [], 0
    for k, (rw, rh) in sorted(want.items()):
        hp = p_of(HD, k)
        if not os.path.isfile(hp):
            missing.append(k)
            continue
        hsz, complete = png(hp)
        if not complete:
            truncated.append(k)
        elif hsz != (rw * SCALE, rh * SCALE):
            wrong_size.append('%s HD=%s 期望 %dx%d' % (k, hsz, rw * SCALE, rh * SCALE))
        else:
            ok += 1

    have = set()
    for d, _, fs in os.walk(HD):
        for f in fs:
            if f.endswith('.png'):
                have.add(os.path.relpath(os.path.join(d, f), HD)[:-4].replace(os.sep, '/'))
    orphan = sorted(have - set(want))

    print('HD 在盘 %d 张 / 四条全过 %d 张' % (len(have), ok))
    red = 0
    for desc, bad in [('覆盖：目标每张都有 HD 文件', missing),
                      ('完整：无截断（尾部 IEND 在位）', truncated),
                      ('尺寸：HD 宽高都正好是原图 4 倍', wrong_size),
                      ('无孤儿：HD 里没有目标集之外的文件', orphan)]:
        print('%s %s%s' % ('OK  ' if not bad else 'FAIL', desc,
                           '' if not bad else '  (%d 个: %s)' % (len(bad), bad[:6])))
        red += len(bad)
    print('结论：%s' % ('绿 —— 超分层与目标集一一对应' if not red else '红'))
    return 0 if not red else 1


if __name__ == '__main__':
    sys.exit(main())
