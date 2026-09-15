"""
导出游戏官方 AssetBundle 依赖表。

files/AssetBundles/dependencies 里有一个 MonoBehaviour（86k+ 条），
m_Keys = bundle 资源名，m_Values = {m_FileName, m_Hash, m_Crc, m_Dependencies}。
prefab 中 PPtr.m_FileID = m_Dependencies 的 1-based 索引（FileID=1 -> deps[0]，
FileID=0 = 本体文件）。这是游戏加载时跨包引用的唯一权威映射。

用法: python export_dependency_manifest.py [--out Output/dependency_manifest.json]
"""
import argparse
import json
import os

import UnityPy
from UnityPy import config

config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

DEP_BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\dependencies"
DEFAULT_OUT = r"D:\Azur Lane Assets\Output\dependency_manifest.json"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=DEFAULT_OUT)
    args = p.parse_args()

    env = UnityPy.load(DEP_BUNDLE)
    manifest = {}
    for o in env.objects:
        if o.type.name != "MonoBehaviour":
            continue
        d = o.read()
        if not hasattr(d, "m_Keys") or d.m_Keys is None or len(d.m_Keys) == 0:
            continue
        keys = [str(k) for k in d.m_Keys]
        vals = list(d.m_Values)
        assert len(keys) == len(vals), f"keys={len(keys)} values={len(vals)} 不匹配"
        for k, v in zip(keys, vals):
            manifest[k] = {
                "file": str(getattr(v, "m_FileName", "")),
                "crc": int(getattr(v, "m_Crc", 0) or 0),
                "deps": [str(x) for x in (getattr(v, "m_Dependencies", None) or [])],
            }
        break

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, separators=(",", ":"))
    n_dep = sum(1 for v in manifest.values() if v["deps"])
    size_mb = os.path.getsize(args.out) / 1048576
    print(f"✓ {args.out}: {len(manifest)} 条目（{n_dep} 条有依赖），{size_mb:.1f} MB")


if __name__ == "__main__":
    main()
