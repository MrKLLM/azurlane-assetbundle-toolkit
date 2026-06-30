import UnityPy, os

face_dir = r"D:\Azur Lane Assets\files\AssetBundles\paintingface"
for name in ["chicheng", "changbo", "abeikelongbi_2", "haifeng", "changbo_3"]:
    path = os.path.join(face_dir, name)
    if os.path.exists(path):
        env = UnityPy.load(path)
        texs = []
        for obj in env.objects:
            if obj.type.name == "Texture2D":
                data = obj.read()
                texs.append((data.m_Name, data.m_Width, data.m_Height))
        texs.sort(key=lambda x: x[0])
        print(f"{name}: {len(texs)} faces")
        for t in texs:
            print(f"  name={t[0]}, size={t[1]}x{t[2]}")
    else:
        print(f"{name}: NOT FOUND")
