"""Scan all PPU register writes and DMA uploads to build a VRAM usage map."""
import re
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else 'dl/roms/kuniokun__SF8127.smc'
d = open(ROM, 'rb').read()

REGNAMES = {
    0x00: 'INIDISP', 0x01: 'OBSEL', 0x02: 'OAMADDL', 0x03: 'OAMADDH',
    0x05: 'BGMODE', 0x06: 'MOSAIC', 0x07: 'BG1SC', 0x08: 'BG2SC',
    0x09: 'BG3SC', 0x0A: 'BG12NBA', 0x0B: 'BG34NBA',
    0x0C: 'BG1HOFS', 0x0D: 'BG1VOFS', 0x0E: 'BG2HOFS', 0x0F: 'BG2VOFS',
    0x10: 'BG3HOFS', 0x11: 'BG3VOFS', 0x12: 'BG4HOFS', 0x13: 'BG4VOFS',
    0x15: 'VMAIN', 0x16: 'VMADDL', 0x17: 'VMADDH', 0x18: 'VMDATAL',
    0x19: 'VMDATAH', 0x1A: 'M7SEL', 0x1B: 'M7A', 0x1C: 'M7B',
    0x20: 'CGADD', 0x21: 'CGDATA', 0x22: 'W12SEL', 0x23: 'W34SEL',
    0x24: 'WOBJSEL', 0x26: 'WH0', 0x28: 'WBGLOG', 0x2B: 'TM',
    0x2C: 'TS', 0x2E: 'TMW', 0x30: 'CGWSEL', 0x31: 'CGADSUB',
    0x32: 'COLDATA', 0x33: 'SETINI',
}

# STA abs (8D), STA abs,X (9D), STA abs,Y (99): opcode, low, high
pat = re.compile(rb'[\x8d\x9d\x99]([\x00-\x3f])\x21')
hits = {}
for m in pat.finditer(d):
    hits.setdefault(m.group(1)[0], []).append(m.start())

print('=== all writes to $2100-$213F ===')
for reg in sorted(hits):
    name = REGNAMES.get(reg, '?')
    print('  $21%02X %-9s %2d hits  %s' % (reg, name, len(hits[reg]),
          ' '.join('%06X' % o for o in hits[reg][:10])))

print()
print('=== context for the key registers ===')
for reg in (0x05, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x15):
    for o in hits.get(reg, []):
        ctx = ' '.join('%02X' % b for b in d[o - 8:o + 3])
        print('  $21%02X @%06X: %s' % (reg, o, ctx))

print()
print('=== DMA channel setup sites ($43x0-$43x7 writes) ===')
dma = {}
for m in re.finditer(rb'\x8d([\x00-\x7f])\x43', d):
    reg = m.group(1)[0]
    ch = reg >> 4
    dma.setdefault(ch, []).append((reg & 0xF, m.start()))

for ch in sorted(dma):
    sites = sorted(dma[ch], key=lambda t: t[1])
    print('  channel %d: %s' % (ch, ' '.join('$43%X%X@%06X' % (ch, r, o) for r, o in sites[:14])))

print()
print('=== DMA descriptor blocks (contiguous $43x0-$43x7 sequences) ===')
seen = set()
for m in re.finditer(rb'\x8d([\x00-\x7f])\x43', d):
    reg = m.group(1)[0]
    if reg & 0xF:
        continue
    ch = reg >> 4
    o = m.start()
    # walk forward collecting up to 8 register writes of this channel
    vals = {}
    pos = o
    end = min(len(d), o + 160)
    while pos < end:
        mm = re.match(rb'\xa9([\x00-\xff])\x8d' + bytes([reg + 1]) + rb'\x43', d[pos:pos + 5])
        if mm:
            vals[1] = mm.group(1)[0]
            pos += 5
            continue
        mm = re.match(rb'\xa9([\x00-\xff])\x8d' + bytes([reg + 2]) + rb'\x43', d[pos:pos + 5])
        if mm:
            vals[2] = mm.group(1)[0]
            pos += 5
            continue
        break
    print('  ch%d @%06X B-bus/ctrl=... vals=%s' % (ch, o, vals))