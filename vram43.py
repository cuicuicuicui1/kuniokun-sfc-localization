# -*- coding: utf-8 -*-
"""Decode the box tile map from a VRAM dump (bytes 0xC000-0xFFFF = words $6000-$7FFF).
Show rows 0..5, columns 0..25: upper-half word and lower-half word per column."""
import sys
import io

dump = open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/v43a_vram.bin', 'rb').read()
base = 0x0                         # the dump starts at VRAM byte $C000
ROM = open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc', 'rb').read()


def word(w):
    o = base + (w - 0x6000) * 2
    return dump[o] | (dump[o + 1] << 8)


for row in range(6):
    up = [word(0x7C00 + row * 0x40 + 3 + c) for c in range(26)]
    lo = [word(0x7C00 + row * 0x40 + 3 + 32 + c) for c in range(26)]
    print('row %2d upper: %s' % (row, ' '.join('%03X' % (v & 0x3FF) for v in up)))
    print('       lower: %s' % (' '.join('%03X' % (v & 0x3FF) for v in lo)))
    print('       attrs: %s' % (' '.join('%X' % (v >> 10) for v in up)))

# what the slots should be: 猪 肉 包 一 个 tiles
print()
for t in (0x98, 0x77, 0xE0, 0xE1, 0xF0):
    o = base + t * 16
    same = dump[o:o + 16] == ROM[0x0F8000 + t * 16:0x0F8000 + t * 16 + 16]
    print('tile %02X: bytes %s  == rom font %s' % (t, dump[o:o + 16].hex(' '), same))
for t in (0x57, 0x58, 0x59, 0x5A, 0xB7, 0xB8, 0xB9, 0xBA):
    o = base + t * 16
    print('tile %02X: %s' % (t, dump[o:o + 16].hex(' ')))