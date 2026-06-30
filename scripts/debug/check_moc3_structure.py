#!/usr/bin/env python3
"""Check moc3 internal structure"""

import struct

with open(r'D:\Azur Lane Assets\Output\Live2D\lingbo\lingbo.moc3', 'rb') as f:
    data = f.read()

print(f'Total size: {len(data)} bytes')

# Find last significant byte
last_sig = len(data) - 1
while last_sig > 0 and data[last_sig] in (0x00, 0xFF):
    last_sig -= 1
print(f'Last significant byte at offset: {last_sig}')
print(f'Potential trailing garbage: {len(data) - last_sig - 1} bytes')

# Print header values that are non-zero
offset = 8
print('\nNon-zero header values:')
for i in range(30):
    val = struct.unpack_from('<I', data, offset + i*4)[0]
    if val != 0:
        print(f'  [{offset + i*4:4d}] = {val}')

# Check if the moc3 data is self-contained
# by verifying that all section offsets point within the file
print('\nChecking section offsets (at header positions 56-120):')
for i in range(16):
    val = struct.unpack_from('<I', data, 56 + i*4)[0]
    if val != 0 and val < len(data):
        print(f'  [{56 + i*4}] = {val} (within file)')
    elif val >= len(data):
        print(f'  [{56 + i*4}] = {val} (OUTSIDE FILE!)')
