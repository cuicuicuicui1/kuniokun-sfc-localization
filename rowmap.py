import zlib
rom = open('kuniokun_cn.smc','rb').read()
v = open('hw/v42a_vram.bin','rb').read()      # VRAM bytes 0xC000..0xFFFF = words $6000..$7FFF
def wb(word):                                  # read VRAM word (as 2 bytes)
    o = (word - 0x6000) * 2
    return v[o] | (v[o+1] << 8)
SLOTS = 53
left  = [rom[0x1F0180+s] for s in range(SLOTS)]
right = [rom[0x1F0180+SLOTS+s] for s in range(SLOTS)]
mine = {}
for s in range(SLOTS):
    for t in (2*left[s], 2*left[s]+1, 2*right[s], 2*right[s]+1):
        mine[t] = s
print('my tiles: %d distinct' % len(mine))
# box tilemap rows: words $7C00 + row*0x40 + 3 + col  (upper) and +0x20 (lower)
for row in range(6):
    hits = []
    for col in range(26):
        w = wb(0x7C00 + row*0x40 + 3 + col)
        t = w & 0x3FF
        if t in mine:
            hits.append('c%02d:t%03X(s%d)' % (col, t, mine[t]))
        lo = wb(0x7C00 + row*0x40 + 3 + 32 + col)
        tlo = lo & 0x3FF
        if tlo in mine:
            hits.append('c%02dL:t%03X(s%d)' % (col, tlo, mine[tlo]))
    print('row %d: %s' % (row, ' '.join(hits) if hits else '(none)'))
# what is in rows 0..3 first cells (to see blank fill / border)
for row in range(4):
    print('row %d words: %s' % (row, ' '.join('%04X' % wb(0x7C00+row*0x40+3+c) for c in range(0, 16))))
