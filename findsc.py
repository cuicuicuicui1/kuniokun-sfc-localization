"""Find every store to PPU registers $2105-$210C / $210A-$210B with any opcode."""
d = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

OPS = {
    0x8D: 'STA abs', 0x9D: 'STA abs,X', 0x99: 'STA abs,Y',
    0x8F: 'STA long', 0x8C: 'STY abs', 0x8E: 'STX abs',
    0x9C: 'STZ abs', 0x9E: 'STZ abs,X', 0x81: 'STA (dp,X)',
    0x91: 'STA (dp),Y', 0x85: 'STA dp', 0x95: 'STA dp,X',
}

targets = [0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C]
found = {}
for i in range(len(d) - 3):
    op = d[i]
    if op not in OPS:
        continue
    if d[i + 1] in targets and d[i + 2] == 0x21:
        found.setdefault(d[i + 1], []).append((i, op))

NAMES = {0x05: 'BGMODE', 0x06: 'MOSAIC', 0x07: 'BG1SC', 0x08: 'BG2SC',
         0x09: 'BG3SC', 0x0A: 'BG12NBA', 0x0B: 'BG34NBA', 0x0C: 'unused'}

for reg in targets:
    hits = found.get(reg, [])
    print('$21%02X %-8s : %d hits' % (reg, NAMES[reg], len(hits)))
    for off, op in hits:
        print('    %06X  %s   ctx: %s' % (off, OPS[op], ' '.join('%02X' % b for b in d[off - 10:off + 5])))

print()
print('=== search for any reference to $2107/$210A/$210B as data (tables) ===')
for pat, lbl in ((b'\x07\x21', '$2107'), (b'\x0a\x21', '$210A'), (b'\x0b\x21', '$210B'),
                 (b'\x68\x21', '$2168')):
    i = 0
    hits = []
    while True:
        j = d.find(pat, i)
        if j < 0:
            break
        hits.append(j)
        i = j + 1
    print('%s: %d occurrences at %s' % (lbl, len(hits), ' '.join('%06X' % h for h in hits[:12])))
    for h in hits[:6]:
        print('    ctx: %s' % ' '.join('%02X' % b for b in d[h - 8:h + 6]))