import UnityPy, os

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

for bundle_name in ["aerbien_3", "adaerbote_2"]:
    path = os.path.join(paint_dir, bundle_name)
    if not os.path.exists(path):
        continue
    
    env = UnityPy.load(path)
    print("\n=== %s ===" % bundle_name)
    
    # Get root size
    root_w, root_h = 0, 0
    for obj in env.objects:
        if obj.type.name != "RectTransform":
            continue
        data = obj.read()
        size = getattr(data, "m_SizeDelta", None)
        if size and size.x > root_w and size.y > root_h:
            root_w, root_h = int(size.x), int(size.y)
    
    print("Root canvas: %dx%d" % (root_w, root_h))
    
    # Get all painting-related components with positions
    for obj in env.objects:
        if obj.type.name != "RectTransform":
            continue
        data = obj.read()
        pos = getattr(data, "m_AnchoredPosition", None)
        size = getattr(data, "m_SizeDelta", None)
        if not pos or not size:
            continue
        
        go_ptr = getattr(data, "m_GameObject", None)
        go_name = None
        if go_ptr:
            try:
                go = go_ptr.read()
                go_name = go.m_Name
            except:
                pass
        
        if go_name is None:
            continue
        
        # Check if this component has a _tex counterpart
        tex_name = go_name + "_tex"
        has_tex = os.path.exists(os.path.join(paint_dir, tex_name))
        
        if has_tex:
            print("  %s: pos=(%.1f, %.1f) size=(%.0f, %.0f)" % (
                go_name, pos.x, pos.y, size.x, size.y))
