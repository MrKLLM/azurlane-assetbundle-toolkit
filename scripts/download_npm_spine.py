#!/usr/bin/env python3
"""Download spine-player from npm and extract"""
import urllib.request
import json
import os
import io
import zipfile

RUNTIME_DIR = r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime"
os.makedirs(RUNTIME_DIR, exist_ok=True)

# Download the npm tarball
print("Downloading spine-player from npm...")
url = "https://registry.npmjs.org/@esotericsoftware/spine-player/-/spine-player-4.3.7.tgz"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
        print(f"Downloaded: {len(data)} bytes")
        
        # Extract tarball (it's a .tgz = tar.gz)
        import tarfile
        tar = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        
        # List contents
        print("\nPackage contents:")
        for member in tar.getnames():
            if member.endswith(".js") or member.endswith(".css") or member.endswith(".html"):
                print(f"  {member}")
        
        # Extract relevant files
        extract_files = []
        for member in tar.getnames():
            basename = os.path.basename(member)
            # Extract JS and CSS files
            if basename.endswith(".js") and "dist" in member:
                extract_files.append(member)
            elif basename.endswith(".css") and "dist" in member:
                extract_files.append(member)
            elif basename == "index.html":
                extract_files.append(member)
        
        print(f"\nExtracting {len(extract_files)} files...")
        for fpath in extract_files:
            basename = os.path.basename(fpath)
            if not basename:
                continue
            out_path = os.path.join(RUNTIME_DIR, basename)
            fobj = tar.extractfile(fpath)
            if fobj:
                content = fobj.read()
                with open(out_path, "wb") as f:
                    f.write(content)
                print(f"  {basename}: {len(content)} bytes")
        
        tar.close()
        
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
