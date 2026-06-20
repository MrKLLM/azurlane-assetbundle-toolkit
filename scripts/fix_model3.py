#!/usr/bin/env python3
"""修复所有 Live2D model3.json 文件为 Live2DViewerEX 兼容格式"""

import os
import json

OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Live2D"

fixed = 0
for model_name in sorted(os.listdir(OUTPUT_DIR)):
    model_dir = os.path.join(OUTPUT_DIR, model_name)
    if not os.path.isdir(model_dir):
        continue
    
    model3_path = os.path.join(model_dir, f"{model_name}.model3.json")
    if not os.path.isfile(model3_path):
        continue
    
    try:
        with open(model3_path, 'r', encoding='utf-8') as f:
            model = json.load(f)
    except:
        continue
    
    changed = False
    refs = model.get('FileReferences', {})

    # 修复 Pose: 对象 → 删除（我们没有 .pose3.json 文件）
    if 'Pose' in refs and isinstance(refs['Pose'], dict):
        del refs['Pose']
        changed = True

    # 修复 DisplayInfo: 对象 → 删除（我们没有 .cdi3.json 文件）
    if 'DisplayInfo' in refs and isinstance(refs['DisplayInfo'], dict):
        del refs['DisplayInfo']
        changed = True

    # 修复 Groups: "Id"+"GroupIds" → "Ids"
    if 'Groups' in model:
        for group in model['Groups']:
            if 'GroupIds' in group:
                group['Ids'] = group.pop('GroupIds')
                changed = True
            # 移除多余的 "Id" 字段
            if 'Id' in group and 'Ids' in group:
                del group['Id']
                changed = True

    # 修复 HitAreas: 从 FileReferences 移到顶层
    if 'HitAreas' in refs:
        hit_areas = refs.pop('HitAreas')
        if hit_areas and isinstance(hit_areas[0], dict):
            pass  # 已经是正确格式
        elif not hit_areas:
            hit_areas = [{"Id": "HitArea", "Name": "Head"}, {"Id": "HitArea2", "Name": "Body"}]
        model['HitAreas'] = hit_areas
        changed = True
    elif 'HitAreas' not in model:
        model['HitAreas'] = [{"Id": "HitArea", "Name": "Head"}, {"Id": "HitArea2", "Name": "Body"}]
        changed = True

    # 修复 Expressions: 删除空数组（我们没有 .exp3.json 文件）
    if 'Expressions' in refs:
        del refs['Expressions']
        changed = True

    # 修复 Physics: 确保引用存在
    physics_path = os.path.join(model_dir, f"{model_name}.physics3.json")
    if os.path.isfile(physics_path) and 'Physics' not in refs:
        refs['Physics'] = f"{model_name}.physics3.json"
        changed = True

    # 修复 Motions: 添加 FadeInTime/FadeOutTime
    if 'Motions' in refs:
        for group_name, motions in refs['Motions'].items():
            for motion in motions:
                if 'FadeInTime' not in motion:
                    motion['FadeInTime'] = 0.5
                    motion['FadeOutTime'] = 0.5
                    changed = True

    if changed:
        model['FileReferences'] = refs
        with open(model3_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        fixed += 1

print(f"Fixed {fixed} model3.json files")
