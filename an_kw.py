"""an_kw.py <vram dump> ... : classify every cell of the box's text rows.
A cell holds (upper tile, lower tile).  Classification is per cell:
  FONT    the pair equals the game's own font entry (FB[code], FA[code])
  LEFTx   the upper tile is one of my slot table's LEFT pairs (value v, v+1):
          half of a 16x16 glyph -- its bytes are compared with the pool
  RIGHTx  same for the RIGHT pairs (the other half of that glyph)
  blank   $2C00 in both cells
So a 16x16 glyph shows as one LEFTx cell followed by one RIGHTx cell, and the
two halves are checked byte for byte against the pool rom.  No eyeballing."""
import sys
import json
import cnbuild5 as cb
import kuniokun_map as km

DUMP = 0x4000


def main():
    params = json.load(open('cn_build_params.json', encoding='utf-8'))
    nslot = params['slots']
    cb.clamp_slots()          # the real slot count, not the module default
    rom = open(cb.OUT_ROM, 'rb').read()
    # 10 bit tiles: the label pair sets sit outside the font window.  The maps
    # cover every entry, so a speaker label cell classifies too (its glyph data
    # lives in the label storage, so its bytes are not compared with the pool).
    nent = (cb.SLOTS + cb.LABEL_GLYPHS * cb.LABEL_SETS
            + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS)
    hi = list(rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * nent])
    left = [rom[cb.E3_SLOTPAIR + i] | (hi[i] << 8) for i in range(nent)]
    right = [rom[cb.E3_SLOTPAIR + nent + i] | (hi[nent + i] << 8)
             for i in range(nent)]
    lmap = {t: i for i, t in enumerate(left)}
    rmap = {t: i for i, t in enumerate(right)}
    font = {}
    for code in range(256):
        font[(km.FB[code], km.FA[code])] = code
    for path in sys.argv[1:]:
        dump = open(path, 'rb').read()
        if len(dump) != DUMP:
            print('%s: size %d != %d' % (path, len(dump), DUMP))
            continue
        w = [dump[2 * i] + dump[2 * i + 1] * 256 for i in range(DUMP // 2)]

        def cell(addr):
            return w[addr - 0x6000] & 0x3FF, w[addr + 0x20 - 0x6000] & 0x3FF

        def half(t):
            return bytes(b for x in w[t * 8:t * 8 + 16] for b in (x & 0xFF, x >> 8))

        def pool_bytes(slot):
            off = cb.POOL_ROM + 0  # placeholder, real offset needs the page
            return off

        def pool_of(slot):
            """every page's bytes for this slot, to name the glyph by content"""
            hits = []
            for page in range(0, 32):
                off = cb.POOL_ROM + page * 0x8000 + slot * cb.POOL_STRIDE
                if off + cb.POOL_STRIDE <= len(rom):
                    hits.append((page, rom[off:off + cb.POOL_STRIDE]))
            return hits

        print('== %s' % path)
        tally = {}
        for row in range(16):
            out = []
            for col in range(3, 29):
                tu, tl = cell(0x7C00 + row * 0x40 + col)
                if tu == 0 and tl == 0 and w[0x7C00 + row * 0x40 + col - 0x6000] == 0x2C00:
                    out.append('c%-2d blank' % col)
                    continue
                if (tu, tl) in font and tu in (0, 1) or ((tu, tl) in font and tu < 0x40):
                    tag = 'c%-2d FONT $%02X' % (col, font[(tu, tl)])
                    tally['FONT'] = tally.get('FONT', 0) + 1
                elif tu in lmap and tl == tu + 1:
                    slot = lmap[tu]
                    ru, rl = cell(0x7C00 + row * 0x40 + col + 1)
                    got = half(tu)
                    name = ''
                    if slot < cb.SLOTS:
                        for page, blob in pool_of(slot):
                            if blob[:32] == got:
                                name += ' p%d' % page
                        if not name:
                            name = ' MISMATCH'
                            tally['LEFT-MISMATCH'] = tally.get('LEFT-MISMATCH', 0) + 1
                    tag = 'c%-2d LEFT s%-2d t%03X%s' % (col, slot, tu, name)
                    tally['LEFT'] = tally.get('LEFT', 0) + 1
                elif tu in rmap and tl == tu + 1:
                    slot = rmap[tu]
                    got = half(tu)
                    name = ''
                    if slot < cb.SLOTS:
                        for page, blob in pool_of(slot):
                            if blob[32:] == got:
                                name += ' p%d' % page
                        if not name:
                            name = ' MISMATCH'
                            tally['RIGHT-MISMATCH'] = tally.get('RIGHT-MISMATCH', 0) + 1
                    tag = 'c%-2d RIGHT s%-2d t%03X%s' % (col, slot, tu, name)
                    tally['RIGHT'] = tally.get('RIGHT', 0) + 1
                else:
                    tag = 'c%-2d ? %03X/%03X' % (col, tu, tl)
                    tally['?'] = tally.get('?', 0) + 1
                out.append(tag)
            if out:
                print(' r%-2d %s' % (row, '  '.join(out)))
        print(' tally: %s' % tally)


if __name__ == '__main__':
    main()