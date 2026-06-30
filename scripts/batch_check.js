#!/usr/bin/env node
/**
 * 批量检查所有角色的 Spine 数据加载情况
 */
const fs = require('fs');
const path = require('path');

eval(fs.readFileSync(path.join(__dirname, '..', 'tools', 'spine-viewer', 'spine-runtime', '3.8_spine-core.js'), 'utf8'));

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

const SPINE_DIR = path.join(__dirname, '..', 'Output', 'Spine', 'spinepainting');
const MANIFEST = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'Output', 'Spine', 'spine_manifest.json'), 'utf8'));

const results = { ok: [], fail: [] };

for (const item of MANIFEST.items) {
    const charDir = path.join(SPINE_DIR, item.name);
    
    for (const variant of item.variants) {
        const skelPath = path.join(charDir, variant.skel);
        
        try {
            const skelBytes = fs.readFileSync(skelPath);
            const reader = new spine.SkeletonBinary(new NullAttachmentLoader());
            const sd = reader.readSkeletonData(skelBytes);
            
            const issues = [];
            
            if (sd.bones.length === 0) issues.push('no bones');
            if (sd.slots.length === 0) issues.push('no slots');
            if (sd.animations.length === 0) issues.push('no animations');
            if (!sd.defaultSkin) issues.push('no defaultSkin');
            
            // Count attachments in default skin
            let attCount = 0;
            if (sd.defaultSkin) {
                for (let i = 0; i < sd.slots.length; i++) {
                    const att = sd.defaultSkin.getAttachment(i, sd.slots[i].name);
                    if (att) attCount++;
                }
            }
            if (attCount === 0 && sd.slots.length > 0) issues.push('0 attachments in skin');
            
            // Check version looks reasonable
            if (sd.version && !sd.version.match(/\d+\.\d+/)) {
                issues.push('bad version: ' + sd.version);
            }
            
            const info = {
                name: item.name,
                variant: variant.variant,
                bones: sd.bones.length,
                slots: sd.slots.length,
                anims: sd.animations.length,
                atts: attCount,
                w: Math.round(sd.width),
                h: Math.round(sd.height),
                ver: (sd.version || '').substring(0, 30)
            };
            
            if (issues.length > 0) {
                info.issues = issues;
                results.fail.push(info);
            } else {
                results.ok.push(info);
            }
        } catch (e) {
            results.fail.push({
                name: item.name,
                variant: variant.variant,
                error: e.message.substring(0, 100)
            });
        }
    }
}

console.log('='.repeat(70));
console.log('Check complete: ' + MANIFEST.total + ' characters');
console.log('OK: ' + results.ok.length + ', FAIL: ' + results.fail.length);
console.log('='.repeat(70));

if (results.fail.length > 0) {
    console.log('\n--- FAILED ---');
    for (const item of results.fail) {
        const label = item.name + '/' + item.variant;
        if (item.error) {
            console.log('[FAIL] ' + label + ': ' + item.error);
        } else {
            console.log('[FAIL] ' + label + ' - bones:' + item.bones + ' slots:' + item.slots + ' anims:' + item.anims + ' atts:' + item.atts);
            for (const issue of (item.issues || [])) {
                console.log('  - ' + issue);
            }
        }
    }
}

console.log('\n--- OK (first 30) ---');
for (const item of results.ok.slice(0, 30)) {
    console.log('[OK] ' + item.name + '/' + item.variant + ' bones:' + item.bones + ' slots:' + item.slots + ' anims:' + item.anims + ' atts:' + item.atts + ' ' + item.w + 'x' + item.h);
}

// Stats
const zeroAtts = results.ok.filter(i => i.atts === 0);
if (zeroAtts.length > 0) {
    console.log('\n--- OK but 0 attachments (character may not display) ---');
    for (const item of zeroAtts) {
        console.log('  ' + item.name + '/' + item.variant);
    }
}
