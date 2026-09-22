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

    # 修复 HitAreas: 若在 FileReferences 里，先移到顶层（生成真实判定区的逻辑在下方 Motions 定稿后）
    if 'HitAreas' in refs:
        model['HitAreas'] = refs.pop('HitAreas')
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

    # ===== 真实 HitAreas 生成（§6.11 根因修复）=====
    # 规则（docs/TROUBLESHOOTING.md §18）：moc3 里存在的 `Touch<X>` drawable ↔ 该模型真实存在的动作组。
    #   - Id 必须是可被前端 getDrawableIndex 解析的 **drawable**（碧蓝统一命名 TouchHead/TouchBody/TouchSpecial）；
    #   - Name 必须落在该模型 Motions 里真实存在的动作组名（老模型常为 Head/Body/Special，新皮肤为 touch_*）。
    # 保守起见：**只替换占位 HitAreas**（Id 全部 ∈ {HitArea, HitArea2} 或为空），
    #   已带正确真实 HitAreas 的模型一律不动 → 256 个既有正确产物逐字段零变化。
    PLACEHOLDER_IDS = {"HitArea", "HitArea2"}
    TOUCH_AREAS = {
        "Head":    ["Head", "tapHead", "tap_head", "touch_head", "head"],
        "Body":    ["Body", "tapBody", "tap_body", "touch_body", "body"],
        "Special": ["Special", "tapSpecial", "tap_special", "touch_special", "special"],
    }
    cur_hits = model.get("HitAreas") or []
    cur_ids = {a.get("Id") for a in cur_hits}
    is_placeholder = (not cur_hits) or (cur_ids and cur_ids <= PLACEHOLDER_IDS)
    if is_placeholder:
        moc3_path = os.path.join(model_dir, f"{model_name}.moc3")
        try:
            with open(moc3_path, "rb") as f:
                moc3_bytes = f.read()
        except OSError:
            moc3_bytes = b""
        groups = list(refs.get("Motions", {}).keys())
        gset = set(groups)
        glower = {g.lower(): g for g in groups}

        def pick_group(cands):
            for c in cands:
                if c in gset:
                    return c
                if c.lower() in glower:
                    return glower[c.lower()]
            return None

        real_hits = []
        for area, cands in TOUCH_AREAS.items():
            if ("Touch" + area).encode() not in moc3_bytes:
                continue                      # moc3 无此触摸 drawable
            nm = pick_group(cands)
            if nm:
                real_hits.append({"Id": "Touch" + area, "Name": nm})
        if real_hits and real_hits != cur_hits:
            model["HitAreas"] = real_hits
            changed = True
            print(f"  {model_name}: 生成真实 HitAreas {[h['Name'] for h in real_hits]}（原为占位）")

    if changed:
        model['FileReferences'] = refs
        with open(model3_path, 'w', encoding='utf-8') as f:
            json.dump(model, f, indent=2, ensure_ascii=False)
        fixed += 1

print(f"Fixed {fixed} model3.json files")
