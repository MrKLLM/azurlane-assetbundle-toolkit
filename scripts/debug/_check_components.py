import UnityPy, os
from PIL import Image
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
from UnityPy.helpers.MeshHelper import MeshHandler

# Check if the synthesized paintings have issues
# Compare with raw texture to see if components are missing
paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"
synth_dir = r"D:\Azur Lane Assets\Output\Paintings_Synthesized"

# For a few characters, compare the _tex synthesis result with the raw texture
for name in ["changbo", "chicheng", "haifeng"]:
    tex_path = os.path.join(paint_dir, name + "_tex")
    synth_path = os.path.join(synth_dir, name + ".png")
    
    if not os.path.exists(tex_path) or not os.path.exists(synth_path):
        continue
    
    # Get raw texture
    env = UnityPy.load(tex_path)
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            raw_img = get_image_from_texture2d(data, flip=False)
            print(f"{name}: raw texture={raw_img.size}")
    
    # Get synthesized
    synth_img = Image.open(synth_path)
    print(f"{name}: synthesized={synth_path} size={synth_img.size}")
    
    # Check the base bundle for component names
    base_path = os.path.join(paint_dir, name)
    if os.path.exists(base_path):
        env2 = UnityPy.load(base_path)
        components = []
        for obj in env2.objects:
            if obj.type.name == "GameObject":
                data = obj.read()
                components.append(data.m_Name)
        print(f"{name}: base components={components}")
    print()
