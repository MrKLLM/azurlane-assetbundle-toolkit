#!/usr/bin/env python3
"""Check spine-player.min.js for browser globals"""
import re

with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

print(f"Size: {len(content)} bytes")

# Check for global variable assignments
globals_found = re.findall(r'(?:window|globalThis|self)\.(\w+)\s*=', content)
print(f"Global assignments: {globals_found[:10]}")

# Check for spine namespace
spine_refs = re.findall(r'spine\.(\w+)', content[:5000])
print(f"spine.* references: {spine_refs[:20]}")

# Check first 500 chars
print(f"\nFirst 300 chars:")
print(content[:300])
