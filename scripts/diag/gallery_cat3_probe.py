# -*- coding: utf-8 -*-
"""三档制的前端验收探针：在真浏览器里证明「舰船 / 剧情角色 / 其他」三档**确实按索引的
category 分好了**，并且秘书舰三族是**三张各自有名字的卡**。

为什么必须跑浏览器而不是只读 index.json：档位是前端 `catOf()` 算出来的，
数据对而前端还留着旧的 `'hei'/'variant'` 分支 ⇒ 页面上一张卡都点不到（假绿灯）。
判据全部落在**渲染那一刻的 DOM** 上（卡片副标题、档位按钮文案与计数）。

  py -3 scripts/diag/gallery_cat3_probe.py            # 需要画廊服务器在 8777
  起服务：py -3 scripts/diag/run_detached.py --log .diag/_srv.log -- \
          py -3 Output/gallery_v2/_gallery_server.py

判据（任一不满足退出码 1）：
  1 档位条恰好 4 个按钮，文案是 全部 / 舰船 / 剧情角色 / 其他（旧的剪影、特殊形态必须消失）
  2 计数自洽：全部 == 舰船 + 剧情角色 + 其他（"报一个点不到的数"就是这条要拦的）
  3 「其他」档里能数到 npc 前缀卡与 `· 剧情剪影` 伪卡，且**没有**秘书舰角色卡
  3d/3e/4b 索引里 root 带 `_dark` 的外迁条目恰好 10 条，且**只**出现在「其他」档（2026-10-05 归档）
  4 三族是剧情角色档里的三张独立卡、各有 ≥10 皮肤
  5 三张卡的皮肤数与索引一致（防止前端合并时把皮肤整批丢掉）
  6 页面上的卡总数 == 索引三档之和（数据与渲染同源核对）
  6b/6c/6d 「埃塞克斯·META」在「舰船」档里、`.tags` 里带 META 阵营与航母/超稀有（副标题只是
     `<id> · N皮肤`，阵营看标签）、不再是宿主卡下的「· 改造」条目、
     且舰船档 DOM 卡片数 == 按钮上的数（网格只渲染一部分时这条会红）
  7 三张秘书舰卡的船级语音数 > 0
  8 台词对应的 ogg 走 HTTP 真取得到（200 且 >1KB），不是"路径写上了"
  9 台词正文已并入 skin_words（≥10 条、无未展开 {namecode}）
"""
import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from gallery_ui_shots import Page, preflight        # noqa: E402

EV = lambda s: f"(()=>{{{s}}})()"
SEC = ['领航员-TB', '领洋者-娜比娅', '探索者-艾普洛']

fails = 0


def chk(desc, ok, detail=''):
    global fails
    fails += 0 if ok else 1
    print('%s %s%s' % ('✓' if ok else '✗', desc, ('  — ' + detail) if detail else ''))


def cards(pg):
    """当前网格里渲染出来的卡片：[名字, 副标题]。"""
    return json.loads(pg.ev(EV(
        "return JSON.stringify([...document.querySelectorAll('#main .card')]"
        ".map(c=>[c.querySelector('.nm').textContent.trim(),"
        "c.querySelector('.py').textContent.trim()]))")))


def click_tab(pg, c):
    pg.ev(EV(f"document.querySelector('#fCat button[data-c=\"{c}\"]').click();return 1"))
    time.sleep(1.2)


def load_all(pg):
    """用页脚的「加载更多」把当前档拉全（确定性，不赌 IO 的触发时机）。

    2026-10-22 实测：`scrollTop=scrollHeight` + 250ms 轮询在 874 张的舰船档只能到 720 ——
    每批 120 张的布局/缩略图还没稳定，滚动位置就被改掉，哨兵没进视野。按钮是产品自己的
    兜底通路，逐批点更稳；无限滚动的触发时机由 `index_paging_probe` 单独判。
    """
    for _ in range(40):
        done = pg.ev(EV("const m=document.querySelector('#main .more');"
                        "return !m || m.classList.contains('done')"))
        if done:
            break
        pg.ev(EV("const b=document.querySelector('#main .more button');"
                 "if(b && getComputedStyle(b).display!=='none') b.click();return 1"))
        time.sleep(0.35)
    return int(pg.ev(EV("return document.querySelectorAll('#main .card').length")))


def card_tags(pg, name):
    """按名字搜出唯一一张卡并读标签；读完清空搜索。返回 '(这张卡不在舰船档)' 即未命中。"""
    pg.ev(EV("(()=>{const s=document.getElementById('search');s.value=%s;"
             "s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()"
             % json.dumps(name, ensure_ascii=False)))
    time.sleep(0.7)
    t = pg.ev(EV("const c=[...document.querySelectorAll('#main .card')]"
                 ".find(c=>c.querySelector('.nm').textContent.trim()===%s);"
                 "return c?c.querySelector('.tags').textContent.replace(/\\s+/g,' ').trim()"
                 ":'(这张卡不在舰船档)'" % json.dumps(name, ensure_ascii=False)))
    pg.ev(EV("(()=>{const s=document.getElementById('search');s.value='';"
             "s.dispatchEvent(new Event('input',{bubbles:true}));return 1})()"))
    time.sleep(0.7)
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=9333)
    ap.add_argument('--page', default='index.html')
    a = ap.parse_args()
    url = preflight(a.page)
    profile = os.path.join(ROOT, '.diag', 'chrome_cat3')
    os.makedirs(profile, exist_ok=True)
    pg = Page(a.port, profile, url, (1440, 900))
    try:
        time.sleep(2.5)                                  # 等 index.js + 首屏渲染
        idx = json.loads(pg.ev(EV("return JSON.stringify(window.GALLERY.counts)")))

        tabs = [t.strip() for t in json.loads(pg.ev(EV(
            "return JSON.stringify([...document.querySelectorAll('#fCat button')]"
            ".map(b=>b.textContent.trim()))")))]
        chk('1 档位条只有 4 档', len(tabs) == 4, str(tabs))
        names = [t.split()[0] for t in tabs]
        chk('1b 旧的「剧情剪影 / 特殊形态」两档已消失',
            not any(n in names for n in ('剧情剪影', '特殊形态')), str(names))
        nums = {n: int(t.split()[-1]) for n, t in zip(names, tabs) if t.split()[-1].isdigit()}
        chk('2 计数自洽 全部 == 舰船+剧情角色+其他',
            nums.get('全部') == nums.get('舰船', 0) + nums.get('剧情角色', 0) + nums.get('其他', 0),
            str(nums))

        click_tab(pg, 'other')
        oth = cards(pg)
        oth_txt = '\n'.join(n + '|' + p for n, p in oth)
        chk('3 「其他」里有 npc 前缀卡', 'npc' in oth_txt.lower(), oth[0][1] if oth else '空')
        chk('3b 「其他」里有「· 剧情剪影」伪卡', '剧情剪影' in oth_txt)
        chk('3c 「其他」里**没有**秘书舰角色卡',
            not any(s in [n for n, _ in oth] for s in SEC))
        # ---------- 2026-10-05：`_dark` 形态族归档，判据落在渲染出来的卡片标题上 ----------
        dark = json.loads(pg.ev(EV(
            "return JSON.stringify((window.GALLERY.variants||[])"
            ".filter(v=>/_dark(_memory)?$/.test(v.root)).map(v=>v.root))")))
        chk('3d 索引里 root 带 `_dark` 的外迁条目 == 10', len(dark) == 10, str(sorted(dark)))
        in_oth = [k for k in dark if any(n.startswith(k) for n, _ in oth)]
        chk('3e 这 10 条全部渲染在「其他」档网格里',
            len(in_oth) == len(dark),
            '%d/%d，未渲染: %s' % (len(in_oth), len(dark), sorted(set(dark) - set(in_oth))))

        click_tab(pg, 'story')
        st = {n: p for n, p in cards(pg)}
        got = {s: st.get(s) for s in SEC}
        chk('4 三族是剧情角色档里的三张独立卡', all(got.values()), str(list(got)))
        chk('4b 「剧情角色」档里**一条 `_dark` 都没有**（改了归档判据就不能再留在这儿）',
            not any(n.startswith(k) for n in st for k in dark),
            str([n for n in st for k in dark if n.startswith(k)]))
        skin_n = json.loads(pg.ev(EV(
            "return JSON.stringify(Object.fromEntries(window.GALLERY.ships"
            ".filter(s=>['tbniang','lingyangzhe32_3','tansuozhe32_3'].includes(s.id))"
            ".map(s=>[s.name,(s.skins||[]).length])))")))
        chk('5 三张卡的皮肤数 ≥10（与索引一致）',
            all(int((skin_n.get(s) or 0)) >= 10 for s in SEC), str(skin_n))
        total = int(pg.ev(EV("return window.GALLERY.ships.length"
                             "+(window.GALLERY.silhouettes||[]).length"
                             "+(window.GALLERY.variants||[]).length")))
        chk('6 页面卡总数 == 索引三档条目之和',
            total == idx['ships'] + idx['silhouettes'] + idx['variants'],
            f'{total} vs {idx["ships"]}+{idx["silhouettes"]}+{idx["variants"]}')

        # ---------- 2026-10-05：拿到 META 阵营才能独立成卡（`normalize()` 的 `_alter` 判据） ----------
        click_tab(pg, 'ship')
        shp = cards(pg)
        chk('6 舰船档首屏只渲染一页（分页生效）', 0 < len(shp) <= 130, '%d 张' % len(shp))
        # 卡片副标题是 `<id> · N皮肤`，阵营/舰种/稀有度在 `.tags` 里 —— 判 META 阵营只能看标签。
        # ⚠️ 分页后 863+ 张舰船不会同时进 DOM，必须**按名字搜出来**再读，不能假设它在首屏。
        tags = card_tags(pg, '埃塞克斯·META')
        chk('6b 埃塞克斯·META 在「舰船」档里，标签带 META 阵营与航母/超稀有',
            'META' in tags and '航母' in tags and '超稀有' in tags, tags)
        # 灵敏·META 走的是另一条通道（META 补桥表，§108）：表里没有她的皮肤行，
        # 阵营/舰种来自 `ship_data_group`，**稀有度表里没有 ⇒ 故意留空**，所以这条不能照抄 6b。
        tags2 = card_tags(pg, '灵敏·META')
        chk('6e 灵敏·META（补桥成卡）在「舰船」档里，标签带 META + 驱逐 + 声明过的稀有度',
            'META' in tags2 and '驱逐' in tags2 and '精锐' in tags2, tags2)
        import urllib.request
        from gallery_ui_shots import BASE
        vp2 = json.loads(pg.ev(EV("return JSON.stringify((window.GALLERY.ships||[])"
                                  ".filter(s=>s.id==='lingmin_alter').map(s=>[s.name,s.voiceCount]))")))
        own = json.loads(urllib.request.urlopen(f'{BASE}/skin_voice.json', timeout=20).read().decode('utf-8'))
        one = (own.get('lingmin_alter') or {}).get('lines') or []
        got2 = []
        for l in one[:3]:
            try:
                # 音频挂在服务器根的 `Audio/…` 下（画廊页在 `gallery_v2/`），与第 8 条同一拼法
                r = urllib.request.urlopen(f"{BASE}/../{l['f']}".replace('\\', '/'), timeout=20)
                got2.append((l['f'].rsplit('/', 1)[-1], r.status, len(r.read())))
            except Exception as e:
                got2.append((l['f'], 'ERR', str(e)[:40]))
        chk('6f 她的语音包号是补桥给的 970113（不是借本体的），且 ogg 真取到字节',
            (own.get('lingmin_alter') or {}).get('cv') == 970113
            and (own.get('lingmin_alter') or {}).get('src') == 'bridge'
            and bool(got2) and all(g[1] == 200 and g[2] > 1024 for g in got2),
            '%s / %s' % (vp2, got2))
        chk('6c 她不再是宿主卡下的「· 改造」外迁条目（剧情角色档里搜不到她）',
            not any('埃塞克斯·META' in n for n in st),
            str([n for n in st if '埃塞克斯' in n]))
        n_ship = load_all(pg)
        chk('6d 滚到底后舰船档 DOM 卡片数与档位按钮的数一致（防止网格只渲染一部分）',
            n_ship == nums.get('舰船', -1), '%d 张 vs 按钮 %s' % (n_ship, nums.get('舰船')))

        # ---------- 秘书舰语音与台词（P4b）：必须真取到字节，不是"路径写上了" ----------
        import urllib.request
        from gallery_ui_shots import BASE
        vp = json.loads(pg.ev(EV(
            "return JSON.stringify(window.GALLERY.ships"
            ".filter(s=>['tbniang','lingyangzhe32_3','tansuozhe32_3'].includes(s.id))"
            ".map(s=>[s.name,s.voiceCount]))")))
        chk('7 三张秘书舰卡船级语音数 > 0',
            all(int(n or 0) > 0 for _, n in vp), str(vp))
        sv = json.loads(urllib.request.urlopen(f'{BASE}/skin_voice.json', timeout=20).read()
                        .decode('utf-8'))
        ent = sv.get('linghangyuan1_2') or {}
        files = [l['f'] for l in (ent.get('lines') or [])][:3]
        got = []
        for f in files:
            u = f'{BASE}/../{f}'.replace('\\', '/')
            try:
                with urllib.request.urlopen(u, timeout=20) as r:
                    got.append((f.rsplit('/', 1)[1], r.status, len(r.read())))
            except Exception as e:
                got.append((f, 'ERR', str(e)[:40]))
        ok_audio = len(got) == 3 and all(s == 200 and n > 1024 for _, s, n in got)
        chk('8 台词对应的 ogg 真的取得到（HTTP 200 且 >1KB）', ok_audio, str(got[:3]))
        sw = json.loads(urllib.request.urlopen(f'{BASE}/skin_words.json', timeout=30).read()
                        .decode('utf-8'))
        key = sw.get('m', {}).get('linghangyuan1_2')
        lines = (sw.get('w', {}).get(key) or {}) if key else {}
        chk('9 台词正文已并入（linghangyuan1_2 ≥10 条且无未展开占位符）',
            len(lines) >= 10 and not any('{namecode' in t for t in lines.values()),
            f'{key} → {len(lines)} 条')
        print('\n索引 counts: ship %s / story %s / other %s'
              % (idx.get('ship'), idx.get('story'), idx.get('other')))
    finally:
        pg.close()
    print('\n%s 三档制前端验收 %s' % ('[PASS]' if not fails else '[FAIL]',
                                     '全绿' if not fails else '%d 条红' % fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
