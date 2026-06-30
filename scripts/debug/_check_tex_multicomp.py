import UnityPy, os
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d

# Check what the _tex bundle actually contains - is it already multi-component?
paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

for name in ["changbo_tex", "chicheng_tex", "haifeng_tex"]:
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    print(f"\n=== {name} ===")
    
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            print(f"  Texture2D: {data.m_Name}, {data.m_Width}x{data.m_Height}")
        elif obj.type.name == "Mesh":
            data = obj.read()
            handler = MeshHandler(data)
            handler.process()
            n = len(handler.m_Vertices)
            print(f"  Mesh: {data.m_Name}, {n} vertices")
            # Show AABB
            aabb = data.m_LocalAABB
            print(f"    AABB: center={aabb.m_Center}, extent={aabb.m_Extent}")
            print(f"    Output size: {int(aabb.m_Center.x + aabb.m_Extent.x)+1} x {int(aabb.m_Center.y + aabb.m_Extent.y)+1}")
            
            # Count unique UV regions (quads)
            uvs = handler.m_UV0
            if uvs and len(uvs) >= 4:
                # Sample first few quads
                print(f"    First 3 quads UV samples:")
                for i in range(0, min(12, len(uvs)), 4):
                    if i+2 < len(uvs):
                        print(f"      UV[{i}]={uvs[i]}, UV[{i+2}]={uvs[i+2]}")

# Also check the base bundle's RectTransform for 'frameContain' - this is the main canvas
print("\n\n=== Canvas sizes from base bundles ===")
for name in ["changbo", "chicheng", "haifeng"]:
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    for obj in env.objects:
        if obj.type.name == "RectTransform":
            data = obj.read()
            size = getattr(data, "m_SizeDelta", None)
            if size and size.x > 1000 and size.y > 1000:
                print(f"  {name} canvas: {size.x}x{size.y}")
