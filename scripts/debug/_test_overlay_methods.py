import sys, os
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from synthesize_paintings import rebuild_painting_from_bundle
from PIL import Image

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"
out_dir = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"

# Test overlay for aerbien_3
base = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_tex"))
rw = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_rw_tex"))
n = rebuild_painting_from_bundle(os.path.join(paint_dir, "aerbien_3_n_tex"))

print("aerbien_3 base: %s" % str(base.size) if base else "None")
print("aerbien_3 rw: %s" % str(rw.size) if rw else "None")
print("aerbien_3 n: %s" % str(n.size) if n else "None")

if base and rw and n:
    # Method 1: Center all layers on base
    canvas1 = base.copy()
    # Paste rw centered
    x = (base.width - rw.width) // 2
    y = (base.height - rw.height) // 2
    canvas1.paste(rw, (x, y), rw)
    # Paste n centered
    x = (base.width - n.width) // 2
    y = (base.height - n.height) // 2
    canvas1.paste(n, (x, y), n)
    canvas1.save(os.path.join(out_dir, "_test_overlay_center.png"))
    print("Saved: _test_overlay_center.png %s" % str(canvas1.size))
    
    # Method 2: Use RectTransform positions
    # Root: 2766x2144
    # aerbien_3 is root, aerbien_3_rw pos=(341, 48)
    # Scale factor: base_img_size / root_size
    root_w, root_h = 2766, 2144
    scale_x = base.width / root_w
    scale_y = base.height / root_h
    
    canvas2 = Image.new("RGBA", base.size, (0, 0, 0, 0))
    # Paste base at center of canvas
    canvas2.paste(base, (0, 0))
    # Paste rw at scaled position
    rw_x = int(341 * scale_x)
    rw_y = int(48 * scale_y)
    canvas2.paste(rw, (rw_x, rw_y), rw)
    # Paste n at center (no position info for n)
    canvas2.save(os.path.join(out_dir, "_test_overlay_rect.png"))
    print("Saved: _test_overlay_rect.png %s" % str(canvas2.size))
    
    # Method 3: Just overlay at (0,0) - simplest
    canvas3 = base.copy()
    canvas3.paste(rw, (0, 0), rw)
    canvas3.paste(n, (0, 0), n)
    canvas3.save(os.path.join(out_dir, "_test_overlay_simple.png"))
    print("Saved: _test_overlay_simple.png %s" % str(canvas3.size))
