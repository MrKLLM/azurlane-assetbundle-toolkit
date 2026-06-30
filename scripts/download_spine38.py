#!/usr/bin/env python3
"""Download spine 3.8 runtime from GitHub"""
import urllib.request
import os

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"

def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return len(data)

# Try to download spine-core 3.8 from GitHub
print("Downloading spine-core 3.8...")
base = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8/spine-ts/spine-core/src"

# The 3.8 branch has TypeScript source, we need compiled JS
# Try the build directory instead
build_base = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8/spine-ts/spine-core/build"

urls = [
    ("spine-core.js", f"{build_base}/spine-core.js"),
    ("spine-core.umd.js", f"{build_base}/spine-core.umd.js"),
    ("spine-core.d.ts", f"{build_base}/spine-core.d.ts"),
]

for name, url in urls:
    out = os.path.join(RUNTIME_DIR, name)
    try:
        size = download(url, out)
        print(f"  {name}: {size} bytes")
    except Exception as e:
        print(f"  {name}: FAILED - {e}")

# Also try spine-webgl 3.8
print("\nDownloading spine-webgl 3.8...")
webgl_base = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8/spine-ts/spine-webgl/build"
urls2 = [
    ("spine-webgl.js", f"{webgl_base}/spine-webgl.js"),
    ("spine-webgl.umd.js", f"{webgl_base}/spine-webgl.umd.js"),
]

for name, url in urls2:
    out = os.path.join(RUNTIME_DIR, name)
    try:
        size = download(url, out)
        print(f"  {name}: {size} bytes")
    except Exception as e:
        print(f"  {name}: FAILED - {e}")

# Try spine-player 3.8
print("\nDownloading spine-player 3.8...")
player_base = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8/spine-ts/spine-player/build"
urls3 = [
    ("spine-player.js", f"{player_base}/spine-player.js"),
    ("spine-player.umd.js", f"{player_base}/spine-player.umd.js"),
    ("spine-player.css", f"{player_base}/spine-player.css"),
]

for name, url in urls3:
    out = os.path.join(RUNTIME_DIR, name)
    try:
        size = download(url, out)
        print(f"  {name}: {size} bytes")
    except Exception as e:
        print(f"  {name}: FAILED - {e}")

# List what we have
print("\n=== Files in runtime dir ===")
for f in sorted(os.listdir(RUNTIME_DIR)):
    fp = os.path.join(RUNTIME_DIR, f)
    size = os.path.getsize(fp)
    print(f"  {f}: {size} bytes")
