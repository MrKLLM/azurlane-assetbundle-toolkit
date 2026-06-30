#!/usr/bin/env python3
"""Download spine runtime from GitHub raw files"""
import urllib.request
import os

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"
os.makedirs(RUNTIME_DIR, exist_ok=True)

def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return len(data)

# Try building from source - check what build artifacts exist
print("=== Checking 3.8 branch build directory ===")
try:
    import json
    req = urllib.request.Request(
        "https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts/build?ref=3.8",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read())
        for item in items:
            print(f"  {item['type']}: {item['name']} ({item.get('size', 'N/A')})")
except Exception as e:
    print(f"  Error: {e}")

# Check core/build
print("\n=== Checking core/build ===")
try:
    req = urllib.request.Request(
        "https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts/core/build?ref=3.8",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read())
        for item in items:
            print(f"  {item['type']}: {item['name']} ({item.get('size', 'N/A')})")
except Exception as e:
    print(f"  Error: {e}")

# Check webgl/build
print("\n=== Checking webgl/build ===")
try:
    req = urllib.request.Request(
        "https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts/webgl/build?ref=3.8",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read())
        for item in items:
            print(f"  {item['type']}: {item['name']} ({item.get('size', 'N/A')})")
except Exception as e:
    print(f"  Error: {e}")

# Check player/build
print("\n=== Checking player/build ===")
try:
    req = urllib.request.Request(
        "https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts/player/build?ref=3.8",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read())
        for item in items:
            print(f"  {item['type']}: {item['name']} ({item.get('size', 'N/A')})")
except Exception as e:
    print(f"  Error: {e}")

# Try spine-player demo/example
print("\n=== Checking spine-player example ===")
try:
    req = urllib.request.Request(
        "https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts/player/example?ref=3.8",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        items = json.loads(resp.read())
        for item in items:
            print(f"  {item['type']}: {item['name']}")
except Exception as e:
    print(f"  Error: {e}")

# Also check the spine-player npm package structure
print("\n=== Checking npm spine-player latest ===")
try:
    req = urllib.request.Request(
        "https://registry.npmjs.org/@esotericsoftware/spine-player/latest",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
        print(f"  Version: {data.get('version')}")
        print(f"  Main: {data.get('main')}")
        print(f"  Browser: {data.get('browser')}")
        dist = data.get('dist', {})
        print(f"  Tarball: {dist.get('tarball')}")
except Exception as e:
    print(f"  Error: {e}")
