#!/usr/bin/env python3
"""Check how spine 4.x BinaryInput reads data"""
with open(r"D:\Azur Lane Assets\tools\spine-viewer\spine-runtime\spine-player.min.js", "r", encoding="utf-8") as f:
    content = f.read()

# Find BinaryInput class (wn in minified)
# It should have readInt32, readString, readFloat methods
idx = content.find("class wn")
if idx < 0:
    idx = content.find("wn=class")
if idx < 0:
    # Search for BinaryInput pattern
    idx = content.find("readInt32")
    if idx >= 0:
        # Go back to find class definition
        start = content.rfind("class ", max(0, idx-2000), idx)
        if start >= 0:
            idx = start

if idx >= 0:
    # Show the class definition
    snippet = content[idx:idx+2000]
    print(f"Found at offset {idx}")
    print(snippet[:2000])
else:
    print("BinaryInput class not found")

# Also search for readInt32 implementation
print("\n\n=== readInt32 ===")
idx = content.find("readInt32")
if idx >= 0:
    print(content[max(0,idx-100):idx+200])
