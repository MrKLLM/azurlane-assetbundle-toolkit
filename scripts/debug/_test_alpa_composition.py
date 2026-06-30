import sys, os
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from synthesize_paintings import rebuild_painting_from_bundle
from PIL import Image
import UnityPy

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"
out_dir = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"

def get_alpa_composition(bundle_name):
    """用 ALPA 逻辑合成立绘"""
    base_path = os.path.join(paint_dir, bundle_name)
    
    # Get pastePoints from base bundle
    env = UnityPy.load(base_path)
    
    root_w, root_h = 0, 0
    components = []
    
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
        
        # Track root size
        if size.x > root_w and size.y > root_h:
            root_w, root_h = int(size.x), int(size.y)
        
        # Check if has _tex
        tex_name = go_name + "_tex"
        tex_path = os.path.join(paint_dir, tex_name)
        if os.path.exists(tex_path):
            components.append({
                "name": go_name,
                "pastePoint": (pos.x, pos.y),
                "size": (size.x, size.y),
                "tex_path": tex_path,
            })
    
    if not components:
        return None
    
    # Create canvas at root size
    canvas = Image.new("RGBA", (root_w, root_h), (0, 0, 0, 0))
    
    # Synthesize and paste each component
    for comp in components:
        img = rebuild_painting_from_bundle(comp["tex_path"])
        if img is None:
            continue
        
        # ALPA: paste at pastePoint (Y is already in image coordinates after flip)
        x = int(comp["pastePoint"][0])
        y = int(comp["pastePoint"][1])
        
        # Flip vertically (ALPA does this)
        img_flipped = img.transpose(Image.FLIP_TOP_BOTTOM)
        
        # Paste
        canvas.paste(img_flipped, (x, y), img_flipped)
    
    # Crop to content
    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    
    return canvas

# Test with aerbien_3
result = get_alpa_composition("aerbien_3")
if result:
    out_path = os.path.join(out_dir, "_test_alpa_aerbien_3.png")
    result.save(out_path, "PNG")
    print("Saved: _test_alpa_aerbien_3.png %s" % str(result.size))

# Test with adaerbote_2
result2 = get_alpa_composition("adaerbote_2")
if result2:
    out_path2 = os.path.join(out_dir, "_test_alpa_adaerbote_2.png")
    result2.save(out_path2, "PNG")
    print("Saved: _test_alpa_adaerbote_2.png %s" % str(result2.size))
