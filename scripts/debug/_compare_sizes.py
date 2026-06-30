import sys, os
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from compose_paintings import get_component_positions, synthesize_tex_bundle

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

root_size, components = get_component_positions(os.path.join(paint_dir, "adaerbote_2"))
print(f"Root: {root_size}")

for comp in components:
    tex_name = comp["name"] + "_tex"
    tex_path = os.path.join(paint_dir, tex_name)
    if os.path.exists(tex_path):
        img = synthesize_tex_bundle(tex_path)
        if img:
            decl = comp["size"]
            print(f"  {comp['name']}: declared=({decl[0]:.0f}x{decl[1]:.0f}) actual={img.size}")
