import UnityPy, os

# Check if there's a direct Moc field on the CubismMoc object
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
                        print(f'Found CubismMoc at path_id={obj.path_id}')
                        print(f'All attrs: {[a for a in dir(data) if not a.startswith("_")]}')
                        
                        # Check if there's a Moc field
                        if hasattr(data, 'Moc'):
                            moc_field = data.Moc
                            print(f'Moc field type: {type(moc_field)}')
                            if isinstance(moc_field, bytes):
                                print(f'Moc field size: {len(moc_field)}')
                                print(f'Moc field first 20: {moc_field[:20].hex()}')
                            elif hasattr(moc_field, 'read'):
                                moc_data = moc_field.read()
                                print(f'Moc field (via read) size: {len(moc_data)}')
                                print(f'Moc field (via read) first 20: {moc_data[:20].hex()}')
                        else:
                            print('No Moc attribute found')
                        
                        break
                except Exception as e:
                    print(f'Error: {e}')
