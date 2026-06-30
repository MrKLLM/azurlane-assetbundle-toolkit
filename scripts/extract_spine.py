#!/usr/bin/env python3
"""
Extract Spine assets from AssetBundles.
Outputs: .skel, .atlas, .png files organized by character name.
"""
import UnityPy
import os
import json
import struct
import sys
from pathlib import Path

ASSET_BUNDLES_DIR = r"D:\Azur Lane Assets\files\AssetBundles"
OUTPUT_DIR = r"D:\Azur Lane Assets\Output\Spine"
ERROR_LOG = r"D:\Azur Lane Assets\docs\ERRORS.log"

def extract_texture(obj, output_dir, name):
    """Extract Texture2D as PNG."""
    try:
        from PIL import Image
        data = obj.read()
        img = data.image
        if img is None:
            return False, "No image data"
        out_path = os.path.join(output_dir, f"{name}.png")
        img.save(out_path, "PNG")
        return True, out_path
    except Exception as e:
        return False, str(e)[:200]

def extract_text_asset(obj, output_dir, name):
    """Extract TextAsset raw bytes."""
    try:
        data = obj.read()
        obj.reset()
        raw = obj.get_raw_data()
        
        # Parse Unity TextAsset format
        name_len = struct.unpack_from("<i", raw, 0)[0]
        script_offset = (4 + name_len + 3) & ~3
        script_len = struct.unpack_from("<i", raw, script_offset)[0]
        script_data = raw[script_offset + 4: script_offset + 4 + script_len]
        
        out_path = os.path.join(output_dir, name)
        with open(out_path, "wb") as f:
            f.write(script_data)
        return True, out_path
    except Exception as e:
        return False, str(e)[:200]


def extract_spine_bundle(bundle_path, output_dir):
    """Extract all Spine assets from a single bundle."""
    results = {"textures": [], "skel": None, "atlas": None, "errors": []}
    
    try:
        env = UnityPy.load(bundle_path)
    except Exception as e:
        results["errors"].append(f"Load failed: {str(e)[:100]}")
        return results
    
    for obj in env.objects:
        data = obj.read()
        
        if obj.type.name == "Texture2D":
            # Texture names may have appended numbers, use the original name
            tex_name = data.m_Name
            ok, info = extract_texture(obj, output_dir, tex_name)
            if ok:
                results["textures"].append(info)
            else:
                results["errors"].append(f"Texture {tex_name}: {info}")
        
        elif obj.type.name == "TextAsset":
            asset_name = data.m_Name
            if asset_name.endswith(".skel"):
                ok, info = extract_text_asset(obj, output_dir, asset_name)
                if ok:
                    results["skel"] = info
                else:
                    results["errors"].append(f"skel {asset_name}: {info}")
            elif asset_name.endswith(".atlas"):
                # Atlas text is stored as string, write directly
                try:
                    script = data.m_Script
                    if isinstance(script, str):
                        atlas_text = script
                    else:
                        atlas_text = script.decode("utf-8", errors="replace")
                    out_path = os.path.join(output_dir, asset_name)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(atlas_text)
                    results["atlas"] = out_path
                except Exception as e:
                    results["errors"].append(f"atlas {asset_name}: {str(e)[:100]}")
    
    return results


def main():
    """Main extraction function."""
    import argparse
    parser = argparse.ArgumentParser(description="Extract Spine assets from AssetBundles")
    parser.add_argument("--dry-run", action="store_true", help="Preview without extracting")
    parser.add_argument("--sample", type=int, default=0, help="Extract N samples only")
    parser.add_argument("--target", choices=["spinepainting", "spineitem", "all"], 
                       default="spinepainting", help="Target directory")
    args = parser.parse_args()
    
    # Collect source directories
    targets = []
    if args.target in ("spinepainting", "all"):
        sp_dir = os.path.join(ASSET_BUNDLES_DIR, "spinepainting")
        if os.path.isdir(sp_dir):
            targets.append(("spinepainting", sp_dir))
    if args.target in ("spineitem", "all"):
        si_dir = os.path.join(ASSET_BUNDLES_DIR, "spineitem")
        if os.path.isdir(si_dir):
            targets.append(("spineitem", si_dir))
    
    # Collect all bundles to process
    bundles_to_process = []
    for category, src_dir in targets:
        for fname in os.listdir(src_dir):
            fpath = os.path.join(src_dir, fname)
            if os.path.isfile(fpath) and not fname.endswith("_res"):
                # Main bundle (non-res) - contains the scene setup
                # We also need the _res bundle for textures and data
                res_path = os.path.join(src_dir, f"{fname}_res")
                bundles_to_process.append((category, fname, fpath, 
                                         res_path if os.path.exists(res_path) else None))
    
    total = len(bundles_to_process)
    print(f"Found {total} spine bundles to process")
    
    if args.sample > 0:
        bundles_to_process = bundles_to_process[:args.sample]
        print(f"Processing {args.sample} samples only")
    
    if args.dry_run:
        print("\nDry run - bundles to process:")
        for cat, name, main_p, res_p in bundles_to_process[:20]:
            res_status = "YES" if res_p else "NO"
            print(f"  [{cat}] {name} (res: {res_status})")
        if len(bundles_to_process) > 20:
            print(f"  ... and {len(bundles_to_process) - 20} more")
        return
    
    # Extract
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    success = 0
    failed = 0
    all_results = []
    
    for i, (category, name, main_path, res_path) in enumerate(bundles_to_process):
        # Create output directory
        out_dir = os.path.join(OUTPUT_DIR, category, name)
        os.makedirs(out_dir, exist_ok=True)
        
        # Extract resource bundle (has the actual spine data)
        if res_path:
            results = extract_spine_bundle(res_path, out_dir)
        else:
            results = {"textures": [], "skel": None, "atlas": None, 
                      "errors": ["No _res bundle found"]}
        
        if results["skel"] and results["atlas"]:
            success += 1
        else:
            failed += 1
            if results["errors"]:
                with open(ERROR_LOG, "a", encoding="utf-8") as f:
                    f.write(f"[Spine] {category}/{name}: {'; '.join(results['errors'])}\n")
        
        all_results.append({"name": name, "category": category, **results})
        
        if (i + 1) % 20 == 0 or (i + 1) == len(bundles_to_process):
            print(f"  [{i+1}/{len(bundles_to_process)}] {name} "
                  f"(OK:{success} FAIL:{failed})")
    
    # Save manifest
    manifest_path = os.path.join(OUTPUT_DIR, "spine_manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump({
            "total": len(all_results),
            "success": success,
            "failed": failed,
            "items": all_results
        }, f, indent=2, ensure_ascii=False)
    
    print(f"\nDone! Success: {success}, Failed: {failed}")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
