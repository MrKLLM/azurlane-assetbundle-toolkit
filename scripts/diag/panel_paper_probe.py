#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""panel_paper_probe.py — 纸本控制台的界面验收（2026-10-17 版面）。

上一版 `panel_ui_probe.py` 判的是「夜航星野 + 海军蓝 + 指针光效」那套版面；
2026-10-17 用户改判为纸本控制台（暖纸 / 墨 / 朱砂 / 苔绿 / 零玻璃 / 零星野），
旧探针里的星点密度、背景显影、指针光效等判据已失去前提，保留作历史对照。
本探针只判**新版面自己声称的东西**：

  1. 骨架：5 个步骤、全部阶段卡片都在（不是"看起来有"）；
  2. 字与色：主标题确实是衬线、纸底是暖色、全站零 backdrop-filter；
  3. 边界：星野与指针光效层确实退役（display:none），静止时 0 个动画；
  4. 交互：五步可点、细节/说明可开合、夜读可切换且能切回；
  5. 窄屏：右栏折到底部、进度线不横穿文字、无横向溢出；
  6. 截图：主屏 / 细节 / 夜读 / 窄屏四张，落到 .diag/panel_paper/。

用法:
  py -3 scripts/diag/panel_paper_probe.py --port 8790
  py -3 scripts/diag/panel_paper_probe.py --port 8790 --win 1600,1000

退出码: 0 全绿；1 有判红（逐条打印）。
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import websocket          # noqa: E402
import chrome_tree        # noqa: E402
from gallery_ui_shots import CHROME   # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
OUT = os.path.join(ROOT, '.diag', 'panel_paper')
FAILS = []


def chk(name, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + name + ((' — ' + detail) if detail else ''))
    if not ok:
        FAILS.append(name)


class Pg:
    def __init__(self, cdp, url, win):
        prof = os.path.join(OUT, f'chrome_{os.getpid()}')
        os.makedirs(prof, exist_ok=True)
        self.proc = chrome_tree.install(subprocess.Popen([
            CHROME, '--headless=new', f'--remote-debugging-port={cdp}',
            '--remote-allow-origins=*', f'--user-data-dir={prof}',
            '--no-first-run', '--no-default-browser-check',
            '--disable-background-timer-throttling', '--enable-unsafe-swiftshader',
            '--use-angle=swiftshader', f'--window-size={win[0]},{win[1]}', url,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        ws = None
        for _ in range(120):
            try:
                tabs = json.load(urllib.request.urlopen(f'http://127.0.0.1:{cdp}/json'))
                hit = [t for t in tabs if '127.0.0.1' in t.get('url', '')
                       and t.get('webSocketDebuggerUrl')]
                if hit:
                    ws = hit[0]['webSocketDebuggerUrl']
                    break
            except Exception:
                pass
            time.sleep(0.5)
        if not ws:
            raise RuntimeError('no CDP tab（控制台起来了么？）')
        self.ws = websocket.create_connection(ws, timeout=120, max_size=None)
        self.i = 0
        self.exc = []

    def cmd(self, method, params=None):
        self.i += 1
        self.ws.send(json.dumps({'id': self.i, 'method': method, 'params': params or {}}))
        while True:
            m = json.loads(self.ws.recv())
            if m.get('method') == 'Runtime.exceptionThrown':
                self.exc.append(m['params']['exceptionDetails'].get('text'))
            if m.get('id') == self.i:
                return m.get('result', {})

    def ev(self, expr):
        r = self.cmd('Runtime.evaluate', {'expression': expr, 'returnByValue': True})
        return r.get('result', {}).get('value')

    def shot(self, name):
        r = self.cmd('Page.captureScreenshot', {'format': 'png'})
        with open(os.path.join(OUT, name), 'wb') as f:
            f.write(base64.b64decode(r['data']))

    def size(self, w, h):
        self.cmd('Emulation.setDeviceMetricsOverride',
                 {'width': w, 'height': h, 'deviceScaleFactor': 1, 'mobile': False})

    def go(self, url, wait=2.4):
        self.cmd('Page.navigate', {'url': url})
        time.sleep(wait)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def start_panel(port):
    try:
        urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1.5)
        return None
    except Exception:
        pass
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, 'scripts', 'pipeline_panel.py'),
                          '--no-open', '--port', str(port)],
                         cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    chrome_tree.install(p)
    for _ in range(60):
        try:
            urllib.request.urlopen(f'http://127.0.0.1:{port}/', timeout=1.5)
            return p
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f'控制台没在 {port} 上起来')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8790)
    ap.add_argument('--cdp', type=int, default=8891)
    ap.add_argument('--win', default='1600,1000')
    a = ap.parse_args()
    win = tuple(int(x) for x in a.win.split(','))
    os.makedirs(OUT, exist_ok=True)
    start_panel(a.port)
    url = f'http://127.0.0.1:{a.port}/'
    pg = Pg(a.cdp, url, win)
    try:
        pg.cmd('Runtime.enable')
        pg.cmd('Page.enable')
        pg.size(*win)
        pg.go(url, 3)

        print('\n── 骨架与文案 ─────────────────────────────────')
        nstep = pg.ev("document.querySelectorAll('.snode').length")
        ndot = pg.ev("document.querySelectorAll('.snode .dot').length")
        nstage = pg.ev("(window.__probe&&__probe.state().stages||[]).length")
        chk('五个步骤全部渲染', nstep == 5, f'.snode={nstep}')
        chk('阶段方块数与状态表一致', ndot == nstage, f'.dot={ndot} / stages={nstage}')

        counts = []
        asks = []
        ebs = []
        for n in range(1, 6):
            pg.ev(f"document.querySelectorAll('.snode')[{n-1}].click()")
            time.sleep(0.35)
            counts.append(pg.ev("document.querySelectorAll('#cards .stage').length"))
            asks.append(pg.ev("document.querySelector('.ask').textContent.trim()"))
            ebs.append(pg.ev("document.getElementById('eyebrowTx').textContent.trim()"))
        chk('每个阶段的卡片都挂在某一步下（合计 = 阶段数）',
            sum(counts) == nstage, f'{counts} 合计 {sum(counts)} / {nstage}')
        chk('五步都有各自的指令句', len(set(asks)) >= 4 and all(asks),
            ' / '.join(x[:10] for x in asks))
        # 步骤标题必须来自状态表，不能是第二份手抄的 STEPNAME（2026-10-17 它曾整体错位一位）
        import json as _json
        titles = _json.loads(pg.ev(
            "JSON.stringify(Object.values(window.__probe.state().steps||{}).map(x=>x[0]))") or '[]')
        chk('步骤标题与状态表逐字一致',
            len(titles) == 5 and all(t in eb for t, eb in zip(titles, ebs)),
            ' / '.join(f'{t}↔{eb.split("·")[1].strip() if "·" in eb else eb}' for t, eb in zip(titles, ebs)))
        # 动作范围必须落在本步：第 2 步「同步配置表」是后加的，旧版手抄的 n===2/3/4
        # 曾整体错位一位，还把「换入」签成空清单（step===4 时 swap 阶段已经搬到第 5 步）。
        scopes = _json.loads(pg.ev(
            "JSON.stringify({cfg:__probe.scope('cfgsync'),exp:__probe.scope('export'),"
            "sw:__probe.scope('swap'),live:__probe.live('swap'),review:__probe.scope('review')})") or '{}')
        smap = _json.loads(pg.ev(
            "JSON.stringify(Object.fromEntries((__probe.state().stages||[]).map(s=>[s.key,s.step])))") or '{}')
        chk('同步配置表动作只跑第 2 步的阶段',
            bool(scopes.get('cfg')) and all(smap.get(k) == 2 for k in scopes['cfg']),
            f"{scopes.get('cfg')}")
        chk('重导动作只跑第 3 步的阶段',
            bool(scopes.get('exp')) and all(smap.get(k) == 3 for k in scopes['exp']),
            f"{scopes.get('exp')}")
        chk('换入动作只跑第 5 步的阶段',
            bool(scopes.get('sw')) and all(smap.get(k) == 5 for k in scopes['sw']),
            f"{scopes.get('sw')}")
        chk('换入签字单不是空清单（swap-in + derive 至少两项）',
            len(scopes.get('live') or []) >= 2, f"{scopes.get('live')}")
        # 截图回到第一步，别把测试末态（第 5 步）当成产品首屏
        pg.ev("document.querySelectorAll('.snode')[0].click()")
        time.sleep(0.4)

        print('\n── 字与色 ─────────────────────────────────────')
        fam = pg.ev("getComputedStyle(document.querySelector('.ask')).fontFamily") or ''
        size = pg.ev("parseFloat(getComputedStyle(document.querySelector('.ask')).fontSize)")
        chk('主标题走衬线字体', 'Noto Serif SC' in fam or 'Source Han Serif' in fam, fam[:42])
        chk('主标题字号 >= 40px', (size or 0) >= 40, f'{size}px')
        body = pg.ev("getComputedStyle(document.body).backgroundColor") or ''
        import re
        m = re.search(r'(\d+),\s*(\d+),\s*(\d+)', body)
        rgb = tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
        chk('纸底是暖色（R>G>B，且不是高饱和）',
            rgb[0] > rgb[1] > rgb[2] and max(rgb) - min(rgb) < 40, str(rgb))
        nbd = pg.ev("[...document.querySelectorAll('*')].filter(e=>"
                    "getComputedStyle(e).backdropFilter!=='none').length")
        chk('全站零 backdrop-filter（玻璃退役）', nbd == 0, f'{nbd} 个')
        nbg = pg.ev("getComputedStyle(document.getElementById('bgfx')).display")
        nfx = pg.ev("getComputedStyle(document.getElementById('fxbeam')).display")
        chk('星野层退役', nbg == 'none', nbg)
        chk('指针光效层退役', nfx == 'none', nfx)

        print('\n── 静止与交互 ─────────────────────────────────')
        time.sleep(1.2)   # 五步点完会触发 .snode.in / .ask.swap 的入场动画，等它们跑完再判
        chk('静止时零个动画在跑', (pg.ev("document.getAnimations().length") or 0) == 0,
            f"getAnimations={pg.ev('document.getAnimations().length')}")
        # 数据状态相关：preflight 因配置表过期判红时，第 1 步不能被锁死成只剩「重查」，
        # 卡点要把修复动作指到第 2 步（2026-10-17 用户：点完再查一次没反应，第一步也没处按）。
        why_now = pg.ev("document.getElementById('why').textContent") or ''
        if '配置表过期' in why_now:
            acts = pg.ev("__probe.ask().acts") or []
            gate_acts = pg.ev("__probe.ask().gateActs") or []
            chk('配置表过期时第 1 步仍能拉包（不把整步锁死）',
                any(x.startswith('pullcheck|') for x in acts), ' / '.join(acts))
            chk('卡点提供「去第 2 步同步配置表」',
                any(x.startswith('goto|') and '同步配置表' in x for x in gate_acts),
                ' / '.join(gate_acts))
            chk('待办指向第 2 步（修复动作所在）',
                pg.ev("__probe.work()") == 2, str(pg.ev("__probe.work()")))
        pg.shot('main.png')

        # 回执：结论没变时也必须留下"跑过"的证据（旧版这里一声不响）
        if '配置表过期' in why_now:
            pg.ev("document.querySelectorAll('#gate button')[1].click()")
            time.sleep(0.3)
            mid = pg.ev("document.getElementById('receipt').textContent") or ''
            chk('动作提交后立刻有回执', ('已提交' in mid or ' 秒' in mid), mid[:60])
            rc = ''
            for _ in range(30):
                time.sleep(0.5)
                rc = pg.ev("document.getElementById('receipt').textContent") or ''
                if ' 秒' in rc:
                    break
            chk('重查跑完留下结论与用时', ('重查闸门' in rc and ' 秒' in rc), rc[:90])
            chk('回执不再把「⇒ 跑 cfg…」塞进括号', '⇒' not in rc, rc[:90])
            pg.shot('gate_receipt.png')

        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.9)
        chk('细节抽屉能打开', bool(pg.ev("document.getElementById('detail').classList.contains('on')")))
        chk('细节里有日志与最近任务',
            bool(pg.ev("!!document.getElementById('log')")) and
            (pg.ev("document.querySelectorAll('#runs tr').length") or 0) > 0)
        chk('日志是深色电传面（与纸面分层）',
            'rgb(18, 16, 13)' == pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"),
            pg.ev("getComputedStyle(document.getElementById('log')).backgroundColor"))
        pg.shot('detail.png')
        pg.ev("document.getElementById('bDetail').click()")
        time.sleep(0.4)

        print('\n── 步骤状态与签字 ─────────────────────────────')
        # 探针不能假设"待办一定是第 2 步"：用户可能已经同步完配置表、正在第 3 步。
        work = pg.ev("__probe.work()")
        # 第 3 步：只要这一步有 live 阶段，主按钮必须先弹签字单，不能"点了直接开跑又回来"
        # （2026-10-17 用户点的就是「重跑到待确认」，以为签字窗坏了）。
        pg.ev("document.querySelectorAll('.snode')[2].click()")
        time.sleep(0.45)
        ask3 = pg.ev("document.querySelector('.ask').textContent") or ''
        cta3 = pg.ev("document.querySelector('#cta .pact').textContent") or ''
        if '签字' in ask3 or '重导' in ask3:
            chk('第 3 步主按钮写明签字或重导', ('签字' in cta3 or '重导' in cta3), cta3)
            pg.shot('export.png')
            pg.ev("document.querySelector('#cta .pact').click()")
            time.sleep(0.5)
            chk('点第 3 步主按钮先弹签字单，不直接开跑',
                bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
            rows3 = pg.ev(
                "[...document.querySelectorAll('#signList .srow .k')].map(x=>x.textContent).join(',')") or ''
            chk('第 3 步签字单列出 deps / meta / audio / cg',
                all(k in rows3 for k in ('deps', 'meta', 'audio', 'cg')), rows3)
            alt = pg.ev("(()=>{const b=document.getElementById('signAlt');"
                        "return b?[b.hidden,b.textContent]:null})()")
            chk('签字单提供「只跑到待确认」退路',
                bool(alt) and not alt[0] and '只跑到待确认' in alt[1], str(alt))
            pg.shot('export_sign.png')
            pg.ev("closeSign()")
            time.sleep(0.3)

        # 查看提示：必须切到一个**非待办**步骤才成立。
        view = 5 if work != 5 else 1
        pg.ev(f"document.querySelectorAll('.snode')[{view-1}].click()")
        time.sleep(0.45)
        vn = pg.ev("!document.getElementById('viewnote').hidden")
        vtx = pg.ev("document.getElementById('viewnote').textContent") or ''
        chk('切到非待办步骤会出查看提示', vn and '你在看第' in vtx, vtx[:48])
        chk('查看提示能说清待办在哪一步', '待办是第' in vtx, vtx[:60])
        chk('查看时徽标写「查看中」而不是「只读」',
            (pg.ev("document.getElementById('stepState').textContent") or '').strip() == '查看中',
            pg.ev("document.getElementById('stepState').textContent"))
        chk('右栏有且只有一个「待办」标记',
            (pg.ev("document.querySelectorAll('.snode.cur').length") or 0) == 1)
        chk('右栏标题常驻显示待办',
            bool(pg.ev("/^待办 \\d\\d$/.test(document.getElementById('railCur').textContent.trim())")),
            pg.ev("document.getElementById('railCur').textContent"))
        pg.shot('preview.png')
        pg.ev("document.getElementById('bBackCur').click()")
        time.sleep(0.4)
        chk('一键跳到待办步骤后提示消失', bool(pg.ev("document.getElementById('viewnote').hidden")))

        # 第 2 步：文案永远是配置表；签字单只在它还没同步完时才有得测。
        pg.ev("document.querySelectorAll('.snode')[1].click()")
        time.sleep(0.45)
        ask2 = pg.ev("document.querySelector('.ask').textContent") or ''
        cta2 = pg.ev("document.querySelector('#cta .pact').textContent") or ''
        chk('第 2 步文案是配置表，不是重导', '配置表' in ask2 and '重算' not in ask2, ask2[:40])
        if '同步配置表' in cta2:
            chk('第 2 步主动作是同步配置表', '同步配置表' in cta2, cta2)
            pg.shot('cfg.png')
            pg.ev("document.querySelector('#cta .pact').click()")
            time.sleep(0.5)
            chk('同步配置表会开签字单（不是直接开跑）',
                bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
            sign_txt = pg.ev("document.getElementById('signList').textContent") or ''
            chk('签字单列的是 cfg.publish 与写入位置',
                'cfg.publish' in sign_txt and 'inputs/gamecfg' in sign_txt, sign_txt[:70])
            chk('未勾选/未签名时放行按钮禁用',
                bool(pg.ev("document.getElementById('signGo').disabled")))
            pg.ev("document.getElementById('signAgree').checked=true;"
                  "const n=document.getElementById('signName');n.value='测试';"
                  "n.dispatchEvent(new Event('input'))")
            time.sleep(0.2)
            chk('勾选并签名后才可放行',
                not bool(pg.ev("document.getElementById('signGo').disabled")))
            pg.shot('cfg_sign.png')
            pg.ev("closeSign()")          # 只验接线，不真的发布 inputs/gamecfg
            time.sleep(0.3)
            chk('取消签字不会关掉配置表这一步',
                '配置表' in (pg.ev("document.querySelector('.ask').textContent") or ''))
        else:
            print(f'  SKIP  第 2 步已同步完成（主动作「{cta2}」），跳过同步签字单')

        pg.ev("openSign({keys:['pull'],what:'测试签字',note:'这是一条测试说明，不会真的发请求。',"
              "onOk:()=>{window.__signed=1}})")
        time.sleep(0.45)
        chk('签字窗口能打开', bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))
        chk('签字窗口逐条列出阶段与写入位置',
            (pg.ev("document.querySelectorAll('#signmodal .srow').length") or 0) > 0 and
            bool(pg.ev("document.getElementById('signList').textContent.includes('写到')")))
        pg.shot('sign.png')
        pg.ev("document.getElementById('signAgree').checked=true;"
              "const m=document.getElementById('signName');m.value='测试';"
              "m.dispatchEvent(new Event('input'))")
        time.sleep(0.2)
        pg.ev("document.getElementById('signGo').click()")
        time.sleep(0.4)
        chk('签字回调执行且窗口关闭',
            pg.ev("window.__signed===1") and
            not bool(pg.ev("document.getElementById('signmodal').classList.contains('on')")))

        pg.ev("document.getElementById('bHelp').click()")
        time.sleep(0.6)
        chk('说明抽屉能打开', bool(pg.ev("document.getElementById('help').classList.contains('on')")))
        pg.ev("document.querySelector('#help [data-close]').click()")
        time.sleep(0.3)
        chk('说明抽屉能关闭', not bool(pg.ev("document.getElementById('help').classList.contains('on')")))

        pg.ev("localStorage.setItem('panel.night','0');document.body.classList.remove('night')")
        time.sleep(0.3)
        day = pg.ev("getComputedStyle(document.body).backgroundColor")
        pg.ev("document.getElementById('bSea').click()")
        time.sleep(0.5)
        night = pg.ev("getComputedStyle(document.body).backgroundColor")
        pg.shot('night.png')
        chk('夜读确实换了底色', day != night, f'{day} → {night}')
        chk('夜读是暖墨而不是蓝黑', bool(pg.ev(
            "(()=>{const c=getComputedStyle(document.body).backgroundColor;"
            "const m=c.match(/\\d+/g).map(Number);return m[0]>=m[1]&&m[1]>=m[2]})()")), night)
        pg.ev("document.getElementById('bSea').click()")
        time.sleep(0.4)

        print('\n── 窄屏 ───────────────────────────────────────')
        pg.size(1000, 800)
        pg.go(url, 2.6)
        chk('右栏折成底部横排',
            pg.ev("getComputedStyle(document.querySelector('.steps')).flexDirection") == 'row')
        chk('进度线不再横穿步骤文字',
            pg.ev("getComputedStyle(document.querySelector('.steps .track')).display") == 'none')
        chk('窄屏无横向溢出',
            bool(pg.ev("document.documentElement.scrollWidth<=innerWidth")))
        chk('窄屏首屏能看到「查看 / 待办」提示',
            bool(pg.ev("(()=>{const e=document.getElementById('viewnote');"
                       "const r=e.getBoundingClientRect();"
                       "return !e.hidden && r.top>=0 && r.bottom<=innerHeight})()")),
            pg.ev("JSON.stringify((()=>{const e=document.getElementById('viewnote');"
                  "const r=e.getBoundingClientRect();return [e.hidden,r.top,r.bottom,innerHeight]})())"))
        chk('窄屏首屏能看到本步主按钮（不用先滚动）',
            bool(pg.ev("(()=>{const b=document.querySelector('#cta .pact');"
                       "if(!b) return false; const r=b.getBoundingClientRect();"
                       "return r.top>=0 && r.bottom<=innerHeight})()")))
        pg.shot('narrow.png')

        chk('全程无 JS 异常', not pg.exc, '; '.join(pg.exc[:3]))
        print('\n截图: ' + os.path.relpath(OUT, ROOT))
    finally:
        pg.close()

    if FAILS:
        print(f'\n[FAIL] {len(FAILS)} 条判红：')
        for x in FAILS:
            print('  - ' + x)
        return 1
    print('\n[PASS] 纸本控制台界面判据全绿')
    return 0


if __name__ == '__main__':
    sys.exit(main())
