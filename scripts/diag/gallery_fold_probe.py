# -*- coding: utf-8 -*-
"""画廊「控制区折叠 / 信息退场 / 密度档」交互验收（2026-11-13 那轮改动的判据）。

全部走真实入口（按钮 .click() / select dispatch change / SiteBg.set），不直接调内部状态函数。
每页一个独立 Chrome（独立 profile 段），断言不过即非零退出；报错与基线（spine-all.js 的
THREE 未定义，改前就在）取差集，只有新增才判红。

  py -3 scripts/diag/gallery_fold_probe.py            # 全跑
  py -3 scripts/diag/gallery_fold_probe.py --only bgm # 只跑一页

判据清单见各 check_* 函数内联注释；截图落在 .diag/ui_fold/probe_*.png 供人眼复核。
"""
import sys, os, json, time, argparse
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, preflight

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'ui_fold')
SITEBG_URL = 'bg_thumbs/bg/bg_2.5ds_cg1.webp'
FAILS = []


def ck(name, cond, detail=''):
    print(('  PASS ' if cond else '  FAIL ') + name + (('  ' + str(detail)) if detail else ''))
    if not cond:
        FAILS.append(name)


def new_page(page, port, wait):
    url = preflight(page)
    pg = Page(port, os.path.join(ROOT, '.diag', '_foldprobe_profile'), url, (1600, 1000))
    pg.cmd('Page.addScriptToEvaluateOnNewDocument',
           {'source': "window.__errs=[];addEventListener('error',e=>__errs.push(String(e.message)));"})
    pg.ev('location.reload()')
    time.sleep(wait)
    return pg


def errs_new(pg):
    e = json.loads(pg.ev('JSON.stringify(window.__errs||[])'))
    return [x for x in e if 'THREE is not defined' not in x]


def check_index(port):
    print('[index]')
    pg = new_page('index.html', port, 6)
    try:
        ck('默认收起', pg.ev("document.getElementById('tMore').hidden===true && document.getElementById('foldBtn').getAttribute('aria-expanded')==='false'"))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点开次区 + 记住', pg.ev("document.getElementById('tMore').hidden===false && localStorage.getItem('gallery.fold.index')==='1'"))
        pg.ev('location.reload()'); time.sleep(5)
        ck('刷新后仍展开', pg.ev("document.getElementById('tMore').hidden===false"))
        r = pg.ev("(()=>{const s=document.getElementById('fFaction');s.value=s.options[1].value;s.dispatchEvent(new Event('change'));return [document.getElementById('foldN').hidden,document.getElementById('foldN').textContent,document.querySelectorAll('.card').length]})()")
        ck('筛选生效上徽标', r[0] is False and r[1] == '1' and r[2] < 1031, r)
        pg.ev("(()=>{const s=document.getElementById('fFaction');s.value='';s.dispatchEvent(new Event('change'))})()")
        ck('清筛选徽标消失', pg.ev("document.getElementById('foldN').hidden===true"))
        pg.ev("document.getElementById('infoBtn').click()")
        ck('ⓘ 弹层开 + 有模式文案', pg.ev("document.getElementById('infoPop').classList.contains('on') && document.getElementById('modehint').textContent.length>0"))
        pg.ev("document.body.click()")
        ck('点外面关弹层', pg.ev("!document.getElementById('infoPop').classList.contains('on')"))
        pg.ev("document.getElementById('foldBtn').click()")
        pg.ev('location.reload()'); time.sleep(5)
        ck('收起也记住', pg.ev("document.getElementById('tMore').hidden===true"))
        ck('无新增报错', not errs_new(pg), errs_new(pg))
    finally:
        pg.close()


def check_backgrounds(port):
    print('[backgrounds]')
    pg = new_page('backgrounds.html', port, 6)
    try:
        ck('默认收起', pg.ev("document.getElementById('fMore').hidden===true"))
        ck('gHint 常驻不折叠', pg.ev("document.getElementById('gHint').hidden===false && document.getElementById('gHint').textContent.includes('藏')"))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点开筛选区', pg.ev("document.getElementById('fMore').hidden===false"))
        pg.ev("document.querySelector('#gTier .chipset .chip:nth-child(2)').click()")
        ck('命名档筛选上徽标', pg.ev("document.getElementById('foldN').hidden===false && document.getElementById('foldN').textContent==='1'"))
        pg.ev('location.reload()'); time.sleep(6)
        ck('刷新后仍展开', pg.ev("document.getElementById('fMore').hidden===false"))
        ck('gHint 仍在', pg.ev("document.getElementById('gHint').hidden===false"))
        ck('无新增报错', not errs_new(pg), errs_new(pg))
    finally:
        pg.close()


def check_room3d(port):
    print('[room3d]')
    pg = new_page('room3d.html', port, 16)
    try:
        ck('次区默认收起', pg.ev("document.getElementById('bMore').hidden===true"))
        ck('hud 默认折叠成小丸', pg.ev("document.getElementById('hud').hidden===true && !!document.getElementById('hudToggle')"))
        pg.ev("document.getElementById('hudToggle').click()")
        ck('小丸展开诊断 + 含装配说明', pg.ev("document.getElementById('hud').hidden===false && document.getElementById('hud').textContent.includes('网格对象') && document.getElementById('hud').textContent.includes('room.glb 由场景包直接装配')"))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点开更多设置', pg.ev("document.getElementById('bMore').hidden===false"))
        pg.ev("document.querySelector('.sw[data-k=sky]').click()")
        ck('折叠区里的推断开关真能拨', pg.ev("document.querySelector('.sw[data-k=sky]').classList.contains('on')"))
        pg.shot(os.path.join(OUT, 'probe_room3d_open.png'))
        pg.ev('location.reload()'); time.sleep(16)
        ck('刷新后展开状态都记住', pg.ev("document.getElementById('bMore').hidden===false && document.getElementById('hud').hidden===false"))
        ck('无新增报错', not errs_new(pg), errs_new(pg))
    finally:
        pg.close()


def check_bgm(port):
    print('[bgm]')
    pg = new_page('bgm.html', port, 9)
    try:
        h0 = pg.ev("document.querySelector('.row').offsetHeight")
        ck('默认舒适档', pg.ev("!document.body.classList.contains('compact')"), 'rowH=' + str(h0))
        pg.ev("document.querySelector('#gDensity button[data-d=compact]').click()")
        h1 = pg.ev("document.querySelector('.row').offsetHeight")
        ck('紧凑档行高下降', pg.ev("document.body.classList.contains('compact')") and h1 < h0 - 15, f'{h0}->{h1}')
        ck('密度记住', pg.ev("localStorage.getItem('gallery.bgmDensity')==='compact'"))
        pg.ev('location.reload()'); time.sleep(9)
        ck('刷新后仍紧凑', pg.ev("document.body.classList.contains('compact')"))
        bg0 = pg.ev("getComputedStyle(document.querySelector('.chartlayer')).backgroundImage")
        pg.ev(f"window.SiteBg.set({{kind:'bg',url:'{SITEBG_URL}'}})")
        pg.ev('location.reload()'); time.sleep(9)
        ck('站背景生效', pg.ev("document.documentElement.classList.contains('has-sitebg')"))
        bg1 = pg.ev("getComputedStyle(document.querySelector('.chartlayer')).backgroundImage")
        ck('压色层随站背景启用', bg0 != bg1 and 'rgba' in bg1, bg1[:90])
        pg.shot(os.path.join(OUT, 'probe_bgm_sitebg_compact.png'))
        ck('无新增报错', not errs_new(pg), errs_new(pg))
    finally:
        pg.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    jobs = [('index', check_index, 9441), ('backgrounds', check_backgrounds, 9442),
            ('room3d', check_room3d, 9443), ('bgm', check_bgm, 9444)]
    for name, fn, port in jobs:
        if a.only and a.only != name:
            continue
        fn(port)
    if FAILS:
        print('! 未过判据：' + ', '.join(FAILS))
        sys.exit(1)
    print('全部判据通过')


if __name__ == '__main__':
    main()