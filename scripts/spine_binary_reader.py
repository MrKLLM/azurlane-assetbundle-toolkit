#!/usr/bin/env python3
"""
Spine binary format reader.
Based on https://esotericsoftware.com/spine-binary-format

Reads the .skel binary files from spine-unity and converts to JSON.
"""
import struct
import json
import sys
import os

class SpineBinaryReader:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        self.shared_strings = []
    
    def read_byte(self):
        if self.pos >= len(self.data):
            raise EOFError(f"Unexpected end of data at pos {self.pos}")
        b = self.data[self.pos]
        self.pos += 1
        return b
    
    def read_bool(self):
        return self.read_byte() != 0
    
    def read_short(self):
        b1 = self.read_byte()
        b2 = self.read_byte()
        return (b1 << 8) | b2
    
    def read_int(self):
        b1 = self.read_byte()
        b2 = self.read_byte()
        b3 = self.read_byte()
        b4 = self.read_byte()
        return (b1 << 24) | (b2 << 16) | (b3 << 8) | b4
    
    def read_varint(self, optimize_positive=True):
        b = self.read_byte()
        value = b & 0x7F
        if b & 0x80:
            b = self.read_byte()
            value |= (b & 0x7F) << 7
            if b & 0x80:
                b = self.read_byte()
                value |= (b & 0x7F) << 14
                if b & 0x80:
                    b = self.read_byte()
                    value |= (b & 0x7F) << 21
                    if b & 0x80:
                        b = self.read_byte()
                        value |= (b & 0x7F) << 28
        if not optimize_positive:
            value = (value >> 1) ^ -(value & 1)
        return value
    
    def read_float(self):
        int_val = self.read_int()
        return struct.unpack("=f", struct.pack("=i", int_val))[0]
    
    def read_string(self):
        count = self.read_varint(True)
        if count <= 1:
            return "" if count == 0 else ""
        count -= 1
        raw = self.data[self.pos:self.pos + count]
        self.pos += count
        return raw.decode("utf-8", errors="replace")
    
    def read_ref_string(self):
        index = self.read_varint(True)
        if index == 0:
            return ""
        return self.shared_strings[index - 1]
    
    def read_color(self):
        rgba = self.read_int()
        r = ((rgba & 0xff000000) >> 24) / 255.0
        g = ((rgba & 0x00ff0000) >> 16) / 255.0
        b = ((rgba & 0x0000ff00) >> 8) / 255.0
        a = (rgba & 0x000000ff) / 255.0
        return [round(r, 3), round(g, 3), round(b, 3), round(a, 3)]
    
    def remaining(self):
        return len(self.data) - self.pos


def read_skeleton_binary(data):
    """Read a spine binary skeleton and return dict."""
    reader = SpineBinaryReader(data)
    
    result = {}
    
    # Hash
    hash_str = reader.read_string()
    result["hash"] = hash_str
    
    # Version
    version = reader.read_string()
    result["skeleton"] = {"hash": hash_str, "version": version, "spine": version}
    
    # Width, Height
    x = reader.read_float()
    y = reader.read_float()
    w = reader.read_float()
    h = reader.read_float()
    result["skeleton"]["x"] = x
    result["skeleton"]["y"] = y
    result["skeleton"]["width"] = w
    result["skeleton"]["height"] = h
    
    print(f"  Hash: {hash_str}", file=sys.stderr)
    print(f"  Version: {version}", file=sys.stderr)
    print(f"  Size: {w} x {h}", file=sys.stderr)
    print(f"  Remaining after header: {reader.remaining()} bytes", file=sys.stderr)
    
    # Nonessential
    nonessential = reader.read_bool()
    result["skeleton"]["nonessential"] = nonessential
    
    if nonessential:
        fps = reader.read_float()
        images = reader.read_string()
        audio = reader.read_string()
        result["skeleton"]["fps"] = fps
        result["skeleton"]["images"] = images
        result["skeleton"]["audio"] = audio
        print(f"  FPS: {fps}, Images: {images}, Audio: {audio}", file=sys.stderr)
    
    # Shared strings
    string_count = reader.read_varint(True)
    print(f"  Shared strings: {string_count}", file=sys.stderr)
    for i in range(string_count):
        s = reader.read_string()
        reader.shared_strings.append(s)
    
    # Bones
    bone_count = reader.read_varint(True)
    print(f"  Bones: {bone_count}", file=sys.stderr)
    bones = []
    for i in range(bone_count):
        bone = {}
        bone["name"] = reader.read_string()
        parent_idx = reader.read_varint(True)
        if parent_idx > 0:
            bone["parent"] = bones[parent_idx - 1]["name"]
        bone["rotation"] = reader.read_float()
        bone["x"] = reader.read_float()
        bone["y"] = reader.read_float()
        bone["scaleX"] = reader.read_float()
        bone["scaleY"] = reader.read_float()
        bone["shearX"] = reader.read_float()
        bone["shearY"] = reader.read_float()
        bone["length"] = reader.read_float()
        bone["transform"] = ["normal", "onlyTranslation", "noRotationOrReflection",
                            "noScale", "noScaleOrReflection"][reader.read_varint(True)]
        if reader.read_bool():
            bone["skinRequired"] = True
        if nonessential:
            bone["color"] = reader.read_color()
        bones.append(bone)
    result["bones"] = bones
    
    # Slots
    slot_count = reader.read_varint(True)
    print(f"  Slots: {slot_count}", file=sys.stderr)
    slots = []
    for i in range(slot_count):
        slot = {}
        slot["name"] = reader.read_string()
        slot["bone"] = bones[reader.read_varint(True) - 1]["name"]
        slot["color"] = reader.read_color()
        dark = reader.read_color()
        if dark != [1, 1, 1, 1]:
            slot["dark"] = dark
        attachment = reader.read_ref_string()
        if attachment:
            slot["attachment"] = attachment
        blend = reader.read_varint(True)
        if blend > 0:
            slot["blend"] = ["normal", "additive", "multiply", "screen"][blend]
        slots.append(slot)
    result["slots"] = slots
    
    # IK constraints
    ik_count = reader.read_varint(True)
    print(f"  IK constraints: {ik_count}", file=sys.stderr)
    ik_constraints = []
    for i in range(ik_count):
        ik = {}
        ik["name"] = reader.read_string()
        ik["order"] = reader.read_varint(True)
        if reader.read_bool():
            ik["skinRequired"] = True
        bone_count_ik = reader.read_varint(True)
        ik["bones"] = [bones[reader.read_varint(True) - 1]["name"] for _ in range(bone_count_ik)]
        ik["target"] = bones[reader.read_varint(True) - 1]["name"]
        ik["mix"] = reader.read_float()
        ik["softness"] = reader.read_float()
        ik["bendPositive"] = reader.read_byte() == 1
        ik["compress"] = reader.read_bool()
        ik["stretch"] = reader.read_bool()
        ik["uniform"] = reader.read_bool()
        ik_constraints.append(ik)
    result["ik"] = ik_constraints
    
    # Transform constraints
    tc_count = reader.read_varint(True)
    print(f"  Transform constraints: {tc_count}", file=sys.stderr)
    transform_constraints = []
    for i in range(tc_count):
        tc = {}
        tc["name"] = reader.read_string()
        tc["order"] = reader.read_varint(True)
        if reader.read_bool():
            tc["skinRequired"] = True
        tc["bone"] = bones[reader.read_varint(True) - 1]["name"]
        tc["target"] = bones[reader.read_varint(True) - 1]["name"]
        tc["local"] = reader.read_bool()
        tc["relative"] = reader.read_bool()
        tc["offsetRotation"] = reader.read_float()
        tc["offsetX"] = reader.read_float()
        tc["offsetY"] = reader.read_float()
        tc["offsetScaleX"] = reader.read_float()
        tc["offsetScaleY"] = reader.read_float()
        tc["offsetShearY"] = reader.read_float()
        tc["rotateMix"] = reader.read_float()
        tc["translateMix"] = reader.read_float()
        tc["scaleMix"] = reader.read_float()
        tc["shearMix"] = reader.read_float()
        transform_constraints.append(tc)
    result["transform"] = transform_constraints
    
    # Path constraints
    pc_count = reader.read_varint(True)
    print(f"  Path constraints: {pc_count}", file=sys.stderr)
    path_constraints = []
    for i in range(pc_count):
        pc = {"name": reader.read_string(), "order": reader.read_varint(True)}
        if reader.read_bool():
            pc["skinRequired"] = True
        pc_bone_count = reader.read_varint(True)
        pc["bones"] = [bones[reader.read_varint(True) - 1]["name"] for _ in range(pc_bone_count)]
        pc["target"] = slots[reader.read_varint(True) - 1]["name"]
        pc["positionMode"] = ["fixed", "percent"][reader.read_varint(True)]
        pc["spacingMode"] = ["length", "fixed", "percent"][reader.read_varint(True)]
        pc["rotateMode"] = ["tangent", "chain", "chainScale"][reader.read_varint(True)]
        pc["offsetRotation"] = reader.read_float()
        pc["position"] = reader.read_float()
        pc["spacing"] = reader.read_float()
        pc["rotateMix"] = reader.read_float()
        pc["translateMix"] = reader.read_float()
        path_constraints.append(pc)
    result["path"] = path_constraints
    
    # Default skin
    default_skin = read_skin(reader, None, bones, slots, ik_constraints,
                            transform_constraints, path_constraints)
    result["skins"] = [default_skin]
    
    # Named skins
    skin_count = reader.read_varint(True)
    print(f"  Skins: {skin_count + 1} (1 default + {skin_count} named)", file=sys.stderr)
    for i in range(skin_count):
        skin_name = reader.read_ref_string()
        skin = read_skin(reader, skin_name, bones, slots, ik_constraints,
                        transform_constraints, path_constraints)
        result["skins"].append(skin)
    
    # Events
    event_count = reader.read_varint(True)
    print(f"  Events: {event_count}", file=sys.stderr)
    if event_count > 0:
        events = {}
        for i in range(event_count):
            name = reader.read_ref_string()
            event = {}
            int_val = reader.read_varint(False)
            if int_val != 0:
                event["int"] = int_val
            float_val = reader.read_float()
            if float_val != 0:
                event["float"] = float_val
            str_val = reader.read_string()
            if str_val:
                event["string"] = str_val
            if nonessential:
                audio = reader.read_string()
                if audio:
                    event["audio"] = audio
                    event["volume"] = reader.read_float()
                    event["balance"] = reader.read_float()
            events[name] = event
        result["events"] = events
    
    # Animations
    anim_count = reader.read_varint(True)
    print(f"  Animations: {anim_count}", file=sys.stderr)
    animations = {}
    for i in range(anim_count):
        anim_name = reader.read_ref_string()
        anim = read_animation(reader, bones, slots, ik_constraints,
                             transform_constraints, path_constraints, skins=result["skins"])
        animations[anim_name] = anim
    result["animations"] = animations
    
    print(f"  Final pos: {reader.pos}/{len(reader.data)} ({reader.remaining()} remaining)", file=sys.stderr)
    
    return result


def read_skin(reader, name, bones, slots, ik_constraints, transform_constraints, path_constraints):
    skin = {}
    if name:
        skin["name"] = name
    
    slot_count = reader.read_varint(True)
    attachments = {}
    for i in range(slot_count):
        slot_index = reader.read_varint(True) - 1
        slot_name = slots[slot_index]["name"]
        att_count = reader.read_varint(True)
        slot_atts = {}
        for j in range(att_count):
            placeholder = reader.read_ref_string()
            att_name = reader.read_ref_string()
            if not att_name:
                att_name = placeholder
            att_type = reader.read_varint(True)
            
            att = {}
            if att_type == 0:  # REGION
                path = reader.read_ref_string()
                if path:
                    att["path"] = path
                att["rotation"] = reader.read_float()
                att["x"] = reader.read_float()
                att["y"] = reader.read_float()
                att["scaleX"] = reader.read_float()
                att["scaleY"] = reader.read_float()
                att["width"] = reader.read_float()
                att["height"] = reader.read_float()
                att["color"] = reader.read_color()
            elif att_type == 1:  # BOUNDING_BOX
                vert_count = reader.read_varint(True)
                vertices = read_vertices(reader, False)
                att["type"] = "boundingbox"
                att["vertices"] = vertices
                att["color"] = reader.read_color()
            elif att_type == 2:  # MESH
                path = reader.read_ref_string()
                if path:
                    att["path"] = path
                att["color"] = reader.read_color()
                uv_count = reader.read_varint(True)
                att["uvs"] = []
                for k in range(uv_count):
                    att["uvs"].extend([reader.read_float(), reader.read_float()])
                tri_count = reader.read_varint(True)
                att["triangles"] = []
                for k in range(tri_count):
                    att["triangles"].append(reader.read_short())
                vertices = read_vertices(reader, False)
                att["vertices"] = vertices
                att["hull"] = reader.read_varint(True)
                edge_count = reader.read_varint(True)
                att["edges"] = []
                for k in range(edge_count):
                    att["edges"].append(reader.read_short())
                att["width"] = reader.read_float()
                att["height"] = reader.read_float()
            elif att_type == 3:  # LINKED_MESH
                path = reader.read_ref_string()
                if path:
                    att["path"] = path
                att["color"] = reader.read_color()
                att["skin"] = reader.read_ref_string()
                att["parent"] = reader.read_ref_string()
                att["deform"] = reader.read_bool()
                att["width"] = reader.read_float()
                att["height"] = reader.read_float()
            elif att_type == 4:  # PATH
                att["type"] = "path"
                att["closed"] = reader.read_bool()
                att["constantSpeed"] = reader.read_bool()
                vert_count = reader.read_varint(True)
                vertices = read_vertices(reader, False)
                att["vertices"] = vertices
                lengths = []
                for k in range(vert_count // 3):
                    lengths.append(reader.read_float())
                att["lengths"] = lengths
                att["color"] = reader.read_color()
            elif att_type == 5:  # POINT
                att["type"] = "point"
                att["rotation"] = reader.read_float()
                att["x"] = reader.read_float()
                att["y"] = reader.read_float()
                att["color"] = reader.read_color()
            elif att_type == 6:  # CLIPPING
                att["type"] = "clipping"
                att["end"] = slots[reader.read_varint(True) - 1]["name"]
                vert_count = reader.read_varint(True)
                vertices = read_vertices(reader, False)
                att["vertices"] = vertices
                att["color"] = reader.read_color()
            
            slot_atts[att_name] = att
        attachments[slot_name] = slot_atts
    skin["attachments"] = attachments
    return skin


def read_vertices(reader, weighted):
    vertices = []
    count = reader.read_varint(True)
    if weighted:
        for i in range(count):
            vertices.append(reader.read_float())  # bone count as float? No...
            # Actually, weighted vertices have different format
            pass
    else:
        for i in range(count):
            vertices.append(reader.read_float())
    return vertices


def read_animation(reader, bones, slots, ik_constraints, transform_constraints,
                   path_constraints, skins):
    anim = {}
    
    # Slot timelines
    slot_count = reader.read_varint(True)
    slot_timelines = {}
    for i in range(slot_count):
        slot_index = reader.read_varint(True) - 1
        slot_name = slots[slot_index]["name"]
        timeline_count = reader.read_varint(True)
        timelines = []
        for j in range(timeline_count):
            tl_type = reader.read_varint(True)
            frame_count = reader.read_varint(True)
            
            if tl_type == 0:  # SLOT_ATTACHMENT
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float()}
                    frame["name"] = reader.read_ref_string()
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                timelines.append({"type": "attachment", "frames": frames})
            elif tl_type == 1:  # SLOT_COLOR
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float()}
                    frame["color"] = reader.read_color()
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                timelines.append({"type": "color", "frames": frames})
            elif tl_type == 2:  # SLOT_TWO_COLOR
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float()}
                    frame["light"] = reader.read_color()
                    frame["dark"] = reader.read_color()
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                timelines.append({"type": "twoColor", "frames": frames})
        if timelines:
            slot_timelines[slot_name] = timelines
    if slot_timelines:
        anim["slots"] = slot_timelines
    
    # Bone timelines
    bone_count = reader.read_varint(True)
    bone_timelines = {}
    for i in range(bone_count):
        bone_index = reader.read_varint(True) - 1
        bone_name = bones[bone_index]["name"]
        timeline_count = reader.read_varint(True)
        timelines = []
        for j in range(timeline_count):
            tl_type = reader.read_varint(True)
            frame_count = reader.read_varint(True)
            
            if tl_type == 0:  # BONE_ROTATE
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float(), "angle": reader.read_float()}
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                timelines.append({"type": "rotate", "frames": frames})
            elif tl_type in [1, 2, 3]:  # BONE_TRANSLATE, SCALE, SHEAR
                prop = ["translate", "scale", "shear"][tl_type - 1]
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float()}
                    frame["x"] = reader.read_float()
                    frame["y"] = reader.read_float()
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                timelines.append({"type": prop, "frames": frames})
        if timelines:
            bone_timelines[bone_name] = timelines
    if bone_timelines:
        anim["bones"] = bone_timelines
    
    # IK constraint timelines
    ik_tl_count = reader.read_varint(True)
    if ik_tl_count > 0:
        ik_timelines = []
        for i in range(ik_tl_count):
            ik_index = reader.read_varint(True) - 1
            frame_count = reader.read_varint(True)
            frames = []
            for k in range(frame_count):
                frame = {"time": reader.read_float()}
                frame["mix"] = reader.read_float()
                frame["bendPositive"] = reader.read_byte() == 1
                frames.append(frame)
                if k < frame_count - 1:
                    read_curve(reader)
            ik_timelines.append({"constraint": ik_constraints[ik_index]["name"], "frames": frames})
        if ik_timelines:
            anim["ik"] = ik_timelines
    
    # Transform constraint timelines
    tc_tl_count = reader.read_varint(True)
    if tc_tl_count > 0:
        tc_timelines = []
        for i in range(tc_tl_count):
            tc_index = reader.read_varint(True) - 1
            frame_count = reader.read_varint(True)
            frames = []
            for k in range(frame_count):
                frame = {"time": reader.read_float()}
                frame["rotateMix"] = reader.read_float()
                frame["translateMix"] = reader.read_float()
                frame["scaleMix"] = reader.read_float()
                frame["shearMix"] = reader.read_float()
                frames.append(frame)
                if k < frame_count - 1:
                    read_curve(reader)
            tc_timelines.append({"constraint": transform_constraints[tc_index]["name"], "frames": frames})
        if tc_timelines:
            anim["transform"] = tc_timelines
    
    # Path constraint timelines
    pc_tl_count = reader.read_varint(True)
    
    # Deform timelines
    deform_count = reader.read_varint(True)
    if deform_count > 0:
        deform_timelines = []
        for i in range(deform_count):
            skin_index = reader.read_varint(True) - 1
            slot_count = reader.read_varint(True)
            for j in range(slot_count):
                slot_index = reader.read_varint(True) - 1
                att_name = reader.read_ref_string()
                frame_count = reader.read_varint(True)
                frames = []
                for k in range(frame_count):
                    frame = {"time": reader.read_float()}
                    end_vertex = reader.read_varint(True)
                    if end_vertex > 0:
                        start_vertex = reader.read_varint(True)
                        vertices = []
                        for v in range(start_vertex, end_vertex):
                            vertices.append(reader.read_float())
                        frame["offset"] = start_vertex
                        frame["vertices"] = vertices
                    frames.append(frame)
                    if k < frame_count - 1:
                        read_curve(reader)
                deform_timelines.append({
                    "slot": slots[slot_index]["name"],
                    "attachment": att_name,
                    "frames": frames
                })
        if deform_timelines:
            anim["deform"] = deform_timelines
    
    # Draw order
    do_count = reader.read_varint(True)
    if do_count > 0:
        do_frames = []
        for i in range(do_count):
            frame = {"time": reader.read_float()}
            change_count = reader.read_varint(True)
            offsets = []
            for j in range(change_count):
                slot_index = reader.read_varint(True) - 1
                offset = reader.read_varint(True)
                offsets.append({"slot": slots[slot_index]["name"], "offset": offset})
            frame["offsets"] = offsets
            do_frames.append(frame)
        anim["drawOrder"] = do_frames
    
    # Event timelines
    event_tl_count = reader.read_varint(True)
    if event_tl_count > 0:
        event_frames = []
        for i in range(event_tl_count):
            frame = {"time": reader.read_float()}
            event_index = reader.read_varint(True) - 1
            frame["value"] = reader.read_varint(False)
            frame["float"] = reader.read_float()
            has_string = reader.read_bool()
            if has_string:
                frame["string"] = reader.read_string()
            event_frames.append(frame)
        anim["events"] = event_frames
    
    return anim


def read_curve(reader):
    type_val = reader.read_byte()
    if type_val == 0:  # LINEAR
        pass
    elif type_val == 1:  # STEPPED
        pass
    elif type_val == 2:  # BEZIER
        reader.read_float()  # cx1
        reader.read_float()  # cy1
        reader.read_float()  # cx2
        reader.read_float()  # cy2


if __name__ == "__main__":
    # Test with one file
    import UnityPy
    
    BUNDLE = r"D:\Azur Lane Assets\files\AssetBundles\spinepainting\aerbien_4_res"
    env = UnityPy.load(BUNDLE)
    
    for obj in env.objects:
        data = obj.read()
        if obj.type.name == "TextAsset" and data.m_Name.endswith(".skel"):
            obj.reset()
            raw = obj.get_raw_data()
            name_len = struct.unpack_from("<i", raw, 0)[0]
            script_offset = (4 + name_len + 3) & ~3
            script_len = struct.unpack_from("<i", raw, script_offset)[0]
            skel_data = raw[script_offset + 4: script_offset + 4 + script_len]
            
            print(f"File: {data.m_Name}, Size: {len(skel_data)} bytes", file=sys.stderr)
            
            # Check if it's standard spine binary (0x1C header)
            if skel_data[0] == 0x1C:
                print("Format: Spine binary with 0x1C header", file=sys.stderr)
                
                # The format after 0x1C is: hash(string) + version(string) + ...
                # But the data we extracted doesn't match standard format
                # Let's try reading it as-is
                try:
                    skeleton = read_skeleton_binary(skel_data[1:])  # skip 0x1C
                    print(f"\nSUCCESS! Parsed skeleton:", file=sys.stderr)
                    print(json.dumps(skeleton, indent=2, ensure_ascii=False)[:2000])
                except Exception as e:
                    print(f"\nParse error: {e}", file=sys.stderr)
                    print(f"At position: {reader.pos if 'reader' in dir() else 'N/A'}", file=sys.stderr)
            else:
                print(f"Not standard spine binary (first byte: 0x{skel_data[0]:02x})", file=sys.stderr)
