// convert_skel.js - Convert .skel to .json using spine 3.8 runtime
const fs = require('fs');
const path = require('path');

eval(fs.readFileSync("D:\\Azur Lane Assets\\tools\\spine-viewer\\spine-runtime\\3.8_spine-core.js", 'utf8'));

class NullAttachmentLoader {
    newRegionAttachment(skin, name) {
        const att = new spine.RegionAttachment(name);
        att.region = new spine.TextureRegion();
        return att;
    }
    newMeshAttachment(skin, name, path) {
        const att = new spine.MeshAttachment(name);
        att.region = new spine.TextureRegion();
        return att;
    }
    newBoundingBoxAttachment(skin, name) { return new spine.BoundingBoxAttachment(name); }
    newPathAttachment(skin, name) { return new spine.PathAttachment(name); }
    newPointAttachment(skin, name) { return new spine.PointAttachment(name); }
    newClippingAttachment(skin, name) { return new spine.ClippingAttachment(name); }
}

function skeletonDataToJson(sd) {
    const json = {};

    json.skeleton = {
        hash: sd.hash || "",
        version: sd.version || "",
        spine: sd.version || "",
        x: sd.x || 0, y: sd.y || 0,
        width: sd.width || 0, height: sd.height || 0,
        fps: sd.fps || 30,
        images: sd.imagesPath || "",
        audio: sd.audioPath || ""
    };

    // Bones (BoneData objects)
    json.bones = sd.bones.map(b => {
        const bone = { name: b.name };
        if (b.parent != null) {
            const parentBone = sd.bones[b.parent];
            if (parentBone) bone.parent = parentBone.name;
        }
        bone.length = b.length || 0;
        bone.x = b.x || 0;
        bone.y = b.y || 0;
        bone.rotation = b.rotation || 0;
        bone.scaleX = b.scaleX != null ? b.scaleX : 1;
        bone.scaleY = b.scaleY != null ? b.scaleY : 1;
        bone.shearX = b.shearX || 0;
        bone.shearY = b.shearY || 0;
        return bone;
    });

    // Slots (SlotData objects)
    json.slots = sd.slots.map(s => {
        const slot = { name: s.name };
        if (s.boneData) slot.bone = s.boneData.name;
        else if (s.bone != null) {
            const bone = sd.bones[s.bone];
            if (bone) slot.bone = bone.name;
        }
        if (s.attachmentName) slot.attachment = s.attachmentName;
        return slot;
    });

    // IK constraints
    if (sd.ikConstraints && sd.ikConstraints.length > 0) {
        json.ik = sd.ikConstraints.map(ik => {
            try {
                return {
                    name: ik.name,
                    order: ik.order || 0,
                    bones: (ik.bones || []).map(b => b.name || sd.bones[b] ? sd.bones[b].name : ""),
                    target: ik.target != null ? sd.bones[ik.target].name : "",
                    mix: ik.mix || 1,
                    softness: ik.softness || 0,
                    bendPositive: ik.bendPositive !== false,
                    compress: !!ik.compress,
                    stretch: !!ik.stretch,
                    uniform: !!ik.uniform
                };
            } catch(e) { return null; }
        }).filter(x => x);
    }

    json.skins = [{}];

    // Animations
    json.animations = {};
    for (const [name, anim] of Object.entries(sd.animations)) {
        try {
            const animJson = {};

            if (anim.slotTimelines && anim.slotTimelines.length > 0) {
                animJson.slots = {};
                for (const st of anim.slotTimelines) {
                    const slotName = sd.slots[st.slotIndex] ? sd.slots[st.slotIndex].name : "slot_" + st.slotIndex;
                    animJson.slots[slotName] = st.frames.map(f => {
                        const frame = { time: f.time };
                        if (f.attachmentName !== undefined) {
                            frame.name = f.attachmentName || "";
                        } else if (f.color) {
                            try { frame.color = rgbaToHex(f.color.r, f.color.g, f.color.b, f.color.a); } catch(e) {}
                        }
                        return frame;
                    });
                }
            }

            if (anim.boneTimelines && anim.boneTimelines.length > 0) {
                animJson.bones = {};
                for (const bt of anim.boneTimelines) {
                    const boneName = sd.bones[bt.boneIndex] ? sd.bones[bt.boneIndex].name : "bone_" + bt.boneIndex;
                    animJson.bones[boneName] = [];
                    if (bt.rotateFrames) {
                        for (const f of bt.rotateFrames) {
                            animJson.bones[boneName].push({ time: f.time, angle: f.angle });
                        }
                    }
                    if (bt.translateFrames) {
                        for (const f of bt.translateFrames) {
                            animJson.bones[boneName].push({ time: f.time, x: f.x, y: f.y });
                        }
                    }
                    if (bt.scaleFrames) {
                        for (const f of bt.scaleFrames) {
                            animJson.bones[boneName].push({ time: f.time, x: f.x, y: f.y });
                        }
                    }
                    if (bt.shearFrames) {
                        for (const f of bt.shearFrames) {
                            animJson.bones[boneName].push({ time: f.time, x: f.x, y: f.y });
                        }
                    }
                }
            }

            json.animations[name] = animJson;
        } catch(e) {
            console.error("  Anim error:", name, e.message);
        }
    }

    return json;
}

function rgbaToHex(r, g, b, a) {
    const ri = Math.round(r * 255);
    const gi = Math.round(g * 255);
    const bi = Math.round(b * 255);
    const ai = Math.round(a * 255);
    return ((ri << 24) | (gi << 16) | (bi << 8) | ai).toString(16).padStart(8, '0');
}

const inputFile = process.argv[2];
const outputFile = process.argv[3] || inputFile.replace('.skel', '.json');

console.log("Converting: " + inputFile);
const skelData = fs.readFileSync(inputFile);

try {
    const reader = new spine.SkeletonBinary(new NullAttachmentLoader());
    const sd = reader.readSkeletonData(skelData);

    console.log("Hash: " + sd.hash);
    console.log("Version: " + sd.version);
    console.log("Size: " + sd.width + " x " + sd.height);
    console.log("Bones: " + sd.bones.length);
    console.log("Slots: " + sd.slots.length);
    console.log("Animations: " + Object.keys(sd.animations).length);

    const json = skeletonDataToJson(sd);
    fs.writeFileSync(outputFile, JSON.stringify(json, null, 2));
    console.log("Output: " + outputFile);
} catch (err) {
    console.error("Error: " + err.message);
    console.error(err.stack.split('\n').slice(0, 5).join('\n'));
}
