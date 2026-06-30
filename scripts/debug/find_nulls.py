#!/usr/bin/env python3
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

with open(r"D:\Azur Lane Assets\Output\Spine\spinepainting\aerbien_4\aerbien_4.json", "r", encoding="utf-8") as f:
    data = json.load(f)

def find_nulls(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if v is None:
                print(f"NULL at {path}.{k}")
            elif isinstance(v, (dict, list)):
                find_nulls(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if v is None:
                print(f"NULL at {path}[{i}]")
            elif isinstance(v, (dict, list)):
                find_nulls(v, f"{path}[{i}]")

find_nulls(data)

# Also check specific slots
print("\nSlots with issues:")
for i, s in enumerate(data.get("slots", [])):
    if not s.get("name"):
        print(f"  [{i}] name is null/empty: {s}")
    if not s.get("bone"):
        print(f"  [{i}] bone is null/empty: {s}")
