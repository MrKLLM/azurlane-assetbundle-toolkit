import UnityPy, os
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
from PIL import Image

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

# Check pastePoint for aerbien_3 components
bundle_name = "aerbien_3"
path = os.path.join(paint_dir, bundle_name)
env = UnityPy.load(path)

print("=== %s ===" % bundle_name)

# Get all RectTransforms with pastePoint
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
    
    # Check if has _tex
    tex_name = go_name + "_tex"
    has_tex = os.path.exists(os.path.join(paint_dir, tex_name))
    
    if has_tex:
        print("  %s: pastePoint=(%.1f, %.1f) size=(%.0f, %.0f)" % (
            go_name, pos.x, pos.y, size.x, size.y))
