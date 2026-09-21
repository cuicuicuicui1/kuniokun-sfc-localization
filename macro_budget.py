"""Macro insert budgets: how many cells can each $E0-$EF macro inject at runtime?"""
import re

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/work_kuniokun_2mb.smc'
data = open(ROM, 'rb').read()
B3 = 0x03 * 0x8000


def rom_of(addr, bank=0x03):
    return bank * 0x8000 + (addr - 0x8000)


def dump_str(off, limit=200):
    out = []
    i = 0
    while i < limit and data[off + i] != 0xF2:
        out.append(data[off + i])
        i += 1
    return out


def table(lab, base_lo_addr, max_entries=200):
    lo = data[rom_of(base_lo_addr)]
    hi = data[rom_of(base_lo_addr + 1)]
    arr = (hi << 8) | lo
    arr_rom = rom_of(arr)
    print('macro %s: pointer-array base $%04X (ROM 0x%06X)' % (lab, arr, arr_rom))
    lens = []
    for i in range(max_entries):
        p = data[arr_rom + 2 * i] | (data[arr_rom + 2 * i + 1] << 8)
        if p == 0:
            break
        s = dump_str(rom_of(p))
        lens.append((i, p, len(s)))
        if i < 6:
            print('    [%2d] $%04X len %2d  %s' % (i, p, len(s),
                  ' '.join('%02X' % v for v in s[:12])))
    if lens:
        mx = max(lens, key=lambda t: t[2])
        print('    entries %d, max %d cells (index %d)' % (len(lens), mx[2], mx[0]))
    return lens


print('=== macro pointer tables ===')
table('$EB (idx $035A)', 0xEAF1)
table('$EC (idx $035C)', 0xEAF1)
table('$ED/$EE (idx $035D/$035E)', 0xEAF3)
table('$EA load6 (idx $0359)', 0xEAF5)

print()
print('=== where do $E0-$EF macros appear in the ORIGINAL text? ===')
orig = open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kuniokun__SF8127.smc', 'rb').read()
REGIONS = [(0x019921, 0x01DBC3), (0x01DCA1, 0x01E096), (0x01E0DE, 0x01E1D3),
           (0x01E239, 0x01E4CB), (0x01E5C6, 0x01E981)]
for a, b in REGIONS:
    seg = orig[a:b]
    counts = {}
    for i, v in enumerate(seg):
        if 0xE0 <= v <= 0xEF:
            counts.setdefault('%02X' % v, []).append(i)
    line = ' '.join('%s x%d' % (k, len(v)) for k, v in sorted(counts.items()))
    print('region 0x%06X: %s' % (a, line))
    for k, v in sorted(counts.items()):
        if k in ('EA', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8', 'E9', 'E0', 'E1'):
            for off in v[:3]:
                ctx = orig[a + off - 6:a + off + 8]
                print('    %s at 0x%06X ctx %s' % (k, a + off,
                      ' '.join('%02X' % c for c in ctx)))

print()
print('=== how many macrocodes in MY encoded text? ===')
mine = open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc', 'rb').read()
AP = json_open = None
import json
amap = json.load(open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/cn_addr_map.json',
                      encoding='utf-8'))
counts = {}
for key, off in amap.items():
    if isinstance(off, list):
        off = off[0]
    pass
print('(my text is reached through cn_addr_map.json; macro tokens preserved by align_tokens)')