import sys, os
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from synthesize_paintings import rebuild_painting_from_bundle
from PIL import Image

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"
out_dir = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"

# Test for aerbien_3
base = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_tex"))
rw = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_rw_tex"))
n = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_n_tex"))

if base and rw and n:
    root_w, root_h = 2766, 2144
    
    # Method 4: Canvas at root size, base centered, rw at RectTransform pos
    canvas = Image.new("RGBA", (root_w, root_h), (0, 0, 0, 0))
    
    # Center base on root canvas
    base_x = (root_w - base.width) // 2
    base_y = (root_h - base.height) // 2
    canvas.paste(base, (base_x, base_y), base)
    
    # Place rw at RectTransform pos (341, 48)
    canvas.paste(rw, (341, 48), rw)
    
    # Place n at center (no position info)
    n_x = (root_w - n.width) // 2
    n_y = (root_h - n.height) // 2
    canvas.paste(n, (n_x, n_y), n)
    
    # Crop to content
    bbox = canvas.getbbox()
    if bbox:
        canvas = canvas.crop(bbox)
    
    canvas.save(os.path.join(out_dir, "_test_overlay_v2.png"))
    print("Saved: _test_overlay_v2.png %s" % str(canvas.size))
    
    # Method 5: Same but with different base position (top-left aligned)
    canvas2 = Image.new("RGBA", (root_w, root_h), (0, 0, 0, 0))
    canvas2.paste(base, (0, 0), base)
    canvas2.paste(rw, (341, 48), rw)
    n_x = (root_w - n.width) // 2
    n_y = (root_h - n.height) // 2
    canvas2.paste(n, (n_x, n_y), n)
    bbox2 = canvas2.getbbox()
    if bbox2:
        canvas2 = canvas2.crop(bbox2)
    canvas2.save(os.path.join(out_dir, "_test_overlay_v3.png"))
    print("Saved: _test_overlay_v3.png %s" % str(canvas2.size))
    
    # Method 6: Scale everything to root size
    canvas3 = Image.new("RGBA", (root_w, root_h), (0, 0, 0, 0))
    base_scaled = base.resize((root_w, root_h), Image.LANCZOS)
    canvas3.paste(base_scaled, (0, 0), base_scaled)
    canvas3.paste(rw, (341, 48), rw)
    n_x = (root_w - n.width) // 2
    n_y = (root_h - n.height) // 2
    canvas3.paste(n, (n_x, n_y), n)
    bbox3 = canvas3.getbbox()
    if bbox3:
        canvas3 = canvas3.crop(bbox3)
    canvas3.save(os.path.join(out_dir, "_test_overlay_v4.png"))
    print("Saved: _test_overlay_v4.png %s" % str(canvas3.size))
