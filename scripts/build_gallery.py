# -*- coding: utf-8 -*-
# 生成「立绘图鉴」网站：元数据(index.json) + 缩略图(thumbs/) + 单页 index.html
# 数据源：Output/WikiData/ship_data.json(阵营/舰种/稀有度) + ship_name_map.py(拼音->中文)
import os
import sys
import json

sys.path.insert(0, os.path.dirname(__file__))
from ship_name_map import SHIP_NAME_MAP

ROOT = r"D:\Azur Lane Assets"
PROD = os.path.join(ROOT, "Output", "Paintings_Synthesized")
GALLERY = os.path.join(ROOT, "Output", "gallery")
THUMBS = os.path.join(GALLERY, "thumbs")
SHIP_DATA = os.path.join(ROOT, "Output", "WikiData", "ship_data.json")
THUMB_MAX = 360  # 缩略图最长边


def resolve_cn_name(bundle):
    """bundle 名 -> 中文舰船名（最长前缀匹配，处理 _n/_dark_shadow 等后缀与 npc 前缀）"""
    parts = bundle.split("_")
    for i in range(len(parts), 0, -1):
        cand = "_".join(parts[:i])
        if cand in SHIP_NAME_MAP:
            return SHIP_NAME_MAP[cand]
    base = parts[0]
    if base.startswith("npc") and base[3:] in SHIP_NAME_MAP:
        return SHIP_NAME_MAP[base[3:]]
    return SHIP_NAME_MAP.get(base, bundle)


def _is_collab(bundle):
    b = bundle.lower()
    return (
        b.startswith("vtuber_") or b.startswith("hdn") or b.startswith("ryouko")
        or "_tolove" in b or "_doa" in b or "_kizuna" in b or "_ssss" in b
        or "_bili" in b or "_shanluan" in b
    )


def main():
    # 1. 加载舰船元数据
    with open(SHIP_DATA, encoding="utf-8") as f:
        ship_list = json.load(f)
    cn_info = {}
    for s in ship_list:
        cn = s.get("name", "")
        if cn:
            cn_info[cn] = {
                "type": s.get("ship_type", ""),
                "rarity": s.get("rarity", ""),
                "faction": s.get("faction", ""),
            }

    # 2. 枚举生产目录 png
    files = sorted(fn for fn in os.listdir(PROD) if fn.lower().endswith(".png"))

    import difflib
    ship_names = list(cn_info.keys())

    def norm_name(s):
        s2 = s.replace("-", "").replace(" ", "").replace("·", "")
        # I-13 -> 伊13 等潜艇命名统一
        if s2.startswith("I") and s2[1:].isdigit():
            s2 = "伊" + s2[1:]
        return s2

    norm_to_cn = {}
    for nm in ship_names:
        norm_to_cn.setdefault(norm_name(nm), nm)

    fuzzy_cache = {}

    def lookup(cn):
        if cn in cn_info:
            return cn
        nc = norm_name(cn)
        if nc in norm_to_cn:
            return norm_to_cn[nc]
        c = fuzzy_cache.get(cn)
        if c is not None:
            return c
        hit = None
        if len(cn) >= 3:
            m = difflib.get_close_matches(cn, ship_names, n=1, cutoff=0.72)
            if m:
                hit = m[0]
        fuzzy_cache[cn] = hit
        return hit

    entries = []
    for fn in files:
        bundle = fn[:-4]
        cn = resolve_cn_name(bundle)
        canon = lookup(cn)
        if canon:
            info = cn_info[canon]
            faction = info.get("faction", "") or "联动"
        else:
            info = {}
            faction = "联动" if _is_collab(bundle) else "未知"
        entries.append({
            "bundle": bundle,
            "cn": canon or cn,
            "faction": faction,
            "type": info.get("type", "") or "未知",
            "rarity": info.get("rarity", "") or "未知",
        })

    # 3. 生成缩略图（引用生产目录大图）
    from PIL import Image
    os.makedirs(THUMBS, exist_ok=True)
    done = 0
    for e in entries:
        src = os.path.join(PROD, e["bundle"] + ".png")
        dst = os.path.join(THUMBS, e["bundle"] + ".jpg")
        if os.path.exists(dst):
            done += 1
            continue
        try:
            im = Image.open(src).convert("RGBA")
            w, h = im.size
            scale = THUMB_MAX / max(w, h)
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
            bg = Image.new("RGBA", im.size, (20, 22, 28, 255))
            bg.paste(im, (0, 0), im)
            bg.convert("RGB").save(dst, "JPEG", quality=82)
            done += 1
        except Exception as ex:
            print(f"  [thumb fail] {e['bundle']}: {ex}", flush=True)
        if done % 300 == 0:
            print(f"  缩略图 {done}/{len(entries)}", flush=True)

    print(f"缩略图完成: {done}/{len(entries)}", flush=True)

    # 4. 写元数据 json（调试/复用）
    with open(os.path.join(GALLERY, "index.json"), "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    # 5. 生成 index.html（元数据内嵌，规避 file:// 跨域）
    html = build_html(entries)
    with open(os.path.join(GALLERY, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)

    print(f"完成: {len(entries)} 条 -> {os.path.join(GALLERY, 'index.html')}", flush=True)


def build_html(entries):
    data_json = json.dumps(entries, ensure_ascii=False)
    return HTML_TEMPLATE.replace("__DATA__", data_json)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>碧蓝航线立绘图鉴</title>
<style>
:root{--bg:#141619;--panel:#1d2024;--card:#22252a;--line:#2e3238;--txt:#e6e9ef;--sub:#9aa3ad;--accent:#5b8def}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font-family:"Segoe UI","Microsoft YaHei",system-ui,sans-serif}
header{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:16px;padding:12px 20px;background:rgba(20,22,25,.96);border-bottom:1px solid var(--line);backdrop-filter:blur(6px)}
header h1{font-size:18px;margin:0;white-space:nowrap}
#search{flex:1;max-width:380px;padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:#101215;color:var(--txt);font-size:14px}
#count{margin-left:auto;color:var(--sub);font-size:13px;white-space:nowrap}
.layout{display:flex;gap:0;min-height:calc(100vh - 58px)}
aside{width:230px;flex:0 0 230px;padding:16px;background:var(--panel);border-right:1px solid var(--line);overflow-y:auto;height:calc(100vh - 58px);position:sticky;top:58px}
.filter-group{margin-bottom:18px}
.filter-group h3{margin:0 0 8px;font-size:13px;color:var(--sub);font-weight:600;letter-spacing:.5px}
.filter-group label{display:flex;align-items:center;gap:8px;padding:4px 6px;border-radius:6px;cursor:pointer;font-size:13px}
.filter-group label:hover{background:#26292e}
.filter-group input{accent-color:var(--accent)}
.filter-group .n{margin-left:auto;color:var(--sub);font-size:11px}
#clear{width:100%;padding:8px;border:1px solid var(--line);background:transparent;color:var(--sub);border-radius:8px;cursor:pointer;font-size:13px}
#clear:hover{color:var(--txt);border-color:var(--accent)}
main{flex:1;padding:20px;display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:14px;align-content:start}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:pointer;transition:transform .12s,border-color .12s}
.card:hover{transform:translateY(-3px);border-color:var(--accent)}
.card .img{width:100%;aspect-ratio:3/4;object-fit:contain;background:#0f1113;display:block}
.card .info{padding:8px 10px}
.card .name{font-size:14px;font-weight:600;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.card .meta{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap}
.badge{font-size:11px;padding:2px 7px;border-radius:11px;border:1px solid var(--line);color:var(--sub)}
.badge.f{border-color:#5b8def;color:#8fb2ff}
.badge.t{border-color:#e0a44e;color:#f0c27a}
.badge.r{border-color:#b372e0;color:#d3a0f5}
.empty{grid-column:1/-1;text-align:center;color:var(--sub);padding:60px 0}
#lightbox{position:fixed;inset:0;background:rgba(0,0,0,.92);z-index:50;display:flex;align-items:center;justify-content:center;cursor:zoom-out}
#lightbox.hidden{display:none}
#lightbox img{max-width:96vw;max-height:96vh;object-fit:contain}
#lb-close{position:absolute;top:18px;right:24px;background:none;border:none;color:#fff;font-size:40px;cursor:pointer;line-height:1}
</style>
</head>
<body>
<header>
  <h1>碧蓝航线立绘图鉴</h1>
  <input id="search" type="search" placeholder="搜索舰船名 / 文件名...">
  <span id="count"></span>
</header>
<div class="layout">
  <aside id="filters"></aside>
  <main id="grid"></main>
</div>
<div id="lightbox" class="hidden"><img id="lb-img" alt=""><button id="lb-close" title="关闭">×</button></div>
<script>
const DATA = __DATA__;
const state = {faction:{}, type:{}, rarity:{}, q:""};

function uniq(vals){return [...new Set(vals)].sort((a,b)=>a.localeCompare(b,"zh"))}
function voteCounts(key){const m={};for(const d of DATA){const v=d[key];m[v]=(m[v]||0)+1}return m}
function renderFilters(){
  const frag=document.createDocumentFragment();
  const groups=[
    ["阵营", voteCounts("faction"), "faction"],
    ["舰种", voteCounts("type"), "type"],
    ["稀有度", voteCounts("rarity"), "rarity"]
  ];
  for(const [title,cnt,key] of groups){
    const g=document.createElement("div");g.className="filter-group";
    const h=document.createElement("h3");h.textContent=title;g.appendChild(h);
    for(const v of uniq(Object.keys(cnt))){
      const lb=document.createElement("label");
      const cb=document.createElement("input");cb.type="checkbox";cb.value=v;
      cb.onchange=()=>{state[key][v]=cb.checked;render()};
      const sp=document.createElement("span");sp.textContent=v;
      const n=document.createElement("span");n.className="n";n.textContent=cnt[v];
      lb.append(cb,sp,n);g.appendChild(lb);
    }
    frag.appendChild(g);
  }
  const clear=document.createElement("button");clear.id="clear";clear.textContent="清除筛选";
  clear.onclick=()=>{state.faction={};state.type={};state.rarity={};document.querySelectorAll("#filters input").forEach(i=>i.checked=false);render()};
  frag.appendChild(clear);
  document.getElementById("filters").appendChild(frag);
}
function active(key){return Object.keys(state[key]).filter(k=>state[key][k])}
function match(d){
  if(active("faction").length && !active("faction").includes(d.faction))return false;
  if(active("type").length && !active("type").includes(d.type))return false;
  if(active("rarity").length && !active("rarity").includes(d.rarity))return false;
  if(state.q){const q=state.q.toLowerCase();if(!(d.cn.toLowerCase().includes(q)||d.bundle.toLowerCase().includes(q)))return false}
  return true;
}
function render(){
  const list=DATA.filter(match);
  const grid=document.getElementById("grid");grid.innerHTML="";
  document.getElementById("count").textContent=`${list.length} / ${DATA.length}`;
  if(!list.length){grid.innerHTML='<div class="empty">没有匹配的立绘</div>';return}
  for(const d of list){
    const c=document.createElement("div");c.className="card";
    const img=document.createElement("img");img.className="img";img.loading="lazy";
    img.src="thumbs/"+d.bundle+".jpg";img.alt=d.cn;
    img.onerror=()=>{img.src="../Paintings_Synthesized/"+d.bundle+".png"};
    const info=document.createElement("div");info.className="info";
    const name=document.createElement("div");name.className="name";name.textContent=d.cn;
    const meta=document.createElement("div");meta.className="meta";
    const b1=document.createElement("span");b1.className="badge f";b1.textContent=d.faction;
    const b2=document.createElement("span");b2.className="badge t";b2.textContent=d.type;
    const b3=document.createElement("span");b3.className="badge r";b3.textContent=d.rarity;
    meta.append(b1,b2,b3);info.append(name,meta);c.append(img,info);
    c.onclick=()=>openLightbox(d.bundle);
    grid.appendChild(c);
  }
}
function openLightbox(bundle){
  const lb=document.getElementById("lightbox");lb.classList.remove("hidden");
  document.getElementById("lb-img").src="../Paintings_Synthesized/"+bundle+".png";
}
document.getElementById("lightbox").onclick=()=>{document.getElementById("lightbox").classList.add("hidden")};
document.getElementById("lb-close").onclick=e=>{e.stopPropagation();document.getElementById("lightbox").classList.add("hidden")};
document.getElementById("search").addEventListener("input",e=>{state.q=e.target.value.trim();render()});
renderFilters();render();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()