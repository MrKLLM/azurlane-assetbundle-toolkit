# -*- coding: utf-8 -*-
"""全量补导 25 首 BGM 的串联 runner：解码 → 转 FLAC 进正式区 → 重建索引 → 探针。
每步输出追加到 .diag/bgm_full.txt，最终写 DONE 标记。
"""
import subprocess, sys, time, os

ROOT = r'D:\Azur Lane Assets'
LOG = r'D:\Azur Lane Assets\.diag\bgm_full.txt'
STAGING_WAV = r'D:\Azur Lane Assets\.diag\bgm_backfill_wav'
OFFICIAL = r'D:\Azur Lane Assets\Output\Audio\BGM'


def log(s):
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(s + '\n')


def run(name, cmd):
    log('\n=== %s start %s ===' % (name, time.strftime('%H:%M:%S')))
    t0 = time.time()
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                      encoding='utf-8', errors='replace')
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(p.stdout)
        if p.stderr.strip():
            f.write('[stderr]\n' + p.stderr)
        f.write('=== %s exit %d 用时 %.1f min ===\n' % (name, p.returncode, (time.time() - t0) / 60))
    return p.returncode


def main():
    log('===== BGM 全量补导 %s =====' % time.strftime('%Y-%m-%d %H:%M:%S'))
    # 1) 解码全部缺的（staging 已有 3 首 wav 会自动跳过）
    rc = run('decode', ['py', '-3', r'scripts\diag\bgm_backfill_decode.py'])
    # 2) 转 FLAC 进正式区
    rc2 = run('transcode', ['py', '-3', r'scripts\transcode_bgm.py',
                            '--src', STAGING_WAV, '--out', OFFICIAL, '--codec', 'flac'])
    # 3) 重建索引
    rc3 = run('build_bgm_index', ['py', '-3', r'scripts\build_bgm_index.py'])
    # 4) 页面探针回归
    rc4 = run('bgm_page_probe', ['py', '-3', r'scripts\diag\bgm_page_probe.py'])
    # 5) 台账校验（删源前的总闸，这里只校验这 25 条能否整条解到底）
    rc5 = run('verify_flac', ['py', '-3', r'scripts\transcode_bgm.py',
                              '--verify-only', '--codec', 'flac'])
    n_wav = len([x for x in os.listdir(STAGING_WAV) if x.endswith('.wav')]) if os.path.isdir(STAGING_WAV) else 0
    n_flac = len([x for x in os.listdir(OFFICIAL) if x.endswith('.flac')]) if os.path.isdir(OFFICIAL) else 0
    log('\n===== 结束：decode=%s transcode=%s build=%s probe=%s verify=%s ; staging_wav=%d official_flac=%d ====='
        % (rc, rc2, rc3, rc4, rc5, n_wav, n_flac))
    with open(r'D:\Azur Lane Assets\.diag\bgm_full_DONE.txt', 'w', encoding='utf-8') as f:
        f.write('done rc=%s,%s,%s,%s,%s wav=%d flac=%d\n' % (rc, rc2, rc3, rc4, rc5, n_wav, n_flac))


if __name__ == '__main__':
    main()
