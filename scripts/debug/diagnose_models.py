#!/usr/bin/env python3
"""诊断所有 Live2D 模型的还原状态"""

import os
import json

OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Live2D"

stats = {
    "A": [],  # 画面+动作完整
    "B": [],  # 画面完整，motion 为空占位符
    "C": [],  # 画面有问题（纹理数量不匹配等）
    "D": [],  # 无法还原（缺少 moc3 等）
}

detail = []

for model_name in sorted(os.listdir(OUTPUT_DIR)):
    model_dir = os.path.join(OUTPUT_DIR, model_name)
    if not os.path.isdir(model_dir):
        continue

    issues = []
    has_moc3 = False
    has_physics = False
    texture_count = 0
    motion_count = 0
    real_motion_count = 0
    placeholder_motion_count = 0

    # Check moc3
    moc3_path = os.path.join(model_dir, f"{model_name}.moc3")
    if os.path.isfile(moc3_path):
        has_moc3 = True
        moc3_size = os.path.getsize(moc3_path)
        if moc3_size < 1000:
            issues.append(f"moc3 太小 ({moc3_size} bytes)")
    else:
        issues.append("缺少 moc3")

    # Check textures
    for f in os.listdir(model_dir):
        if f.startswith("texture_") and f.endswith(".png"):
            texture_count += 1

    # Check model3.json
    model3_path = os.path.join(model_dir, f"{model_name}.model3.json")
    if os.path.isfile(model3_path):
        try:
            with open(model3_path, "r", encoding="utf-8") as f:
                model3 = json.load(f)
            refs = model3.get("FileReferences", {})
            has_physics = "Physics" in refs
            if "Motions" in refs:
                motion_count = sum(len(v) for v in refs["Motions"].values())
        except:
            issues.append("model3.json 解析失败")
    else:
        issues.append("缺少 model3.json")

    # Check motion files
    motion_dir = os.path.join(model_dir, "motion")
    if os.path.isdir(motion_dir):
        for f in os.listdir(motion_dir):
            if f.endswith(".motion3.json"):
                motion_file = os.path.join(motion_dir, f)
                try:
                    with open(motion_file, "r", encoding="utf-8") as f:
                        motion = json.load(f)
                    curves = motion.get("Curves", [])
                    if curves and any(c.get("Segments") for c in curves):
                        real_motion_count += 1
                    else:
                        placeholder_motion_count += 1
                except:
                    placeholder_motion_count += 1

    # Classify
    if not has_moc3:
        category = "D"
    elif texture_count == 0:
        category = "C"
        issues.append("无纹理文件")
    elif real_motion_count > 0:
        category = "A"
    elif placeholder_motion_count > 0 or motion_count > 0:
        category = "B"
    else:
        category = "B"

    stats[category].append(model_name)
    detail.append({
        "name": model_name,
        "category": category,
        "moc3": has_moc3,
        "textures": texture_count,
        "physics": has_physics,
        "real_motions": real_motion_count,
        "placeholder_motions": placeholder_motion_count,
        "issues": issues,
    })

# Print summary
print("=" * 60)
print("Live2D 模型还原状态统计")
print("=" * 60)
print(f"A 类 (画面+动作完整): {len(stats['A'])} 个")
print(f"B 类 (画面完整, 动作为空占位符): {len(stats['B'])} 个")
print(f"C 类 (画面有问题): {len(stats['C'])} 个")
print(f"D 类 (无法还原): {len(stats['D'])} 个")
print(f"总计: {sum(len(v) for v in stats.values())} 个")

# Print details for C and D
if stats["C"]:
    print(f"\n--- C 类 (画面有问题) ---")
    for name in stats["C"]:
        d = next(x for x in detail if x["name"] == name)
        print(f"  {name}: textures={d['textures']}, issues={d['issues']}")

if stats["D"]:
    print(f"\n--- D 类 (无法还原) ---")
    for name in stats["D"]:
        d = next(x for x in detail if x["name"] == name)
        print(f"  {name}: issues={d['issues']}")

# Print some A and B examples
print(f"\n--- A 类示例 (前10个) ---")
for name in stats["A"][:10]:
    d = next(x for x in detail if x["name"] == name)
    print(f"  {name}: textures={d['textures']}, motions={d['real_motions']}")

print(f"\n--- B 类示例 (前10个) ---")
for name in stats["B"][:10]:
    d = next(x for x in detail if x["name"] == name)
    print(f"  {name}: textures={d['textures']}, placeholder_motions={d['placeholder_motions']}")

# Texture count distribution
print(f"\n--- 纹理数量分布 ---")
tex_dist = {}
for d in detail:
    tc = d["textures"]
    tex_dist[tc] = tex_dist.get(tc, 0) + 1
for tc in sorted(tex_dist.keys()):
    print(f"  {tc} 张纹理: {tex_dist[tc]} 个模型")

# Save full report
report_path = os.path.join(OUTPUT_DIR, "diagnosis_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump({"summary": {k: len(v) for k, v in stats.items()}, "detail": detail}, f, indent=2, ensure_ascii=False)
print(f"\n详细报告已保存: {report_path}")
