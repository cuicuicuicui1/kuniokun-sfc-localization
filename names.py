import kuniokun_map as km
orig = open('dl/roms/kuniokun__SF8127.smc','rb').read()
base = 0x48000
blob = orig[base:base+0x400]
# entries: 16 bytes each, text terminated by 0x00 (the copier stops at $00)
codes = set()
for i in range(0, 0x400, 16):
    ent = blob[i:i+16]
    s = ''
    j = 0
    while j < 16 and ent[j] != 0:
        c = ent[j]
        s += km.CHAR.get(c, '{%02X}' % c) if hasattr(km, 'CHAR') else ''
        codes.add(c)
        j += 1
    print('%04X: %-16s | %s' % (base+i, ' '.join('%02X' % b for b in ent[:8]), s))
print('distinct codes in the name table:', len(codes))
def tiles_of(cs):
    base_t = {0x00,0x01} | set(range(0x10,0x20)) | {0x20,0x72,0x85,0x86,0x93}
    for c in cs:
        base_t.add(km.FA[c]); base_t.add(km.FB[c])
    return base_t
t = tiles_of(codes)
pairs = [p for p in range(128) if 2*p not in t and 2*p+1 not in t]
print('name-table codes -> protected %d tiles, free pairs %d' % (len(t), len(pairs)))
