# -*- coding: utf-8 -*-
"""给 vendor/three 生成台账条目：逐个从 jsdelivr 重新下载并按 sha256 对拍，
**只有哈希命中才标 verified=true**（台账的纪律：不许写没验证过的来源）。"""
import hashlib
import io
import json
import os
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.dirname(HERE)
ROOT = os.path.dirname(SCRIPTS)      # 本文件在 scripts/diag/ 下，离根两层
VER = "0.160.0"
BASE = "https://cdn.jsdelivr.net/npm/three@%s/" % VER
UP = {
    "three.module.min.js": "build/three.module.min.js",
}
VDIR = os.path.join(ROOT, "Output", "gallery_v2", "vendor", "three")

entries = []
for dirpath, _dn, fns in os.walk(VDIR):
    for fn in sorted(fns):
        lp = os.path.join(dirpath, fn)
        rel = os.path.relpath(lp, VDIR).replace("\\", "/")
        up = UP.get(rel) or ("examples/jsm/" + rel[len("jsm/"):])
        url = BASE + up
        raw = open(lp, "rb").read()
        want = hashlib.sha256(raw).hexdigest()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "gallery-vendor-provision"})
            got_bytes = urllib.request.urlopen(req, timeout=60).read()
            got = hashlib.sha256(got_bytes).hexdigest()
            ok = got == want
            note = "verified" if ok else "哈希不符 %s" % got[:16]
        except Exception as ex:
            ok = False
            note = "下载失败 %s: %s" % (type(ex).__name__, ex)
        entries.append({
            "path": "Output/gallery_v2/vendor/three/" + rel,
            "version": "three %s（REVISION 160）" % VER,
            "bytes": len(raw),
            "sha256": want,
            "license": "MIT（three.js 上游 LICENSE；文件头 SPDX-License-Identifier: MIT）",
            "sources": [{"url": url, "verified": bool(ok)}],
            "note": "本轮对拍：%s" % note,
        })
        print("%-58s %8d  %s" % (rel, len(raw), note))
io.open(os.path.join(ROOT, ".diag", "vendor_three_entries.json"), "w", encoding="utf-8").write(
    json.dumps(entries, ensure_ascii=False, indent=2))
print("共 %d 条，验证命中 %d 条" % (len(entries), sum(1 for e in entries if e["sources"][0]["verified"])))
