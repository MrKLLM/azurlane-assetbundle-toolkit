"""
导出碧蓝航线立绘的布局树（逆向自游戏 AssetBundle）。

游戏把静态立绘做成纯 UI 结构：painting/<name> 里是 RectTransform + CanvasRenderer 的
层级树，每个节点记录了该部件的位置/大小/锚点/层级；真正的图集在 painting/<name>_tex
（Texture2D + Mesh，Mesh 记录每个部件在图集上的 UV）。

本脚本把这些布局数据导出成 JSON，供合成脚本直接使用 —— 不用再猜坐标。

关键前提：新版 AssetBundle 把 UnityFS 头部的 unity_version 伪装成 "5.x.x"，
必须显式指定真实版本（从包内 serialized file header 读到）才能解析。

用法:
    python export_painting_layout.py 2b
    python export_painting_layout.py 2b 22 laffey --out layout.json
"""
import argparse
import json
import os
import sys

import UnityPy
from UnityPy import config

# 游戏把 UnityFS header 的版本字段改成了 "5.x.x"，需要显式 fallback
config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

ASSET_ROOT = r"D:\Azur Lane Assets\files\AssetBundles"


def vec(v):
    """把 UnityPy 的向量对象转成普通 dict（兼容 x/y/z 或 key/value 命名）。"""
    if v is None:
        return None
    d = {}
    for k in ("x", "y", "z", "w"):
        if hasattr(v, k):
            d[k] = getattr(v, k)
    if not d and hasattr(v, "key"):
        return {"key": v.key, "value": v.value}
    return d or None


def read_painting(name):
    """读取 painting/<name> 的布局树，返回节点列表。"""
    path = os.path.join(ASSET_ROOT, "painting", name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到 {path}")

    env = UnityPy.load(path)
    objs = list(env.objects)

    rects, gos = {}, {}
    for o in objs:
        try:
            if o.type.name == "RectTransform":
                rects[o.path_id] = o.read()
            elif o.type.name == "GameObject":
                gos[o.path_id] = o.read()
        except Exception:
            continue

    # GameObject -> 名字
    go_name = {pid: getattr(g, "m_Name", "") for pid, g in gos.items()}

    nodes = []
    for pid, r in rects.items():
        # RectTransform 继承自 Component，自带 m_GameObject 指针
        go_ptr = getattr(r, "m_GameObject", None)
        go_pid = getattr(go_ptr, "m_PathID", None) if go_ptr is not None else None
        nodes.append({
            "rect_path_id": pid,
            "gameobject_path_id": go_pid,
            "name": go_name.get(go_pid, ""),
            "anchoredPosition": vec(getattr(r, "m_AnchoredPosition", None)),
            "sizeDelta": vec(getattr(r, "m_SizeDelta", None)),
            "anchorMin": vec(getattr(r, "m_AnchorMin", None)),
            "anchorMax": vec(getattr(r, "m_AnchorMax", None)),
            "pivot": vec(getattr(r, "m_Pivot", None)),
            "localScale": vec(getattr(r, "m_LocalScale", None)),
            "father": getattr(getattr(r, "m_Father", None), "m_PathID", None),
            "children": [getattr(c, "m_PathID", None)
                         for c in (getattr(r, "m_Children", None) or [])],
        })

    # 按名字排序，根节点（father 为 0 或 None）排最前
    nodes.sort(key=lambda n: (0 if not n["father"] else 1, n["name"]))
    return nodes, len(objs)


def read_tex(name):
    """读取 painting/<name>_tex 的纹理与网格信息。"""
    path = os.path.join(ASSET_ROOT, "painting", name + "_tex")
    if not os.path.exists(path):
        return None
    env = UnityPy.load(path)
    info = {"textures": [], "meshes": [], "sprites": []}
    for o in env.objects:
        try:
            d = o.read()
            if o.type.name == "Texture2D":
                info["textures"].append({
                    "name": d.m_Name, "width": d.m_Width, "height": d.m_Height,
                    "format": str(d.m_TextureFormat),
                })
            elif o.type.name == "Mesh":
                info["meshes"].append({"name": getattr(d, "m_Name", ""),
                                       "vertex_count": getattr(d, "m_VertexCount", None)})
            elif o.type.name == "Sprite":
                info["sprites"].append({"name": d.m_Name})
        except Exception:
            continue
    return info


def main():
    p = argparse.ArgumentParser(description="导出立绘布局树（逆向自游戏 AssetBundle）")
    p.add_argument("names", nargs="+", help="立绘名，如 2b 22 laffey")
    p.add_argument("--out", help="输出 JSON 路径（不指定则打印到终端）")
    args = p.parse_args()

    result = {}
    for name in args.names:
        try:
            nodes, nobj = read_painting(name)
        except FileNotFoundError as e:
            print(f"✗ {name}: {e}", file=sys.stderr)
            continue
        entry = {
            "name": name,
            "object_count": nobj,
            "rect_count": len(nodes),
            "nodes": nodes,
        }
        tex = read_tex(name)
        if tex:
            entry["tex"] = tex
        result[name] = entry

        # 终端摘要
        print(f"=== {name} ===")
        print(f"  对象 {nobj} 个 / RectTransform {len(nodes)} 个")
        if tex and tex["textures"]:
            t = tex["textures"][0]
            print(f"  纹理: {t['name']} {t['width']}x{t['height']} ({t['format']})")
        roots = [n for n in nodes if not n["father"]]
        for n in roots:
            print(f"  根: {n['name']!r}  子节点 {len(n['children'])} 个")
        for n in nodes:
            if n["name"] and n["name"] != roots[0]["name"] if roots else False:
                ap, sd = n["anchoredPosition"], n["sizeDelta"]
                if ap and sd and (sd.get("x") or sd.get("y")):
                    print(f"    {n['name']:<16} pos=({ap['x']:.1f},{ap['y']:.1f}) "
                          f"size=({sd['x']:.1f},{sd['y']:.1f})")
        print()

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✓ 已写入 {args.out}")


if __name__ == "__main__":
    main()
