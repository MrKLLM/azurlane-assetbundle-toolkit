"""对一个 Unity AssetBundle 做「3D 还原能力」实测，只读，不写盘。

用途：判定某个包里的 3D 数据到底能取到哪一层——几何 / 蒙皮权重 / 贴图解码 /
动画曲线（含切线）/ 材质参数 / 着色器。结论只认这台机器上真实读出来的字段，
不认「别的管线当年还原不出来」这类外推。

    py -3 scripts/diag/probe_3d_capability.py files/AssetBundles/model/worldmap3d
    py -3 scripts/diag/probe_3d_capability.py <某个 dorm3d 的 res 包>

SKIN WEIGHTS 那段是整条 3D 路的生死判据：反解 m_VertexData 的流切分、读出每顶点的骨号与权重，
并要求「每顶点权重和恰为 1 / 最大骨索引 < bindPose 数 / 覆盖率 100%」三条同时成立，
另配一条"故意偏移 1 字节必须判不出来"的反向对照——防止判据写成恒真。

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
        # m_CompressedMesh 这个**对象**在 TypeTree 里恒存在，判它有无没有信息量；
        # 只有它内部各段的 m_NumItems>0 才说明数据真走了压缩网格那条路。
        cmn = 0
        if comp is not None:
            for f in ("m_Vertices", "m_Normals", "m_Tangents", "m_UV", "m_Colors",
                      "m_BoneIndices", "m_BoneWeights", "m_Triangles"):
                cmn = max(cmn, int(getattr(getattr(comp, f, None), "m_NumItems", 0) or 0))
        idx = getattr(m, "m_IndexBuffer", b"") or b""
        print(f"  [{n}] {m.m_Name}: verts={vc} channels={ch} indexBytes={len(idx)} "
              f"bindPose={bind} boneHashes={bones} compressedItems={cmn}"
              f"{'  (压缩网格是空壳，权重在 m_VertexData)' if comp is not None and cmn == 0 else ''}")
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


def data_at(m):
    """整块顶点缓冲。UnityPy 1.25.3 把它放在 m_VertexData.m_DataSize 里（名字会骗人）——
    m_Streams 恒是空 list、m_Streams_0_..3_ 全是 None。"""
    return bytes(m.m_VertexData.m_DataSize)


# m_Channels 的数组下标就是 Unity 的着色器通道号：
# 0=Position 1=Normal 2=Tangent 3=Color 4..11=UV0..UV7 12=BlendWeight 13=BlendIndices
CH_BLEND_WEIGHT, CH_BLEND_INDICES = 12, 13


def candidate_layouts(vd, total_bytes):
    """反解打包顶点缓冲的流切分与各通道元素字节宽。

    每流只有**最后一个通道**的宽度推不出来（其余可由 next_offset - offset 整除得），
    未知数 = 流数，枚举属于 {1,2,4}，用"各流 stride 之和 == 每顶点字节数"筛掉错的。
    ⚠️ 尾部 padding 不一定在整块末尾——实测 hair 的余量落在**末段流起点之前**。
    """
    import itertools
    ch = sorted((c.stream, c.offset, c.dimension, i)
                for i, c in enumerate(vd.m_Channels) if c.dimension)
    n = vd.m_VertexCount
    if not n:
        return
    per, tail = divmod(total_bytes, n)
    streams = sorted({c[0] for c in ch})
    groups = {s: [c for c in ch if c[0] == s] for s in streams}
    derived = {}
    for s, g in groups.items():
        for k in range(len(g) - 1):
            gap, dim = g[k + 1][1] - g[k][1], g[k][2]
            if dim and gap % dim == 0 and gap // dim in (1, 2, 4):
                derived[g[k][3]] = gap // dim
    unk = [g[-1][3] for g in groups.values()]
    for vals in itertools.product((1, 2, 4), repeat=len(unk)):
        e = dict(derived)
        e.update(dict(zip(unk, vals)))
        stride = {s: max(t[1] + t[2] * e[t[3]] for t in g) for s, g in groups.items()}
        if sum(stride.values()) != per:
            continue
        base, cur = {}, 0
        for s in streams:
            base[s] = cur + (tail if s == streams[-1] else 0)
            cur += stride[s] * n
        yield ch, streams, stride, base, e, n, per, tail


def decode_skin(m, ch, stride, base, e, n, shift=0):
    """按给定布局读每顶点的骨号与权重。**只读不修**——布局错了就该判不出来。"""
    import struct
    W = next((t for t in ch if t[3] == CH_BLEND_WEIGHT), None)
    I = next((t for t in ch if t[3] == CH_BLEND_INDICES), None)
    bp = len(getattr(m, "m_BindPose", None) or [])
    if I is None or e.get(I[3]) not in (1, 2, 4):
        return None
    xs, xo, xd, xi = I
    ifmt = "<%d%s" % (xd, {1: "B", 2: "H", 4: "I"}[e[xi]])
    data = data_at(m)
    if W is None:            # 单骨部件：Unity 不写权重通道，权重恒 1
        wd = we = 0
    else:
        ws, wo, wd, wi = W
        we = e.get(wi)
        if we not in (2, 4):
            return None
        wfmt = "<%d%s" % (wd, {2: "H", 4: "f"}[we])
    good, mn, mx, mbi = 0, 1.0, 1.0, -1
    for v in range(n):
        try:
            if wd:
                raw = struct.unpack_from(wfmt, data, base[ws] + shift + v * stride[ws] + wo)
                s2 = sum(x / 65535.0 if we == 2 else x for x in raw)
                mn, mx = min(mn, s2), max(mx, s2)
                good += 1 if s2 > 0 else 0
            else:
                good += 1          # 单骨部件没有权重通道，权重恒 1，也算"已覆盖"
            ii = struct.unpack_from(ifmt, data, base[xs] + shift + v * stride[xs] + xo)
        except struct.error:
            # 越界 = 这条布局根本不成立（反向对照靠它把自己顶出缓冲区）
            return None
        mbi = max(mbi, max(ii))
    return dict(has_weight_chan=bool(wd), bones_per_vert=wd or 1, weight_bytes=we,
                idx_bytes=e[xi], weighted=good, total=n, wmin=mn, wmax=mx,
                max_bone_idx=mbi, bind_pose=bp)


def self_proof(r):
    """三重自证：权重和恰为 1（每个顶点）、最大骨索引 < bindPose 数、覆盖率 100%。"""
    if not r:
        return False
    return (abs(r["wmin"] - 1.0) < 1e-3 and abs(r["wmax"] - 1.0) < 1e-3
            and r["max_bone_idx"] < r["bind_pose"] and r["weighted"] == r["total"])


def probe_weights(env):
    """整条 3D 路的生死判据：每顶点的骨号 + 权重能不能**完整**读出来。

    判据不是"读出了字节"而是三条同时成立——错布局不可能同时满足，所以这既是判据也是回归闸门。
    每条 ✅ 配一条**反向对照**：末段流起点整体偏移 1 字节再解，必须判不出来；
    若偏移后仍"通过"，说明判据太松（恒真），打印里会直接点名。
    """
    hdr("SKIN WEIGHTS (Mesh.m_VertexData 通道 12/13 —— 整条 3D 路的生死判据)")
    passed = failed = skipped = 0
    for o in env.objects:
        if o.type.name != "Mesh":
            continue
        m = o.read()
        vd = m.m_VertexData
        if not getattr(vd, "m_VertexCount", 0):
            continue
        if not any(c.dimension and i in (CH_BLEND_WEIGHT, CH_BLEND_INDICES)
                   for i, c in enumerate(vd.m_Channels)):
            skipped += 1
            print(f"  - {m.m_Name}: 无 BlendWeight/BlendIndices 通道（静态网格，不算失败）")
            continue
        hit = None
        for ctx in candidate_layouts(vd, len(data_at(m))):
            ch, streams, stride, base, e, n, per, tail = ctx
            r = decode_skin(m, ch, stride, base, e, n)
            if self_proof(r):
                hit = (r, ctx)
                break
        if not hit:
            failed += 1
            print(f"  ✗ {m.m_Name}: verts={vd.m_VertexCount} —— 无自洽布局"
                  f"（**判不出不等于读不出**，先怀疑枚举宽度集合）")
            continue
        r, ctx = hit
        ch, streams, stride, base, e, n, per, tail = ctx
        neg = decode_skin(m, ch, stride, base, e, n, shift=1)
        bites = not self_proof(neg)
        passed += 1
        print(f"  ✓ {m.m_Name}: verts={n} 每顶点={per}B 流={[stride[s] for s in streams]} "
              f"padding={tail} 权重={r['bones_per_vert']}×{r['weight_bytes'] or '隐式1.0'}B "
              f"骨号={r['bones_per_vert']}×{r['idx_bytes']}B")
        print(f"      weighted={r['weighted']}/{r['total']} 权重和=[{r['wmin']:.5f},{r['wmax']:.5f}] "
              f"maxBoneIdx={r['max_bone_idx']} < bindPose={r['bind_pose']} "
              f"| 反向对照(偏移1B)={'判不出来(判据是活的)' if bites else '仍然通过(判据太松!)'}")
    print(f"  小结: 蒙皮可完整反解 {passed} / 解不出 {failed} / 无蒙皮通道 {skipped}")
    if failed:
        print("  ⚠️ 有网格解不出时，先确认它是不是压根走了 compressedItems>0 那条路，"
              "再谈'读不出'")
    return passed, failed


def probe_skin(env):
    """SkinnedMeshRenderer 侧：骨数与骨名（权重在 Mesh 侧，见 SKIN WEIGHTS 段）。"""
    hdr("SKIN (SkinnedMeshRenderer)")
    found = 0
    for o in env.objects:
        if o.type.name != "SkinnedMeshRenderer":
            continue
        s = o.read()
        found += 1
        try:
            name = s.m_GameObject.read().m_Name
        except Exception:
            name = "?"
        bones = list(getattr(s, "m_Bones", None) or [])
        names = []
        for b in bones[:4]:
            try:
                names.append(b.read().m_GameObject.read().m_Name)
            except Exception:
                names.append("?")
        print(f"  [{found}] {name}: bones={len(bones)} 前4骨名={names} "
              f"rootBone={'Y' if getattr(s, 'm_RootBone', None) else 'N'} "
              f"m_Skin={'有' if getattr(s, 'm_Skin', None) is not None else '无(2022.3 已搬进 Mesh.m_VertexData，不是失败)'}")
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
    probe_weights(env)
    probe_texture(env)
    probe_clip(env)
    probe_material_shader(env)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "files/AssetBundles/model/worldmap3d"))
