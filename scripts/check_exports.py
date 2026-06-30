#!/usr/bin/env python3
"""Check spine-player.min.js exports at the end"""
with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

# Show last 1000 chars
print("Last 1000 chars:")
print(content[-1000:])

# Check if spine.SkeletonBinary exists in the code
print("\n\nSearching for SkeletonBinary in code...")
idx = content.find("SkeletonBinary")
if idx >= 0:
    print(f"Found at offset {idx}")
    print(f"Context: ...{content[max(0,idx-50):idx+100]}...")

# Check for Skeleton
idx = content.find("class Skeleton")
if idx >= 0:
    print(f"\nSkeleton class at offset {idx}")

# Check how spine is constructed
print("\n\nFirst 200 chars of IIFE body:")
# Find the IIFE body
iife_start = content.find("(()=>{")
if iife_start >= 0:
    print(content[iife_start:iife_start+200])
