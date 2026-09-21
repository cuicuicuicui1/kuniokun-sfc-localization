"""Build the Chinese-patched kuniokun ROM  (design v3 - self-contained dispatcher).

Renderer hooks (all offsets verified byte-for-byte against the original ROM):
  0x00FC79 (4) -> JML $3E:8000     (was LDA $03DBC3,X)
  0x00FC85 (2) -> EA EA            (was LDA #$03, so my bank in $24 survives)
  0x00FC92 (4) -> JML $3E:8057     (was LDA [$22],Y ; CMP #$F2)

Chinese code = 2 bytes: [0xF8+page][id]
  glyph number g = page*256 + id  (page 0..3 -> 1024 glyphs)
  glyph data     = bank ($21+page) : ($8000 + id*32)   (32 bytes = 8x16 = 2 tiles)
  VRAM slot      = ($20 & 0x7F)   -> tiles slot*2, slot*2+1 at VRAM $6000
  glyph is DMA'd into its slot on EVERY draw, so no cache and no RAM are needed,
  and two different glyphs can never share tiles on screen.
Text stays in bank $03 (the area freed by dropping the Japanese text), so the
original 2-byte pointer tables keep working untouched.
"""
import json
import os
import re
import sys

import kuniokun_map as km
from cnfont8 import render8x16

GLYPH_THRESH = 140
GLYPH_WIDEN = 1.12
from sfc_tools import pack_8x8, make_ips

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
SRC_ROM = BASE + '/work_kuniokun_2mb.smc'           # already expanded to 2 MB
OUT_ROM = BASE + '/kuniokun_cn.smc'
ORIG_ROM = BASE + '/dl/roms/kuniokun__SF8127.smc'
FONT_PATH = 'C:/Windows/Fonts/msyh.ttc'

CODE_ROM = 0x1F0000
PRELOAD_ROM = CODE_ROM                 # $3E:8000
DISPATCH_ROM = CODE_ROM + 0x80         # $3E:8080
SLOTTAB_ROM = CODE_ROM + 0x180         # $3E:8180 (128 x slot -> tile pair base)
POOL_ROM = 0x108000                    # bank $21 onward
TEXT_AREA = 0x019921                   # bank $03 text area
TEXT_END = 0x01E982
MAX_SLOTS = 128
PAGES = 8                              # codes 0xF8..0xFF -> banks $21..$28, 2048 slots

TABLES = [(0x0193B5, 694), (0x01DBC5, 110), (0x01E098, 35),
          (0x01E1D5, 50), (0x01E4CE, 124)]

# Each table's messages live in their own region of bank $03, and the five
# regions are separated by the pointer tables themselves (which must not move:
# six loaders address them through the base table at ROM 0x01EAEB).  The engine
# also walks a region byte by byte counting 0xF2 delimiters, so rebuilt text
# must stay densely packed in the original order.
REGIONS = [(0x019921, 0x01DBC3), (0x01DCA1, 0x01E096), (0x01E0DE, 0x01E1D3),
           (0x01E239, 0x01E4CC), (0x01E5C6, 0x01E982)]

# Characters that keep their original single-byte code, which saves one byte
# each and reuses the original font glyph.  Their tiles are protected in the
# slot table.  Add katakana here if the text ever needs more room.
KEEP1 = {'!': 0x01, ':': 0x09, '?': 0x0C}

# Tiles the surviving original codes still need: the structural codes
# ($E2/$E3/$E7/$EA..$F7) all render the box tile, and the original decor
# routine writes five glyph tiles of its own.
DECOR_TILES = (0x20, 0x72, 0x85, 0x86, 0x93)

HOOK_A = 0x00FC79
HOOK_KEEP_BANK = 0x00FC85
HOOK_B = 0x00FC92



def snes_of_rom(off):
    return (off // 0x8000, 0x8000 + (off % 0x8000))


def build_preload():
    """Entered in place of `LDA $03DBC3,X`. Sets $22/$23/$24 from the pointer
    table, then JMLs back to 0x00FC7F (skipping the original `STA $22`)."""
    b = bytearray([
        0xBF, 0xC3, 0xDB, 0x03,   # LDA $03DBC3,X
        0x85, 0x22,               # STA $22
        0xBF, 0xC4, 0xDB, 0x03,   # LDA $03DBC4,X
        0x85, 0x23,               # STA $23
        0xE2, 0x30,               # SEP #$30
        0xA9, 0x03,               # LDA #$03
        0x85, 0x24,               # STA $24
    ])
    cb, ca = snes_of_rom(0x00FC89)
    b += bytes([0x5C, ca & 0xFF, ca >> 8, cb])   # JML $01:FC89 (LDA #$81 ...)
    return bytes(b)


def build_dispatch():
    """Entered in place of `LDA [$22],Y ; CMP #$F2` at 0x00FC92.
    A already holds the code byte; Y is the string index; M/X are 8-bit."""
    b = bytearray()
    pos = {}

    def br(op, key):
        pos[key] = len(b)
        b.extend([op, 0x00])

    def jml(key, rom_off):
        pos[key] = len(b)
        bk, ad = snes_of_rom(rom_off)
        b.extend([0x5C, ad & 0xFF, ad >> 8, bk])

    b += bytes([0xB7, 0x22])            # LDA [$22],Y
    b += bytes([0xC9, 0xF2])            # CMP #$F2
    br(0xD0, 'bne_notdone')             # BNE -> not F2
    jml('done', 0x00FCC6)               # F2 -> original RTS path (Y at the F2)
    pos['notdone'] = len(b)
    b += bytes([0xC9, 0xF8])            # CMP #$F8
    br(0xB0, 'bcs_cn')                  # >= $F8 -> Chinese
    jml('normal', 0x00FC98)             # else original path (A intact)

    # ---------------- Chinese path ----------------
    pos['cn'] = len(b)
    b += bytes([0x38])                  # SEC
    b += bytes([0xE9, 0xF8])            # SBC #$F8      -> page
    b += bytes([0x18])                  # CLC
    b += bytes([0x69, 0x21])            # ADC #$21      -> glyph bank
    b += bytes([0x8D, 0x14, 0x43])      # STA $4314     (DMA source bank)
    b += bytes([0xC8])                  # INY
    b += bytes([0xB7, 0x22])            # LDA [$22],Y   -> id
    b += bytes([0xC2, 0x20])            # REP #$20
    b += bytes([0x0A]) * 5              # ASL x5 -> id*32
    b += bytes([0x09, 0x00, 0x80])      # ORA #$8000
    b += bytes([0x8D, 0x12, 0x43])      # STA $4312 (lo/hi)
    b += bytes([0xE2, 0x20])            # SEP #$20
    b += bytes([0xA9, 0x01])            # LDA #$01
    b += bytes([0x8D, 0x10, 0x43])      # STA $4310  (mode 1: $2118/$2119)
    b += bytes([0xA9, 0x18])            # LDA #$18
    b += bytes([0x8D, 0x11, 0x43])      # STA $4311  (B-bus $2118)
    b += bytes([0xA9, 0x20])            # LDA #$20
    b += bytes([0x8D, 0x15, 0x43])      # STA $4315  (size 32 bytes = 16 words)
    b += bytes([0x9C, 0x16, 0x43])      # STZ $4316
    # --- glyph destination: table[slot] gives the tile pair, which skips the
    # --- tiles the surviving original codes still need (0/1 blank, $20/$21 box)
    b += bytes([0xA5, 0x20])            # LDA $20
    b += bytes([0x29, 0x7F])            # AND #$7F   -> slot
    b += bytes([0xAA])                  # TAX
    b += bytes([0xBF, 0x80, 0x81, 0x3E])  # LDA $3E:8180,X  -> base tile
    b += bytes([0xC2, 0x20])            # REP #$20
    b += bytes([0x0A]) * 3              # ASL x3 -> tile*8 words
    b += bytes([0x09, 0x00, 0x60])      # ORA #$6000 -> VRAM dest word
    b += bytes([0x8D, 0x16, 0x21])      # STA $2116
    b += bytes([0xE2, 0x20])            # SEP #$20
    b += bytes([0xA9, 0x80])            # LDA #$80
    b += bytes([0x8D, 0x15, 0x21])      # STA $2115  (glyph DMA: +1 word)
    b += bytes([0xA9, 0x02])            # LDA #$02
    b += bytes([0x8D, 0x0B, 0x42])      # STA $420B  (start DMA)
    b += bytes([0xA9, 0x81])            # LDA #$81
    b += bytes([0x8D, 0x15, 0x21])      # STA $2115  (tilemap: +32 words)
    b += bytes([0xA5, 0x20])            # LDA $20
    b += bytes([0x8D, 0x16, 0x21])      # STA $2116
    b += bytes([0xA5, 0x21])            # LDA $21
    b += bytes([0x8D, 0x17, 0x21])      # STA $2117
    b += bytes([0xA5, 0x20])            # LDA $20
    b += bytes([0x29, 0x7F])            # AND #$7F   -> slot
    b += bytes([0xAA])                  # TAX
    b += bytes([0xBF, 0x80, 0x81, 0x3E])  # LDA $3E:8180,X -> base tile
    b += bytes([0x48])                  # PHA (save base tile)
    b += bytes([0x8D, 0x18, 0x21])      # STA $2118
    b += bytes([0xA9, 0x24])            # LDA #$24
    b += bytes([0x8D, 0x19, 0x21])      # STA $2119   (top tile at A)
    b += bytes([0x68])                  # PLA
    b += bytes([0x1A])                  # INC A       -> bottom tile
    b += bytes([0x8D, 0x18, 0x21])      # STA $2118
    b += bytes([0xA9, 0x24])            # LDA #$24
    b += bytes([0x8D, 0x19, 0x21])      # STA $2119   (bottom tile at A+32)
    b += bytes([0xC8])                  # INY
    b += bytes([0xE6, 0x20])            # INC $20
    br(0xF0, 'beq_row')
    jml('loop1', DISPATCH_ROM)
    pos['row'] = len(b)
    b += bytes([0xE6, 0x21])            # INC $21
    jml('loop2', DISPATCH_ROM)
    pos['normal_target'] = len(b)
    jml('to_normal', 0x00FC98)
    pos['done_target'] = len(b)
    jml('to_done', 0x00FCC6)

    def setbr(key, target_key):
        p = pos[key]
        off = pos[target_key] - (p + 2)
        assert -128 <= off <= 127, (key, off)
        b[p + 1] = off & 0xFF
    setbr('bne_notdone', 'notdone')
    setbr('bcs_cn', 'cn')
    setbr('beq_row', 'row')
    return bytes(b)


def build_slottab():
    """slot (0..127) -> base tile number of the two tiles a glyph occupies.

    Slots are the low 7 bits of the tilemap cursor, so every cell of a screen
    gets its own pair of tiles.  Pairs are handed out in order, skipping every
    pair that holds a tile some surviving original code still draws.
    """
    res = set([0x00]) | set(DECOR_TILES)
    for c in KEEP1.values():
        res.add(km.FA[c])
        res.add(km.FB[c])
    pairs = [p for p in range(128) if 2 * p not in res and 2 * p + 1 not in res]
    t = bytearray()
    for s in range(MAX_SLOTS):
        p = pairs[s] if s < len(pairs) else pairs[s - len(pairs)]
        t.append((p * 2) & 0xFF)
    return bytes(t), len(pairs)


TOKEN = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')


class Encoder:
    """Encodes Chinese text to the game code stream.

    Every `{XX...}` token coming from the extractor is preserved byte for byte
    (structural codes: name box E2, value slots EF/ED/EE, 1-byte codes F6/F7,
    2-byte controls F2F3/F2F4/F2F6...).  A plain space maps to the game's own
    space code 0x00, a character listed in KEEP1 keeps its original single-byte
    code, and every other character becomes a 2-byte Chinese code.
    """

    def __init__(self):
        self.glyphs = {}      # char -> glyph number
        self.order = []       # glyph number -> char

    def encode(self, s):
        out = bytearray()
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', s):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                out += bytes.fromhex(h)
                continue
            for ch in part:
                if ch == ' ':
                    out.append(0x00)
                    continue
                if ch in KEEP1:
                    out.append(KEEP1[ch])
                    continue
                if ch not in self.glyphs:
                    self.glyphs[ch] = len(self.order)
                    self.order.append(ch)
                g = self.glyphs[ch]
                out += bytes([0xF8 + (g >> 8), g & 0xFF])
        return out


_glyph_cache = {}


def glyph32(ch):
    if ch not in _glyph_cache:
        g = render8x16(ch, FONT_PATH, 16, GLYPH_THRESH, GLYPH_WIDEN)
        _glyph_cache[ch] = pack_8x8(g[:8]) + pack_8x8(g[8:])
    return _glyph_cache[ch]


def main():
    tp = BASE + '/cn_translation.json'
    if not os.path.exists(tp):
        raise SystemExit('missing ' + tp)
    tr = json.load(open(tp, encoding='utf-8'))
    textrecs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))

    enc = Encoder()
    addr_of = {}
    bodies = []                      # (region_start, region_end, payload)
    missing = []
    over = []
    for ti, (table_off, count) in enumerate(TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        assert len(recs) == count, (hex(table_off), len(recs), count)
        start, end = REGIONS[ti]
        body = bytearray()
        for r in recs:
            key = '%06X' % r['text_rom_off']
            if key not in tr:
                missing.append(key)
                addr_of[key] = None
                continue
            addr_of[key] = start + len(body)
            body += enc.encode(tr[key])
        if len(body) > end - start:
            over.append((table_off, len(body), end - start))
        bodies.append((start, end, bytes(body)))
        print('  table 0x%06X: %5d / %5d bytes (%d entries)%s'
              % (table_off, len(body), end - start, count,
                 '   OVER by %d' % (len(body) - (end - start)) if len(body) > end - start else ''))
    total = sum(len(b) for _, _, b in bodies)
    cap = sum(e - s for s, e, _ in bodies)

    print('distinct Chinese glyphs : %d  (capacity %d)' % (len(enc.order), PAGES * 256))
    print('encoded text bytes      : %d  (capacity %d)' % (total, cap))
    json.dump({k: v for k, v in addr_of.items() if v is not None},
              open(BASE + '/cn_addr_map.json', 'w'), indent=0)
    if len(enc.order) > PAGES * 256:
        raise SystemExit('too many distinct glyphs')
    if over:
        for t, n, c in over:
            print('OVERFLOW table 0x%06X: %d > %d' % (t, n, c))
        raise SystemExit('text does not fit its region')

    rom = bytearray(open(SRC_ROM, 'rb').read())
    assert len(rom) == 0x200000

    # --- glyph pool: page p -> bank $21+p, glyph id i -> $8000 + i*32 ---
    pool = bytearray(PAGES * 0x8000)
    for g, ch in enumerate(enc.order):
        page, idx = g >> 8, g & 0xFF
        off = page * 0x8000 + idx * 32
        pool[off:off + 32] = glyph32(ch)
    rom[POOL_ROM:POOL_ROM + len(pool)] = pool
    print('glyph pool              : %d bytes at ROM 0x%06X (banks $21-$24)'
          % (len(pool), POOL_ROM))

    # --- text + rebuilt pointer tables ---
    # Each region gets its table's messages densely packed from the original
    # start, so the byte-by-byte 0xF2 walk still finds every segment; the unused
    # tail is zeroed (code 0x00 = blank) instead of leaving Japanese text behind.
    for start, end, body in bodies:
        rom[start:end] = body + b'\x00' * (end - start - len(body))
    for table_off, count in TABLES:
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        for i, r in enumerate(recs):
            a = addr_of.get('%06X' % r['text_rom_off'])
            if a is None:
                a = TEXT_AREA          # untranslated string -> point at stub
            # pointer tables store SNES addresses in bank $03
            sa = 0x8000 + (a & 0x7FFF)
            rom[table_off + 2 * i] = sa & 0xFF
            rom[table_off + 2 * i + 1] = sa >> 8
        print('  table 0x%06X: %d entries rebuilt' % (table_off, count))

    # --- code + hooks ---
    pre, dis = build_preload(), build_dispatch()
    assert len(dis) <= 0x100, len(dis)
    rom[PRELOAD_ROM:PRELOAD_ROM + len(pre)] = pre
    rom[DISPATCH_ROM:DISPATCH_ROM + len(dis)] = dis
    tab, npairs = build_slottab()
    rom[SLOTTAB_ROM:SLOTTAB_ROM + len(tab)] = tab
    print('slot table: %d free tile pairs (slots beyond that wrap)' % npairs)
    pb, pa = snes_of_rom(PRELOAD_ROM)
    rom[HOOK_A:HOOK_A + 4] = bytes([0x5C, pa & 0xFF, pa >> 8, pb])
    rom[HOOK_KEEP_BANK:HOOK_KEEP_BANK + 2] = bytes([0xEA, 0xEA])
    db, da = snes_of_rom(DISPATCH_ROM)
    rom[HOOK_B:HOOK_B + 4] = bytes([0x5C, da & 0xFF, da >> 8, db])
    print('preload %d B @ROM 0x%06X ($3E:%04X) ; dispatch %d B @ROM 0x%06X ($3E:%04X)'
          % (len(pre), PRELOAD_ROM, pa, len(dis), DISPATCH_ROM, da))

    # --- checksum (this ROM stores complement first) ---
    rom[0x7FDC:0x7FE0] = b'\x00\x00\x00\x00'
    t = sum(rom) & 0xFFFF
    chk = (t + 0x1FE) & 0xFFFF
    rom[0x7FDC] = (chk ^ 0xFFFF) & 0xFF
    rom[0x7FDD] = (chk ^ 0xFFFF) >> 8
    rom[0x7FDE] = chk & 0xFF
    rom[0x7FDF] = chk >> 8
    print('checksum 0x%04X / complement 0x%04X ; verify sum&FFFF = 0x%04X'
          % (chk, chk ^ 0xFFFF, sum(rom) & 0xFFFF))

    open(OUT_ROM, 'wb').write(rom)
    n = make_ips(open(ORIG_ROM, 'rb').read(), bytes(rom), BASE + '/kuniokun_cn.ips')
    print('wrote %s and kuniokun_cn.ips (%d records)' % (OUT_ROM, n))


if __name__ == '__main__':
    main()