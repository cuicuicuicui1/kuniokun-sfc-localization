import json
import kuniokun_map as km
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
cn   = open('kuniokun_cn.smc','rb').read()

# 1) locate the speaker-name table by searching for the known runtime bytes 'りき'+2 spaces+':'
pat = bytes([0x47, 0x26, 0x00, 0x00, 0x09])
hits = []
i = orig.find(pat)
while i >= 0 and len(hits) < 20:
    hits.append(i); i = orig.find(pat, i+1)
print('name-table pattern hits (ROM offsets):', [hex(h) for h in hits])
for h in hits[:3]:
    bank = h // 0x8000
    print('  at bank $%02X offset $%04X' % (bank, 0x8000 + h % 0x8000))

# 2) codes used by the untranslated item table (region 0x01DCA1..0x01E096) - segment-wise, stop at F2/F3 style
reg = orig[0x01DCA1:0x01E096]
codes_item = set(b for b in reg if b < 0xE0)
print('item region bytes', len(reg), 'distinct codes <E0:', len(codes_item))

# 3) codes anywhere in the original text regions (< 0xE0)
regions = [(0x019921,0x01DBC3),(0x01DCA1,0x01E096),(0x01E0DE,0x01E1D3),(0x01E239,0x01E4CC),(0x01E5C6,0x01E982)]
codes_all = set()
for a,b in regions:
    codes_all |= set(x for x in orig[a:b] if x < 0xE0)
print('codes in all original text regions:', len(codes_all))

# 4) name table span: assume a table of 16-byte entries before/around the hit; collect < 0xE0 in a window
if hits:
    h = hits[0]
    win = orig[max(0,h-0x200):h+0x200]
    codes_names = set(x for x in win if x < 0xE0)
    print('codes in +-0x200 around name table:', len(codes_names))

# 5) what the ORIGINAL 8x16 build protected (reconstruct): FA/FB of codes <0xE0 used by...? just report tile usage
base = {0x00,0x01} | set(range(0x10,0x20)) | {0x20,0x72,0x85,0x86,0x93}
def tiles_of(codes):
    res = set(base)
    for c in codes:
        res.add(km.FA[c]); res.add(km.FB[c])
    return res
for label, cs in (('item only', codes_item), ('item+names', codes_item | (codes_names if hits else set())), ('all text regions', codes_all)):
    t = tiles_of(cs)
    pairs = [p for p in range(128) if 2*p not in t and 2*p+1 not in t]
    print('%-16s codes %3d -> protected tiles %3d, free pairs %3d, slots(pair-pair) %2d' % (label, len(cs), len(t), len(pairs), len(pairs)//2))
# 6) digit codes
print('digit/symbol codes:', {ch: km.CODE.get(ch) for ch in '0123456789:!?.,-/'})
