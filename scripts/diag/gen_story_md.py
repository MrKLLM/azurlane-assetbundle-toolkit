# -*- coding: utf-8 -*-
"""生成带缩略图内嵌的剧情角色复核 MD（file:// 绝对路径）。"""
import json, os, io
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
idx = {s['id']: s for s in json.load(io.open(os.path.join(ROOT,'Output','gallery_v2','index.json'),encoding='utf-8'))['ships']}
meta = json.load(io.open(os.path.join(ROOT,'Output','ship_meta.json'),encoding='utf-8'))
THUMB = os.path.join(ROOT,'Output','gallery_v2','thumbs')

def file_url(p):
    p = p.replace('\\','/')
    return 'file:///' + p.replace(' ', '%20')

def thumb_of(s):
    ds = s['skins'][0] if s['skins'] else None
    if not ds: return None
    if ds.get('cg'):
        key = os.path.basename(ds['cg']).rsplit('.',1)[0] + '_cg.webp'   # CG_v2/x.png -> thumbs/x_cg.webp
    elif ds.get('image'):
        key = os.path.basename(ds['image']).rsplit('.',1)[0] + '.webp'
    else:
        return None
    p = os.path.join(THUMB, key)
    return p if os.path.exists(p) else None

story = [s for s in idx.values() if s['category']=='story']
def score(s):
    k=0
    if s['faction']:k+=4
    if s['type']:k+=2
    if s['rarity']:k+=1
    if s.get('spineSkins'):k+=2
    if s.get('live2dSkins'):k+=1
    return -k
story.sort(key=score)

out = ['# 剧情角色复核清单（共 %d 条）'%len(story),
       '',
       '> 每条下面把「自机?」后的 `[]` 改成 `[x]` 表示**其实是可玩舰船**（应移出剧情）。全默认 `[]`＝维持剧情角色。',
       '> 排序：越像自机的越靠前（有阵营/舰种/Spine/Live2D 的先看）。',
       '']
for i,s in enumerate(story,1):
    e = meta.get(s['id'],{})
    tags = ' / '.join(x for x in [s['faction'] or '无阵营', s['type'] or '无舰种', s['rarity'] or '无稀有度'])
    extra = []
    if s.get('spineSkins'): extra.append('Spine')
    if s.get('live2dSkins'): extra.append('Live2D')
    if s['voiceCount']: extra.append('语音%d'%s['voiceCount'])
    out.append('### %d. %s  `%s`'%(i, s['name'], s['id']))
    out.append('- %s ｜ 皮肤 %d ｜ %s ｜ source=%s'%(tags, len(s['skins']), '、'.join(extra) or '—', e.get('source','')))
    if e.get('en'): out.append('- 英文：%s'%e['en'])
    tu = thumb_of(s)
    if tu:
        out.append('![%s](%s)'%(s['name'], file_url(tu)))
    else:
        out.append('- （无缩略图）')
    out.append('- 自机? []')
    out.append('')

dst = os.path.join(ROOT,'story_review.md')
io.open(dst,'w',encoding='utf-8').write('\n'.join(out))
print('written', dst, len(story), 'entries')
