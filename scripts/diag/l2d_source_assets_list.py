# -*- coding: utf-8 -*-
"""l2d_source_assets_list.py — 罗列一个 Live2D **源包**里到底装了什么。只读。

为什么需要它：整条还原链（`reconstruct_live2d.py` → `extract_motions.py` → `fix_model3.py`）
只搬了 moc3 / Texture2D / physics3 TextAsset / AnimationClip 四类，其余一律忽略；
而 `fix_model3.py` 还主动**删掉** model3.json 里的 `Pose`/`Expressions`/`DisplayInfo`，
理由是"我们没有 .pose3.json/.exp3.json"。于是存在一种系统性盲区：
**源包里真的有 pose3/exp3/motion 这类文本资产，而链路从没搬过**——
这正是"游戏内难道没有蓝本吗"这一问的判据所在：先看源包里有没有。

输出三类：
  ① 对象类型直方图（含 MonoBehaviour 的脚本名分布）
  ② TextAsset 清单（名 + 前若干字节，用来认 physics3/pose3/exp3/motion3/model3 文本）
  ③ AnimationClip 清单（名 + 时长）

用法: py -3 scripts/diag/l2d_source_assets_list.py gezi_2
      py -3 scripts/diag/l2d_source_assets_list.py gezi_2 --text-chars 200
"""
import argparse
import os
import sys
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import UnityPy
from UnityPy import config as upy_config

upy_config.FALLBACK_UNITY_VERSION = "2022.3.62f3"
import paths as P


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("key", help="模型 key（源包文件名，如 gezi_2）")
    ap.add_argument("--text-chars", type=int, default=120, help="TextAsset 预览字节数")
    a = ap.parse_args()

    bp = os.path.join(P.LIVE2D_SRC, a.key)
    if not os.path.isfile(bp):
        print("[FAIL] 源包不在盘上: %s" % bp)
        return 2
    print("[*] 源包: %s  (%.2f MB)" % (bp, os.path.getsize(bp) / 1048576.0))
    env = UnityPy.load(bp)

    types = Counter()
    script_names = Counter()
    textassets = []
    clips = []
    for o in env.objects:
        types[o.type.name] += 1
        if o.type.name == "MonoBehaviour":
            try:
                sr = getattr(o.read(), "m_Script", None)
                sn = getattr(sr.read(), "m_Name", "") if sr else ""
                script_names[sn or "(空)"] += 1
            except Exception:
                script_names["(读失败)"] += 1
        elif o.type.name == "TextAsset":
            try:
                d = o.read()
                nm = getattr(d, "m_Name", "")
                sc = getattr(d, "m_Script", b"")
                if isinstance(sc, str):
                    sc = sc.encode("utf-8")
                textassets.append((nm, bytes(sc)))
            except Exception as e:
                textassets.append(("(读失败 %s)" % type(e).__name__, b""))
        elif o.type.name == "AnimationClip":
            try:
                d = o.read()
                clips.append((getattr(d, "m_Name", ""), getattr(d, "m_AnimationClipSettings", None)))
            except Exception:
                clips.append(("(读失败)", None))

    print("\n① 对象类型直方图:")
    for t, n in types.most_common():
        print("   %-22s %d" % (t, n))
    print("   MonoBehaviour 脚本名:")
    for s, n in script_names.most_common():
        print("      %-28s %d" % (s, n))

    print("\n② TextAsset 清单（共 %d 个）:" % len(textassets))
    if not textassets:
        print("   （无 TextAsset —— 源包内没有任何文本资产）")
    for nm, raw in textassets:
        prev = raw[:a.text_chars].decode("utf-8", "replace").replace("\n", "\\n").replace("\r", "")
        print("   %-34s %8d bytes  | %s" % (nm, len(raw), prev))

    print("\n③ AnimationClip 清单（共 %d 个）:" % len(clips))
    for nm, _ in clips:
        print("   %s" % nm)
    return 0


if __name__ == "__main__":
    sys.exit(main())
