import UnityPy, os

# Check the actual moc3 header format
# MOC3 format: magic(4) + version(4) + ...
# But some versions have different header layouts

live2d_dir = r'D:\Azur Lane Assets\files\AssetBundles\live2d'

for name in ['lingbo', 'z23', 'qiye_7', 'abeikelongbi_3']:
    path = os.path.join(live2d_dir, name)
    if not os.path.isfile(path):
        continue
    
    env = UnityPy.load(path)
    for obj in env.objects:
        if obj.type.name == 'MonoBehaviour':
            data = obj.read()
            if hasattr(data, 'm_Script'):
                script = data.m_Script
                if script:
                    try:
                        script_obj = script.read()
                        script_name = getattr(script_obj, 'm_Name', '')
                        if 'Moc' in script_name:
                            raw = obj.get_raw_data()
                            moc3_offset = raw.find(b'MOC3')
                            if moc3_offset >= 0:
                                moc3_data = raw[moc3_offset:]
                                print(f'\n=== {name} ===')
                                print(f'Offset: {moc3_offset}')
                                print(f'First 32 bytes hex: {moc3_data[:32].hex()}')
                                print(f'Magic: {moc3_data[:4]}')
                                # Version might be at offset 4 or later
                                ver_bytes = moc3_data[4:8]
                                print(f'Version bytes: {ver_bytes.hex()}')
                                print(f'Version as uint32 LE: {int.from_bytes(ver_bytes, "little")}')
                                break
                    except Exception as e:
                        print(f'{name}: error {e}')
