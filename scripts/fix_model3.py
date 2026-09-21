#!/usr/bin/env python3
"""修复所有 Live2D model3.json 文件为 Live2DViewerEX / Web 运行时兼容格式。

输出目录可用 L2D_OUT_DIR 覆盖（用于先在临时目录验证再换入正式目录）。
"""

import os
import json

OUTPUT_DIR = os.environ.get("L2D_OUT_DIR") or r"D:\Azur Lane Assets\Output\Live2D"

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

    # 修复 Motions: 添加 FadeInTime/FadeOutTime；并**剔除指向不存在文件的动作组**
    # （碧蓝有极少数 clip 在资产层就是空的，如 *_3 的 effect / wuqi_3 的 idle11；
    #   extract_motions.py 现在不再为此写空壳，留着引用只会在下拉里出现"点了没反应"的死项）
    refs['Motions'] = refs.get('Motions') or {}
    pruned = 0
    for group_name in list(refs['Motions'].keys()):
        keep = []
        for motion in refs['Motions'][group_name] or []:
            fp = os.path.join(model_dir, motion.get('File', ''))
            if motion.get('File') and os.path.isfile(fp):
                if 'FadeInTime' not in motion:
                    motion['FadeInTime'] = 0.5
                    motion['FadeOutTime'] = 0.5
                    changed = True
                keep.append(motion)
            else:
                pruned += 1
        if keep:
            if refs['Motions'][group_name] != keep:
                refs['Motions'][group_name] = keep
                changed = True
        else:
            del refs['Motions'][group_name]
            changed = True
    if pruned:
        print(f"  {model_name}: 剔除 {pruned} 条指向缺失文件的动作引用")

    # 补登记：磁盘上存在但 model3.json 没引用的动作文件
    # （权威提取能解出的 clip 比旧占位清单多——实测多 852 条，不补就永远选不到）
    mdir = os.path.join(model_dir, 'motion')
    referenced = {os.path.normpath(m.get('File', '')) for ms in refs['Motions'].values() for m in (ms or [])}
    added = 0
    if os.path.isdir(mdir):
        for fn in sorted(os.listdir(mdir)):
            if not fn.endswith('.motion3.json'):
                continue
            rel = os.path.join('motion', fn)
            if os.path.normpath(rel) in referenced:
                continue
            group = fn[:-len('.motion3.json')]
            refs['Motions'].setdefault(group, [])
            refs['Motions'][group].append({'File': rel.replace('\\', '/'),
                                           'FadeInTime': 0.5, 'FadeOutTime': 0.5})
            added += 1
    if added:
        print(f"  {model_name}: 补登记 {added} 条未引用的动作")
        changed = True

    if changed:
        model['FileReferences'] = refs
        with open(model3_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        fixed += 1

print(f"Fixed {fixed} model3.json files")
