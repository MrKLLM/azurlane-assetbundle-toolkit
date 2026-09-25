#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UnityPy 的 brute_force_key 只试 `\\w{16}` 候选，太窄；本脚本把候选集换成
"语料里**每一个 16 字节窗口**"，预言机沿用它的等价条件，因此是同一件事的穷举版。

推导（32 号已在本机实测的三段事实）：
    ASM 校验 = decrypt_key(key_sig, data_sig, K) == UNITY3D_SIGNATURE
    decrypt_key(K) = AES-128-ECB(K).encrypt(key_sig) XOR data_sig
 => 只需  AES_K(key_sig) == data_sig XOR "#$unity3dchina!@"  = 一个**固定 16 字节目标**
    命中强度 128 位；候选 ~10^7 时期望假命中 ~10^-27。

语料默认 = global-metadata.dat（UnityPy 官方建议的来源之一）。
也支持任意别的文件（libil2cpp.so、内存 dump）：把它们作为参数传进来即可，脚本会
逐字节滑窗扫（每窗口一次 AES key-setup，约 1~2 微秒）。

找到密钥后立刻：set_assetbundle_decrypt_key → 打开 31 号产出的 <name>.ab（补指纹区后）
→ 打印对象类型与名字，作为端到端验收。

用法:
  py -3 tools/sharecfg_re/33_asm_key_scan.py [语料文件 ...] [--aligned] [--which scripts64]
"""
import os, struct, sys

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
AB = os.path.join(ROOT, 'files', 'AssetBundles')
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')
SIGN = b'#$unity3dchina!@'
KEY_SIG = bytes.fromhex('69cd5c3ea99ab0597fc2fabeb1151f41')
DATA_SIG = bytes.fromhex('f13ad9c690692ed3eb422d616e64726f')
TARGET = bytes(a ^ b for a, b in zip(DATA_SIG, SIGN))


def fingerprint():
    for dp, dn, fn in os.walk(AB):
        for f in fn:
            p = os.path.join(dp, f)
            if p.endswith('.ab') or p.endswith('.probe'):
                continue
            try:
                with open(p, 'rb') as fh:
                    h = fh.read(32)
            except OSError:
                continue
            if h[:8] == b'UnityFS\x00' and h[8:12] in (b'\x00\x00\x00\x06', b'\x00\x00\x00\x07',
                                                       b'\x00\x00\x00\x08'):
                return h[8:32]
    raise SystemExit('找不到明文 AB 参照')


def scan(path, step=1, chunk=1 << 20, overlap=15):
    from Crypto.Cipher import AES
    size = os.path.getsize(path)
    found = []
    base = 0
    tail = b''
    with open(path, 'rb') as fh:
        while True:
            buf = fh.read(chunk)
            if not buf:
                break
            data = tail + buf
            for i in range(0, len(data) - 15, step):
                if AES.new(data[i:i + 16], AES.MODE_ECB).encrypt(KEY_SIG) == TARGET:
                    found.append((base + i - len(tail), data[i:i + 16]))
            tail = data[-overlap:] if overlap else b''
            base += len(buf)
            print('   ... %s 已扫 %d/%d (%.0f%%)' % (os.path.basename(path), base, size,
                                                     base * 100.0 / size), flush=True)
            if found:
                return found
    return found


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    step = 4 if '--aligned' in args or '--aligned' in sys.argv else 1
    which = 'scripts64'
    if '--which' in sys.argv:
        which = sys.argv[sys.argv.index('--which') + 1]
    corpus = args or [MD]
    print('预言机目标 = %s   （候选步长 %d 字节）' % (TARGET.hex(' '), step))
    for p in corpus:
        print('\n语料: %s (%d B)' % (p, os.path.getsize(p)))
        hits = scan(p, step)
        if not hits:
            print('   未命中')
            continue
        for off, k in hits:
            print('   ✅ 命中 偏移 0x%X  key=%s (%r)' % (off, k.hex(), k))
        k = hits[0][1]
        import UnityPy
        UnityPy.set_assetbundle_decrypt_key(k)
        ab = os.path.join(DI, which + '.ab')
        if not os.path.exists(ab):
            print('   缺 %s（先跑 31 号），跳过打开' % ab)
            continue
        data = bytearray(open(ab, 'rb').read())
        fp = fingerprint()
        data[8:32] = fp
        full = os.path.join(DI, which + '.opened')
        open(full, 'wb').write(bytes(data))
        env = UnityPy.Environment(full)
        objs = list(env.objects)
        print('\n   打开成功：%d 个对象，类型 = %s'
              % (len(objs), sorted({str(t.type) for t in objs})))
        for t in objs[:10]:
            print('     -', t.type, getattr(t.object, 'm_Name', ''))
        return 0
    print('\n所有语料都没命中 -> 密钥不在这些文件里（下一步：内存快照或 APK 里的别处）')
    return 1


if __name__ == '__main__':
    sys.exit(main())
