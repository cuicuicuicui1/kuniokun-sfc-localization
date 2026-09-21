"""Find where the text cursor $20/$21 (VRAM tilemap address) is set."""
d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()


def find_all(pat, lo=0, hi=None):
    hi = len(d) if hi is None else hi
    out = []
    i = lo
    while True:
        j = d.find(pat, i, hi)
        if j < 0:
            break
        out.append(j)
        i = j + 1
    return out


print('=== STA $20 (85 20) sites ===')
for o in find_all(b'\x85\x20'):
    print('  %06X: %s' % (o, ' '.join('%02X' % b for b in d[o - 10:o + 4])))

print()
print('=== STA $21 (85 21) sites ===')
for o in find_all(b'\x85\x21'):
    print('  %06X: %s' % (o, ' '.join('%02X' % b for b in d[o - 10:o + 4])))

print()
print('=== LDA #$20 / #$21 immediate setups ===')
for pat in (b'\xa9\x20\x85\x20', b'\xa9\x20\x85\x21', b'\xa9\x21\x85\x20',
            b'\xa9\x21\x85\x21', b'\xa9\x7c\x85\x21', b'\xa9\x78\x85\x21',
            b'\xa9\x70\x85\x21', b'\xa9\x60\x85\x21'):
    for o in find_all(pat):
        print('  %06X: %s' % (o, ' '.join('%02X' % b for b in d[o - 6:o + 6])))

print()
print('=== window around the text renderer 0x00F940-0x00FCE0: all $2116/$2117 writes ===')
for pat in (b'\x8d\x16\x21', b'\x8d\x17\x21', b'\x8d\x15\x21', b'\x8d\x18\x21', b'\x8d\x19\x21'):
    for o in find_all(pat, 0x00F800, 0x00FE00):
        print('  %06X: %s' % (o, ' '.join('%02X' % b for b in d[o - 12:o + 3])))