# -*- coding: utf-8 -*-
"""
动态立绘（Spine）提取 v2 —— 依赖表驱动，兼容两种包结构：
  A. 内联型（如 2b_2）：主包直接含 .skel/.atlas TextAsset + Texture2D
  B. 分离型（如 aersasi）：主包只有 UI 结构，资源在 spinepainting/<name>_res

atlas 页纹理若不在以上两包内，按 dependencies 官方依赖表去外部包
（artresource/effect/*、ui/commonui_atlas 等）找同名 Texture2D 补齐。

输出（DeskSpine / spine-webgl 兼容目录结构）:
  Output/Spine_v2/<name>/<name>.skel
  Output/Spine_v2/<name>/<name>.atlas      （页名已重写为本地 png 文件）
  Output/Spine_v2/<name>/<page>.png

用法:
  python extract_spine_v2.py               # 全部
  python extract_spine_v2.py aersasi 2b_2  # 指定
"""
import json
import os
import re
import sys

import UnityPy
from UnityPy import config
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

AB_ROOT = r"D:\Azur Lane Assets\files\AssetBundles"
MANIFEST_PATH = r"D:\Azur Lane Assets\Output\dependency_manifest.json"
OUT_ROOT = r"D:\Azur Lane Assets\Output\Spine_v2"

manifest = json.load(open(MANIFEST_PATH, encoding="utf-8"))
_env_cache = {}


def load_bundle(name):
    if name in _env_cache:
        return _env_cache[name]
    path = os.path.join(AB_ROOT, name.lower().replace("/", os.sep))
    env = None
    if os.path.isfile(path):
        try:
            env = UnityPy.load(path)
        except Exception as e:
            print(f"  ! {name}: {e}")
    _env_cache[name] = env
    return env


def collect_assets(bundle_names):
    """从若干 bundle 收集 TextAsset(skel/atlas) 与 Texture2D。"""
    texts, textures = {}, {}
    for bn in bundle_names:
        env = load_bundle(bn)
        if not env:
            continue
        for o in env.objects:
            try:
                if o.type.name == "TextAsset":
                    d = o.read()
                    texts[str(d.m_Name)] = d.m_Script
                elif o.type.name == "Texture2D":
                    d = o.read()
                    textures[str(d.m_Name)] = o
            except Exception:
                pass
    return texts, textures


PAGE_RE = re.compile(r"^([^\s/\\:]+\.png)\s*$", re.M)


def atlas_pages(atlas_text):
    """解析 atlas 文本中的页纹理文件名列表（页名独占一行、后跟 size:）。"""
    pages = []
    lines = atlas_text.splitlines()
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.endswith(".png") and i + 1 < len(lines) and lines[i + 1].strip().startswith("size:"):
            if s not in pages:
                pages.append(s)
    return pages


def to_bytes(script):
    if isinstance(script, (bytes, bytearray)):
        return bytes(script)
    return str(script).encode("utf-8", "surrogateescape")


def extract_one(name):
    key = f"spinepainting/{name}"
    main = os.path.join(AB_ROOT, "spinepainting", name)
    if not os.path.isfile(main):
        return False, "主包缺失"
    deps = manifest.get(key, {}).get("deps", [])
    src_bundles = [key] + [d for d in deps if d.endswith("_res")]
    texts, textures = collect_assets(src_bundles)

    skels, atlases = {}, {}
    for k, v in texts.items():
        b = to_bytes(v)
        if k.endswith(".atlas") or k.endswith(".atlas.txt"):
            atlases[k[:-4] if k.endswith(".txt") else k] = v
        elif k.endswith(".skel"):
            skels[k] = v
        else:
            # 无后缀变体：atlas 文本含 spine 特征词；其余大二进制当 skel
            head = b[:4096]
            try:
                txt = head.decode("utf-8")
                is_atlas = ("size:" in txt and ("filter:" in txt or "pma:" in txt))
            except UnicodeDecodeError:
                is_atlas = False
            if is_atlas:
                atlases[k + ".atlas"] = v
            elif len(b) > 1024:
                skels[k + ".skel"] = v
    if not skels:
        return False, "无 skel"

    out_dir = os.path.join(OUT_ROOT, name)
    os.makedirs(out_dir, exist_ok=True)
    n_png = 0
    notes = []
    # 外部依赖包（补页纹理用）
    ext_bundles = [d for d in deps if not d.endswith("_res") and d != "custom_builtin"
                   and d != key]

    for aname, ascript in atlases.items():
        base = aname[:-len(".atlas")]
        atext = to_bytes(ascript).decode("utf-8", "replace")
        pages = atlas_pages(atext)
        for pg in pages:
            texname = pg[:-4]
            o = textures.get(texname)
            if o is None and ext_bundles:
                t2, x2 = collect_assets(ext_bundles)
                o = x2.get(texname)
                textures.update(x2)
                if o is None:
                    notes.append(f"缺页 {pg}")
                    continue
            if o is not None:
                # Spine 运行时按标准 PNG（行0=顶）采样，Unity raw data 需翻转
                img = get_image_from_texture2d(o.read(), flip=True)
                img.save(os.path.join(out_dir, pg))
                n_png += 1
        with open(os.path.join(out_dir, aname), "wb") as f:
            f.write(to_bytes(ascript))
    for sname, sscript in skels.items():
        with open(os.path.join(out_dir, sname), "wb") as f:
            f.write(to_bytes(sscript))
    msg = f"{len(skels)} skel / {len(atlases)} atlas / {n_png} png"
    if notes:
        msg += " | " + "; ".join(notes)
    return True, msg


def main():
    global OUT_ROOT
    argv = sys.argv[1:]
    if "--out" in argv:
        i = argv.index("--out")
        OUT_ROOT = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if argv:
        names = [a.strip() for a in argv if a.strip()]
    else:
        d = os.path.join(AB_ROOT, "spinepainting")
        names = sorted(f for f in os.listdir(d)
                       if os.path.isfile(os.path.join(d, f)) and not f.endswith("_res"))
    ok = miss = 0
    for n in names:
        try:
            good, msg = extract_one(n)
        except Exception as e:
            good, msg = False, f"异常: {e}"
        if good:
            ok += 1
            print(f"✓ {n}: {msg}")
        else:
            miss += 1
            print(f"✗ {n}: {msg}")
    print(f"\n成功 {ok}，失败 {miss} -> {OUT_ROOT}")


if __name__ == "__main__":
    main()
