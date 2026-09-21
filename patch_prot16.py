# -*- coding: utf-8 -*-
"""Give the builder a correct tile protection set.

Why: protected_tiles() used to be derived from the characters that appear in my
own translation, so cutting KEEP1 down to 20 characters left only 23 protected
tiles and the Chinese slots claimed tiles that the engine itself still draws --
speaker names ({E2} -> bank $09 name records), the untranslated item window and
the status screen script all come out as Chinese glyph fragments.

What the engine draws with the original font:
  * item window text, ROM 0x01DCA1..0x01E096 (left in Japanese on purpose)
  * speaker name records, bank $09 ROM 0x4802A + i*16, <= 4 bytes each
  * the status screen's static drawing script at $00:F9DB (literal tiles and codes)
  * scene graphics + dialogue box frame that live inside the font window
    (tiles $E0/$E1/$F0 -- seen in the tile maps of every VRAM dump)

Rewriting the katakana of those untranslated strings to hiragana keeps them
readable while freeing 38 font tiles, which is what makes enough slots for 16x16.
"""
import io
import os

P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
src = io.open(P, encoding='utf-8', newline='').read()
src = src.replace('\r\n', '\n')
orig = src

# --------------------------------------------------------------- 1. new helpers
anchor = """PROTECT_TILES = (set([0x00, 0x01]) | set(range(0x10, 0x20))
                 | set([0x1A, 0x1E]) | set(DECOR_TILES))
"""
assert src.count(anchor) == 1
helpers = anchor + '''
# Tiles inside the font window that the engine draws as graphics, not as text:
# the scene background and the dialogue box frame.  Seen in the tile maps of
# every VRAM dump ($E0/$E1 in the scene rows, $F0 as the frame).
GFX_TILES = (0xE0, 0xE1, 0xF0)

# katakana code -> hiragana code with the same reading (Unicode -0x60 pairs)
_inv = {}
for _c, _ch in km.CODE.items():
    if len(_ch) == 1:
        _inv.setdefault(_ch, _c)
KANA_MAP = {}
for _ch, _c in _inv.items():
    _o = ord(_ch)
    if 0x30A1 <= _o <= 0x30F6 and chr(_o - 0x60) in _inv:
        KANA_MAP[_c] = _inv[chr(_o - 0x60)]


def rewrite_kana(b):
    """Katakana -> hiragana for text the engine still draws with the original
    font.  Same language, same byte count, same pointer table, but 38 fewer font
    tiles have to stay reserved."""
    return bytes(KANA_MAP.get(x, x) for x in b)


def status_script_code_runs():
    """(start, end) of every code run in the status screen drawing script.

    The interpreter at $00:F971 walks blocks of [addr_lo][addr_hi][count]: with
    count < $80 the bytes are literal tile numbers, with count >= $80 they are
    font codes -- only the latter may be rewritten."""
    data = open(ORIG_ROM, 'rb').read()
    base = 0x00F9DB
    blob = data[base:base + 0x125]
    runs, y = [], 0
    while y < len(blob) and blob[y] != 0xFF:
        y += 2
        cnt = blob[y]
        y += 1
        if cnt == 0:
            continue
        n = cnt & 0x7F
        if cnt & 0x80:
            runs.append((base + y, base + y + n))
        y += n
    return runs


def untranslated_codes():
    """Original-font codes the engine still renders itself."""
    data = open(ORIG_ROM, 'rb').read()
    codes = set(KEEP1_EXPLICIT.values()) | set(range(0x10, 0x1A))
    for s, e in ((0x01DCA1, 0x01E096),):            # item window text
        codes |= set(b for b in rewrite_kana(data[s:e]) if 0 < b < 0xE0)
    for i in range(560):                            # speaker name records
        rec = rewrite_kana(data[0x4802A + i * 16:0x4802A + i * 16 + 4])
        for b in rec:
            if b == 0:
                break
            if b < 0xE0:
                codes.add(b)
    for s, e in status_script_code_runs():          # status screen script
        codes |= set(b for b in rewrite_kana(data[s:e]) if 0 < b < 0xE0)
    return codes


PROTECT_CODES = None
'''
src = src.replace(anchor, helpers)

# --------------------------------------------------- 2. derive_keep1 -> free reuse
old_keep = src[src.index('def derive_keep1(texts, need_pairs=None):'):src.index('    return added') + len('    return added')]
new_keep = '''def derive_keep1(texts=None, need_pairs=None):
    """Keep every character whose original font tiles are protected anyway.

    A kept character costs one byte instead of two and is drawn by the original
    font, so it also removes a Chinese glyph from the slot demand.  Characters
    that would need extra protected tiles are not worth it: two tiles are half a
    glyph slot.  The untranslated item window, the speaker names and the status
    script already protect all the kana, digits and punctuation.
    """
    by_char = {}
    for code, ch in km.CODE.items():
        if code >= 0xE0 or len(ch) != 1 or ch == ' ':
            continue
        by_char.setdefault(ch, code)
    prot = protected_tiles()
    keep = dict(KEEP1_EXPLICIT)
    added = {}
    for ch in sorted(by_char):
        if ch in keep:
            continue
        code = by_char[ch]
        if km.FA[code] in prot and km.FB[code] in prot:
            added[ch] = code
    keep.update(added)
    KEEP1.clear()
    KEEP1.update(keep)
    return added'''
src = src.replace(old_keep, new_keep)

# --------------------------------------------------------- 3. protected_tiles()
old_prot = """def protected_tiles():
    res = set(PROTECT_TILES)
    for c in KEEP1.values():
        res.add(km.FA[c])
        res.add(km.FB[c])
    return res"""
assert src.count(old_prot) == 1
new_prot = """def protected_tiles():
    global PROTECT_CODES
    if PROTECT_CODES is None:
        PROTECT_CODES = untranslated_codes()
    res = set(PROTECT_TILES) | set(GFX_TILES)
    for c in PROTECT_CODES:
        res.add(km.FA[c])
        res.add(km.FB[c])
    for c in KEEP1.values():
        res.add(km.FA[c])
        res.add(km.FB[c])
    return res"""
src = src.replace(old_prot, new_prot)

# -------------------------------------------------------------- 4. free_pairs()
old_free = """def free_pairs():
    \"\"\"Tile pairs no surviving original code and no decor routine draws into.\"\"\"
    res = protected_tiles()
    return [p for p in range(128) if 2 * p not in res and 2 * p + 1 not in res]"""
assert src.count(old_free) == 1
new_free = """def free_pairs():
    \"\"\"Base tiles t whose successor t+1 is free too.

    A glyph half is uploaded by one 32 byte DMA, so its two tiles have to be
    consecutive; they no longer have to be even aligned, which recovers a good
    part of the tiles the untranslated Japanese needs.  Pairs never overlap.\"\"\"
    res = protected_tiles()
    fs = set(t for t in range(256) if t not in res)
    used, out = set(), []
    for t in range(256):
        if t in fs and (t + 1) in fs and t not in used and (t + 1) not in used:
            out.append(t)
            used.add(t)
            used.add(t + 1)
    return out"""
src = src.replace(old_free, new_free)

# --------------------------------------------- 5. drawer: tiles are base tiles
old_t = """    a.hexs('AD %02X 0D 0A 8D %02X 0D 1A 8D %02X 0D' % ((DRW_PA) & 0xFF, (DRW_T1) & 0xFF, (DRW_T2) & 0xFF))     # tiles 2a and 2a+1
    a.hexs('AD %02X 0D 0A 8D %02X 0D 1A 8D %02X 0D' % ((DRW_PB) & 0xFF, (DRW_T3) & 0xFF, (DRW_T4) & 0xFF))     # tiles 2b and 2b+1"""
assert src.count(old_t) == 1
new_t = """    a.hexs('AD %02X 0D 8D %02X 0D 1A 8D %02X 0D' % ((DRW_PA) & 0xFF, (DRW_T1) & 0xFF, (DRW_T2) & 0xFF))     # tiles a and a+1
    a.hexs('AD %02X 0D 8D %02X 0D 1A 8D %02X 0D' % ((DRW_PB) & 0xFF, (DRW_T3) & 0xFF, (DRW_T4) & 0xFF))     # tiles b and b+1"""
src = src.replace(old_t, new_t)

old_v1 = """    a.hexs('AD %02X 0D 29 FF 00' % ((DRW_PA) & 0xFF))
    a.hexs('0A 0A 0A 0A')                  # asl x4 (pair * 16 words)
    a.hexs('09 00 60 8D %02X 0D' % ((DRW_VMADD) & 0xFF))   # ora #$6000 / sta scratch
    a.hexs('AD %02X 0D 29 FF 00' % ((DRW_PB) & 0xFF))
    a.hexs('0A 0A 0A 0A')"""
assert src.count(old_v1) == 1
new_v1 = """    a.hexs('AD %02X 0D 29 FF 00' % ((DRW_PA) & 0xFF))
    a.hexs('0A 0A 0A')                     # asl x3 (base tile * 8 words)
    a.hexs('09 00 60 8D %02X 0D' % ((DRW_VMADD) & 0xFF))   # ora #$6000 / sta scratch
    a.hexs('AD %02X 0D 29 FF 00' % ((DRW_PB) & 0xFF))
    a.hexs('0A 0A 0A')"""
src = src.replace(old_v1, new_v1)

old_doc = """    A glyph occupies four tiles that need not be adjacent: the slot table gives
    two free tile pairs, the left screen cell shows tiles 2a/2a+1 and the right
    one 2b/2b+1."""
assert src.count(old_doc) == 1
src = src.replace(old_doc, """    A glyph occupies four tiles that need not be adjacent: the slot table gives
    two consecutive free tile pairs, the left screen cell shows tiles a/a+1 and
    the right one b/b+1.""")

old_doc2 = """    A glyph is 16x16 = four 8x8 tiles, but they do not have to be adjacent: the
    two tiles of the left screen cell come from one free tile pair and the two of
    the right cell from another.  That needs 86 -> 53 slots instead of the 39 a
    single four-aligned quad would allow, and 53 is what the slot colouring needs
    to keep consecutive list entries apart (43 would just barely do for single
    messages, 39 does not)."""
assert src.count(old_doc2) == 1
src = src.replace(old_doc2, """    Each slot stores two base tiles: the glyph's left half is the pair t/t+1 and
    its right half u/u+1, where t and u come from free_pairs().  Two independent
    pairs instead of one four-aligned quad is what makes the slot count
    comfortable (a quad would need four consecutive free tiles).""")

# --------------------------------------------- 6. main(): rewrite the kana
old_chk = """    # ---- 5. checksum (this ROM stores the complement first)"""
assert src.count(old_chk) == 1
new_chk = """    # ---- 4b. the untranslated Japanese is drawn with the original font, so its
    # katakana is rewritten to hiragana: same reading, same length, and 38 font
    # tiles fewer stay reserved (each freed tile pair buys two glyph slots).
    print('font tiles protected: %d of 256; %d free consecutive tile pairs'
          % (len(protected_tiles()), len(free_pairs())))
    rom[0x01DCA1:0x01E096] = rewrite_kana(bytes(rom[0x01DCA1:0x01E096]))
    for i in range(560):
        o = 0x4802A + i * 16
        rom[o:o + 4] = rewrite_kana(bytes(rom[o:o + 4]))
    nrun = 0
    for s, e in status_script_code_runs():
        rom[s:e] = rewrite_kana(bytes(rom[s:e]))
        nrun += 1
    print('kana: item window, 560 speaker name records and %d status script runs '
          'rewritten to hiragana' % nrun)

    # ---- 5. checksum (this ROM stores the complement first)"""
src = src.replace(old_chk, new_chk)

assert src != orig
io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
print('cnbuild5.py patched: %d -> %d bytes' % (len(orig), len(src)))