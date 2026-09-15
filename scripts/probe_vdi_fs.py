"""
只读探测 MuMu VDI 磁盘镜像内部分区的文件系统类型。

思路：
1. 解析 VDI Header（512B）拿到 block size / block map 偏移 / data 偏移
2. 解析 MBR 分区表拿到各分区起始 LBA
3. 定位到目标分区起始，读出 superblock 前几 KB，比对 magic 判断文件系统

全程只读，不修改任何文件。
"""
import struct
import sys

VDI_PATH = r"C:\Program Files\Netease\MuMuPlayer\vms\MuMuPlayerGlobal-12.0-0\data.vdi"

# 文件系统 magic: (偏移, magic bytes, 名称)
FS_MAGICS = [
    (1024, bytes.fromhex("1020F5F2"), "f2fs"),          # f2fs magic, LE
    (0x438, bytes.fromhex("53EF"), "ext2/ext3/ext4"),   # ext superblock magic
    (0x3, b"NTFS    ", "ntfs"),
    (0x52, b"EXFAT   ", "exfat"),
    (0x3, b"MSDOS5.0", "fat32"),
]


def parse_vdi_header(f):
    f.seek(0)
    hdr = f.read(512)
    sig = struct.unpack_from("<I", hdr, 0x40)[0]
    if sig != 0xBEDA107F:
        raise ValueError(f"不是有效的 VDI 文件, signature=0x{sig:08X}")

    img_type = struct.unpack_from("<I", hdr, 0x4C)[0]
    off_blocks = struct.unpack_from("<I", hdr, 0x154)[0]
    off_data = struct.unpack_from("<I", hdr, 0x158)[0]
    cb_sector = struct.unpack_from("<I", hdr, 0x168)[0]
    cb_disk = struct.unpack_from("<Q", hdr, 0x170)[0]
    cb_block = struct.unpack_from("<I", hdr, 0x178)[0]
    c_blocks = struct.unpack_from("<I", hdr, 0x180)[0]

    type_name = {1: "动态分配", 2: "固定大小", 3: "undo", 4: "diff"}.get(img_type, f"?{img_type}")
    print(f"[VDI] 类型={type_name}  逻辑容量={cb_disk/1024**3:.1f}GiB  "
          f"块大小={cb_block//1024}KiB ({cb_block}B)  块数={c_blocks}  扇区={cb_sector}B")
    print(f"[VDI] blockmap@0x{off_blocks:X}  data@0x{off_data:X}")
    return off_blocks, off_data, cb_block, c_blocks, cb_disk


def read_at(f, off_blocks, off_data, cb_block, c_blocks, vdi_off, length):
    """从 VDI 的逻辑偏移处读取 length 字节（处理动态块的映射）。"""
    out = bytearray()
    cur = vdi_off
    end = vdi_off + length
    while cur < end:
        blk_idx = cur // cb_block
        if blk_idx >= c_blocks:
            break
        blk_off = cur % cb_block
        # block map 是 u32 数组，0xFFFFFFFF 表示未分配（全零）
        f.seek(off_blocks + blk_idx * 4)
        (data_blk,) = struct.unpack("<I", f.read(4))
        chunk = min(cb_block - blk_off, end - cur)
        if data_blk == 0xFFFFFFFF:
            out.extend(b"\x00" * chunk)
        else:
            f.seek(off_data + data_blk * cb_block + blk_off)
            out.extend(f.read(chunk))
        cur += chunk
    return bytes(out)


def parse_mbr(f, off_blocks, off_data, cb_block, c_blocks):
    mbr = read_at(f, off_blocks, off_data, cb_block, c_blocks, 0, 512)
    if mbr[510:512] != b"\x55\xaa":
        raise ValueError("MBR 签名无效")
    parts = []
    for i in range(4):
        entry = mbr[446 + i * 16: 446 + i * 16 + 16]
        ptype = entry[4]
        if ptype == 0:
            continue
        (lba_start,) = struct.unpack_from("<I", entry, 8)
        (sectors,) = struct.unpack_from("<I", entry, 12)
        parts.append((i, ptype, lba_start, sectors))
        print(f"[MBR] 分区{i}: type=0x{ptype:02X}  起始LBA={lba_start}  "
              f"大小={sectors*512/1024**2:.1f}MiB")
    return parts


def detect_fs(blk):
    for off, magic, name in FS_MAGICS:
        if blk[off:off + len(magic)] == magic:
            return name
    return "未知"


def dump_ext4_super(sb):
    """解析 ext4 superblock（相对分区起始 1024 字节处）。"""
    s = sb[1024:]
    magic = struct.unpack_from("<H", s, 56)[0]
    print(f"         s_magic = 0x{magic:04X}")
    inodes = struct.unpack_from("<I", s, 0)[0]
    blocks_lo = struct.unpack_from("<I", s, 4)[0]
    free_lo = struct.unpack_from("<I", s, 12)[0]
    log_bs = struct.unpack_from("<I", s, 24)[0]
    state = struct.unpack_from("<H", s, 58)[0]
    incompat = struct.unpack_from("<I", s, 96)[0]
    ro_compat = struct.unpack_from("<I", s, 100)[0]
    volume = s[120:136].rstrip(b"\x00").decode("ascii", "replace")

    print(f"         inode数={inodes}  块数={blocks_lo}  空闲={free_lo}  "
          f"块大小={1024 << log_bs}  卷名='{volume}'")
    print(f"         state={'干净' if state == 1 else f'非干净(0x{state:X})'}")

    inc_flags = {
        0x0002: "FILETYPE", 0x0004: "RECOVER(journal)", 0x0040: "EXTENTS",
        0x0080: "64BIT", 0x0200: "FLEX_BG", 0x1000: "DIRDATA",
        0x4000: "LARGEDIR", 0x8000: "INLINE_DATA", 0x10000: "ENCRYPT",
    }
    ro_flags = {
        0x0002: "LARGE_FILE", 0x0010: "GDT_CSUM", 0x0020: "DIR_NLINK",
        0x0040: "EXTRA_ISIZE", 0x0100: "BIGALLOC", 0x0200: "METADATA_CSUM",
        0x1000: "PROJECT", 0x8000: "VERITY", 0x10000: "ORPHAN_PRESENT",
    }
    print(f"         incompat=0x{incompat:08X} → "
          f"{[n for b, n in inc_flags.items() if incompat & b] or '无'}")
    print(f"         ro_compat=0x{ro_compat:08X} → "
          f"{[n for b, n in ro_flags.items() if ro_compat & b] or '无'}")

    if incompat & 0x10000:
        print("         ⚠ 开启了 ext4 文件系统级加密(fscrypt)，"
              "直接挂载可能看到加密文件名")


def main():
    with open(VDI_PATH, "rb") as f:
        off_blocks, off_data, cb_block, c_blocks, cb_disk = parse_vdi_header(f)
        print()
        parts = parse_mbr(f, off_blocks, off_data, cb_block, c_blocks)
        print()
        for idx, ptype, lba, sectors in parts:
            vdi_off = lba * 512
            sb = read_at(f, off_blocks, off_data, cb_block, c_blocks, vdi_off, 4096)
            fs = detect_fs(sb)
            size_gb = sectors * 512 / 1024 ** 3
            print(f"[分区{idx}] 偏移=0x{vdi_off:X}  大小={size_gb:.2f}GiB  →  文件系统: {fs}")
            if fs in ("ext2/ext3/ext4",):
                dump_ext4_super(sb)


if __name__ == "__main__":
    main()
