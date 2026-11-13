# -*- coding: utf-8 -*-
"""子脚本编排的唯一实现（rebuild_bgm_library / rebuild_labels 共用）。

两调用方的历史差异（默认超时、超时是否兜底）留在各自包装里：
bgm 侧超时直接抛 TimeoutExpired（原行为），labels 侧兜底返回 (124, '')。
"""
import os
import subprocess
import time


def run_stage(name, argv, *, key_line, root, timeout=7200, verbose=False, catch_timeout=False):
    """跑一个子脚本，回显 key_line 命中的关键行。返回 (rc, 合并后的输出文本)。"""
    print('\n▶ %s' % name)
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        if not catch_timeout:
            raise
        print('   ↳ 超时（%ds）' % timeout)
        return 124, ''
    out = (p.stdout or '') + (p.stderr or '')
    if verbose:
        print(out)
    else:
        for line in out.splitlines():
            if key_line.search(line):
                print('   ' + line.rstrip())
    print('   ↳ rc=%d / %.1fs' % (p.returncode, time.time() - t0))
    return p.returncode, out