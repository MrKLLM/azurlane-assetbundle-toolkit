"""跨包 PPtr 解析 —— dorm3d 房间场景的打通探针（只读，不碰台账、不写正式产物区）。

房间场景包里 348 个 `MeshFilter` 的网格**全是外链 PPtr**，装配房间必须先跨包解析。
本探针把这条路打通到「两条独立实现互证 + 一条会红的反向对照」的程度，并如实分桶计数。

    py -3 scripts/diag/dorm3d_pptr_resolve.py                       # 默认靶子 = 房间 1
    py -3 scripts/diag/dorm3d_pptr_resolve.py --sample 40 --seed 1
    py -3 scripts/diag/peak_mem.py --tag pptr -- py -3 scripts/diag/dorm3d_pptr_resolve.py

三条踩过的坑（本探针的实现就是围着它们写的，交接文档里的坑 #2 本轮已否证）：
1. **一个 bundle 里有多个 `SerializedFile`**（房间场景：主包 2332 对象/357 externals
   + `.sharedAssets` 32 对象/360 externals，另有 2 个 `.resS` **不是** SerializedFile）。
   拿 `next(iter(env.file.files.values()))` 会取到 `.sharedAssets` ⇒ `externals[file_id-1]`
   整体错位（上一轮据此把 `WallLeft` 的网格算成了 `fbx_db_pail01_fbx`）。
2. 归属**不需要**自建 path_id 表：UnityPy 1.25.3 的 `ObjectReader.assets_file`（带下划线）
   在这批包上是有值的，逐对象给出它自己的 SerializedFile ⇒ externals 只能取那一份。
   （恒 None 的是 **PPtr** 上的 `assetsfile`，两者不是一回事。）
3. 外链落点按 **CAB 名**索引到本地包；`unity default resources` 这类内置外链**盘上没有文件**，
   必须单独归桶、不得当成解析失败，也不得放进判据分母。

判据（退出码即结论）：
  J1 分桶求和 == MeshFilter 总数（无静默丢失）
  J2 固定种子抽 20 条（只从可落盘解析的外链命中里抽）语义相符 >= 18/20
  J3 同批样本走 UnityPy 原生 `pptr.deref()` 再解一遍，(包, 网格名, 顶点数) 与自实现逐条相同
  J4 反向对照：故意用错的那份 externals 重解同一批 ⇒ 语义相符率必须塌（不塌说明判据空心）
  J4b 反向对照：同一份 externals 下标 ±1（直接验 `file_id 从 1 起` 这条约定）必须塌
  J5 顶点数两条独立锚点：`m_VertexData.m_VertexCount` == UnityPy 自己 `export()` 出的 `v` 行数，
     且索引缓冲里的最大索引 < 顶点数
  J6 自建的 CAB 索引与缓存 `.diag/dorm3d_cab_index.json` 在 dorm3d 范围内键集一致

另附一条**信息项**（不进判据但装配时必须照它做）：激活态交叉表 —— 自身+全祖先 `m_IsActive`
（§55「只画游戏里开着的层」在 3D 侧的同一件事）。实测本场景 348 个 MeshFilter 里
**49 个挂在关闭态对象上**，绝大多数在 `night` 子树里（昼夜两套陈设同一位置）。
"""
import argparse
import collections
import json
import os
import random
import re
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import UnityPy                                                    # noqa: E402
from UnityPy.files import SerializedFile                          # noqa: E402

# 与 export_assets.py 同一行设置：不设时**场景包会直接读不开**（见 §116）。
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f3"

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AB_ROOT = os.path.join(REPO, "files", "AssetBundles")
DEF_DIR = os.path.join(AB_ROOT, "dorm3d")
DEF_SCENE = os.path.join(AB_ROOT, "dorm3d", "scenesres", "scenes", "tianlangxing_db",
                         "siriushostel", "map_siriushostel_01_scene")
DEF_CACHE = os.path.join(REPO, ".diag", "dorm3d_cab_index.json")
DEF_OUT = os.path.join(REPO, ".diag", "dorm3d_pptr", "resolve_report.json")
DEP_MANIFEST = os.path.join(REPO, "Output", "dependency_manifest.json")

# 资产命名前缀：对象名与网格名各带一种，剥掉后才可比
NAME_PREFIXES = ("pre_db_", "pre_", "fbx_db_", "fbx_", "mat_db_", "geo_", "obj_")
CLONE_SUFFIX = re.compile(r"\s*\(\d+\)$")


def norm(p):
    return p.replace("\\", "/")


def rel(p):
    """相对仓库根的归一路径 —— 索引里存绝对路径，对照缓存时必须先折成同一个口径。"""
    return norm(os.path.relpath(p, REPO)) if os.path.isabs(p) else norm(p)


def cab_key(name):
    return name.lower()


def die(msg, code=1):
    print("[FAIL] " + msg)
    sys.exit(code)


# ---------------------------------------------------------------- 索引

def bundle_cab_names(bundle_path):
    """一个 bundle 里所有 SerializedFile 的 CAB 名（跳过 .resS 这类非 SerializedFile）。"""
    env = UnityPy.load(bundle_path)
    out = []
    for k, v in env.file.files.items():
        if isinstance(v, SerializedFile):
            out.append(k)
    del env
    return out


def build_index(dirs, extra_bundles=()):
    """CAB 名 -> 本地包绝对路径。每个 SerializedFile 单独登记（`.sharedAssets` 也要）。"""
    index = {}
    dup = []
    t0 = time.time()
    n = 0
    for d in dirs:
        for root, _subs, files in os.walk(d):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                n += 1
                try:
                    for cab in bundle_cab_names(p):
                        k = cab_key(cab)
                        if k in index and norm(index[k]) != norm(p):
                            dup.append((cab, norm(index[k]), norm(p)))
                        index[k] = p
                except Exception as ex:
                    print("  [索引跳过] %s: %s %s" % (norm(p), type(ex).__name__, str(ex)[:60]))
    for p in extra_bundles:
        try:
            for cab in bundle_cab_names(p):
                index[cab_key(cab)] = p
        except Exception as ex:
            print("  [依赖包跳过] %s: %s" % (norm(p), type(ex).__name__))
    return index, n, round(time.time() - t0, 1), dup


def dep_bundle_paths(scene_path, manifest_path):
    """官方依赖表里该场景包的依赖 -> 盘上路径（dorm3d 之外的依赖靠这一步补进索引）。"""
    if not os.path.isfile(manifest_path):
        return [], None
    rel = norm(os.path.relpath(scene_path, AB_ROOT))
    d = json.load(open(manifest_path, encoding="utf-8"))
    ent = d.get(rel)
    if ent is None:
        return [], rel
    out = []
    for dep in ent.get("deps", []):
        p = os.path.join(AB_ROOT, *dep.split("/"))
        if os.path.isfile(p):
            out.append(p)
    return out, rel


def go_active(own, tr_of_go, sfn, goid):
    """自身 + 全祖先的 m_IsActive —— 与 §55「只画游戏里开着的层」同一个口径。

    房间场景里有 **49/348 个 MeshFilter 挂在关闭态对象上**，其中绝大多数在 `night`
    子树里（昼夜两套陈设）。装配时只该画激活的那批，否则同一个位置白天灯与夜灯叠画。
    返回 (是否全开, 第一个关闭态祖先名)。
    """
    cur = tr_of_go.get((sfn, goid))
    seen = set()
    on = True
    blocker = None
    while cur and (sfn, cur) in own and cur not in seen:
        seen.add(cur)
        t = own[(sfn, cur)].read()
        gp = getattr(t.m_GameObject, "path_id", 0) or 0
        g = own.get((sfn, gp))
        if g is not None and g.type.name == "GameObject":
            gg = g.read()
            if not bool(getattr(gg, "m_IsActive", True)):
                on = False
                blocker = blocker or gg.m_Name
        cur = getattr(getattr(t, "m_Father", None), "path_id", 0) or 0
    return on, blocker


# ---------------------------------------------------------------- 解析层

class Resolver:
    """按「对象自己那份 SerializedFile 的 externals」解析 PPtr，落到 CAB 精确选中的那个文件。"""

    def __init__(self, index):
        self.index = index
        self._envs = {}
        self._tables = {}
        self.load_seconds = 0.0

    def table(self, bundle_path):
        tbl = self._tables.get(bundle_path)
        if tbl is None:
            t0 = time.time()
            env = UnityPy.load(bundle_path)
            self._envs[bundle_path] = env
            tbl = {}
            for o in env.objects:
                tbl[(cab_key(o.assets_file.name), o.path_id)] = o
            self._tables[bundle_path] = tbl
            self.load_seconds += time.time() - t0
        return tbl

    def bundle_of(self, cab):
        return self.index.get(cab_key(cab))

    def classify(self, owner_sf, pp):
        """返回 (bucket, cab, path_id)。bucket ∈ null/self/oob/builtin/ext_hit/ext_miss"""
        pid = getattr(pp, "path_id", 0) or 0
        if not pid:
            return "null", None, 0
        fid = getattr(pp, "file_id", None)
        if fid is None:
            fid = getattr(pp, "m_FileID", 0) or 0
        if fid == 0:
            return "self", owner_sf.name, pid
        ext = owner_sf.externals or []
        if fid > len(ext):
            return "oob", None, pid
        e = ext[fid - 1]
        if not str(getattr(e, "path", "")).startswith("archive:"):
            return "builtin", e.name, pid
        if self.bundle_of(e.name) is None:
            return "ext_miss", e.name, pid
        return "ext_hit", e.name, pid

    def fetch(self, owner_env_table, bucket, cab, pid):
        """拿到目标 ObjectReader；解不开返回 (None, 原因)。

        ⚠️ `file_id == 0` 的"本包"指的是**引用方自己那个 SerializedFile**，不是"这次装配的源包"。
        材质对象住在 `mat_db_*` 包里，它自己引用的贴图常常也在同一个包里 ⇒ 拿源包的表去查会
        静默查不到（实测：141 个材质里 93 个因此丢了贴图）。所以本包先查调用者给的表，
        查不到再按 CAB 名回落到索引里那个包。
        """
        if bucket == "self":
            o = owner_env_table.get((cab_key(cab), pid))
            if o is not None:
                return o, None
            bp = self.bundle_of(cab)
            if bp is None:
                return None, "本包 path_id 未命中，且 CAB %s 不在索引里" % cab
            o = self.table(bp).get((cab_key(cab), pid))
            return (o, None) if o is not None else (None, "本包 path_id 未命中 (%s)" % norm(bp))
        if bucket != "ext_hit":
            return None, "不落盘: %s" % bucket
        bp = self.bundle_of(cab)
        o = self.table(bp).get((cab_key(cab), pid))
        return (o, None) if o is not None else (None, "外链包内 path_id 未命中 (%s)" % norm(bp))


def mesh_summary(reader):
    m = reader.read()
    vd = getattr(m, "m_VertexData", None)
    vc = int(getattr(vd, "m_VertexCount", 0) or 0) if vd is not None else 0
    return m, vc


def index_hi(mesh):
    """索引缓冲里的最大索引值（按 16/32 位格式）——必须 < 顶点数。"""
    buf = getattr(mesh, "m_IndexBuffer", b"") or b""
    if not buf:
        return None
    use32 = bool(getattr(mesh, "m_Use16BitIndices", 1)) is False
    fmt = getattr(mesh, "m_IndexFormat", None)
    if fmt is not None:
        try:
            use32 = int(fmt) != 0
        except (TypeError, ValueError):
            pass
    if use32:
        vals = [int.from_bytes(buf[i:i + 4], "little") for i in range(0, len(buf) - 3, 4)]
    else:
        vals = [int.from_bytes(buf[i:i + 2], "little") for i in range(0, len(buf) - 1, 2)]
    return max(vals) if vals else None


def obj_v_count(mesh):
    """UnityPy 自己的解码路径（完全不经过 m_VertexCount）给出顶点数，当独立锚点用。"""
    txt = mesh.export()
    return sum(1 for line in txt.splitlines() if line.startswith("v "))


def tokens(name):
    """`pre_db_ceram01b (3)` / `Chair_1` / `fbx_db_ceram01b` 折成可比的词元序列。

    两处必要的规范化：① 数字段去前导零（`chair01` 与 `Chair_1` 是同一个东西）；
    ② 只按非字母数字切分（下划线不算边界）。前缀（pre_/fbx_/mat_）与副本后缀 ` (N)` 剥掉。
    """
    n = CLONE_SUFFIX.sub("", (name or "").strip()).lower()
    for p in NAME_PREFIXES:
        if n.startswith(p):
            n = n[len(p):]
            break
    out = []
    for t in (x for x in re.split(r"[^a-z0-9]+", n) if x):
        out.append(re.sub(r"\d+", lambda m: str(int(m.group())), t))
    return out


def is_subseq(small, big):
    i = 0
    for t in big:
        if i < len(small) and small[i] == t:
            i += 1
    return i == len(small)


def semantic(a, b):
    """strict = 词元序列完全相同；subseq = 一方是另一方的子序列（允许中间插入词元，
    如对象名里多一个颜色/变体词：`pre_oak02_green02_lod3` ↔ `fbx_oak02_lod3`）；
    否则 mismatch。用序列顺序而不是集合包含，是为了让 `WallLeft` ↔ `pail01` 这类真错位必红。
    """
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return "none", False
    if ta == tb:
        return "strict", True
    if is_subseq(tb, ta) or is_subseq(ta, tb):
        return "subseq", True
    return "mismatch", False


# ---------------------------------------------------------------- 取样

def collect(env, resolver, want_types=("MeshFilter",)):
    """遍历源包对象，按各自 assets_file 取 externals，产目标记录 + 分桶计数。"""
    own = {}
    for o in env.objects:
        own[(cab_key(o.assets_file.name), o.path_id)] = o
    # 源包里每个 SerializedFile 都要一份「对象自己那份」的表；env.objects 已跨文件
    sfs = {o.assets_file.name.lower(): o.assets_file for o in env.objects}
    tr_of_go = {}
    for (sfn, pid), o in own.items():
        if o.type.name == "Transform":
            gp = getattr(o.read().m_GameObject, "path_id", 0) or 0
            if gp:
                tr_of_go[(sfn, gp)] = pid
    rows, buckets, objs = [], {k: 0 for k in ("null", "self", "ext_hit", "ext_miss", "builtin", "oob")}, 0
    miss_cabs = {}
    for o in env.objects:
        if o.type.name not in want_types:
            continue
        objs += 1
        obj = o.read()
        pp = getattr(obj, "m_Mesh", None)
        if pp is None:
            buckets["null"] += 1
            continue
        sfn = o.assets_file.name.lower()
        go = own.get((sfn, getattr(obj.m_GameObject, "path_id", 0) or 0))
        gname = go.read().m_Name if go is not None else "?"
        sf = sfs[sfn]
        on, blocker = go_active(own, tr_of_go, sfn, getattr(obj.m_GameObject, "path_id", 0) or 0)
        bucket, cab, pid = resolver.classify(sf, pp)
        buckets[bucket] += 1
        rec = {"type": o.type.name, "object": gname, "bucket": bucket, "cab": cab, "active": on,
               "blocker": blocker,
               "path_id": pid, "sf": sf.name, "src_pid": o.path_id}
        if bucket == "ext_miss":
            miss_cabs[cab] = miss_cabs.get(cab, 0) + 1
        if bucket in ("self", "ext_hit"):
            tgt, err = resolver.fetch(own, bucket, cab, pid)
            if tgt is None:
                rec.update({"ok": False, "err": err})
            elif tgt.type.name != "Mesh":
                rec.update({"ok": False, "err": "目标类型是 %s 不是 Mesh" % tgt.type.name})
            else:
                m, vc = mesh_summary(tgt)
                bundle = ("(源包自身)" if bucket == "self"
                          else rel(resolver.bundle_of(cab)))
                rec.update({"ok": vc > 0, "mesh": m.m_Name, "verts": vc, "bundle": bundle,
                            "target_type": tgt.type.name})
        rows.append(rec)
    return rows, buckets, objs, miss_cabs, own, sfs


# ---------------------------------------------------------------- 主流程

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default=DEF_SCENE)
    ap.add_argument("--root", default=DEF_DIR, help="建 CAB 索引的目录")
    ap.add_argument("--cache", default=DEF_CACHE, help="上一轮的 CAB 索引缓存，仅用于对照")
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261008)
    ap.add_argument("--pass-mark", type=int, default=18, help="J2 通过线")
    ap.add_argument("--out", default=DEF_OUT)
    args = ap.parse_args()

    if not os.path.isfile(args.scene):
        die("场景包不存在: %s" % args.scene)
    if not os.path.isdir(args.root):
        die("索引根目录不存在: %s" % args.root)

    print("靶子: %s" % rel(args.scene))
    deps, dep_key = dep_bundle_paths(args.scene, DEP_MANIFEST)
    print("官方依赖表条目: %s（盘上存在的依赖包 %d 个）" % (dep_key or "无", len(deps)))

    # --- J6: 自建索引 与 缓存索引 对照（两套独立构建）
    t0 = time.time()
    index, scanned, secs, dup = build_index([args.root], extra_bundles=deps)
    inroot = rel(args.root).rstrip("/") + "/"
    outside = [k for k, v in index.items() if not rel(v).startswith(inroot)]
    print("索引: 扫 %d 个包 / %.1f 秒 / %d 条 CAB（dorm3d 之外 %d 条，来自官方依赖清单）"
          % (scanned, secs, len(index), len(outside)))
    for k in outside[:6]:
        print("   索引补: %s -> %s" % (k, rel(index[k])))
    if dup:
        print("  ⚠️ 同一 CAB 名落在 %d 个不同包（解析会歧义，必须先看这里）" % len(dup))
        for d in dup[:5]:
            print("     ", d)
    cache = {}
    if os.path.isfile(args.cache):
        for k, v in json.load(open(args.cache, encoding="utf-8")).items():
            cache[cab_key(k)] = norm(v)
    shared = [k for k in cache if k in index]
    only_cache = [k for k in cache if k not in index]
    disagree = [k for k in shared if rel(index[k]) != cache[k]]
    print("缓存索引: %d 条 | 自建命中 %d | 仅缓存有 %d | 同键不同包 %d | 仅自建有 %d"
          % (len(cache), len(shared), len(only_cache), len(disagree), len(index) - len(shared)))
    for k in only_cache[:5]:
        print("   仅缓存: %s -> %s" % (k, cache[k]))
    for k in disagree[:5]:
        print("   分歧: %s 缓存=%s 自建=%s" % (k, cache[k], rel(index[k])))

    resolver = Resolver(index)
    env = UnityPy.load(args.scene)
    rows, buckets, total, miss_cabs, own, sfs = collect(env, resolver)

    print("\n== 分桶 (J1) ==")
    for k in ("self", "ext_hit", "ext_miss", "builtin", "null", "oob"):
        print("  %-9s %d" % (k, buckets[k]))
    print("  合计 %d / MeshFilter 总数 %d" % (sum(buckets.values()), total))
    for cab, n in sorted(miss_cabs.items(), key=lambda x: -x[1]):
        hint = resolver.index.get(cab_key(cab))
        print("  未命中 CAB %s 被引 %d 次%s" % (cab, n, "" if hint else "（索引里也没有）"))
    self_rows = [r for r in rows if r["bucket"] == "self"]
    builtin_rows = [r for r in rows if r["bucket"] == "builtin"]
    print("  本包 %d 条（不进抽样分母，单独核）:" % len(self_rows))
    for r in self_rows:
        print("     %-28s -> %s v=%s" % (r["object"][:28], r.get("mesh"), r.get("verts")))
    print("  内置资源 %d 条 = 盘上没有对应文件的 Unity 原语网格，单列、不算失败也不进分母。对象名:"
          % len(builtin_rows))
    print("     " + ", ".join(sorted(set(r["object"] for r in builtin_rows))[:24]))

    # --- 激活态交叉表（信息项，非判据）：装配时只该画开着的
    print("\n== 激活态交叉表（自身+全祖先 m_IsActive；信息项，不进判据）==")
    tab = collections.Counter((r["bucket"], r["active"]) for r in rows if r["bucket"] != "null")
    blockers = collections.Counter(r["blocker"] for r in rows if not r["active"] and r["blocker"])
    print("  %-9s %6s %6s" % ("bucket", "开", "关"))
    for b in ("self", "ext_hit", "ext_miss", "builtin"):
        print("  %-9s %6d %6d" % (b, tab[(b, True)], tab[(b, False)]))
    print("  关闭态首因（哪个祖先先关）: %s" % dict(blockers.most_common(8)))
    print("  ⇒ 装配口径: 只画 %d 条开着的；`night` 子树是夜版陈设，与日版同位置，两套都画会叠面。"
          % sum(1 for r in rows if r["active"]))

    ok_rows = [r for r in rows if r.get("ok")]
    bad_rows = [r for r in rows if r["bucket"] in ("self", "ext_hit") and not r.get("ok")]
    modes = [semantic(r["object"], r["mesh"]) for r in ok_rows]
    strict = sum(1 for m, _ in modes if m == "strict")
    matched = sum(1 for _m, o in modes if o)
    print("\n== 全量语义（母体 = 可落盘解析的 %d 条：本包 %d + 外链命中 %d）=="
          % (buckets["self"] + buckets["ext_hit"], buckets["self"], buckets["ext_hit"]))
    print("  解出网格并读到顶点数>0: %d / 应解 %d（解出但顶点数 0 或类型不对 = %d）"
          % (len(ok_rows), buckets["self"] + buckets["ext_hit"], len(bad_rows)))
    print("  语义相符 %d（完全同名 %d / 子序列 %d）| 不符 %d"
          % (matched, strict, matched - strict, len(ok_rows) - matched))
    print("  外链包去重后 %d 个，跨包加载耗时 %.1f 秒" % (
        len(set(r["bundle"] for r in ok_rows if r["bucket"] == "ext_hit")), resolver.load_seconds))
    for r in bad_rows[:5]:
        print("   [未解出] %s: %s" % (r["object"], r.get("err")))
    print("   语义不符清单（逐条列出来人工看一眼，别当噪声）:")
    for r, (mode, o) in zip(ok_rows, modes):
        if not o:
            print("     %-30s -> %-30s v=%d  [%s]"
                  % (r["object"][:30], r["mesh"][:30], r["verts"],
                     os.path.basename(r["bundle"])[:30]))

    # --- 抽样 J2
    pool = [r for r in rows if r["bucket"] == "ext_hit" and r.get("ok")]
    if len(pool) < args.sample:
        die("外链命中且解出的只有 %d 条，不足抽样数 %d" % (len(pool), args.sample))
    picked = random.Random(args.seed).sample(pool, args.sample)
    print("\n== 抽样 %d 条 (J2, seed=%d) ==" % (args.sample, args.seed))
    j2 = 0
    for i, r in enumerate(picked):
        mode, oksem = semantic(r["object"], r["mesh"])
        j2 += 1 if oksem else 0
        print("  %2d %-24s -> %-28s v=%-6d %s   [%s]"
              % (i + 1, r["object"][:24], r["mesh"][:28], r["verts"],
                 ("语义OK/" + mode) if oksem else "语义不符",
                 os.path.basename(r["bundle"])[:38]))
    print("  J2 语义相符 %d/%d（线 %d）" % (j2, args.sample, args.pass_mark))

    # --- J3: UnityPy 原生 deref（另一套代码）逐条比对
    print("\n== 路径 B: 原生 pptr.deref() 互证 (J3) ==")
    benv = UnityPy.load(args.scene)
    need = set(r["bundle"] for r in picked)
    t0 = time.time()
    load_err = 0
    for relp in need:
        try:
            benv.load_file(os.path.join(REPO, *relp.split("/")))
        except Exception as ex:
            load_err += 1
            print("   load_file 失败 %s: %s" % (relp, type(ex).__name__))
    btab = {}
    for o in benv.objects:
        btab[(cab_key(o.assets_file.name), o.path_id)] = o
    mismatch = 0
    for r in picked:
        bo = btab.get((cab_key(r["sf"]), r["src_pid"]))
        if bo is None:
            mismatch += 1
            print("   源对象在路径 B 的 Environment 里找不到: %s" % r["object"])
            continue
        bpp = bo.read().m_Mesh
        tgt = bpp.deref()
        bm, bvc = mesh_summary(tgt)
        bpath = index.get(cab_key(tgt.assets_file.name))
        bbundle = ("?" if bpath is None else norm(os.path.relpath(bpath, REPO)))
        same = (bbundle == r["bundle"] and bm.m_Name == r["mesh"] and bvc == r["verts"]
                and tgt.type.name == "Mesh")
        if not same:
            mismatch += 1
            print("   不一致 %s: A=(%s,%s,%d) B=(%s,%s,%d)"
                  % (r["object"], os.path.basename(r["bundle"]), r["mesh"], r["verts"],
                     os.path.basename(bbundle), bm.m_Name, bvc))
    print("  装载 %d 个依赖包 / %.1f 秒 / 失败 %d | A-B 不一致 %d/%d"
          % (len(need), time.time() - t0, load_err, mismatch, len(picked)))

    # --- J4: 反向对照 —— 故意用错的那份 externals（上一轮的真实错误）
    print("\n== 反向对照: 用 next(iter(files)) 那份 externals 重解 (J4) ==")
    wrong_sf = None
    for v in env.file.files.values():
        if isinstance(v, SerializedFile):
            wrong_sf = v
            break
    right_names = set(o.assets_file.name for o in env.objects if o.type.name in ("MeshFilter",))
    print("  盲取到的是 %s（正确归属应是 %s）%s"
          % (wrong_sf.name, ", ".join(sorted(right_names)),
             "  == 与正确那份不同，对照有效" if wrong_sf.name not in right_names
             else "  ⚠️ 与正确那份相同，这条对照没改变任何物理量"))
    wrong_ok = 0
    wrong_fail = {"oob": 0, "builtin": 0, "miss": 0, "notfound": 0}
    for r in picked:
        pid = r["path_id"]
        ext = wrong_sf.externals or []
        # 按同一对象再取一次原始 file_id，保证对照与 J2 量的确实是同一个 PPtr
        so = own[(cab_key(r["sf"]), r["src_pid"])]
        fid = so.read().m_Mesh.file_id
        if fid == 0 or fid > len(ext):
            wrong_fail["oob"] += 1
            continue
        e = ext[fid - 1]
        if not str(getattr(e, "path", "")).startswith("archive:"):
            wrong_fail["builtin"] += 1
            continue
        bp = resolver.bundle_of(e.name)
        if bp is None:
            wrong_fail["miss"] += 1
            continue
        t2 = resolver.table(bp).get((cab_key(e.name), pid))
        if t2 is None or t2.type.name != "Mesh":
            wrong_fail["notfound"] += 1
            continue
        _m, vc = mesh_summary(t2)
        if vc > 0 and semantic(r["object"], t2.read().m_Name)[1]:
            wrong_ok += 1
    print("  错表解析仍「语义相符」的: %d/%d，失败细分 %s" % (wrong_ok, len(picked), wrong_fail))
    print("  J4 要求这条必须显著低于 J2（对照有效时它越红越好）")

    # --- J4b: 同一份 externals，下标偏移 ±1 —— 直接验 `file_id 从 1 起` 这条约定
    print("\n== 反向对照: externals 下标 ±1 (J4b) ==")

    def shifted(delta):
        hit = 0
        fail = collections.Counter()
        for r in picked:
            so = own[(cab_key(r["sf"]), r["src_pid"])]
            fid = so.read().m_Mesh.file_id + delta
            ext = sfs[cab_key(r["sf"])].externals or []
            if fid <= 0 or fid > len(ext):
                fail["oob"] += 1
                continue
            e = ext[fid - 1]
            if not str(getattr(e, "path", "")).startswith("archive:"):
                fail["builtin"] += 1
                continue
            bp = resolver.bundle_of(e.name)
            if bp is None:
                fail["miss"] += 1
                continue
            t2 = resolver.table(bp).get((cab_key(e.name), r["path_id"]))
            if t2 is None or t2.type.name != "Mesh":
                fail["notfound"] += 1
                continue
            _m, vc = mesh_summary(t2)
            if vc > 0 and semantic(r["object"], t2.read().m_Name)[1]:
                hit += 1
        return hit, dict(fail)

    shift_stats = {}
    for delta in (1, -1):
        hit, fail = shifted(delta)
        print("  偏移 %+d: 仍语义相符 %d/%d，失败细分 %s" % (delta, hit, len(picked), fail))
        shift_stats[delta] = hit

    # --- J5: 顶点数独立锚点
    print("\n== 顶点数独立锚点 (J5) ==")
    j5bad = 0
    for i, r in enumerate(picked):
        so = own[(cab_key(r["sf"]), r["src_pid"])]
        pp = so.read().m_Mesh
        tgt, _ = resolver.fetch(own, r["bucket"], r["cab"], r["path_id"])
        m, vc = mesh_summary(tgt)
        try:
            nv = obj_v_count(m)
        except Exception as ex:
            nv = -1
            print("   export() 失败 %s: %s" % (r["object"], type(ex).__name__))
        hi = index_hi(m)
        good = (vc > 0 and nv == vc and (hi is None or hi < vc))
        j5bad += 0 if good else 1
        if not good:
            print("   [锚点红] %s vc=%d export_v=%d maxIdx=%s" % (r["object"], vc, nv, hi))
    print("  锚点不符 %d / %d（vc vs UnityPy export 的 v 行数，另查最大索引 < vc）"
          % (j5bad, len(picked)))

    # --- 结论
    j1 = sum(buckets.values()) == total
    j2ok = j2 >= args.pass_mark
    j6ok = (not only_cache) and (not disagree)
    j4b = max(shift_stats.values()) < j2
    checks = [("J1 分桶求和==总数", j1, "%d/%d" % (sum(buckets.values()), total)),
              ("J2 抽样语义>=%d" % args.pass_mark, j2ok, "%d/%d" % (j2, args.sample)),
              ("J3 原生 deref 零不一致", mismatch == 0 and load_err == 0,
               "%d/%d" % (len(picked) - mismatch, len(picked))),
              ("J4 换错 SerializedFile 必须塌", wrong_ok < j2, "%d/%d (对照 J2 的 %d/%d)"
               % (wrong_ok, len(picked), j2, args.sample)),
              ("J4b externals 下标±1 必须塌", j4b,
               "+1得%d / -1得%d (对照 J2 的 %d)" % (shift_stats[1], shift_stats[-1], j2)),
              ("J5 顶点数双锚点全过", j5bad == 0, "%d/%d" % (len(picked) - j5bad, len(picked))),
              ("J6 索引与缓存键集一致", j6ok, "仅缓存 %d / 分歧 %d" % (len(only_cache), len(disagree)))]
    print("\n== 判据 ==")
    allok = True
    for name, ok, detail in checks:
        print("  %s %-28s %s" % ("✅" if ok else "❌", name, detail))
        allok = allok and ok
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump({"scene": rel(args.scene), "seed": args.seed,
               "sample": args.sample, "buckets": buckets, "total": total,
               "strict_all": strict, "matched_all": matched, "ok_all": len(ok_rows),
               "bad": bad_rows[:20], "sample_rows": picked, "self_rows": self_rows,
               "builtin_objects": sorted(set(r["object"] for r in builtin_rows)),
               "activation": {"active": sum(1 for r in rows if r["active"]),
                              "inactive": sum(1 for r in rows if not r["active"]),
                              "blockers": dict(blockers)},
               "deref_mismatch": mismatch, "negative_control_ok": wrong_ok,
               "shift_control_ok": {str(k): v for k, v in shift_stats.items()},
               "anchor_bad": j5bad, "index_scanned": scanned, "index_keys": len(index),
               "cache_only": only_cache[:20], "disagree": disagree[:20],
               "checks": [[n, bool(o), d] for n, o, d in checks]},
              open(args.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("报告: %s" % rel(args.out))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
