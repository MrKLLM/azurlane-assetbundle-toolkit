import UnityPy, os

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

for name in ["changbo", "chicheng", "haifeng"]:
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    print(f"\n=== BASE: {name} ===")

    game_objects = {}
    for obj in env.objects:
        if obj.type.name == "GameObject":
            data = obj.read()
            game_objects[obj.path_id] = data.m_Name

    rects = []
    for obj in env.objects:
        if obj.type.name == "RectTransform":
            data = obj.read()
            pos = getattr(data, "m_AnchoredPosition", None)
            size = getattr(data, "m_SizeDelta", None)
            rects.append((obj.path_id, pos, size))

    print(f"  GameObjects ({len(game_objects)}):")
    for pid in sorted(game_objects):
        print(f"    {pid}: {game_objects[pid]}")

    print(f"\n  RectTransforms ({len(rects)}):")
    for pid, pos, size in rects[:15]:
        print(f"    {pid}: pos={pos}, size={size}")

    # Check MonoBehaviours for painting-related data
    print(f"\n  MonoBehaviours:")
    for obj in env.objects:
        if obj.type.name == "MonoBehaviour":
            data = obj.read()
            script = getattr(data, "m_Script", None)
            print(f"    path_id={obj.path_id}, script={script}")
            # Try to read raw data
            if hasattr(data, "m_Script"):
                print(f"    m_Name={getattr(data, 'm_Name', 'N/A')}")
