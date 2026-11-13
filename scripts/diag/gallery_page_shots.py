# -*- coding: utf-8 -*-
"""画廊多页改前/改后对照截图（真实等待，不用 virtual-time-budget）。

与 gallery_ui_shots.py 的分工：那个拍 index 的「列表+三种查看器」状态对；
这个拍**多个页面**的整页观感对（index / backgrounds / bgm / room3d），
支持昼/夜双主题、每页渲染断言、window 报错收集。

  py -3 scripts/diag/gallery_page_shots.py --tag before --out .diag/ui_fold
  py -3 scripts/diag/gallery_page_shots.py --tag after  --out .diag/ui_fold --theme both

⚠️ 判据落在「画面真的渲染了」：每页有各自的非空断言（卡片数/格子数/曲目行/.in 已挂/hud 文本），
截图前断言不过就非零退出——不许产出"空白但 exit 0"的假对照（gallery_ui_shots 的 preflight 同款教训）。
⚠️ 等待必须走真实墙钟：--virtual-time-budget 会把 IntersectionObserver 交错进场拍成半透明，
误判成对比度缺陷（2026-11-13 实测，见 TROUBLESHOOTING 对应条目）。
"""
import sys, os, json, time, argparse
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, preflight, BASE

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
WAIT = {'index.html': 6, 'backgrounds.html': 6, 'bgm.html': 9, 'room3d.html': 16, 'cg_export.html': 6}

# 每页的「真渲染了」断言，返回 [ok, 说明]
ASSERT = {
    'index.html': "(()=>{const n=document.querySelectorAll('.card').length;return [n>0,'cards='+n]})()",
    'backgrounds.html': "(()=>{const n=document.querySelectorAll('#grid .cell, #grid > *').length;return [n>0,'cells='+n]})()",
    'bgm.html': "(()=>{const r=document.querySelectorAll('.row');const i=document.querySelectorAll('.row.in');return [r.length>0&&i.length>0,'rows='+r.length+' in='+i.length]})()",
    'room3d.html': "(()=>{const c=document.querySelector('#stage canvas');const h=document.getElementById('hud');return [!!c&&!!h&&h.textContent.length>10,'canvas='+!!c+' hud='+(h?h.textContent.length:0)]})()",
}
ERRHOOK = ("window.__errs=[];addEventListener('error',e=>__errs.push(String(e.message)));"
           "addEventListener('unhandledrejection',e=>__errs.push('rej:'+String(e.reason&&e.reason.message||e.reason)));")


def shoot_page(page, theme, win, out, tag, port):
    url = preflight(page)
    profile = os.path.join(ROOT, '.diag', '_pageshots_profile')
    pg = Page(port, profile, url, win)
    try:
        pg.cmd('Page.addScriptToEvaluateOnNewDocument', {'source': ERRHOOK})
        pg.ev(f"try{{localStorage.setItem('gallery.theme','{theme}')}}catch(e){{}};location.reload()")
        time.sleep(WAIT.get(page, 8))
        ok, why = pg.ev(ASSERT.get(page, "[true,'no-assert']"))
        if not ok:
            raise SystemExit(f'! {page}/{theme}: 渲染断言不过（{why}）')
        errs = pg.ev('JSON.stringify(window.__errs||[])')
        path = os.path.join(out, f'{tag}_{page.replace(".html","")}_{theme}.png')
        pg.shot(path)
        print(f'  {os.path.basename(path)}  {why}  errs={errs}')
        return json.loads(errs)
    finally:
        pg.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pages', default='index.html,backgrounds.html,bgm.html,room3d.html')
    ap.add_argument('--tag', required=True)
    ap.add_argument('--out', default=os.path.join(ROOT, '.diag', 'ui_fold'))
    ap.add_argument('--win', default='2560,1600')
    ap.add_argument('--theme', default='light', choices=['light', 'dark', 'both'])
    ap.add_argument('--port', type=int, default=9437)
    ap.add_argument('--allow-err', default='THREE is not defined',
                    help='基线已存在的报错子串（spine-all.js 的 threejs 模块在 index 上无 THREE，改前就在）；差集之外的新报错才判红')
    a = ap.parse_args()
    win = tuple(int(x) for x in a.win.split(','))
    os.makedirs(a.out, exist_ok=True)
    themes = ['light', 'dark'] if a.theme == 'both' else [a.theme]
    all_errs = {}
    for p in a.pages.split(','):
        for t in themes:
            errs = shoot_page(p, t, win, a.out, a.tag, a.port)
            if errs:
                all_errs[f'{p}/{t}'] = errs
    if all_errs:
        new = {k: [e for e in v if a.allow_err not in e] for k, v in all_errs.items()}
        new = {k: v for k, v in new.items() if v}
        if new:
            print('! 新报错（基线之外）：' + json.dumps(new, ensure_ascii=False))
            sys.exit(2)
        print('报错与基线一致（' + a.allow_err + '），无新增')
    print('全部截图完成')


if __name__ == '__main__':
    main()