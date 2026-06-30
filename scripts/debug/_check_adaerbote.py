import UnityPy, os
from UnityPy.helpers.MeshHelper import MeshHandler

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

# Check ALL _tex bundles for adaerbote to understand which have real paintings vs just faces
for name in ["adaerbote_tex", "adaerbote_2_tex", "adaerbote_3_tex", "adaerbote_rw_tex", "adaerbote_jz_tex", "adaerbote_n_tex", "adaerbote_2_rw_tex", "adaerbote_2_n_tex", "adaerbote_3_n_tex"]:
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        print(f"{name}: NOT FOUND")
        continue
    env = UnityPy.load(path)
    tex = None
    mesh = None
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            tex = (data.m_Name, data.m_Width, data.m_Height)
        elif obj.type.name == "Mesh":
            data = obj.read()
            if data.m_VertexData and data.m_VertexData.m_VertexCount > 10:
                handler = MeshHandler(data)
                handler.process()
                aabb = data.m_LocalAABB
                mesh = (data.m_Name, len(handler.m_Vertices), int(aabb.m_Center.x+aabb.m_Extent.x)+1, int(aabb.m_Center.y+aabb.m_Extent.y)+1)
    
    tex_info = f"tex={tex[0]} {tex[1]}x{tex[2]}" if tex else "no tex"
    mesh_info = f"mesh={mesh[0]} {mesh[1]} verts -> {mesh[2]}x{mesh[3]}" if mesh else "no mesh"
    print(f"{name}: {tex_info} | {mesh_info}")
