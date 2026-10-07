"""对一个 Unity AssetBundle 做「3D 还原能力」实测，只读，不写盘。

用途：判定某个包里的 3D 数据到底能取到哪一层——几何 / 蒙皮权重 / 贴图解码 /
动画曲线（含切线）/ 材质参数 / 着色器。结论只认这台机器上真实读出来的字段，
不认「别的管线当年还原不出来」这类外推。

    py -3 scripts/diag/probe_3d_capability.py files/AssetBundles/model/worldmap3d
    py -3 scripts/diag/probe_3d_capability.py <某个 dorm3d 的 *_db 包>

退出码：0 = 探针跑完（不代表能力齐全，看打印）；2 = 文件读不开。
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import collections
import os

import UnityPy

# Unity TextureFormat 里 ASTC/ETC 这些必须靠 texture2ddecoder 才解得开
BLOCKED_FMT_HINT = "解不开就先确认 texture2ddecoder 是否可用，别当成包坏了"


def hdr(t):
    print("\n== " + t + " ==")


def probe_mesh(env):
    hdr("MESH")
    n = 0
    for o in env.objects:
        if o.type.name != "Mesh":
            continue
        m = o.read()
        n += 1
        vd = getattr(m, "m_VertexData", None)
        vc = getattr(vd, "m_VertexCount", 0) if vd is not None else 0
        ch = len(getattr(vd, "m_Channels", []) or []) if vd is not None else 0
        bind = len(getattr(m, "m_BindPose", []) or [])
        bones = len(getattr(m, "m_BoneNameHashes", []) or [])
        comp = getattr(m, "m_CompressedMesh", None)
        idx = getattr(m, "m_IndexBuffer", b"") or b""
        print(f"  [{n}] {m.m_Name}: verts={vc} channels={ch} indexBytes={len(idx)} "
              f"bindPose={bind} boneHashes={bones} compressedMesh={'Y' if comp else 'N'}")
        if n == 1:
            try:
                out = m.export()
                print(f"  export() -> {type(out).__name__} len={len(out)}  "
                      f"(注意：OBJ 不含骨骼/蒙皮)")
            except Exception as e:
                print(f"  export() ERR {type(e).__name__}: {str(e)[:80]}")
    if n == 0:
        print("  无 Mesh")
    return n


def probe_skin(env):
    """真正决定「宿舍 3D 能不能动」的一条：SkinnedMeshRenderer 的权重。"""
    hdr("SKIN (SkinnedMeshRenderer)")
    found = 0
    for o in env.objects:
        if o.type.name != "SkinnedMeshRenderer":
            continue
        s = o.read()
        found += 1
        skin = getattr(s, "m_Skin", None)
        if skin is None:
            print("  m_Skin 字段不存在 —— 该 Unity 版本的网格把权重放在 Mesh.m_VertexData 流里，"
                  "改读 m_StreamData 的 BlendWeight/BlendIndex 通道")
            continue
        cnt = len(getattr(skin, "boneWeights", []) or getattr(skin, "m_BoneWeights", []) or [])
        paths = getattr(skin, "path", None) or getattr(skin, "bonePath", "") or ""
        print(f"  [{found}] bonePaths={'Y' if paths else 'EMPTY'} weightedVerts={cnt} "
              f"rootGameObj={getattr(s, 'm_rootBone', 'n/a') != ''}")
    if found == 0:
        print("  无 SkinnedMeshRenderer（静态网格包；不能据此推断蒙皮读不出来）")
    return found


def probe_texture(env):
    hdr("TEXTURE")
    ok = fail = 0
    for o in env.objects:
        if o.type.name != "Texture2D":
            continue
        t = o.read()
        try:
            img = t.image
            ok += 1
            if ok <= 3:
                print(f"  {t.m_Name}: {t.m_Width}x{t.m_Height} fmt={t.m_TextureFormat} "
                      f"mip={t.m_MipCount} -> {getattr(img, 'mode', '?')} 解码 OK")
        except Exception as e:
            fail += 1
            print(f"  {t.m_Name}: fmt={t.m_TextureFormat} 解码失败 {type(e).__name__} —— {BLOCKED_FMT_HINT}")
    print(f"  小结: 成功 {ok} / 失败 {fail}")
    return ok, fail


def probe_clip(env):
    hdr("ANIMATION")
    kf_fields = None
    try:
        from UnityPy.classes import Keyframe
        kf_fields = sorted(x for x in dir(Keyframe) if not x.startswith("_"))
    except Exception:
        pass
    if kf_fields:
        print(f"  Keyframe 字段: {kf_fields}")
        tang = [x for x in kf_fields if "lope" in x or "Weight" in x or "weighted" in x]
        print(f"  切线可得: {'Y' if tang else 'N'} {tang}")
    total = empty = comp = 0
    for o in env.objects:
        if o.type.name != "AnimationClip":
            continue
        a = o.read()
        total += 1
        n = sum(len(getattr(a, f, []) or []) for f in
                ("m_PositionCurves", "m_RotationCurves", "m_ScaleCurves", "m_FloatCurves",
                 "m_CompressedRotationCurves"))
        if bool(getattr(a, "m_Compressed", False)):
            comp += 1
        if n == 0:
            empty += 1
        print(f"  {a.m_Name}: curves={n} rate={getattr(a, 'm_SampleRate', '?')} "
              f"compressed={getattr(a, 'm_Compressed', '?')} events={len(a.m_Events or [])}")
    print(f"  小结: clip {total}（空 {empty} / compressed {comp}）")
    return total, empty


def probe_material_shader(env):
    hdr("MATERIAL PARAMS (重写 toon 材质的依据在这里)")
    for o in env.objects:
        if o.type.name != "Material":
            continue
        m = o.read()
        sp = m.m_SavedProperties
        fl = list(getattr(sp, "m_Floats", []) or [])
        col = list(getattr(sp, "m_Colors", []) or [])
        tex = list(getattr(sp, "m_Textures", []) or [])
        print(f"  {m.m_Name}: floats={len(fl)} colors={len(col)} texRefs={len(tex)} "
              f"queue={m.m_CustomRenderQueue} keywords={m.m_ShaderKeywords}")
        print(f"    值: {fl[:4]} {col[:2]}")
    hdr("SHADER")
    for o in env.objects:
        if o.type.name != "Shader":
            continue
        s = o.read()
        pf = s.m_ParsedForm
        props = list(getattr(pf.m_PropInfo, "m_Props", []) or [])
        names = [getattr(p, "m_Name", "?") for p in props]
        blob = len(getattr(s, "compressedBlob", b"") or b"")
        plats = list(getattr(s, "platforms", []) or [])
        print(f"  {pf.m_Name}: props={len(props)} {names[:8]}")
        print(f"  编译后字节码: platforms={plats} blob={blob} B —— 源码块不在包里，"
              f"但 blob 可走 DXBC/SPIR-V 反编译")
        try:
            e = s.export()
            txt = e if isinstance(e, str) else str(e)
            declares_invalid = "*not* a valid" in txt[:160].lower()
            print(f"  export() {len(txt)} 字符, 头部自述『不是有效的 shader 文件』: {declares_invalid} "
                  f"(True = 源码块已被裁掉，只剩 Properties 声明)")
        except Exception as ex:
            print(f"  export ERR {type(ex).__name__}")
        break


def main(path):
    if not os.path.isfile(path):
        print("文件不存在:", path)
        return 2
    try:
        env = UnityPy.load(path)
    except Exception as e:
        print(f"读不开: {type(e).__name__}: {str(e)[:160]}")
        print("若是 'No valid Unity version found'，设 UnityPy.config.FALLBACK_UNITY_VERSION 再试")
        return 2
    hist = collections.Counter(o.type.name for o in env.objects)
    print(f"PROBE {path}  size={os.path.getsize(path)/1024:.1f}KB")
    print("类型分布:", dict(hist.most_common(16)))
    probe_mesh(env)
    probe_skin(env)
    probe_texture(env)
    probe_clip(env)
    probe_material_shader(env)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "files/AssetBundles/model/worldmap3d"))
