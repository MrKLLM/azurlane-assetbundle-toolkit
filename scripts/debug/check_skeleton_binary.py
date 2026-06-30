#!/usr/bin/env python3
"""Find SkeletonBinary.readSkeletonData in spine-player.min.js"""
with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find SkeletonBinary class or readSkeletonData
import re

# Find readSkeletonData method
idx = content.find("readSkeletonData")
if idx >= 0:
    # Show context around it
    start = max(0, idx - 200)
    end = min(len(content), idx + 500)
    snippet = content[start:end]
    print(f"readSkeletonData found at offset {idx}")
    print(f"Context:")
    print(snippet)
else:
    print("readSkeletonData not found")

# Also check for the hash reading pattern
print("\n\n=== Searching for 0x1C signature check ===")
idx = content.find("28")  # 0x1C = 28
if idx >= 0:
    # Look for comparison with 28 or 0x1c
    for pattern in ["0x1c", "0x1C", "\\x1c", "\\x1C", "==28", "== 28"]:
        idx2 = content.find(pattern)
        if idx2 >= 0:
            print(f"Pattern '{pattern}' at offset {idx2}")
            print(f"  Context: ...{content[max(0,idx2-50):idx2+50]}...")

# Check how the binary reader handles the header
print("\n\n=== Searching for hash/version reading ===")
for pattern in ["readString", "readVarint", "readFloat"]:
    idx = content.find(pattern)
    if idx >= 0:
        print(f"{pattern} at offset {idx}")
