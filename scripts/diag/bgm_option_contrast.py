# -*- coding: utf-8 -*-
"""音乐库「活动回忆」下拉选项可读性回归（2026-11-13 用户报「字看不清」）。

原生 <select> 弹窗底色不一定跟 color-scheme 走，选项文字若继承中间调 --ch-ink-2
落在浅底上对比不足。修法给 option 显式纸面底 + 墨色字。本探针读两套主题下 option
的**计算色**，按 WCAG 相对亮度算对比度，要求 ≥4.5:1（正文级）。

  py -3 scripts/diag/bgm_option_contrast.py

⚠️ 原生弹窗本身截不到图（OS 渲染），所以判据落在 option 的计算 color/background，
不是截图——这是这类原生控件可读性的可证形式。
"""
import sys, os, re, json, time
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, preflight

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def parse(s):
    return tuple(float(x) for x in re.findall(r'[\d.]+', s)[:3])


def ratio(c1, c2):
    a, b = lum(parse(c1)), lum(parse(c2))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def main():
    url = preflight('bgm.html')
    pg = Page(9453, os.path.join(ROOT, '.diag', '_bgmopt_profile'), url, (1600, 1000))
    fails = []
    try:
        for theme in ['light', 'dark']:
            pg.ev("try{localStorage.setItem('gallery.theme','%s')}catch(e){};location.reload()" % theme)
            time.sleep(8)
            col, bg = json.loads(pg.ev(
                "(()=>{const o=document.querySelector('#fEvent option:nth-child(2)');"
                "const c=getComputedStyle(o);return JSON.stringify([c.color,c.backgroundColor])})()"))
            r = ratio(col, bg)
            ok = r >= 4.5
            print(f'  {theme}: option color={col} bg={bg} contrast={r:.2f}:1 '
                  f'{"PASS" if ok else "FAIL"}')
            if not ok:
                fails.append(f'{theme} contrast {r:.2f}<4.5')
    finally:
        pg.close()
    if fails:
        print('! 未过：' + ', '.join(fails))
        sys.exit(1)
    print('两套主题选项对比度均 ≥4.5:1')


if __name__ == '__main__':
    main()