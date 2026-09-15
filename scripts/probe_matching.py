"""
探查游戏本体的「立绘匹配机制」三件事：
1. dependencies 载体：{资源名 -> 依赖 bundle 列表} 的完整映射
2. painting/<name> prefab：每个渲染组件引用哪张纹理、来自哪个 _tex bundle
3. paintingface/<name>：内部 Sprite 的命名（差分表情如何对应）

用法: python probe_matching.py 2b
"""
import os
import sys

import UnityPy
from UnityPy import config

config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

AB_ROOT = r"D:\Azur Lane Assets\files\AssetBundles"
name = sys.argv[1] if len(sys.argv) > 1 else "2b"

# ---------- 1. dependencies ----------
print("=" * 60)
print("1) dependencies 载体")
env = UnityPy.load(os.path.join(AB_ROOT, "dependencies"))
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    d = o.read()
    tree = d.read_type_tree_enhanced() if hasattr(d, "read_type_tree_enhanced") else None
    raw = d.__dict__
    keys = None
    vals = None
    # 常见字段名: m_Keys / m_Values
    for attr in dir(d):
        if attr in ("m_Keys", "Keys"):
            keys = getattr(d, attr)
        if attr in ("m_Values", "Values"):
            vals = getattr(d, attr)
    if keys is None:
        continue
    print(f"  MonoBehaviour path_id={o.path_id} 条目数={len(keys)}")
    # 找目标立绘相关的条目
    idx = {}
    for i, k in enumerate(keys):
        ks = str(k)
        if ks.startswith(f"painting/{name}") or ks.startswith(f"paintingface/{name}") \
           or ks.startswith(f"spinepainting/{name}"):
            idx[ks] = i
    for ks, i in sorted(idx.items()):
        v = vals[i]
        fname = getattr(v, "m_FileName", None)
        deps = getattr(v, "m_Dependencies", None)
        print(f"  {ks}  -> file={fname} deps={[str(x) for x in (deps or [])][:10]}"
              + (" ..." if deps and len(deps) > 10 else ""))
    break

# ---------- 2. painting prefab 引用链 ----------
print("=" * 60)
print(f"2) painting/{name} 组件与 PPtr 引用")
env = UnityPy.load(os.path.join(AB_ROOT, "painting", name))
typecount = {}
for o in env.objects:
    typecount[o.type.name] = typecount.get(o.type.name, 0) + 1
print("  对象构成:", typecount)
# 打印所有 MonoBehaviour 的字段名，找 MeshImage / Image 的 sprite 引用的 m_FileID
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        d = o.read()
    except Exception:
        continue
    cls = ""
    try:
        ms = getattr(d, "m_Script", None)
    except Exception:
        ms = None
    fields = [a for a in dir(d) if not a.startswith("_")]
    interesting = [f for f in fields if any(t in f.lower() for t in
                 ("sprite", "texture", "mesh", "rawimage", "maintexture", "atlas"))]
    if interesting:
        print(f"  MB path_id={o.path_id} 字段(引用类)={interesting}")
        for f in interesting:
            try:
                v = getattr(d, f)
            except Exception:
                continue
            if hasattr(v, "m_PathID"):
                print(f"    {f}: FileID={getattr(v,'m_FileID','?')} PathID={v.m_PathID}")
            elif hasattr(v, "read"):
                print(f"    {f}: (readable)")

# ---------- 3. paintingface ----------
print("=" * 60)
print(f"3) paintingface/{name}")
pf = os.path.join(AB_ROOT, "paintingface", name)
if os.path.exists(pf):
    env = UnityPy.load(pf)
    tc = {}
    for o in env.objects:
        tc[o.type.name] = tc.get(o.type.name, 0) + 1
    print("  对象构成:", tc)
    for o in env.objects:
        try:
            d = o.read()
        except Exception:
            continue
        if o.type.name == "Sprite":
            print(f"  Sprite path_id={o.path_id} name={d.m_Name!r} "
                  f"rect=({d.m_Rect.x},{d.m_Rect.y},{d.m_Rect.width}x{d.m_Rect.height})")
        elif o.type.name == "Texture2D":
            print(f"  Texture2D path_id={o.path_id} name={d.m_Name!r} "
                  f"{d.m_Width}x{d.m_Height} fmt={d.m_TextureFormat}")
else:
    print("  (不存在)")
