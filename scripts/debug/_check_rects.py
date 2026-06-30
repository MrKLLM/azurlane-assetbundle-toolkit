import UnityPy, os

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

# Check RectTransform positions for adaerbote_2 base bundle
# This tells us where each component should be placed
for bundle_name in ["adaerbote_2", "aerbien_3"]:
    path = os.path.join(paint_dir, bundle_name)
    if not os.path.exists(path):
        continue
    
    env = UnityPy.load(path)
    print(f"\n=== {bundle_name} base bundle ===")
    
    # Build path_id -> name mapping
    names = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            data = obj.read()
            names[obj.path_id] = data.m_Name
    
    # Get RectTransforms with their parent info
    rects = {}
    for obj in env.objects:
        if obj.type.name == "RectTransform":
            data = obj.read()
            pos = getattr(data, "m_AnchoredPosition", None)
            size = getattr(data, "m_SizeDelta", None)
            # Get the GameObject this RectTransform belongs to
            go_id = getattr(data, "m_GameObject", None)
            go_name = "unknown"
            if go_id:
                # go_id is a PPtr, need to resolve
                try:
                    go = go_id.read()
                    go_name = go.m_Name
                except:
                    pass
            rects[obj.path_id] = {
                "name": go_name,
                "pos": pos,
                "size": size,
                "path_id": obj.path_id
            }
    
    # Print all RectTransforms sorted by name
    for pid in sorted(rects, key=lambda x: rects[x]["name"]):
        r = rects[pid]
        if r["pos"] and r["size"]:
            print(f"  {r['name']:20s} pos=({r['pos'].x:8.1f}, {r['pos'].y:8.1f}) size=({r['size'].x:8.1f}, {r['size'].y:8.1f})")
