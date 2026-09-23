#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 metadata 里筛出的候选密钥试分组密码解 sharecfgdata，按「像不像明文」评分。

候选依据（见 README「已定位的线索」）：
  - 7 个 32 hex 串（16 字节）= AES-128 密钥/摘要形态
  - 熵 6.73（<8.0）+ 34 个文件 body 前 16 字节完全相同 → **AES-ECB 特征**（相同明文块→相同密文块）
  - 头部有可变长度段（byte[4] 恒 0，byte[5..6] 小值），body 起点在 offset 9 或 11

⚠️ 说明：本脚本里出现 ECB 只是**候选试法**（我们在猜游戏用了哪种模式，不是在选加密方案）；
ECB 必须留在候选里，因为密文的重复块特征正指向它。别当成生产加密建议。

AES 走 openssl 子进程（Python 侧 pycryptodome / cryptography 都没装，不为此引入依赖）。
评分：可打印占比 + JSON 标点占比 + 中文 UTF-8 三连密度。**不自证为成功**——真明文要能解析成
JSON 且与 .diag/azdata_ship_skin_template.json 逐字段一致（见 README 判据）。
"""
import os, sys, shutil, tempfile, subprocess

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
CAND = os.path.join(ROOT, 'files', 'AssetBundles', 'sharecfgdata', 'ship_skin_template')
OPENSSL = shutil.which('openssl')

KEYS = [
    'e5e299b2d9e44255b8990bb71af8922d',
    'fccfec2b7369466d88502a9dd38505f4',
    '53546641df1347bc8aa315278a603586',
    'fcd9651ded40425995dfa6aeb78f1f1c',
    '0d58e99045904672b3ef34b8797d23cb',
    '548716b2534a45369ab0c9323fc8b4a8',
    'b9fe706dfc854d7ca109a5e38d7db730',
]
OFFSETS = [0, 8, 9, 11]
MODES = [('aes-128-ecb', 'ECB', None), ('aes-128-cbc', 'CBC0', '0' * 32),
         ('aes-128-cbc', 'CBCk', 'k'), ('aes-128-ctr', 'CTR0', '0' * 32)]


def dec(body, keyhex, cipher, ivhex, tmp_in, tmp_out):
    open(tmp_in, 'wb').write(body)
    cmd = [OPENSSL, 'enc', '-d', '-' + cipher, '-K', keyhex, '-nosalt', '-nopad']
    if ivhex is not None:
        cmd += ['-iv', keyhex if ivhex == 'k' else ivhex]
    cmd += ['-in', tmp_in, '-out', tmp_out]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    if r.returncode != 0 or not os.path.exists(tmp_out):
        return None
    return open(tmp_out, 'rb').read()


def score(b):
    if not b:
        return (0, 0, 0, 0)
    n = len(b)
    printable = sum(1 for x in b if 32 <= x < 127 or x in (9, 10, 13)) / n
    punct = sum(1 for x in b if x in b'{}[]":,=') / n
    seg = b[:200000]
    ok = i = 0
    while i + 2 < len(seg):
        if 0xe4 <= seg[i] <= 0xe9 and 0x80 <= seg[i + 1] <= 0xbf and 0x80 <= seg[i + 2] <= 0xbf:
            ok += 1
            i += 3
            continue
        i += 1
    return (printable, punct, ok / max(1, len(seg) // 3), n)


def main():
    if not OPENSSL:
        print('!! 找不到 openssl'); return 2
    raw = open(CAND, 'rb').read()
    tmp = tempfile.mkdtemp(prefix='scfg_')
    ti, to = os.path.join(tmp, 'in.bin'), os.path.join(tmp, 'out.bin')
    rows = []
    for kh in KEYS:
        for off in OFFSETS:
            body = raw[off:]
            body = body[:len(body) - len(body) % 16]
            for cipher, tag, iv in MODES:
                out = dec(body, kh, cipher, iv, ti, to)
                if out is None:
                    continue
                p, j, c, n = score(out)
                rows.append((p + j * 3 + c * 6, kh, off, tag, 'aes', p, j, c, n))
    rows.sort(reverse=True)
    print('%-34s %-3s %-5s %7s %7s %8s %s' % ('key', 'off', 'mode', 'print', 'punct', '中文', '长度'))
    for r in rows[:15]:
        print('%-34s %-3d %-5s %7.3f %7.4f %8.3f %d' % (r[1], r[2], r[3], r[5], r[6], r[7], r[8]))
    top = rows[0] if rows else None
    if top and top[5] > 0.7:
        print('\n可疑高分候选（key=%s off=%d %s）——**必须**再与 azdata 基准逐字段比对才算通过'
              % (top[1], top[2], top[3]))
    else:
        print('\n全部候选都不像明文（最高可打印 %.3f）→ 这 7 个 hex 串不是 AES-128 密钥，'
              '或还有别的前置/后置变换（压缩、二次编码、分段密钥）。' % (top[5] if top else 0))
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
