import sys, os
sys.path.insert(0, r"D:\Azur Lane Assets\scripts")
from compose_paintings import get_component_positions

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

root_size, components = get_component_positions(os.path.join(paint_dir, "adaerbote_2"))
print("Root:", root_size)
print("Components:", len(components))

for comp in components:
    tex_name = comp["name"] + "_tex"
    has_tex = os.path.exists(os.path.join(paint_dir, tex_name))
    decl = comp["size"]
    name = comp["name"]
    print("  %s size=(%.0fx%.0f) has_tex=%s" % (name, decl[0], decl[1], has_tex))
