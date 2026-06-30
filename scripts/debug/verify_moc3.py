import UnityPy, os

# The issue: raw_data includes bytes BEFORE MOC3 magic
# Let's check if we're including Unity serialization header in the moc3 file

path = r'D:\Azur Lane Assets\files\AssetBundles\live2d\lingbo'
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
                        print(f'raw_data total size: {len(raw)}')
                        print(f'MOC3 starts at offset: {moc3_offset}')
                        print(f'Bytes before MOC3: {raw[:moc3_offset].hex()}')
                        print(f'MOC3 data size: {len(raw) - moc3_offset}')
                        
                        # The correct extraction: from MOC3 to end
                        correct_moc3 = raw[moc3_offset:]
                        print(f'Correct MOC3 first 16 bytes: {correct_moc3[:16].hex()}')
                        
                        # Check the file we already extracted
                        extracted_path = r'D:\Azur Lane Assets\Output\Live2D\lingbo\lingbo.moc3'
                        with open(extracted_path, 'rb') as f:
                            extracted = f.read()
                        print(f'Extracted file size: {len(extracted)}')
                        print(f'Extracted first 16 bytes: {extracted[:16].hex()}')
                        print(f'Files match: {extracted == correct_moc3}')
                        
                        break
                except Exception as e:
                    print(f'Error: {e}')
