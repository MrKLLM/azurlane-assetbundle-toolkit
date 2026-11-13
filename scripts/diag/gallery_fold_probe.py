# -*- coding: utf-8 -*-
"""画廊「控制区折叠 / 信息退场 / 密度档」交互验收（2026-11-13 那轮改动的判据）。

全部走真实入口（按钮 .click() / select dispatch change / SiteBg.set），不直接调内部状态函数。
每页一个独立 Chrome（独立 profile 段），断言不过即非零退出；报错与基线（spine-all.js 的
THREE 未定义，改前就在）取差集，只有新增才判红。

  py -3 scripts/diag/gallery_fold_probe.py            # 全跑
  py -3 scripts/diag/gallery_fold_probe.py --only bgm # 只跑一页

判据清单见各 check_* 函数内联注释；截图落在 .diag/ui_fold/probe_*.png 供人眼复核。
"""
import sys, os, json, time, argparse, tempfile
from contextlib import contextmanager
sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, preflight

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'ui_fold')
SITEBG_URL = 'bg_thumbs/bg/bg_2.5ds_cg1.webp'
FAILS = []


def ck(name, cond, detail=''):
    # Page.ev 的异常是非空 'EXC ...' 字符串，不能按 Python truthiness 放行。
    ok = cond is True
    if not ok and not detail:
        detail = repr(cond)
    print(('  PASS ' if ok else '  FAIL ') + name + (('  ' + str(detail)) if detail else ''))
    if not ok:
        FAILS.append(name)


READY = {
    'index.html': "document.querySelectorAll('.card').length>0 && document.querySelectorAll('#fFaction option').length>1",
    'backgrounds.html': "!!document.querySelector('#gTier .chipset .chip:nth-child(2)') && !!document.querySelector('#grid .card')",
    'room3d.html': "!!document.querySelector('#load.hide') && document.getElementById('hud').textContent.includes('网格对象')",
    'bgm.html': "!!document.querySelector('.row') && !!document.querySelector('#gDensity button[data-d=compact]') && !!window.SiteBg",
}


def wait_dom(pg, expr, timeout=45):
    deadline = time.monotonic() + timeout
    while True:
        result = pg.ev(expr)
        if result is True:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError(f'DOM 等待超时: {expr}; 最后结果={result!r}')
        time.sleep(0.1)


def errs_new(pg):
    e = pg.ev('window.__errs')
    if not isinstance(e, list) or not all(isinstance(x, str) for x in e):
        return [f'错误列表读取失败: {e!r}']
    return [x for x in e if 'THREE is not defined' not in x]


def reload_page(pg, page, check_errors=True):
    if check_errors:
        errors = errs_new(pg)
        ck('刷新前无新增报错', not errors, errors)
    # 旧文档即使仍 complete 也不能通过；新文档不会保留这个标记。
    pg.ev('window.__foldProbeLeaving=true; location.reload()')
    wait_dom(pg, "window.__foldProbeLeaving!==true && document.readyState==='complete' && (" + READY[page] + ")",
             timeout=120 if page == 'room3d.html' else 45)


@contextmanager
def new_page(page, port):
    url = preflight(page)
    with tempfile.TemporaryDirectory(prefix='gallery_fold_probe_') as profile:
        pg = Page(port, profile, url, (1600, 1000))
        try:
            pg.cmd('Page.addScriptToEvaluateOnNewDocument',
                   {'source': "window.__errs=[];addEventListener('error',e=>__errs.push(String(e.message)));"})
            reload_page(pg, page, check_errors=False)
            yield pg
        finally:
            pg.close()  # Chrome 退出后才由 TemporaryDirectory 清除 profile。


def fold_state(pg, panel, expanded=True):
    return pg.ev("""(()=>{const e=document.getElementById(%s), b=document.getElementById('foldBtn');
      if(!e||!b) return false;
      const r=e.getBoundingClientRect(), s=getComputedStyle(e);
      return %s ? e.hidden===false && s.display!=='none' && s.visibility==='visible' &&
        r.width>0 && r.height>0 && b.getAttribute('aria-expanded')==='true'
        : e.hidden===true && s.display==='none' && b.getAttribute('aria-expanded')==='false';})()"""
        % (json.dumps(panel), json.dumps(expanded)))


def check_narrow(pg, page, panel):
    controls = {'tMore': '#fFaction, #fType, #fRarity, #fHas, #gOpt button, #clearBg',
                'fMore': '#gTier .chip, #gGroup .chip', 'bMore': '#bMore button, #bMore input'}
    pg.cmd('Emulation.setDeviceMetricsOverride',
           {'width': 390, 'height': 844, 'deviceScaleFactor': 1, 'mobile': False})
    try:
        wait_dom(pg, "document.readyState==='complete' && window.innerWidth===390")
        ck('390px 高频控制区仍展开可见', fold_state(pg, panel))
        sizes = pg.ev('({viewport:innerWidth, client:document.documentElement.clientWidth, '
                      'html:document.documentElement.scrollWidth, body:document.body.scrollWidth})')
        ck('390px 无横向溢出', pg.ev("innerWidth===390 && Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)<=document.documentElement.clientWidth"), sizes)
        ck('390px 高频控件有尺寸且不越过左右边界', pg.ev("""(()=>{
          const nodes=[document.getElementById('foldBtn'),...document.querySelectorAll(%s)];
          return nodes.length>1 && nodes.every(e=>{if(!e) return false;
            const r=e.getBoundingClientRect(), s=getComputedStyle(e);
            return !e.hidden && s.display!=='none' && s.visibility==='visible' && r.width>0 && r.height>0 &&
              r.left>=-1 && r.right<=document.documentElement.clientWidth+1;});})()""" % json.dumps(controls[panel])))
        pg.shot(os.path.join(OUT, f'probe_{page[:-5]}_legacy0_390.png'))
    finally:
        pg.cmd('Emulation.clearDeviceMetricsOverride')


def check_reload_defaults(pg, page, panel):
    key = json.dumps('gallery.fold.' + page[:-5])
    ck('手动折叠未写持久化键', pg.ev(f'localStorage.getItem({key})===null'))
    pg.ev("document.getElementById('foldBtn').click()")
    ck('刷新前确实手动收起', fold_state(pg, panel, False))
    reload_page(pg, page)
    ck('收起后刷新必展开', fold_state(pg, panel))
    ck('刷新未写持久化键', pg.ev(f'localStorage.getItem({key})===null'))
    ck('显式种入旧键0', pg.ev(f"localStorage.setItem({key},'0'); localStorage.getItem({key})==='0'"))
    reload_page(pg, page)
    ck('旧键0刷新仍展开', fold_state(pg, panel))
    ck('旧键保持0（页面不再写入）', pg.ev(f"localStorage.getItem({key})==='0'"))
    pg.shot(os.path.join(OUT, f'probe_{page[:-5]}_legacy0.png'))
    check_narrow(pg, page, panel)


def check_index(port):
    print('[index]')
    with new_page('index.html', port) as pg:
        ck('干净 profile 无旧折叠键', pg.ev("localStorage.getItem('gallery.fold.index')===null"))
        ck('默认展开（高频控件真可见）', fold_state(pg, 'tMore'))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点一下收起', fold_state(pg, 'tMore', False))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('再点展开', fold_state(pg, 'tMore'))
        check_reload_defaults(pg, 'index.html', 'tMore')
        r = pg.ev("(()=>{const s=document.getElementById('fFaction');s.value=s.options[1].value;s.dispatchEvent(new Event('change'));return [document.getElementById('foldN').hidden,document.getElementById('foldN').textContent,document.querySelectorAll('.card').length]})()")
        ck('筛选生效上徽标', isinstance(r, list) and len(r) == 3 and r[0] is False and r[1] == '1' and isinstance(r[2], int) and 0 < r[2] < 1031, r)
        pg.ev("(()=>{const s=document.getElementById('fFaction');s.value='';s.dispatchEvent(new Event('change'))})()")
        ck('清筛选徽标消失', pg.ev("document.getElementById('foldN').hidden===true"))
        pg.ev("document.getElementById('infoBtn').click()")
        ck('ⓘ 弹层开 + 有模式文案', pg.ev("document.getElementById('infoPop').classList.contains('on') && document.getElementById('modehint').textContent.length>0"))
        pg.ev("document.body.click()")
        ck('点外面关弹层', pg.ev("!document.getElementById('infoPop').classList.contains('on')"))
        ck('无新增报错', not errs_new(pg), errs_new(pg))


def check_backgrounds(port):
    print('[backgrounds]')
    with new_page('backgrounds.html', port) as pg:
        ck('干净 profile 无旧折叠键', pg.ev("localStorage.getItem('gallery.fold.backgrounds')===null"))
        ck('默认展开（高频筛选真可见）', fold_state(pg, 'fMore'))
        ck('gHint 常驻不折叠', pg.ev("document.getElementById('gHint').hidden===false && document.getElementById('gHint').textContent.includes('藏')"))
        pg.ev("document.querySelector('#gTier .chipset .chip:nth-child(2)').click()")
        ck('命名档筛选上徽标', pg.ev("document.getElementById('foldN').hidden===false && document.getElementById('foldN').textContent==='1'"))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点一下收起', fold_state(pg, 'fMore', False))
        ck('收起后 gHint 仍在', pg.ev("document.getElementById('gHint').hidden===false"))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('再点展开', fold_state(pg, 'fMore'))
        check_reload_defaults(pg, 'backgrounds.html', 'fMore')
        ck('无新增报错', not errs_new(pg), errs_new(pg))


def check_room3d(port):
    print('[room3d]')
    with new_page('room3d.html', port) as pg:
        ck('干净 profile 无旧折叠键', pg.ev("localStorage.getItem('gallery.fold.room3d')===null"))
        ck('次区默认展开（主操作常驻）', fold_state(pg, 'bMore'))
        ck('hud 默认折叠成小丸（低频信息）', pg.ev("document.getElementById('hud').hidden===true && !!document.getElementById('hudToggle')"))
        pg.ev("document.getElementById('hudToggle').click()")
        ck('小丸展开诊断 + 含装配说明', pg.ev("document.getElementById('hud').hidden===false && document.getElementById('hud').textContent.includes('网格对象') && document.getElementById('hud').textContent.includes('room.glb 由场景包直接装配')"))
        pg.ev("document.querySelector('.sw[data-k=sky]').click()")
        ck('推断开关真能拨', pg.ev("document.querySelector('.sw[data-k=sky]').classList.contains('on')"))
        pg.shot(os.path.join(OUT, 'probe_room3d_open.png'))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('点一下收起更多', fold_state(pg, 'bMore', False))
        pg.ev("document.getElementById('foldBtn').click()")
        ck('再点展开更多', fold_state(pg, 'bMore'))
        check_reload_defaults(pg, 'room3d.html', 'bMore')
        ck('hud 展开状态记住', pg.ev("document.getElementById('hud').hidden===false"))
        ck('无新增报错', not errs_new(pg), errs_new(pg))


def check_bgm(port):
    print('[bgm]')
    with new_page('bgm.html', port) as pg:
        h0 = pg.ev("document.querySelector('.row').offsetHeight")
        ck('默认舒适档', pg.ev("!document.body.classList.contains('compact')"), 'rowH=' + str(h0))
        pg.ev("document.querySelector('#gDensity button[data-d=compact]').click()")
        h1 = pg.ev("document.querySelector('.row').offsetHeight")
        ck('紧凑档行高下降', pg.ev("document.body.classList.contains('compact')") is True and isinstance(h0, (int, float)) and isinstance(h1, (int, float)) and h1 > 0 and h1 < h0 - 15, f'{h0}->{h1}')
        ck('密度记住', pg.ev("localStorage.getItem('gallery.bgmDensity')==='compact'"))
        reload_page(pg, 'bgm.html')
        ck('刷新后仍紧凑', pg.ev("document.body.classList.contains('compact')"))
        bg0 = pg.ev("getComputedStyle(document.querySelector('.chartlayer')).backgroundImage")
        pg.ev(f"window.SiteBg.set({{kind:'bg',url:'{SITEBG_URL}'}})")
        reload_page(pg, 'bgm.html')
        ck('站背景生效', pg.ev("document.documentElement.classList.contains('has-sitebg')"))
        bg1 = pg.ev("getComputedStyle(document.querySelector('.chartlayer')).backgroundImage")
        ck('压色层随站背景启用', isinstance(bg0, str) and isinstance(bg1, str) and not bg0.startswith('EXC ') and not bg1.startswith('EXC ') and bg0 != bg1 and 'rgba' in bg1, str(bg1)[:90])
        pg.shot(os.path.join(OUT, 'probe_bgm_sitebg_compact.png'))
        ck('无新增报错', not errs_new(pg), errs_new(pg))


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