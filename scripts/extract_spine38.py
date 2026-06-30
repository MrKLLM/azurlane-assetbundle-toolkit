#!/usr/bin/env python3
"""Extract spine 3.8 build files from the downloaded zip"""
import zipfile
import io
import os
import urllib.request

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"
os.makedirs(RUNTIME_DIR, exist_ok=True)

print("Downloading spine-runtimes 3.8...")
url = "https://github.com/EsotericSoftware/spine-runtimes/archive/refs/heads/3.8.zip"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

with urllib.request.urlopen(req, timeout=120) as resp:
    data = resp.read()

with zipfile.ZipFile(io.BytesIO(data)) as zf:
    # Extract the pre-built JS files
    files_to_extract = [
        "spine-runtimes-3.8/spine-ts/build/spine-core.js",
        "spine-runtimes-3.8/spine-ts/build/spine-core.d.ts",
        "spine-runtimes-3.8/spine-ts/build/spine-webgl.js",
        "spine-runtimes-3.8/spine-ts/build/spine-webgl.d.ts",
        "spine-runtimes-3.8/spine-ts/build/spine-canvas.js",
        "spine-runtimes-3.8/spine-ts/build/spine-canvas.d.ts",
        "spine-runtimes-3.8/spine-ts/build/spine-player.js",
        "spine-runtimes-3.8/spine-ts/build/spine-player.d.ts",
        "spine-runtimes-3.8/spine-ts/build/spine-all.js",
    ]
    
    for f in files_to_extract:
        try:
            content = zf.read(f)
            basename = os.path.basename(f)
            out_path = os.path.join(RUNTIME_DIR, f"3.8_{basename}")
            with open(out_path, "wb") as out:
                out.write(content)
            print(f"  {basename}: {len(content)} bytes -> 3.8_{basename}")
        except KeyError:
            print(f"  {f}: NOT FOUND")

# Also extract example HTML for reference
try:
    example_html = zf.read("spine-runtimes-3.8/spine-ts/example/index.html")
    with open(os.path.join(RUNTIME_DIR, "3.8_example.html"), "wb") as f:
        f.write(example_html)
    print(f"\n  Example HTML extracted")
except:
    pass

# List final files
print("\n=== Runtime files ===")
for f in sorted(os.listdir(RUNTIME_DIR)):
    fp = os.path.join(RUNTIME_DIR, f)
    size = os.path.getsize(fp)
    print(f"  {f}: {size:,} bytes")
