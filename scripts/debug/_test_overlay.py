import sys, UnityPy, os
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
from PIL import Image
import numpy as np

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"
out_dir = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"

# For adaerbote, compare the base and _rw outputs
# Check if _rw has transparent areas that would reveal the base underneath

# First, synthesize both
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from synthesize_paintings import rebuild_painting_from_bundle

for suffix in ["", "_rw", "_jz"]:
    name = f"adaerbote{suffix}"
    tex_name = f"{name}_tex"
    path = os.path.join(paint_dir, tex_name)
    if not os.path.exists(path):
        continue
    
    img = rebuild_painting_from_bundle(path)
    if img is None:
        print(f"{tex_name}: synthesis failed")
        continue
    
    arr = np.array(img)
    non_transparent = np.count_nonzero(arr[:,:,3]) / (arr.shape[0] * arr.shape[1]) * 100
    print(f"{name}: {img.size} non_transparent={non_transparent:.1f}%")
    
    # Check alpha distribution
    alpha = arr[:,:,3]
    print(f"  Alpha: min={alpha.min()}, max={alpha.max()}, mean={alpha.mean():.0f}")
    print(f"  Fully transparent: {(alpha == 0).sum() / alpha.size * 100:.1f}%")
    print(f"  Fully opaque: {(alpha == 255).sum() / alpha.size * 100:.1f}%")
    
    # Save for visual inspection
    out_path = os.path.join(out_dir, f"_test_{name}.png")
    img.save(out_path, "PNG")
    print(f"  Saved: {out_path}")

# Now test overlay: base + _rw
print("\n=== Overlay test ===")
base_img = rebuild_painting_from_bundle(os.path.join(paint_dir, "adaerbote_tex"))
rw_img = rebuild_painting_from_bundle(os.path.join(paint_dir, "adaerbote_rw_tex"))

if base_img and rw_img:
    # Create canvas large enough for both
    max_w = max(base_img.width, rw_img.width)
    max_h = max(base_img.height, rw_img.height)
    
    # Paste base at bottom-left, _rw on top
    canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    canvas.paste(base_img, (0, max_h - base_img.height))
    canvas.paste(rw_img, (0, max_h - rw_img.height), rw_img)  # Use alpha as mask
    
    out_path = os.path.join(out_dir, "_test_adaerbote_overlay.png")
    canvas.save(out_path, "PNG")
    print(f"Overlay result: {canvas.size}, saved to {out_path}")
    
    # Also try: base on top of _rw
    canvas2 = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    canvas2.paste(rw_img, (0, max_h - rw_img.height))
    canvas2.paste(base_img, (0, max_h - base_img.height), base_img)
    
    out_path2 = os.path.join(out_dir, "_test_adaerbote_overlay2.png")
    canvas2.save(out_path2, "PNG")
    print(f"Overlay result 2: {canvas2.size}, saved to {out_path2}")
