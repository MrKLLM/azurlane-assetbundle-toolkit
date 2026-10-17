# -*- coding: utf-8 -*-
"""生成画廊 BGM 页的数据 `Output/gallery_v2/bgm.json`（自包含，前端不再回头读 .diag）。

三个来源，缺后两个也能跑（只是没有中文名）：
  1. `Output/Audio/BGM*/*.flac` —— 曲目本体（时长优先取 `transcode_bgm.py` 的台账（按 codec 分文件），缺则 ffprobe）
  2. `.diag/sharecfg_re/lua_json/music_collect_config.json` —— 官方中文曲名（实测 54 首）
  3. `.diag/sharecfg_re/lua_json/music_album.json` —— 11 张专辑的中文名
  4. `.diag/sharecfg_re/lua_json/beat_game_music.json` —— 音游 12 首（song01-12；11/12 有官方名）
⚠️ 2/3 在 `.diag/`（gitignore、可再生的解表产物），所以**名字一律烘进 bgm.json**，
   前端只读 bgm.json；这两张表读不到时打警告并降级成 slug，不静默出半截数据。

用法: py -3 scripts/build_bgm_index.py [--dir Output/Audio/BGM_ogg] [--out Output/gallery_v2/bgm.json]
"""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P

LUA = os.path.join(P.ROOT, '.diag', 'sharecfg_re', 'lua_json')

# 「出处」= 哪张配置表引用了这首曲子。标签是**按这张表在配什么**给的，不是游戏自己的曲库分类。
# 这 13 张表来自对 779 张 lua 表的逐字段扫描（2026-10-06 全量；2026-10-17 复扫确认
# 名单外再无 ≥5 处的精确引用源，只有 1~4 处的散点垃圾）；`--rescan` 会重扫并报告新出处。
SCENE_TABLES = {
    'voice_bgm': '主界面 / 通用场景',
    'activity_sp_story': '活动剧情',
    'expedition_data_by_map': '远征地图',
    'memory_storyline': '回忆剧情',
    'music_collect_config': '音游收藏曲',
    'soundstory_template': '声音故事',
    'dorm3d_rooms': '3D 宿舍房间',
    'island_map': '海岛地图',
    'story_template': '剧情',
    'world_expedition_data': '大世界远征',
    'login': '登录界面',
    'activity_series_enemy_story': '活动敌方剧情',
    'beat_game_music': '音游',
}
# 表里若有这些字段，就把值当"这一行的中文名"带出来（宿舍房间名、剧情名…）
LABEL_FIELDS = ('room', 'name', 'album_name', 'title', 'story_name', 'map_name')
# 个别表的"名字字段"不走默认校验：`beat_game_music.music_name` 是官方曲名，
# 会带拉丁字母（`無限大HearT`），默认的"不得出现连续拉丁字母"会把整列判掉 ⇒ 单独放行。
TABLE_LABEL_OVERRIDE = {
    'beat_game_music': (('music_name',), lambda s: bool(s and s.strip()) and len(s) <= 30),
}
# ⚠️ 但**不是每张表的 `name` 都是给人看的**：实测 `expedition_data_by_map` / `memory_storyline`
#    的 `name` 装的是内部代号（`浮樱影华-下篇||CHAPTER_EX||E_X`、`EP2-1 发生于行动前的事`），
#    搬到界面上就是噪声。所以按内容筛：要含中文、不含代码分隔符、不太长。
JUNK = re.compile(r'\||CHAPTER|_E\b|_EX|\{|\}|\\')
# 更管用的一条：中文行名里**不该出现两个以上连续拉丁字母** ——
# 实测漏进来的全是活动代号（`EPS-3 悠闲午餐会`、`EP-7 和声`、`EP-？ 步入天原·下`），
# 而留下的行名都是纯中文（`光与影的鸢尾之华·上`、`铁血、音符与誓言·下`）⇒ 误杀风险低。
CODE = re.compile(r'[A-Za-z]{2,}')


def label_ok(s):
    s = (s or '').strip()
    return (bool(s) and len(s) <= 14 and re.search(r'[一-鿿]', s)
            and not JUNK.search(s) and not CODE.search(s))
# slug 里这些 token 长得像舰名但不是（`bgm-battle-unknown-approaching` 曾误命中舰 key `unknown`）
SHIP_STOP = {'unknown', 'boss', 'theme', 'story', 'battle', 'main', 'full', 'loop', 'soft', 'pv',
             'ver', 'inst', 'short', 'long', 'type', 'day', 'night', 'one', 'two', 'three', 'image'}
USAGE = [('battle', '战斗'), ('boss', 'BOSS 战'), ('story', '剧情'), ('theme', '主题曲'),
         ('idol', '偶像'), ('login', '登录'), ('main', '主界面'), ('backyard', '后宅'),
         ('room', '宿舍'), ('event', '活动'), ('richang', '日常'), ('airraid', '空袭'),
         ('ninjacity', '联动'), ('nier', '联动'), ('ryza', '联动'), ('azumaster', '联动'),
         ('masangainu', '联动'), ('se', '音效'),
         # 2026-10-17 增补：以下词根逐一做过游戏内证据扫描（.diag/bgm_probe10_report.txt），
         # 有表内文字佐证才收录；sk/qe/cw/tl/wavyflow/diego/echo 等查无依据 ⇒ 保持空，不硬凑。
         ('holo', '联动'),      # memory_template 通关「集结hololive反抗军」/「异世界的来客」
         ('idom', '联动'),      # memory_template「响彻碧海的偶像歌」+ 765 事务所主题
         ('yumia', '联动'),     # character_voice atelier_yumia_* / activity_series_enemy_story 引用
         ('doa', '联动'),       # memory_template「假日航线」+ DOA 联动装备文本
         ]
_SHIP_BASE = {}          # 由 main() 调 ship_base_names() 填（classify 要用，避免每张表都重读 meta）


def _lua(name):
    """读一张解好的 lua 表。**表头行按内容剔**（它带 `__name`），不按键的 `#` 前缀——
    实测两种约定并存：`music_collect_config` 的数据行键是 `1/10/11…`、表头是 `#54`；
    而 `music_album` 的**数据行键本身就是 `#0..#9`**，按前缀滤会把整张表滤空。"""
    try:
        with open(os.path.join(LUA, name), encoding='utf-8') as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return [v for v in d.values() if isinstance(v, dict) and '__name' not in v]


def _norm_bgm(x):
    """表里的曲名有的带 `bgm-` 前缀有的不带（`bgm-bsm-1` vs `story-room-agir`）⇒ 两边都归一。
    ⚠️ 要**剥到没有为止**：源文件里有一批双前缀的（`bgm-bgm-cccp`），只剥一层的话
    表值 `bgm-cccp`（⇒`cccp`）永远追不上文件（⇒`bgm-cccp`）——2026-10-17 修复，
    一次捞回 北境序曲/破晓冰华/极地风暴/活动剧情引用 4 首。"""
    x = str(x).strip().lower()
    while x.startswith('bgm-'):
        x = x[4:]
    return x


def collect_refs(tables, stems_norm):
    """→ {归一名: [(出处标签, 行内中文名), …]}。
    ⚠️ 表里的曲名**不带** `bgm-` 前缀（`story-room-agir`），而文件名带（`bgm-story-room-agir`）
       —— 第一版拿原始 slug 去查，结果 0 命中，看着像"这些曲子没有归属"。
       所以两边都过 `_norm_bgm`，键用归一名。"""
    refs = {}
    for t, label in tables.items():
        fields, ok = TABLE_LABEL_OVERRIDE.get(t, (LABEL_FIELDS, label_ok))
        for r in (_lua(t + '.json') or []):
            cn = next((str(r[k]).strip() for k in fields if ok(r.get(k))), '')
            for v in r.values():
                if isinstance(v, str) and v:
                    key = _norm_bgm(v)
                    stem = stems_norm.get(key)
                    if stem:
                        pair = (label, cn)
                        bucket = refs.setdefault(stem, [])
                        if pair not in bucket:
                            bucket.append(pair)
    return refs


def scan_tables():
    """重扫全部 lua 表找出处（慢约 1 分钟）。返回 {表名: 命中的曲名引用数}。"""
    out = {}
    pat = re.compile(r'^(bgm-)?(battle|story|theme|main|login|backyard|idol|ss|se|dorm|airraid|'
                     r'ninjacity|nier|ryza|azumaster|richang|event|room)', re.I)
    for fn in sorted(os.listdir(LUA)):
        rows = _lua(fn)
        if not rows:
            continue
        n = sum(1 for r in rows for v in r.values() if isinstance(v, str) and pat.match(v))
        if n:
            out[fn[:-5]] = n
    return out


def classify(slug):
    """→ (用途, 关联舰/角色中文名)。允许为空，空就是真的没有，不硬凑。"""
    toks = [x for x in re.split(r'[-_]', slug.lower()) if x]
    usage = next((cn for key, cn in USAGE if key in toks), '')
    # 音游曲：`beat_game_music` 12 行的 `bgm` 数值字段 1..12 与 `settlement_type`
    # （song11/song12）两行确证了"第 N 行 ↔ bgm-songNN"的映射，其余 10 行只是没填名。
    if not usage and any(re.fullmatch(r'song\d{1,2}', x) for x in toks):
        usage = '音游曲'
    ship = ''
    for x in toks:
        if len(x) > 2 and x not in SHIP_STOP and x in _SHIP_BASE:
            ship = _SHIP_BASE[x]
            break
    return usage, ship


def ship_base_names():
    """`ship_meta.json` 的键是皮肤 key（`2b_2`、`nep_alter`…），剥掉后缀就是舰级标识；
    slug 里的 `tiancheng` / `masazhusai` 这类正是它 ⇒ 能反查中文名。"""
    try:
        with open(os.path.join(P.OUT, 'ship_meta.json'), encoding='utf-8') as f:
            m = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in m.items():
        if not isinstance(v, dict) or not v.get('cn'):
            continue
        b = re.sub(r'(_\d+|_alter|_hx|_n|_dark|_hei|_px|_bw|_s|_raw|_image)+$', '', k).lower()
        out.setdefault(b, v['cn'])
    return out


def humanize(slug):
    """`bgm-battle-nep` → `Battle · Nep`；`-inst`/`-short`/`-full` 这类版本尾巴单独标。"""
    s = re.sub(r'^bgm[-_]', '', slug)
    parts = [x for x in re.split(r'[-_]', s) if x]
    tail = ''
    if parts and parts[-1].lower() in ('inst', 'short', 'full', 'loop', 'ver2', 'edit'):
        tail = parts.pop()
    name = ' · '.join(x.upper() if len(x) <= 3 and x.isascii() else x.capitalize() for x in parts)
    return (name + (f'（{tail}）' if tail else '')) or slug


def main():
    ap = argparse.ArgumentParser(description='生成 bgm.json')
    ap.add_argument('--dir', default=os.path.join(P.OUT, 'Audio', 'BGM'),
                    help='音频目录（换完档后就是 Output/Audio/BGM，里面是 .flac）')
    ap.add_argument('--out', default=os.path.join(P.OUT, 'gallery_v2', 'bgm.json'))
    ap.add_argument('--rescan', action='store_true',
                    help='重扫全部 lua 表报告名单外的新出处（慢约 1 分钟，不自动改名单）')
    a = ap.parse_args()
    if not os.path.isdir(a.dir):
        print(f'[FAIL] 目录不存在: {a.dir}')
        return 2

    exts = {os.path.splitext(f)[1].lstrip('.').lower()
            for f in os.listdir(a.dir) if os.path.splitext(f)[1]}
    ext = next((e for e in ('flac', 'ogg', 'opus', 'mp3', 'm4a') if e in exts), '')
    if not ext:
        print(f'[FAIL] {a.dir} 里没有可识别的音频（找到扩展名 {sorted(exts)[:6]}）')
        return 2
    # 台账按 codec 分文件（跑 FLAC 不该覆盖 opus 那 536 条溯源）⇒ 跟着产物扩展名挑
    man = (os.path.join(P.ROOT, 'ledger', 'bgm_transcode.json') if ext in ('ogg', 'opus')
           else os.path.join(P.ROOT, 'ledger', f'bgm_transcode_{ext}.json'))
    print(f'产物格式 .{ext}，时长台账 {os.path.relpath(man, P.ROOT)}')

    durs = {}
    try:
        with open(man, encoding='utf-8') as f:
            for w, r in (json.load(f).get('done') or {}).items():
                durs[w] = r.get('src_dur') or r.get('dst_dur')
    except (OSError, ValueError):
        print('! 时长台账读不到，改用 ffprobe（慢一些）')

    cn = {}
    rows = _lua('music_collect_config.json')
    if rows:
        # 专辑表**没有 id 字段**（键是 `#0..#9` 的行号），能对上 `album_id` 的只有 `order`：
        # 1..10 连续无重复，且 id=10 的曲目全是鸢尾主题、正对 order=10「奏响鸢尾之歌」⇒ 按 order 连。
        albums = {str(x.get('order')): x.get('album_name') for x in (_lua('music_album.json') or [])}
        for r in rows:
            m = r.get('music')
            if m:
                cn[m] = {'title_cn': r.get('name') or '', 'album': albums.get(str(r.get('album_id')), '')}
    else:
        print('! music_collect_config.json 读不到 ⇒ 中文曲名/专辑留空（bgm.json 仍自包含）')

    oggs = sorted(f for f in os.listdir(a.dir) if f.lower().endswith('.' + ext))
    stems = {os.path.splitext(f)[0] for f in oggs}
    stems_norm = {_norm_bgm(s): s for s in stems}
    # 归一是"剥到没有 bgm- 为止"，若两份源文件归一后同键（如 bgm-x 与 bgm-bgm-x 并存）
    # 会静默互覆 ⇒ 闸一道。
    if len(stems_norm) != len(stems):
        seen = {}
        for s in stems:
            n = _norm_bgm(s)
            if n in seen:
                print(f'[FAIL] 归一冲突: {seen[n]} vs {s}（都归一成 {n}）')
                return 2
            seen[n] = s
    global _SHIP_BASE
    _SHIP_BASE = ship_base_names()
    if a.rescan:
        found = scan_tables()
        new = {k: v for k, v in found.items() if k not in SCENE_TABLES and v >= 3}
        print(f'--rescan（候选，正则宽松、会把 `Dorm*` 这类剧情键误算进来 ⇒ 加进名单前要逐张核）：'
              f'{len(found)} 张表含曲名引用；名单外引用 ≥3 的前 12 张：'
              + ', '.join(f'{k}({v})' for k, v in sorted(new.items(), key=lambda x: -x[1])[:12]))
    refs = collect_refs(SCENE_TABLES, stems_norm)
    print(f'出处：{len(refs)} / {len(stems)} 首至少被一张配置表引用')

    tracks = []
    for f in oggs:
        stem = os.path.splitext(f)[0]
        p = os.path.join(a.dir, f)
        # 转码台账的键是**源 wav 名**，不是 ogg 名
        dur = durs.get(stem + '.wav')
        if dur is None:
            ff = P.tool('AL_FFMPEG', 'ffmpeg')
            r = subprocess.run([ff.replace('ffmpeg', 'ffprobe'), '-v', 'error', '-show_entries',
                                'format=duration', '-of', 'default=nw=1:nk=1', p],
                               capture_output=True, text=True, encoding='utf-8', errors='replace')
            try:
                dur = round(float(r.stdout.strip()), 2)
            except ValueError:
                dur = 0.0
        info = cn.get(stem) or cn.get('bgm-' + stem) or {}
        usage, ship = classify(stem)
        seen, scenes = set(), []
        for label, cnl in refs.get(stem, []):
            if label in seen:
                continue
            seen.add(label)
            scenes.append({'t': label, 'n': cnl})
        # 前端在 Output/gallery_v2/ 里，所以 URL 相对 Output 再加一层 ../（与语音条同一写法）
        tracks.append({'file': f, 'url': '../' + os.path.relpath(p, P.OUT).replace(os.sep, '/'),
                       'slug': stem, 'title': humanize(stem), 'title_cn': info.get('title_cn', ''),
                       'album': info.get('album', ''), 'usage': usage, 'ship': ship,
                       'scenes': scenes, 'dur': round(dur or 0, 2), 'size': os.path.getsize(p)})
    tracks.sort(key=lambda t: (t['album'] == '', t['album'], t['usage'], t['slug']))
    out = {'generated': dt.datetime.now().strftime('%Y-%m-%d %H:%M'),
           'source_dir': os.path.relpath(a.dir, P.ROOT).replace(os.sep, '/'),
           'counts': {'tracks': len(tracks), 'named_cn': sum(1 for t in tracks if t['title_cn']),
                      'albums': len({t['album'] for t in tracks if t['album']}),
                      'with_scene': sum(1 for t in tracks if t['scenes']),
                      'with_usage': sum(1 for t in tracks if t['usage']),
                      'with_ship': sum(1 for t in tracks if t['ship']),
                      'usages': sorted({t['usage'] for t in tracks if t['usage']}),
                      'scene_kinds': sorted({s['t'] for t in tracks for s in t['scenes']}),
                      'hours': round(sum(t['dur'] for t in tracks) / 3600, 2),
                      'mb': round(sum(t['size'] for t in tracks) / 2 ** 20, 1)},
           'tracks': tracks}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    c = out['counts']
    print(f'[OK] {a.out}：{c["tracks"]} 首 / {c["hours"]} 小时 / {c["mb"]} MB')
    print(f'     官方中文名 {c["named_cn"]} 首 · 专辑 {c["albums"]} 张 · '
          f'有出处 {c["with_scene"]} 首 · 有用途 {c["with_usage"]} 首 · 关联舰名 {c["with_ship"]} 首')
    print(f'     用途：{", ".join(c["usages"])}')
    print(f'     出处：{", ".join(c["scene_kinds"])}')
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.exit(main())
