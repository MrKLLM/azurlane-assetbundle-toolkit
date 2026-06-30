// debug_bones.js - Check spine 3.8 Bone object structure
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

const skelData = fs.readFileSync("D:\\Azur Lane Assets\\Output\\Spine\\spinepainting\\aerbien_4\\aerbien_4.skel");
const reader = new spine.SkeletonBinary(new NullAttachmentLoader());
const sd = reader.readSkeletonData(skelData);

// Inspect first bone
const bone = sd.bones[0];
console.log("Bone keys:", Object.keys(bone));
console.log("Bone:", JSON.stringify(bone, (k, v) => {
    if (v instanceof Function) return "[Function]";
    if (typeof v === "object" && v !== null && v.constructor && v.constructor.name !== "Object") return "[" + v.constructor.name + "]";
    return v;
}, 2).substring(0, 500));

// Check boneData
console.log("\nBoneData keys:", Object.keys(bone.data));
console.log("BoneData name:", bone.data.name);
console.log("BoneData parent:", bone.data.parent);
console.log("Bone parent:", bone.parent);

// Check first slot
const slot = sd.slots[0];
console.log("\nSlot keys:", Object.keys(slot));
console.log("SlotData keys:", Object.keys(slot.data));
console.log("SlotData name:", slot.data.name);
console.log("SlotData boneData:", slot.data.boneData ? slot.data.boneData.name : "null");
