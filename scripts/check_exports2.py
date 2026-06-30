#!/usr/bin/env python3
"""Check the actual export structure of spine-player.min.js"""
with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find the exports object - look for the pattern of exported names
# In the minified code, the exports should be near the __export call
import re

# Look for the spine-player/src/index.ts exports pattern
# In minified form, it would be something like:
# tr(index_exports, { Skeleton: () => SkeletonClass, ... })
# or
# __export(index_exports, { ... })

# Find all class-like names that are exported
# Look for patterns like: Name: () => minifiedName
export_pattern = re.findall(r'(\w+):\(\)=>(\w+)', content[:20000])
print("Export patterns found:")
for name, impl in export_pattern[:40]:
    print(f"  {name} -> {impl}")

# Also look for spine.Player or spine.Skeleton references
print("\nDirect spine references:")
spine_refs = re.findall(r'spine\.(\w+)', content[:10000])
for ref in set(spine_refs):
    print(f"  spine.{ref}")
