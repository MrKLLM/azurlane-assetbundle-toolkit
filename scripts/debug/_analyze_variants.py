import UnityPy, os
from UnityPy.helpers.MeshHelper import MeshHandler
from UnityPy.export.Texture2DConverter import get_image_from_texture2d
from PIL import Image
import numpy as np

paint_dir = r"D:\Azur Lane Assets\files\AssetBundles\painting"

# Analyze all adaerbote _tex bundles
print("=== adaerbote variants ===")
for suffix in ["", "_rw", "_jz", "_2", "_2_rw", "_2_n", "_3", "_3_n"]:
    name = f"adaerbote{suffix}_tex"
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    tex = mesh = None
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            img = get_image_from_texture2d(data, flip=False)
            tex = (data.m_Name, data.m_Width, data.m_Height, img)
        elif obj.type.name == "Mesh":
            data = obj.read()
            if data.m_VertexData and data.m_VertexData.m_VertexCount > 10:
                handler = MeshHandler(data)
                handler.process()
                aabb = data.m_LocalAABB
                mesh = (len(handler.m_Vertices), int(aabb.m_Center.x+aabb.m_Extent.x)+1, int(aabb.m_Center.y+aabb.m_Extent.y)+1)
    
    tex_info = f"tex={tex[0]} {tex[1]}x{tex[2]}" if tex else "no tex"
    mesh_info = f"mesh {mesh[0]}v -> {mesh[1]}x{mesh[2]}" if mesh else "no mesh"
    print(f"  {name}: {tex_info} | {mesh_info}")
    
    # Check texture properties
    if tex:
        img = tex[3]
        arr = np.array(img)
        # Check if it's mostly one color (normal map = mostly blue/purple)
        if arr.shape[2] >= 3:
            r_mean, g_mean, b_mean = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()
            a_mean = arr[:,:,3].mean() if arr.shape[2] == 4 else 255
            non_transparent = np.count_nonzero(arr[:,:,3]) / (arr.shape[0] * arr.shape[1]) * 100 if arr.shape[2] == 4 else 100
            print(f"    RGB=({r_mean:.0f},{g_mean:.0f},{b_mean:.0f}) A={a_mean:.0f} non_transparent={non_transparent:.1f}%")

# Also check aerbien
print("\n=== aerbien_3 variants ===")
for suffix in ["_3", "_3_rw", "_3_n", "_3_shophx"]:
    name = f"aerbien{suffix}_tex"
    path = os.path.join(paint_dir, name)
    if not os.path.exists(path):
        continue
    env = UnityPy.load(path)
    tex = mesh = None
    for obj in env.objects:
        if obj.type.name == "Texture2D":
            data = obj.read()
            img = get_image_from_texture2d(data, flip=False)
            tex = (data.m_Name, data.m_Width, data.m_Height, img)
        elif obj.type.name == "Mesh":
            data = obj.read()
            if data.m_VertexData and data.m_VertexData.m_VertexCount > 10:
                handler = MeshHandler(data)
                handler.process()
                aabb = data.m_LocalAABB
                mesh = (len(handler.m_Vertices), int(aabb.m_Center.x+aabb.m_Extent.x)+1, int(aabb.m_Center.y+aabb.m_Extent.y)+1)
    
    tex_info = f"tex={tex[0]} {tex[1]}x{tex[2]}" if tex else "no tex"
    mesh_info = f"mesh {mesh[0]}v -> {mesh[1]}x{mesh[2]}" if mesh else "no mesh"
    print(f"  {name}: {tex_info} | {mesh_info}")
    
    if tex:
        img = tex[3]
        arr = np.array(img)
        if arr.shape[2] >= 3:
            r_mean, g_mean, b_mean = arr[:,:,0].mean(), arr[:,:,1].mean(), arr[:,:,2].mean()
            a_mean = arr[:,:,3].mean() if arr.shape[2] == 4 else 255
            non_transparent = np.count_nonzero(arr[:,:,3]) / (arr.shape[0] * arr.shape[1]) * 100 if arr.shape[2] == 4 else 100
            print(f"    RGB=({r_mean:.0f},{g_mean:.0f},{b_mean:.0f}) A={a_mean:.0f} non_transparent={non_transparent:.1f}%")
