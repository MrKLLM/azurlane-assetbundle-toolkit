# -*- coding: utf-8 -*-
"""把控制台页面里的 JS 抽出来做语法检查——**整页死掉**是这里唯一要防的事。

一个 `continue` 写进 `forEach` 回调，浏览器就**不执行整段脚本**：页面看起来还在（HTML 是静态的），
但 `panelState()` / `render()` 全是 undefined，界面永远停在"正在读数据…"。
探针撞上这种情况时只会报一句看不懂的 `AttributeError: 'str' object has no attribute 'get'`
（因为 `pg.ev` 把 JS 错误当字符串返回了）——所以这条检查要**在探针之前**跑。

    py -3 scripts/diag/check_page_js.py            # 没有 node 时打印 SKIP 并返回 0
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
S = os.path.dirname(HERE)
ROOT = os.path.dirname(S)
sys.path.insert(0, S)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def extract(panel_py):
    s = io.open(panel_py, encoding='utf-8').read()
    m = re.search(r"PAGE = r'''(.*?)'''", s, re.S)
    if not m:
        return None
    return '\n;\n'.join(re.findall(r'<script>(.*?)</script>', m.group(1), re.S))


def main():
    node = shutil.which('node') or shutil.which('node.exe')
    if not node:
        print('[SKIP] 这台机器上没有 node，跳过 JS 语法检查'
              '（探针仍会跑，但它对"整页没解析"只会报一句难懂的 AttributeError）')
        return 0
    bad = []
    for rel in ('pipeline_panel.py',):
        p = os.path.join(S, rel)
        js = extract(p)
        if js is None:
            print(f'  ! {rel}: 没找到 PAGE，跳过')
            continue
        tmp = os.path.join(tempfile.gettempdir(), 'page_check.js')
        io.open(tmp, 'w', encoding='utf-8').write(js)
        r = subprocess.run([node, '--check', tmp], capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        if r.returncode != 0:
            err = (r.stderr or r.stdout or '').strip().splitlines()
            bad.append((rel, err[:6]))
            print(f'  ✗ {rel} 内嵌 JS 语法错误（整页都不会执行）：')
            for l in err[:6]:
                print('      ' + l[:150])
        else:
            print(f'  [OK] {rel}：内嵌 JS {len(js.splitlines())} 行语法通过')
    print('[FAIL] 页面 JS 语法不过' if bad else '[PASS] 页面 JS 语法全过')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
