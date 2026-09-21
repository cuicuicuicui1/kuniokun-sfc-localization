"""Audit a patched ROM: for each of the 1013 known entries, check what bytes sit at its
offset -- my Chinese encoding (2-byte prefix $C0-$D8 / single-byte $DC-$DF), leftover
Japanese, or a mismatch.  Also verify the pointer tables are intact.

usage: python audit_rom.py <rom> [translation.json]
"""
import json
import sys

ROM = sys.argv[1] if len(sys.argv) > 1 else 'kuniokun_cn.smc'
ORIG = 'dl/roms/kuniokun__SF8127.smc'

tr = json.load(open('cn_translation.json', encoding='utf-8'))
d = open(ROM, 'rb').read()
o = open(ORIG, 'rb').read()

TABLES = [
    ('items ', 0x01DCA1, 0x01E096),
    ('menuA ', 0x01E0DE, 0x01E1D2),
    ('menuB ', 0x01E239, 0x01E4CB),
    ('menuC ', 0x01E5C6, 0x01E981),
    ('main  ', 0x019921, 0x01DBC2),
]


def table_of(off):
    for name, a, b in TABLES:
        if a <= off < b:
            return name
    return '??????'


def span(rom, off):
    e = rom.index(b'\xF2', off)
    return rom[off:e], e


stats = {}
bad = []
for off_s in sorted(tr, key=lambda k: int(k, 16)):
    off = int(off_s, 16)
    tab = table_of(off)
    cur, cur_end = span(d, off)
    old, old_end = span(o, off)
    # how many bytes of the *original* span are still present verbatim
    cn_bytes = sum(1 for b in cur if 0xC0 <= b <= 0xDF)
    same = (cur == old)
    st = stats.setdefault(tab, [0, 0, 0])   # [entries, with-cn-code, byte-identical-to-jp]
    st[0] += 1
    if cn_bytes:
        st[1] += 1
    if same:
        st[2] += 1
        bad.append((off_s, tab, 'IDENTICAL-TO-JAPANESE', old.hex()))

print('rom: %s (%d bytes)' % (ROM, len(d)))
print('%-7s %6s %8s %10s' % ('table', 'n', 'has_cn', '==japanese'))
for k in sorted(stats):
    n, c, s = stats[k]
    print('%-7s %6d %8d %10d' % (k, n, c, s))
print()
print('entries byte-identical to the japanese original: %d' % len(bad))
for b in bad[:30]:
    print('   ', b)