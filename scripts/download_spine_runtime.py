#!/usr/bin/env python3
"""Download spine-ts 3.8 runtime files"""
import urllib.request
import json
import os
import sys

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"

# spine-ts 3.8 release assets from GitHub
# We need: spine-core, spine-webgl (or spine-canvas)
BASE_URL = "https://raw.githubusercontent.com/EsotericSoftware/spine-runtimes/3.8"

FILES = {
    "spine-core.js": f"{BASE_URL}/spine-ts/spine-core/build/spine-core.js",
    "spine-webgl.js": f"{BASE_URL}/spine-ts/spine-webgl/build/spine-webgl.js",
}

os.makedirs(RUNTIME_DIR, exist_ok=True)

for name, url in FILES.items():
    out_path = os.path.join(RUNTIME_DIR, name)
    print(f"Downloading {name}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  Saved: {len(data)} bytes")
    except Exception as e:
        print(f"  Failed: {e}")

# Also try to get the UMD/browser build
print("\nChecking for browser-ready builds...")
UMD_FILES = {
    "spine-core.umd.js": f"{BASE_URL}/spine-ts/spine-core/build/spine-core.umd.js",
    "spine-webgl.umd.js": f"{BASE_URL}/spine-ts/spine-webgl/build/spine-webgl.umd.js",
}

for name, url in UMD_FILES.items():
    out_path = os.path.join(RUNTIME_DIR, name)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            print(f"  {name}: {len(data)} bytes")
    except Exception as e:
        print(f"  {name}: not available ({e})")
