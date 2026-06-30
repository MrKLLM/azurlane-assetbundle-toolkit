#!/usr/bin/env python3
"""Clone and build spine-ts 3.8 from source"""
import subprocess
import os
import shutil

WORK_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-build"
RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"

os.makedirs(WORK_DIR, exist_ok=True)

# Check if git is available
try:
    result = subprocess.run(["git", "--version"], capture_output=True, text=True, timeout=5)
    print(f"Git: {result.stdout.strip()}")
except Exception as e:
    print(f"Git not available: {e}")
    print("Trying alternative: download via HTTPS...")

# Try to download the spine-ts source as a zip
import urllib.request
import zipfile
import io

print("\nDownloading spine-runtimes 3.8 as zip...")
url = "https://github.com/EsotericSoftware/spine-runtimes/archive/refs/heads/3.8.zip"
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        print(f"Downloaded: {len(data)} bytes")
        
        # Extract
        print("Extracting...")
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # List spine-ts directories
            ts_dirs = [n for n in zf.namelist() if "spine-ts/" in n and n.count("/") <= 4]
            print(f"Files matching spine-ts/: {len(ts_dirs)}")
            for d in ts_dirs[:20]:
                print(f"  {d}")
            
            # Extract spine-core source
            core_files = [n for n in zf.namelist() 
                         if "spine-ts/spine-core/" in n and n.endswith(".ts")]
            print(f"\nspine-core TypeScript files: {len(core_files)}")
            for f in core_files[:10]:
                print(f"  {f}")
            
            # Extract spine-webgl source
            webgl_files = [n for n in zf.namelist() 
                          if "spine-ts/spine-webgl/" in n and n.endswith(".ts")]
            print(f"\nspine-webgl TypeScript files: {len(webgl_files)}")
            
            # Check for build output
            build_files = [n for n in zf.namelist() 
                          if "spine-ts/" in n and ("build/" in n or "dist/" in n or ".js" in n)]
            print(f"\nBuild/dist files: {len(build_files)}")
            for f in build_files[:20]:
                print(f"  {f}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
