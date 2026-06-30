#!/usr/bin/env python3
"""Find and download spine-ts runtime files"""
import urllib.request
import json
import os

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"
os.makedirs(RUNTIME_DIR, exist_ok=True)

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())

def download(url, out_path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)
        return len(data)

# Try to list spine-ts directory on 3.8 branch
print("=== Checking spine-runtimes 3.8 branch structure ===")
try:
    items = fetch_json("https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts?ref=3.8")
    for item in items:
        print(f"  {item['type']}: {item['name']}")
except Exception as e:
    print(f"  Error listing spine-ts: {e}")

# Try 4.1 branch
print("\n=== Checking spine-runtimes 4.1 branch ===")
try:
    items = fetch_json("https://api.github.com/repos/EsotericSoftware/spine-runtimes/contents/spine-ts?ref=4.1")
    for item in items:
        print(f"  {item['type']}: {item['name']}")
except Exception as e:
    print(f"  Error: {e}")

# Try checking the spine-player package versions
print("\n=== Checking npm registry for spine-player ===")
try:
    data = fetch_json("https://registry.npmjs.org/@esotericsoftware/spine-player")
    versions = list(data.get("versions", {}).keys())
    print(f"  Available versions: {versions[-10:]}")
    # Check latest 3.x version
    v3x = [v for v in versions if v.startswith("3.8")]
    print(f"  3.8.x versions: {v3x}")
except Exception as e:
    print(f"  Error: {e}")

# Try the spine-player UMD build from CDN
print("\n=== Trying CDN builds ===")
CDN_URLS = [
    ("spine-player.js", "https://unpkg.com/@esotericsoftware/spine-player@3.8.99/dist/spine-player.js"),
    ("spine-player.js", "https://unpkg.com/@esotericsoftware/spine-player@3.8/dist/spine-player.js"),
    ("spine-player.js", "https://cdn.jsdelivr.net/npm/@esotericsoftware/spine-player@3.8/dist/spine-player.js"),
    ("spine-player.js", "https://unpkg.com/spine-player@3.8/dist/spine-player.js"),
]

for name, url in CDN_URLS:
    try:
        size = download(url, os.path.join(RUNTIME_DIR, name))
        print(f"  OK: {url} -> {size} bytes")
        break
    except Exception as e:
        print(f"  FAIL: {url} -> {e}")
