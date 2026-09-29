# -*- coding: utf-8 -*-
"""画廊控件状态取证：同一个元素，静止 / 悬停 / 按下 三态成对截图并拼一张对比图。

为什么必须走 CDP 真实事件而不是 `dispatchEvent`：`:hover` / `:active` 这类伪类
由浏览器的**命中测试**决定，不由事件决定——合成事件永远点不亮它们，
用它们做判据得到的是假绿（详见 docs/TROUBLESHOOTING.md §62）。
按压的事件类型是 `mousePressed`/`mouseReleased`，写成 `mouseDown` 会被**静默忽略**。

  py -3 scripts/diag/gallery_state_shots.py                        # 默认三个全局开关 + 一张卡
  py -3 scripts/diag/gallery_state_shots.py --theme dark --tags "#gOpt button[data-k=lines],.dd-btn"
  py -3 scripts/diag/gallery_state_shots.py --card 3 --out .diag/uishots

⚠️ 三态之间要把指针**移回空白处**再拍"静止"，否则上一张卡的 hover 会留在画面里；
   悬停要边小幅挪边轮询到 `matches(':hover')` 为真——单次 mouseMoved 不一定刷新命中测试。
"""
import sys, os, time, json, base64, io, argparse
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gallery_ui_shots import Page, BASE, preflight
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))


def load_font(px=18):
    for f in (r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\segoeui.ttf'):
        try:
            return ImageFont.truetype(f, px)
        except Exception:
            pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--page', default='index.html')
    ap.add_argument('--theme', default='light', choices=['light', 'dark'])
    ap.add_argument('--tags', default='#gOpt button[data-k=voice],#gOpt button[data-k=lines],.dd-btn',
                    help='逗号分隔的 CSS 选择器，每个都拍三态')
    ap.add_argument('--card', type=int, default=3, help='额外拍一张卡片的静止/悬停对照；<0 跳过')
    ap.add_argument('--port', type=int, default=9541)
    ap.add_argument('--win', default='1440,900')
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'uishots'))
    a = ap.parse_args()
    W, H = (int(v) for v in a.win.split(','))
    os.makedirs(a.out, exist_ok=True)
    url = preflight(a.page)
    pg = Page(a.port, os.path.join(ROOT, '.diag', 'chrome_stateshots'), url, (W, H))
    pg.cmd('Emulation.setDeviceMetricsOverride',
           {'width': W, 'height': H, 'deviceScaleFactor': 1, 'mobile': False})
    pg.ev(f"localStorage.setItem('gallery.theme','{a.theme}')")
    pg.cmd('Page.navigate', {'url': url})
    time.sleep(9)

    def shot(clip):
        d = base64.b64decode(pg.cmd('Page.captureScreenshot',
                                    {'format': 'png', 'clip': dict(clip, scale=1.6)})['data'])
        return Image.open(io.BytesIO(d)).convert('RGB')

    def move(x, y):
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseMoved', 'x': x, 'y': y})

    def rect_of(sel):
        return json.loads(pg.ev(
            f"(()=>{{const b=document.querySelector({json.dumps(sel)});"
            "if(!b) return '[]'; const r=b.getBoundingClientRect();"
            'return JSON.stringify([r.x,r.y,r.width,r.height]);})()'))

    def wait_hover(sel):
        """边小幅挪边轮询：单次 mouseMoved 不一定刷新命中测试（§62 第 9 条）。"""
        r = rect_of(sel)
        if not r:
            return None
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        for k in range(12):
            move(cx - 3 + k * .6, cy - 2 + k * .4)
            time.sleep(0.14)
            if pg.ev(f"(()=>{{const b=document.querySelector({json.dumps(sel)});"
                     "return String(b.matches(':hover'))===\'true\'}})()"):
                return r
        return r

    rows = []
    for sel in [x.strip() for x in a.tags.split(',') if x.strip()]:
        r = rect_of(sel)
        if not r:
            print('跳过（找不到元素）:', sel)
            continue
        clip = {'x': r[0] - 26, 'y': r[1] - 22, 'width': r[2] + 52, 'height': r[3] + 44}
        move(6, 6); time.sleep(0.6)
        still = shot(clip)
        wait_hover(sel); time.sleep(0.5)
        hov = shot(clip)
        cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2
        st = pg.ev(f"getComputedStyle(document.querySelector({json.dumps(sel)})).filter")
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mousePressed', 'x': cx, 'y': cy,
                                           'button': 'left', 'buttons': 1, 'clickCount': 1})
        for _ in range(14):                      # 轮询到过渡落位，别用固定 sleep
            time.sleep(0.15)
            pr = pg.ev(f"getComputedStyle(document.querySelector({json.dumps(sel)})).filter")
            if 'brightness' in (pr or '') and abs(float(pr.split('(')[1].split(')')[0]) - .94) < .04:
                break
        press = shot(clip)
        pg.cmd('Input.dispatchMouseEvent', {'type': 'mouseReleased', 'x': cx, 'y': cy,
                                           'button': 'left', 'buttons': 0, 'clickCount': 1})
        move(6, 6); time.sleep(0.4)
        rows.append((sel, still, hov, press))
        print(f'{sel}: hover.filter={st} → press.filter={pr}')

    card_pair = None
    if a.card >= 0:
        c = pg.ev(f"""(()=>{{const k=document.querySelectorAll('.card')[{a.card}];
          const r=k.getBoundingClientRect(); return JSON.stringify([r.x,r.y,r.width,r.height]);}})()""")
        c = json.loads(c)
        clip = {'x': c[0] - 24, 'y': c[1] - 24, 'width': c[2] + 48, 'height': c[3] + 48}
        move(6, 6); time.sleep(0.7)
        c0 = shot(clip)
        move(c[0] + c[2] * .22, c[1] + c[3] * .24); time.sleep(0.5)
        move(c[0] + c[2] * .24, c[1] + c[3] * .26); time.sleep(1.0)
        c1 = shot(clip)
        move(6, 6)
        card_pair = (c0, c1)
    pg.close()

    f = load_font()
    labels = ['静止', '悬停', '按下']
    cw = max(max(r[1].width for r in rows), 1) + 16
    rh = max(r[1].height for r in rows)
    n_rows = len(rows) + (1 if card_pair else 0)
    out = Image.new('RGB', (cw * 3 + 32, (rh + 30) * n_rows + 8), (255, 255, 255))
    d = ImageDraw.Draw(out)
    for i, lab in enumerate(labels):
        d.text((10 + i * (cw + 8), 4), lab, fill=(20, 40, 70), font=f)
    y = 28
    for sel, *ims in rows:
        for i, im in enumerate(ims):
            out.paste(im, (8 + i * (cw + 8), y))
        y += rh + 30
    if card_pair:
        d.text((10, y + 4), f'卡片 #{a.card}（静止 / 悬停）', fill=(20, 40, 70), font=f)
        out.paste(card_pair[0], (8, y + 26))
        out.paste(card_pair[1], (8 + cw + 8, y + 26))
    dest = os.path.join(a.out, f'states_{a.page.replace(".html", "")}_{a.theme}.png')
    out.save(dest)
    print('拼图：', dest, out.size)


if __name__ == '__main__':
    main()
