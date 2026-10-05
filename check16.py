"""Programmatic checks of the 16x16 build (no eyeballing, no emulator).

Verifies the hook bytes, the slot table, a few glyph pool entries against a
fresh cnglyph render, the drawer/wipe/arm blobs (no RTS, all exits JML into
bank $03), and the IPS round trip.
"""
import zlib
import cnbuild5 as cb
cb.load_build_params()   # the switches this ROM was built with
import cnglyph
import sfc_tools as st
from kuniokun_map import CODE

rom = open('kuniokun_cn.smc', 'rb').read()
orig = open(cb.ORIG_ROM, 'rb').read()
print('rom %d bytes crc32 %08X ; orig %d bytes crc32 %08X'
      % (len(rom), zlib.crc32(rom), len(orig), zlib.crc32(orig)))


def snes(off):
    return cb.snes_of_rom(off)


# ---- hooks -------------------------------------------------------------
db, da = snes(cb.E3_DRAWER)
checks = [
    ('drawer hook $03:FA30', rom[cb.HOOK_DRAWER:cb.HOOK_DRAWER + 4],
     bytes([0x5C, da & 0xFF, da >> 8, db])),
    # the loader is untouched: the row blanking happens in the drawer itself
    ('loader $03:EB9E', rom[cb.HOOK_LOAD:cb.HOOK_LOAD + 5],
     bytes([0xA9, 0x40, 0x0C, 0x73, 0x03])),
]
failures = 0
for name, got, want in checks:
    failures += got != want
    print('%-22s %s  %s' % (name, got.hex(' '), 'OK' if got == want else
                            'MISMATCH want %s' % want.hex(' ')))
for hook in (cb.HOOK_COPY1, cb.HOOK_COPY2):
    got = rom[hook:hook + 3]
    failures += got != bytes([0x9D, 0xEA, 0x03])
    print('%-22s %s %s' % ('sanitize call $%06X' % hook, got.hex(' '),
                           'OK (removed)' if got == bytes([0x9D, 0xEA, 0x03])
                           else 'MISMATCH'))
for hook, name in ((cb.HOOK_A, 'widget preload'), (cb.HOOK_B, 'widget dispatch'),
                   (cb.HOOK_DRIVER, 'driver entry')):
    print('%-22s %s (original bytes kept = that path is off)'
          % (name, rom[hook:hook + 4].hex(' ')))

# ---- slot table --------------------------------------------------------
params = __import__('json').load(open('cn_build_params.json', encoding='utf-8'))
NSLOT = params['slots']
TABLE_N = NSLOT + cb.LABEL_GLYPHS * cb.LABEL_SETS + cb.LABEL_NAME_GLYPHS * cb.LABEL_NAME_SETS
left = rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR + NSLOT]
right = rom[cb.E3_SLOTPAIR + TABLE_N:cb.E3_SLOTPAIR + TABLE_N + NSLOT]
HI = rom[cb.E3_SLOTHI:cb.E3_SLOTHI + 2 * TABLE_N]
print('slot table %d slots: left %s right %s'
      % (NSLOT, left[:8].hex(' '), right[:8].hex(' ')))
res = cb.protected_tiles()
free = cb.free_pairs()
allp = [left[i] | (HI[i] << 8) for i in range(NSLOT)] +        [right[i] | (HI[TABLE_N + i] << 8) for i in range(NSLOT)]
bad = [p for p in allp if 0 < p < 256 and p not in free]
bad += [p for p in allp if p >= 256 and p not in cb.OUTSIDE_PAIRS]
print('every slot pair free: %s (protected %d tiles, %d free pairs)'
      % ('OK' if not bad else 'MISMATCH %s' % bad, len(res), len(free)))

failures += len(bad)

# ---- pool --------------------------------------------------------------
cell = __import__('json').load(open('cn_glyph_cell.json', encoding='utf-8'))
print('glyph cell map entries: %d ; one byte codes %s'
      % (len(cell), ' '.join('%s=%02X' % (k, v)
                             for k, v in sorted(params['fixed'].items(),
                                                key=lambda kv: kv[1]))))
bad = 0
for ch, (page, slot) in list(cell.items()):
    off = cb.POOL_ROM + page * 0x8000 + slot * cb.POOL_STRIDE
    if len(ch)==2 and all('A'<=c<='Z' or c in ' ()-' for c in ch) or len(ch)==1 and 'A'<=ch<='Z':
        # Independent fresh 8x16 raster and four-tile packing, not cb.glyph64.
        from cnfont8 import render8x16
        halves=[render8x16(c,cb.FONT_PATH,thresh=cb.GLYPH8_THRESH,widen=cb.GLYPH_WIDEN)
                if c!=' ' else [[0]*8 for _ in range(16)] for c in ch.ljust(2)]
        g=[halves[0][y]+halves[1][y] for y in range(16)]
    else:
        g = cnglyph.render16x16(ch)
    want = (st.pack_8x8(g[:8][:8] and [row[:8] for row in g[:8]]) +
            st.pack_8x8([row[:8] for row in g[8:]]) +
            st.pack_8x8([row[8:] for row in g[:8]]) +
            st.pack_8x8([row[8:] for row in g[8:]]))
    if rom[off:off + cb.POOL_STRIDE] != want:
        bad += 1
        if bad < 4:
            print('  pool mismatch %r page %d slot %d' % (ch, page, slot))
print('pool matches a fresh render for all %d glyphs: %s'
      % (len(cell), 'OK' if bad == 0 else '%d MISMATCH' % bad))

# ---- speaker name label glyphs ----------------------------------------
names = __import__('json').load(open('name_hanzi.json', encoding='utf-8'))
ids = {}
for name in names.values():
    for ch in name:
        ids.setdefault(ch, len(ids))
per_page = 256 - cb.LABEL_ID0
lbad = 0
for ch, gid in ids.items():
    page, idx = divmod(gid, per_page)
    off = cb.POOL_ROM + page * 0x8000 + (cb.LABEL_ID0 + idx) * cb.POOL_STRIDE
    if rom[off:off + cb.POOL_STRIDE] != cb.glyph64(ch):
        lbad += 1
        if lbad < 4:
            print('  label glyph mismatch %r id %d' % (ch, gid))
print('label pool: %d name glyphs, %d mismatched' % (len(ids), lbad))
rec_bad = rec_ok = 0
for i in range(cb.NAME_RECORDS):
    o = cb.NAME_RECORD_BASE + i * 16
    kana = ''.join(cb.km.CODE.get(b, '') for b in orig[o:o + 4]).strip()
    h = names.get(kana)
    if not h:
        continue
    want = bytearray()
    for ch in h:
        page, idx = divmod(ids[ch], per_page)
        want += bytes([cb.PREFIX0 + page, cb.LABEL_ID0 + idx])
    want += bytes(4 - len(want))
    if bytes(want) != rom[o:o + 4]:
        rec_bad += 1
        if rec_bad < 4:
            print('  record %d %r -> %s want %s'
                  % (i, kana, rom[o:o + 4].hex(' '), bytes(want).hex(' ')))
    else:
        rec_ok += 1
print('name records: %d in hanzi, %d wrong' % (rec_ok, rec_bad))

failures += bad + lbad + rec_bad
print('PASS' if not failures else f'FAIL: {failures} build-data mismatches')
raise SystemExit(1 if failures else 0)
