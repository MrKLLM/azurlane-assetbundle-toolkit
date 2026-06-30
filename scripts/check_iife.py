#!/usr/bin/env python3
"""Check how spine-player.min.js exports its API"""
with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find the IIFE pattern
import re

# Look for the pattern: var spine = (() => { ... return ... })();
# and see what's returned
iife_start = content.find("var spine=(()=>{")
if iife_start >= 0:
    print(f"IIFE starts at {iife_start}")
    # Find the return statement near the end
    # Look for the last return before })();
    last_return = content.rfind("return ")
    if last_return > 0:
        print(f"Last return at {last_return}")
        print(f"Context: {content[last_return:last_return+100]}")

# Look for how exports are structured
# Find __export or __toCommonJS patterns
export_pattern = content.find("__export")
if export_pattern >= 0:
    print(f"\n__export at {export_pattern}")
    print(f"Context: {content[export_pattern:export_pattern+200]}")

# Check for module.exports or exports assignment
module_exports = content.find("module.exports")
if module_exports >= 0:
    print(f"\nmodule.exports at {module_exports}")
    print(f"Context: {content[module_exports:module_exports+200]}")

# Look for the actual skeleton class definitions
skeleton_idx = content.find("class di ")  # minified class name
if skeleton_idx < 0:
    skeleton_idx = content.find("class Skeleton ")
if skeleton_idx >= 0:
    print(f"\nSkeleton class at {skeleton_idx}")
    print(f"Context: {content[skeleton_idx:skeleton_idx+200]}")

# Try to find what's assigned to spine
# The pattern should be: var spine = (() => { ... assignments to spine ... return spine; })();
# or: var spine = (() => { ... module stuff ... return module; })();

# Check if spine is actually the module object
spine_assign = content.find("spine.SkeletonBinary")
if spine_assign >= 0:
    print(f"\nspine.SkeletonBinary at {spine_assign}")
    print(f"Context: {content[spine_assign:spine_assign+100]}")
