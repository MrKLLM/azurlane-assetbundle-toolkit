#!/usr/bin/env python3
"""
inspect_atlas.py — 诊断 _tex bundle 中的纹理图集结构
分析 Texture2D / Sprite / Mesh 之间的关系
"""

import UnityPy
import json
import os
import sys

PAINTING_DIR = r"D:\Azur Lane Assets\files\AssetBundles\painting"

# 测试几个不同的 bundle
TEST_BUNDLES = ["lingbo_tex", "qiye_tex", "bisimai_tex", "chicheng_tex", "z23_tex"]

for tex_name in TEST_BUNDLES:
    bundle_path = os.path.join(PAINTING_DIR, tex_name)
    if not os.path.isfile(bundle_path):
        print(f"[SKIP] {tex_name} not found")
        continue

    print(f"\n{'='*60}")
    print(f"Bundle: {tex_name}")
    print(f"{'='*60}")

    env = UnityPy.load(bundle_path)

    for obj in env.objects:
        data = obj.read()
        t = obj.type.name

        if t == "Texture2D":
            img = data.image
            fmt = getattr(data, "m_TextureFormat", None)
            print(f"\n  Texture2D: {getattr(data, 'm_Name', '?')}")
            print(f"    size: {img.size}")
            print(f"    format: {fmt}")

        elif t == "Sprite":
            name = getattr(data, "m_Name", "?")
            print(f"\n  Sprite: {name}")
            print(f"    m_Rect: {data.m_Rect}")

            rd = getattr(data, "m_RD", None)
            if rd:
                for attr in ["textureRect", "textureRectOffset", "atlasRectOffset",
                             "settingsRaw", "pivot", "border"]:
                    val = getattr(rd, attr, None)
                    if val is not None:
                        print(f"    m_RD.{attr}: {val}")

            # Check for sub-sprites / packing tag
            for attr in ["m_PackingTag", "m_SpriteID", "m_Rect",
                         "m_Offset", "m_TileData", "mpriteBorder"]:
                val = getattr(data, attr, None)
                if val is not None:
                    print(f"    {attr}: {val}")

        elif t == "Mesh":
            verts = getattr(data, "vertices", [])
            uvs = getattr(data, "uv", [])
            print(f"\n  Mesh: {getattr(data, 'm_Name', '?')}")
            print(f"    vertices: {len(verts)}")
            print(f"    uv: {len(uvs)}")

        elif t not in ("AssetBundle",):
            name = getattr(data, "m_Name", "?")
            print(f"\n  {t}: {name}")

    # Also check the base bundle
    base_name = tex_name.replace("_tex", "")
    base_path = os.path.join(PAINTING_DIR, base_name)
    if os.path.isfile(base_path):
        print(f"\n--- Base bundle: {base_name} ---")
        env2 = UnityPy.load(base_path)
        type_counts = {}
        for obj in env2.objects:
            t = obj.type.name
            type_counts[t] = type_counts.get(t, 0) + 1
        for t, c in sorted(type_counts.items()):
            print(f"  {t}: {c}")

        # Check if there are any Sprite or Texture2D in base
        for obj in env2.objects:
            data = obj.read()
            t = obj.type.name
            if t in ("Sprite", "Texture2D", "Mesh"):
                name = getattr(data, "m_Name", "?")
                if t == "Texture2D":
                    img = data.image
                    print(f"  {t}: {name} size={img.size}")
                elif t == "Sprite":
                    print(f"  {t}: {name} m_Rect={data.m_Rect}")
                elif t == "Mesh":
                    uvs = getattr(data, "uv", [])
                    print(f"  {t}: {name} uv={len(uvs)}")
    else:
        print(f"\n  [No base bundle found for {base_name}]")
