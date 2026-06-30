#!/usr/bin/env python3
"""
Convert spine 3.8 binary .skel to JSON format.
Uses the correct varint+string format from spine 3.8.
"""
import struct
import json
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

class BinaryReader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.strings = []
    
    def read_byte(self):
        b = self.data[self.pos]
        self.pos += 1
        return b
    
    def read_bool(self):
        return self.read_byte() != 0
    
    def read_int(self, optimize_positive=True):
        b = self.read_byte()
        value = b & 0x7F
        shift = 7
        while b & 0x80:
            b = self.read_byte()
            value |= (b & 0x7F) << shift
            shift += 7
        if not optimize_positive:
            value = (value >> 1) ^ -(value & 1)
        return value
    
    def read_float(self):
        val = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return val
    
    def read_string(self):
        length = self.read_int(True)
        if length <= 1:
            return "" if length == 0 else ""
        length -= 1
        s = self.data[self.pos:self.pos + length].decode("utf-8", errors="replace")
        self.pos += length
        return s
    
    def read_ref_string(self):
        index = self.read_int(True)
        if index == 0:
            return ""
        return self.strings[index - 1]
    
    def read_color(self):
        rgba = struct.unpack_from("<i", self.data, self.pos)[0]
        self.pos += 4
        r = ((rgba >> 24) & 0xFF) / 255.0
        g = ((rgba >> 16) & 0xFF) / 255.0
        b = ((rgba >> 8) & 0xFF) / 255.0
        a = (rgba & 0xFF) / 255.0
        return [round(r, 4), round(g, 4), round(b, 4), round(a, 4)]
    
    def remaining(self):
        return len(self.data) - self.pos


def convert_skel_to_json(data):
    r = BinaryReader(data)
    result = {}
    
    # Skip 0x1C signature
    if data[0] == 0x1C:
        r.pos = 1
    
    # Hash
    hash_str = r.read_string()
    result["hash"] = hash_str
    
    # Version
    version = r.read_string()
    result["skeleton"] = {"hash": hash_str, "version": version, "spine": version}
    
    # x, y, width, height
    x = r.read_float()
    y = r.read_float()
    w = r.read_float()
    h = r.read_float()
    result["skeleton"]["x"] = round(x, 2)
    result["skeleton"]["y"] = round(y, 2)
    result["skeleton"]["width"] = round(w, 2)
    result["skeleton"]["height"] = round(h, 2)
    
    # Nonessential
    nonessential = r.read_bool()
    result["skeleton"]["nonessential"] = nonessential
    
    if nonessential:
        fps = r.read_float()
        images = r.read_string()
        audio = r.read_string()
        result["skeleton"]["fps"] = fps
        result["skeleton"]["images"] = images
        result["skeleton"]["audio"] = audio
    
    # Shared strings
    string_count = r.read_int(True)
    for i in range(string_count):
        s = r.read_string()
        r.strings.append(s)
    
    # Bones
    bone_count = r.read_int(True)
    bones = []
    for i in range(bone_count):
        bone = {"name": r.read_string()}
        parent_idx = r.read_int(True)
        if parent_idx > 0:
            bone["parent"] = bones[parent_idx - 1]["name"]
        bone["rotation"] = round(r.read_float(), 2)
        bone["x"] = round(r.read_float(), 2)
        bone["y"] = round(r.read_float(), 2)
        bone["scaleX"] = round(r.read_float(), 4)
        bone["scaleY"] = round(r.read_float(), 4)
        bone["shearX"] = round(r.read_float(), 4)
        bone["shearY"] = round(r.read_float(), 4)
        bone["length"] = round(r.read_float(), 2)
        transform = r.read_int(True)
        transform_names = ["normal", "onlyTranslation", "noRotationOrReflection",
                          "noScale", "noScaleOrReflection"]
        bone["transform"] = transform_names[transform] if transform < len(transform_names) else "normal"
        if r.read_bool():
            bone["skinRequired"] = True
        if nonessential:
            bone["color"] = r.read_color()
        bones.append(bone)
    result["bones"] = bones
    
    # Slots
    slot_count = r.read_int(True)
    slots = []
    for i in range(slot_count):
        slot = {"name": r.read_string()}
        slot["bone"] = bones[r.read_int(True) - 1]["name"]
        slot["color"] = r.read_color()
        dark = r.read_color()
        if dark != [1, 1, 1, 1]:
            slot["dark"] = dark
        att = r.read_ref_string()
        if att:
            slot["attachment"] = att
        slots.append(slot)
    result["slots"] = slots
    
    # IK constraints
    ik_count = r.read_int(True)
    if ik_count > 0:
        ik_constraints = []
        for i in range(ik_count):
            ik = {"name": r.read_string()}
            ik["order"] = r.read_int(True)
            if r.read_bool():
                ik["skinRequired"] = True
            bone_count_ik = r.read_int(True)
            ik["bones"] = [bones[r.read_int(True) - 1]["name"] for _ in range(bone_count_ik)]
            ik["target"] = bones[r.read_int(True) - 1]["name"]
            ik["mix"] = round(r.read_float(), 4)
            ik["softness"] = round(r.read_float(), 4)
            ik["bendPositive"] = r.read_byte() == 1
            ik["compress"] = r.read_bool()
            ik["stretch"] = r.read_bool()
            ik["uniform"] = r.read_bool()
            ik_constraints.append(ik)
        result["ik"] = ik_constraints
    
    # Transform constraints
    tc_count = r.read_int(True)
    if tc_count > 0:
        tc_list = []
        for i in range(tc_count):
            tc = {"name": r.read_string(), "order": r.read_int(True)}
            if r.read_bool():
                tc["skinRequired"] = True
            tc["bone"] = bones[r.read_int(True) - 1]["name"]
            tc["target"] = bones[r.read_int(True) - 1]["name"]
            tc["local"] = r.read_bool()
            tc["relative"] = r.read_bool()
            tc["offsetRotation"] = round(r.read_float(), 2)
            tc["offsetX"] = round(r.read_float(), 2)
            tc["offsetY"] = round(r.read_float(), 2)
            tc["offsetScaleX"] = round(r.read_float(), 4)
            tc["offsetScaleY"] = round(r.read_float(), 4)
            tc["offsetShearY"] = round(r.read_float(), 4)
            tc["rotateMix"] = round(r.read_float(), 4)
            tc["translateMix"] = round(r.read_float(), 4)
            tc["scaleMix"] = round(r.read_float(), 4)
            tc["shearMix"] = round(r.read_float(), 4)
            tc_list.append(tc)
        result["transform"] = tc_list
    
    # Path constraints
    pc_count = r.read_int(True)
    if pc_count > 0:
        pc_list = []
        for i in range(pc_count):
            pc = {"name": r.read_string(), "order": r.read_int(True)}
            if r.read_bool():
                pc["skinRequired"] = True
            pc_bone_count = r.read_int(True)
            pc["bones"] = [bones[r.read_int(True) - 1]["name"] for _ in range(pc_bone_count)]
            pc["target"] = slots[r.read_int(True) - 1]["name"]
            pc["positionMode"] = ["fixed", "percent"][r.read_int(True)]
            pc["spacingMode"] = ["length", "fixed", "percent"][r.read_int(True)]
            pc["rotateMode"] = ["tangent", "chain", "chainScale"][r.read_int(True)]
            pc["offsetRotation"] = round(r.read_float(), 2)
            pc["position"] = round(r.read_float(), 2)
            pc["spacing"] = round(r.read_float(), 2)
            pc["rotateMix"] = round(r.read_float(), 4)
            pc["translateMix"] = round(r.read_float(), 4)
            pc_list.append(pc)
        result["path"] = pc_list
    
    # Default skin (unnamed)
    default_skin = {"attachments": {}}
    skin_slot_count = r.read_int(True)
    for i in range(skin_slot_count):
        slot_idx = r.read_int(True) - 1
        slot_name = slots[slot_idx]["name"]
        att_count = r.read_int(True)
        slot_atts = {}
        for j in range(att_count):
            placeholder = r.read_ref_string()
            att_name = r.read_ref_string()
            if not att_name:
                att_name = placeholder
            att_type = r.read_int(True)
            att = {}
            
            if att_type == 0:  # REGION
                path = r.read_ref_string()
                if path:
                    att["path"] = path
                att["rotation"] = round(r.read_float(), 2)
                att["x"] = round(r.read_float(), 2)
                att["y"] = round(r.read_float(), 2)
                att["scaleX"] = round(r.read_float(), 4)
                att["scaleY"] = round(r.read_float(), 4)
                att["width"] = round(r.read_float(), 2)
                att["height"] = round(r.read_float(), 2)
                att["color"] = r.read_color()
            elif att_type == 1:  # BOUNDING_BOX
                vert_count = r.read_int(True)
                verts = [round(r.read_float(), 2) for _ in range(vert_count)]
                att["type"] = "boundingbox"
                att["vertices"] = verts
                att["color"] = r.read_color()
            elif att_type == 2:  # MESH
                path = r.read_ref_string()
                if path:
                    att["path"] = path
                att["color"] = r.read_color()
                uv_count = r.read_int(True)
                att["uvs"] = []
                for _ in range(uv_count):
                    att["uvs"].extend([round(r.read_float(), 4), round(r.read_float(), 4)])
                tri_count = r.read_int(True)
                att["triangles"] = [r.read_short() for _ in range(tri_count)]
                weighted = r.read_bool()
                vert_count = r.read_int(True)
                if weighted:
                    verts = []
                    for _ in range(vert_count):
                        verts.append(round(r.read_float(), 2))
                        bone_count_v = int(r.read_float())
                        for _ in range(bone_count_v):
                            verts.append(r.read_int(True))
                            verts.append(round(r.read_float(), 2))
                            verts.append(round(r.read_float(), 2))
                            verts.append(round(r.read_float(), 4))
                    att["vertices"] = verts
                    att["weighted"] = True
                else:
                    att["vertices"] = [round(r.read_float(), 2) for _ in range(vert_count)]
                att["hull"] = r.read_int(True)
                edge_count = r.read_int(True)
                att["edges"] = [r.read_short() for _ in range(edge_count)]
                att["width"] = round(r.read_float(), 2)
                att["height"] = round(r.read_float(), 2)
            elif att_type == 3:  # LINKED_MESH
                path = r.read_ref_string()
                if path:
                    att["path"] = path
                att["color"] = r.read_color()
                att["skin"] = r.read_ref_string()
                att["parent"] = r.read_ref_string()
                att["deform"] = r.read_bool()
                att["width"] = round(r.read_float(), 2)
                att["height"] = round(r.read_float(), 2)
            elif att_type == 4:  # PATH
                att["type"] = "path"
                att["closed"] = r.read_bool()
                att["constantSpeed"] = r.read_bool()
                vert_count = r.read_int(True)
                att["vertices"] = [round(r.read_float(), 2) for _ in range(vert_count)]
                lengths = [round(r.read_float(), 2) for _ in range(vert_count // 3)]
                att["lengths"] = lengths
                att["color"] = r.read_color()
            elif att_type == 5:  # POINT
                att["type"] = "point"
                att["rotation"] = round(r.read_float(), 2)
                att["x"] = round(r.read_float(), 2)
                att["y"] = round(r.read_float(), 2)
                att["color"] = r.read_color()
            elif att_type == 6:  # CLIPPING
                att["type"] = "clipping"
                att["end"] = slots[r.read_int(True) - 1]["name"]
                vert_count = r.read_int(True)
                att["vertices"] = [round(r.read_float(), 2) for _ in range(vert_count)]
                att["color"] = r.read_color()
            
            slot_atts[att_name] = att
        default_skin["attachments"][slot_name] = slot_atts
    
    result["skins"] = [default_skin]
    
    # Named skins
    skin_count = r.read_int(True)
    for i in range(skin_count):
        skin_name = r.read_ref_string()
        skin = {"name": skin_name, "attachments": {}}
        skin_slot_count2 = r.read_int(True)
        for j in range(skin_slot_count2):
            slot_idx = r.read_int(True) - 1
            slot_name = slots[slot_idx]["name"]
            att_count2 = r.read_int(True)
            slot_atts2 = {}
            for k in range(att_count2):
                r.read_ref_string()  # placeholder
                att_name2 = r.read_ref_string()
                att_type2 = r.read_int(True)
                # Skip attachment data (simplified - just advance position)
                if att_type2 == 0:
                    r.read_ref_string()
                    for _ in range(7): r.read_float()
                    r.read_color()
                elif att_type2 == 1:
                    vc = r.read_int(True)
                    for _ in range(vc): r.read_float()
                    r.read_color()
                elif att_type2 == 2:
                    r.read_ref_string()
                    r.read_color()
                    uc = r.read_int(True)
                    for _ in range(uc * 2): r.read_float()
                    tc = r.read_int(True)
                    for _ in range(tc): r.read_short()
                    w = r.read_bool()
                    vc2 = r.read_int(True)
                    if w:
                        for _ in range(vc2):
                            r.read_float()
                            bc = int(r.read_float())
                            for _ in range(bc):
                                r.read_int(True)
                                r.read_float()
                                r.read_float()
                                r.read_float()
                    else:
                        for _ in range(vc2): r.read_float()
                    r.read_int(True)  # hull
                    ec = r.read_int(True)
                    for _ in range(ec): r.read_short()
                    r.read_float()
                    r.read_float()
                elif att_type2 == 3:
                    r.read_ref_string()
                    r.read_color()
                    r.read_ref_string()
                    r.read_ref_string()
                    r.read_bool()
                    r.read_float()
                    r.read_float()
                elif att_type2 == 4:
                    r.read_bool()
                    r.read_bool()
                    vc3 = r.read_int(True)
                    for _ in range(vc3): r.read_float()
                    for _ in range(vc3 // 3): r.read_float()
                    r.read_color()
                elif att_type2 == 5:
                    for _ in range(3): r.read_float()
                    r.read_color()
                elif att_type2 == 6:
                    r.read_int(True)
                    vc4 = r.read_int(True)
                    for _ in range(vc4): r.read_float()
                    r.read_color()
                slot_atts2[att_name2] = {}  # simplified
            skin["attachments"][slot_name] = slot_atts2
        result["skins"].append(skin)
    
    # Events
    event_count = r.read_int(True)
    if event_count > 0:
        events = {}
        for i in range(event_count):
            name = r.read_ref_string()
            event = {}
            int_val = r.read_int(False)
            if int_val != 0:
                event["int"] = int_val
            float_val = r.read_float()
            if float_val != 0:
                event["float"] = round(float_val, 4)
            str_val = r.read_string()
            if str_val:
                event["string"] = str_val
            if nonessential:
                audio_val = r.read_string()
                if audio_val:
                    event["audio"] = audio_val
                    event["volume"] = round(r.read_float(), 4)
                    event["balance"] = round(r.read_float(), 4)
            events[name] = event
        result["events"] = events
    
    # Animations
    anim_count = r.read_int(True)
    print(f"  Animations: {anim_count}", file=sys.stderr)
    
    animations = {}
    for i in range(anim_count):
        anim_name = r.read_ref_string()
        anim = {}
        
        # Slot timelines
        slot_tl_count = r.read_int(True)
        if slot_tl_count > 0:
            anim["slots"] = {}
            for j in range(slot_tl_count):
                slot_idx = r.read_int(True) - 1
                slot_name = slots[slot_idx]["name"]
                tl_count = r.read_int(True)
                timelines = []
                for k in range(tl_count):
                    tl_type = r.read_int(True)
                    frame_count = r.read_int(True)
                    frames = []
                    for f in range(frame_count):
                        frame = {"time": round(r.read_float(), 4)}
                        if tl_type == 0:  # ATTACHMENT
                            frame["name"] = r.read_ref_string()
                        elif tl_type == 1:  # COLOR
                            frame["color"] = r.read_color()
                        elif tl_type == 2:  # TWO_COLOR
                            frame["light"] = r.read_color()
                            frame["dark"] = r.read_color()
                        frames.append(frame)
                        if f < frame_count - 1:
                            read_curve(r)
                    tl_names = ["attachment", "color", "twoColor"]
                    timelines.append({"type": tl_names[tl_type], "frames": frames})
                anim["slots"][slot_name] = timelines
        
        # Bone timelines
        bone_tl_count = r.read_int(True)
        if bone_tl_count > 0:
            anim["bones"] = {}
            for j in range(bone_tl_count):
                bone_idx = r.read_int(True) - 1
                bone_name = bones[bone_idx]["name"]
                tl_count2 = r.read_int(True)
                timelines2 = []
                for k in range(tl_count2):
                    tl_type2 = r.read_int(True)
                    frame_count2 = r.read_int(True)
                    frames2 = []
                    for f in range(frame_count2):
                        frame2 = {"time": round(r.read_float(), 4)}
                        if tl_type2 == 0:  # ROTATE
                            frame2["angle"] = round(r.read_float(), 2)
                        elif tl_type2 in [1, 2, 3]:  # TRANSLATE, SCALE, SHEAR
                            frame2["x"] = round(r.read_float(), 2)
                            frame2["y"] = round(r.read_float(), 2)
                        frames2.append(frame2)
                        if f < frame_count2 - 1:
                            read_curve(r)
                    tl_names2 = ["rotate", "translate", "scale", "shear"]
                    timelines2.append({"type": tl_names2[tl_type2], "frames": frames2})
                anim["bones"][bone_name] = timelines2
        
        # IK timelines
        ik_tl_count = r.read_int(True)
        if ik_tl_count > 0:
            anim["ik"] = []
            for j in range(ik_tl_count):
                ik_idx = r.read_int(True) - 1
                fc = r.read_int(True)
                frames3 = []
                for f in range(fc):
                    frame3 = {"time": round(r.read_float(), 4)}
                    frame3["mix"] = round(r.read_float(), 4)
                    frame3["bendPositive"] = r.read_byte() == 1
                    frames3.append(frame3)
                    if f < fc - 1:
                        read_curve(r)
                anim["ik"].append({"constraint": ik_constraints[ik_idx]["name"], "frames": frames3})
        
        # Transform timelines
        tc_tl_count = r.read_int(True)
        if tc_tl_count > 0:
            anim["transform"] = []
            for j in range(tc_tl_count):
                tc_idx = r.read_int(True) - 1
                fc2 = r.read_int(True)
                frames4 = []
                for f in range(fc2):
                    frame4 = {"time": round(r.read_float(), 4)}
                    frame4["rotateMix"] = round(r.read_float(), 4)
                    frame4["translateMix"] = round(r.read_float(), 4)
                    frame4["scaleMix"] = round(r.read_float(), 4)
                    frame4["shearMix"] = round(r.read_float(), 4)
                    frames4.append(frame4)
                    if f < fc2 - 1:
                        read_curve(r)
                anim["transform"].append({"constraint": tc_list[tc_idx]["name"], "frames": frames4})
        
        # Path timelines
        pc_tl_count = r.read_int(True)
        # Skip path timelines for now (simplified)
        for j in range(pc_tl_count):
            r.read_int(True)  # path constraint index
            pc_tl_count2 = r.read_int(True)
            for k in range(pc_tl_count2):
                r.read_int(True)  # type
                fc3 = r.read_int(True)
                for f in range(fc3):
                    r.read_float()  # time
                    r.read_float()  # value
                    r.read_float()  # value
                    if f < fc3 - 1:
                        read_curve(r)
        
        # Deform timelines
        deform_count = r.read_int(True)
        if deform_count > 0:
            anim["deform"] = []
            for j in range(deform_count):
                skin_idx = r.read_int(True) - 1
                slot_tl_count2 = r.read_int(True)
                for k in range(slot_tl_count2):
                    slot_idx2 = r.read_int(True) - 1
                    att_name3 = r.read_ref_string()
                    fc4 = r.read_int(True)
                    frames5 = []
                    for f in range(fc4):
                        frame5 = {"time": round(r.read_float(), 4)}
                        end_vert = r.read_int(True)
                        if end_vert > 0:
                            start_vert = r.read_int(True)
                            verts2 = [round(r.read_float(), 2) for _ in range(end_vert - start_vert)]
                            frame5["offset"] = start_vert
                            frame5["vertices"] = verts2
                        frames5.append(frame5)
                        if f < fc4 - 1:
                            read_curve(r)
                    anim["deform"].append({
                        "slot": slots[slot_idx2]["name"],
                        "attachment": att_name3,
                        "frames": frames5
                    })
        
        # Draw order
        do_count = r.read_int(True)
        if do_count > 0:
            anim["drawOrder"] = []
            for j in range(do_count):
                frame6 = {"time": round(r.read_float(), 4)}
                change_count = r.read_int(True)
                offsets = []
                for k in range(change_count):
                    sidx = r.read_int(True) - 1
                    offset = r.read_int(True)
                    offsets.append({"slot": slots[sidx]["name"], "offset": offset})
                frame6["offsets"] = offsets
                anim["drawOrder"].append(frame6)
        
        # Event timelines
        evt_tl_count = r.read_int(True)
        if evt_tl_count > 0:
            anim["events"] = []
            for j in range(evt_tl_count):
                frame7 = {"time": round(r.read_float(), 4)}
                frame7["value"] = r.read_int(False)
                frame7["float"] = round(r.read_float(), 4)
                has_str = r.read_bool()
                if has_str:
                    frame7["string"] = r.read_string()
                anim["events"].append(frame7)
        
        animations[anim_name] = anim
        
        if (i + 1) % 10 == 0:
            print(f"  Converted {i+1}/{anim_count} animations...", file=sys.stderr)
    
    result["animations"] = animations
    print(f"  Final pos: {r.pos}/{len(data)} ({r.remaining()} remaining)", file=sys.stderr)
    return result


def read_curve(r):
    curve_type = r.read_byte()
    if curve_type == 2:  # BEZIER
        r.read_float()  # cx1
        r.read_float()  # cy1
        r.read_float()  # cx2
        r.read_float()  # cy2


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="Input .skel file")
    parser.add_argument("-o", "--output", help="Output .json file")
    parser.add_argument("--sample", action="store_true", help="Convert only first animation")
    args = parser.parse_args()
    
    with open(args.input, "rb") as f:
        data = f.read()
    
    print(f"Converting {args.input} ({len(data)} bytes)...", file=sys.stderr)
    result = convert_skel_to_json(data)
    
    output = args.output or args.input.rsplit(".", 1)[0] + ".json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    
    print(f"Output: {output}", file=sys.stderr)
    print(f"Bones: {len(result.get('bones', []))}")
    print(f"Slots: {len(result.get('slots', []))}")
    print(f"Animations: {len(result.get('animations', {}))}")
    print(f"Skins: {len(result.get('skins', []))}")
