"""Dump every translated entry as (rom_offset, index, japanese_original, chinese) for review."""
import json
import io
import kuniokun_map as km

adj = json.load(open('cn_addr_map.json', encoding='utf-8'))
tr = json.load(open('cn_translation.json', encoding='utf-8'))

orig = open(km.ROM, 'rb').read()

# group entries by which table they belong to, using the known layout
TABLES = [
    ('items   ', 0x01DCA1, 0x01E096),
    ('menuA   ', 0x01E0DE, 0x01E1D2),
    ('menuB   ', 0x01E239, 0x01E4CB),
    ('menuC   ', 0x01E5C6, 0x01E981),
    ('main    ', 0x019921, 0x01DBC2),
]


def table_of(off):
    for name, a, b in TABLES:
        if a <= off < b:
            return name
    return '???????'


out = io.open('pairs.txt', 'w', encoding='utf-8')
for off_s, cn in sorted(tr.items(), key=lambda kv: int(kv[0], 16)):
    off = int(off_s, 16)
    end = orig.index(b'\xF2', off)
    jp, _ = km.decode(orig, off, maxlen=end - off)
    jp = jp.replace('\n', '/')
    out.write('%s %s [%06X] JP: %s\n' % (table_of(off), off_s, off, jp))
    out.write('%s %s [%06X] CN: %s\n' % (' ' * 8, off_s, off, cn))
out.close()
print('wrote pairs.txt')
# quick stats
import collections
c = collections.Counter(table_of(int(k, 16)) for k in tr)
print(c)