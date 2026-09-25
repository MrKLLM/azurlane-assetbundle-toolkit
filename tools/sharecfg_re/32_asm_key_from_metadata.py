#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""走完最后一段：ECB 解包 -> 补回被改写的"指纹区" -> 让 UnityPy 认出这是
Unity 官方 ArchiveStorage 加密 -> 用 UnityPy 自带的 brute_force_key 从 global-metadata.dat
里定位那 32 字节 ASM 密钥 -> 打开包并列出口子里有什么。

每一步的输入都不是我写死的：
  * ECB 与 L/ALEN 由 `30_www_endtoend_reproduce.py` 的 A1~A5 判据在真实文件上证过；
  * "指纹区"= 明文 AB 头部的 version + unityVersion + revision 字段，
    **直接从同一构建里的明文 AssetBundle 读**（同构建该 24 字节是常量，实测 8000 个包里
    前 10 字节 100% 一致），不硬编码；
  * key_sig / data_sig 由捕获 UnityPy 自己抛出的 LookupError 文本**解析**得到；
  * 密钥搜索走 UnityPy 公开 API `ArchiveStorageManager.brute_force_key(fp, key_sig, data_sig)`
    （它就是为"从 metadata/内存 dump 里找 ASM 密钥"这件事设计的），只读本地文件。

前置：先跑 `31_decrypt_scripts_bundle.py`（它产出 .diag/sharecfg_re/<name>.ab）。
用法: py -3 tools/sharecfg_re/32_asm_key_from_metadata.py [scripts64]
"""
import ast, os, re, struct, sys, traceback

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'sharecfg_re'))
AB = os.path.join(ROOT, 'files', 'AssetBundles')
MD = os.path.join(ROOT, 'files', 'il2cpp', 'Metadata', 'global-metadata.dat')
DI = os.path.join(ROOT, '.diag', 'sharecfg_re')


def fingerprint_region():
    """从同构建的一个**明文** AB 里取 8..31 这 24 字节（version + 两个版本串 + i64 高位）。"""
    for dp, dn, fn in os.walk(AB):
        for f in fn:
            p = os.path.join(dp, f)
            if p.endswith('.ab'):
                continue
            try:
                with open(p, 'rb') as fh:
                    h = fh.read(32)
            except OSError:
                continue
            if h[:8] == b'UnityFS\x00' and h[8:12] in (b'\x00\x00\x00\x06', b'\x00\x00\x00\x07',
                                                       b'\x00\x00\x00\x08'):
                return p, h[8:32]
    raise SystemExit('找不到明文 AB 参照，无法取指纹区常量')


def main(which='scripts64'):
    src, fp = fingerprint_region()
    print('指纹区参照包: %s\n指纹区 24B = %s' % (os.path.relpath(src, ROOT), fp.hex(' ')))
    ab = os.path.join(DI, which + '.ab')
    if not os.path.exists(ab):
        print('缺少 %s，请先跑 31 号' % ab); return 2
    data = bytearray(open(ab, 'rb').read())
    alen = len(data)
    size_declared = struct.unpack_from('>i', data, 34)[0]
    print('ECB 解出 %d B；偏移 34 处 >i4 = %d  %s' % (alen, size_declared,
          '== ALEN ✓' if size_declared == alen else '!= ALEN ✗'))
    data[8:32] = fp
    tmp = os.path.join(DI, which + '.probe')
    open(tmp, 'wb').write(bytes(data[:1 << 20]))      # 只喂前 1MB 就够触发异常，省时间
    import UnityPy
    from UnityPy.helpers import ArchiveStorageManager as ASM
    key_sig = data_sig = None
    try:
        UnityPy.Environment(tmp)
        print('UnityPy 直接打开了（无需 ASM 密钥）')
    except Exception as e:
        msg = str(e)
        m1 = re.search(r"key_sig = (b'.*?'|b\".*?\")", msg, re.S)
        m2 = re.search(r"data_sig = (b'.*?'|b\".*?\")", msg, re.S)
        print('解析异常文本: key_sig=%s data_sig=%s' % (bool(m1), bool(m2)))
        if not (m1 and m2):
            print(msg[:400]); os.remove(tmp); return 3
        key_sig = ast.literal_eval(m1.group(1))
        data_sig = ast.literal_eval(m2.group(1))
    try:
        os.remove(tmp)
    except OSError:
        pass   # Windows: UnityPy 可能还握着句柄
    if key_sig is None:
        return 0
    print('key_sig  = %s' % key_sig.hex(' '))
    print('data_sig = %s  (%r)' % (data_sig.hex(' '), data_sig))
    print('\nbrute_force_key（只读 metadata，18MB 窗口扫描）...', flush=True)
    key = ASM.brute_force_key(MD, key_sig, data_sig)
    if not key:
        print('未找到密钥 -> 该包的 ASM 密钥不在 global-metadata.dat 里（可能在内存/别处）')
        return 1
    key = bytes(key)
    print('ASM 密钥 = %s' % key.hex())
    UnityPy.set_assetbundle_decrypt_key(key)
    full = os.path.join(DI, which + '.asm')
    open(full, 'wb').write(bytes(data))
    env = UnityPy.Environment(full)
    objs = list(env.objects)
    print('\n打开成功：%d 个对象，类型分布 = %s'
          % (len(objs), sorted({str(t.type) for t in objs})))
    for t in objs[:12]:
        print('   -', t.type, getattr(t.object, 'm_Name', ''))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main(*(sys.argv[1:] or [])))
    except Exception:
        traceback.print_exc()
        sys.exit(4)
