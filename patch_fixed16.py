# -*- coding: utf-8 -*-
"""Give the most frequent Chinese characters a one byte code.

The text no longer fits bank $03 comfortably because the freed katakana tiles
mean kana can no longer ride along as 1 byte codes, so every Chinese character
costs two bytes.  Codes $D2..$DF are dead in the original font (FA/FB = $20, the
box glyph) and no drawing path in the ROM uses them, so they become one byte
codes for the most frequent characters; the drawer recognises them without a
second byte.

Also: the macro sanitizer is dropped.  It only ever protected the speaker name
copier and the $E7-$E9 copier, and both now read kana-only tables (the katakana
rewrite), so it is dead code -- and its range would collide with $D2..$DF.  The
18 bytes it occupied become text space.
"""
import io

P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py'
src = io.open(P, encoding='utf-8', newline='').read()
src = src.replace('\r\n', '\n')
orig = src

# ---------------------------------------------------------------- 1. constants
anchor = "PREFIX0 = 0xC5"
assert src.count(anchor) == 1
src = src.replace(anchor, """PREFIX0 = 0xC5
FIXED0 = 0xD2                           # one byte codes for frequent glyphs
FIXED_N = 8                             # how many of them (slots 0..N-1, page 0)
FIXED_CODES = {}                        # filled in main(): char -> code byte
DRW_MODE = 0x0D48                       # drawer scratch: 0 two byte, 1 fixed""")

# ---------------------------------------------------------------- 2. Encoder
old = """    def colour(self, windows):
        \"\"\"Greedy colouring, least-loaded slot first.

        Balanced slots matter because a slot is also a storage column: chars that
        share a slot must live in different pool banks, so no slot may collect
        more than PAGES glyphs.
        \"\"\"
        freq = {}
        for w in windows:
            for ch in w:
                freq[ch] = freq.get(ch, 0) + 1
        for ch in sorted(freq, key=lambda c: (-freq[c], c)):
            banned = set()
            for w in windows:
                if ch in w:
                    banned |= {self.slot[c] for c in w if c in self.slot}
            free = [s for s in range(SLOTS) if s not in banned]"""
assert src.count(old) == 1
new = """    def colour(self, windows):
        \"\"\"Greedy colouring, least-loaded slot first.

        Balanced slots matter because a slot is also a storage column: chars that
        share a slot must live in different pool banks, so no slot may collect
        more than PAGES glyphs.  The one byte codes own slots 0..FIXED_N-1 for
        good (their code byte says which slot), so the rest uses the others.
        \"\"\"
        freq = {}
        for w in windows:
            for ch in w:
                freq[ch] = freq.get(ch, 0) + 1
        for ch in sorted(freq, key=lambda c: (-freq[c], c)):
            if ch in FIXED_CODES:
                self.slot[ch] = FIXED_CODES[ch] - FIXED0
                self.load[self.slot[ch]] += 1
                continue
            banned = set()
            for w in windows:
                if ch in w:
                    banned |= {self.slot[c] for c in w if c in self.slot}
            free = [s for s in range(FIXED_N, SLOTS) if s not in banned]"""
src = src.replace(old, new)

old = """        used = [set() for _ in range(PAGES)]
        for ch in sorted(self.slot, key=lambda c: (self.slot[c], c)):"""
assert src.count(old) == 1
new = """        used = [set() for _ in range(PAGES)]
        for ch in sorted(FIXED_CODES, key=lambda c: FIXED_CODES[c]):
            s = FIXED_CODES[ch] - FIXED0            # one byte codes live in page 0
            self.cell[ch] = (0, s)
            used[0].add(s)
            self.order.append(ch)
        for ch in sorted(self.slot, key=lambda c: (self.slot[c], c)):
            if ch in FIXED_CODES:
                continue"""
src = src.replace(old, new)

old = """                elif ch in KEEP1:
                    out.append(KEEP1[ch])
                else:"""
assert src.count(old) == 1
new = """                elif ch in KEEP1:
                    out.append(KEEP1[ch])
                elif ch in FIXED_CODES:
                    out.append(FIXED_CODES[ch])
                else:"""
src = src.replace(old, new)

# ---------------------------------------------------------------- 3. drawer
old = """    a = Asm(E3_DRAWER)
    # ---- dispatch on the code in $12 -----------------------------------------
    a.hexs('A5 12')                        # lda $12
    a.hexs('C9 %02X' % PREFIX0)            # cmp #$c5
    a.rel(0x90, 'orig')                    # bcc orig
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #$c5+pages
    a.rel(0x90, 'cn')                      # bcc cn
    a.label('orig')
    a.hexs('AD 6F 03')                     # lda $036f
    a.hexs('C9 1A')                        # cmp #$1a (eaten by the 4 byte hook)
    a.long_to(0x01FA35)                    # jml $03:fa35 (the original drawer)

    # ---- Chinese branch ------------------------------------------------------
    a.label('cn')"""
assert src.count(old) == 1
new = """    a = Asm(E3_DRAWER)
    # ---- remember the box row: the wipe covers every row a message drew into --
    a.hexs('AD 6E 03')                     # lda $036e
    a.hexs('CD %02X 0D' % ((WIPE_TOP) & 0xFF))
    a.rel(0xB0, 'nt')                      # bcs nt
    a.hexs('8D %02X 0D' % ((WIPE_TOP) & 0xFF))
    a.label('nt')
    a.hexs('AD 6E 03')
    a.hexs('CD %02X 0D' % ((WIPE_BOT) & 0xFF))
    a.rel(0x90, 'nb')                      # bcc nb
    a.hexs('8D %02X 0D' % ((WIPE_BOT) & 0xFF))
    a.label('nb')

    # ---- dispatch on the code in $12 -----------------------------------------
    #   $c5..$c5+pages-1  two byte Chinese code (prefix + id)
    #   $d2..$d2+FIXED_N  one byte Chinese code of a frequent character
    #   everything else   the original drawer, whose first instructions the
    #                     4 byte hook ate and which are replayed here
    a.hexs('A5 12')                        # lda $12
    a.hexs('C9 %02X' % PREFIX0)            # cmp #$c5
    a.rel(0x90, 'occ')                     # bcc occ
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #$c5+pages
    a.rel(0x90, 'setc')                    # bcc setc
    a.hexs('C9 %02X' % FIXED0)             # cmp #$d2
    a.rel(0x90, 'occ')                     # bcc occ (unused code space)
    a.hexs('C9 %02X' % (FIXED0 + FIXED_N))  # cmp #$d2+n
    a.rel(0x90, 'setf')                    # bcc setf
    a.label('occ')
    a.hexs('A9 02 8D %02X 0D' % ((DRW_MODE) & 0xFF))   # lda #$02 / sta mode
    a.hexs('AD 6F 03 C9 1A')               # lda $036f / cmp #$1a (hook food)
    a.long_to(0x01FA35)                    # jml $03:fa35 (the original drawer)
    a.label('setc')
    a.hexs('9C %02X 0D' % ((DRW_MODE) & 0xFF))         # stz mode: two byte code
    a.rel(0x80, 'checks')
    a.label('setf')
    a.hexs('A9 01 8D %02X 0D' % ((DRW_MODE) & 0xFF))   # lda #$01 / sta mode
    a.label('checks')"""
src = src.replace(old, new)

old = """    # ---- slot, glyph id, tiles -----------------------------------------------
    a.hexs('8B')                           # phb (DBR is $03 here)
    a.hexs('A5 12 38 E9 %02X 18 69 %02X 48'
           % (PREFIX0, POOL_BANK0))        # glyph bank = code - $c5 + $21 -> stack
    a.hexs('AD E9 03 1A A8')               # lda $03e9 / inc a / tay
    a.hexs('B9 EA 03')                     # lda $03ea,y (the glyph id = slot)
    a.hexs('C9 %02X' % SLOTS)              # cmp #SLOTS"""
assert src.count(old) == 1
new = """    # ---- slot, glyph id, tiles -----------------------------------------------
    a.hexs('8B')                           # phb (DBR is $03 here)
    a.hexs('AD %02X 0D' % ((DRW_MODE) & 0xFF))
    a.rel(0xD0, 'fx')                      # bne fx (one byte code)
    a.hexs('A5 12 38 E9 %02X 18 69 %02X 48'
           % (PREFIX0, POOL_BANK0))        # glyph bank = code - $c5 + $21 -> stack
    a.hexs('AD E9 03 1A A8')               # lda $03e9 / inc a / tay
    a.hexs('B9 EA 03')                     # lda $03ea,y (the glyph id = slot)
    a.rel(0x80, 'gotid')                   # bra gotid
    a.label('fx')
    a.hexs('A9 %02X 48' % POOL_BANK0)      # lda #$21 / pha (one byte codes: page 0)
    a.hexs('A5 12 38 E9 %02X' % FIXED0)    # lda $12 / sec / sbc #$d2 = id
    a.label('gotid')
    a.hexs('C9 %02X' % SLOTS)              # cmp #SLOTS"""
src = src.replace(old, new)

# tail: only a two byte code eats the id byte
old = """    # ---- bookkeeping --------------------------------------------------------
    a.hexs('EE E9 03')                     # inc $03e9 (consume the id byte)"""
assert src.count(old) == 1
new = """    # ---- bookkeeping --------------------------------------------------------
    a.hexs('AD %02X 0D' % ((DRW_MODE) & 0xFF))
    a.rel(0xD0, 'noid')                    # bne noid (one byte code: nothing to eat)
    a.hexs('EE E9 03')                     # inc $03e9 (consume the id byte)
    a.label('noid')"""
src = src.replace(old, new)

# the row bookkeeping now lives at the entry, so drop it from the cn path
old = """    a.hexs('AD 6E 03')                     # lda $036e
    a.hexs('CD %02X 0D' % ((WIPE_TOP) & 0xFF))        # cmp $0d40
    a.rel(0xB0, 'nt')                      # bcs nt
    a.hexs('8D %02X 0D' % ((WIPE_TOP) & 0xFF))        # sta $0d40
    a.label('nt')
    a.hexs('AD 6E 03')
    a.hexs('CD %02X 0D' % ((WIPE_BOT) & 0xFF))        # cmp $0d41
    a.rel(0x90, 'nb')                      # bcc nb
    a.hexs('8D %02X 0D' % ((WIPE_BOT) & 0xFF))        # sta $0d41
    a.label('nb')
    a.hexs('68')                           # pla (the saved DBR)"""
assert src.count(old) == 1
src = src.replace(old, """    a.hexs('68')                           # pla (the saved DBR)""")

# defer: a one byte code has nothing to undo
old = """    a.label('defer')
    a.hexs('AD E9 03')                     # lda $03e9
    a.rel(0xF0, 'defer2')                  # beq defer2 (index 0, nothing to undo)"""
assert src.count(old) == 1
new = """    a.label('defer')
    a.hexs('AD %02X 0D' % ((DRW_MODE) & 0xFF))
    a.rel(0xD0, 'defer2')                  # bne defer2 (one byte code: nothing to undo)
    a.hexs('AD E9 03')                     # lda $03e9
    a.rel(0xF0, 'defer2')                  # beq defer2 (index 0, nothing to undo)"""
src = src.replace(old, new)

# ------------------------------------------------------------- 4. main(): codes
old = """    added = derive_keep1(fixed.values())

    def _len_with(keepset):"""
assert src.count(old) == 1
new = """    added = derive_keep1(fixed.values())

    # the dead codes $d2..$d2+n-1 become one byte codes for the most frequent
    # Chinese characters: 2 bytes per occurrence is what outgrows bank $03
    cnt = {}
    for t in fixed.values():
        for part in re.split(r'\\{[0-9A-Fa-f]{2,4}\\}', t):
            for ch in part:
                if ch != ' ' and ch not in KEEP1:
                    cnt[ch] = cnt.get(ch, 0) + 1
    top = [c for c, n in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:FIXED_N]]
    FIXED_CODES.clear()
    FIXED_CODES.update({ch: FIXED0 + i for i, ch in enumerate(top)})
    print('one byte codes: %s (%d occurrences)'
          % (' '.join('%s=%02X' % (c, FIXED_CODES[c]) for c in top),
             sum(cnt[c] for c in top)))

    def _len_with(keepset):"""
src = src.replace(old, new)

# ------------------------------------------------- 5. drop the sanitizer
old = """    slotpairs, npairs = build_slotpairs()
    r5_end = active[-1][0] + len(chunks[active[-1][0]])
    assert r5_end <= B3_SANITIZE, (hex(r5_end), hex(B3_SANITIZE))"""
assert src.count(old) == 1
new = """    slotpairs, npairs = build_slotpairs()
    r5_end = active[-1][0] + len(chunks[active[-1][0]])
    assert r5_end <= B3_SANITIZE_END, (hex(r5_end), hex(B3_SANITIZE_END))"""
src = src.replace(old, new)

old = """    san = build_sanitize()
    rom[B3_SANITIZE:B3_SANITIZE + len(san)] = san
"""
assert src.count(old) == 1
src = src.replace(old, """    # the macro sanitizer is gone: its only callers copy kana only now, and its
    # range would swallow the one byte codes $d2..$df
""")
old = """    assert B3_SANITIZE + len(san) < B3_SANITIZE_LIMIT, (len(san),)
    assert 0xF2 not in san, 'sanitizer must not contain an F2 byte'
"""
assert src.count(old) == 1
src = src.replace(old, "")
old = """    sb, sa_ = snes_of_rom(B3_SANITIZE)
    for hook in (HOOK_COPY1, HOOK_COPY2):
        assert rom[hook:hook + 3] == bytes([0x9D, 0xEA, 0x03]), rom[hook:hook + 3]
        rom[hook:hook + 3] = bytes([0x20, sa_ & 0xFF, sa_ >> 8])
    print('drawer %d B @ROM 0x%06X ($%02X:%04X); wipe %d B ($%02X:%04X); '
          'arm %d B ($%02X:%04X); sanitize %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(wipe), *snes_of_rom(E3_WIPE),
             len(arm), *snes_of_rom(E3_ARM), len(san), sb, sa_))"""
assert src.count(old) == 1
new = """    for hook in (HOOK_COPY1, HOOK_COPY2):
        assert rom[hook:hook + 3] == bytes([0x9D, 0xEA, 0x03]), \\
            'the sanitizer call has already been removed: %s' % rom[hook:hook + 3].hex(' ')
    print('drawer %d B @ROM 0x%06X ($%02X:%04X); wipe %d B ($%02X:%04X); '
          'arm %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(wipe), *snes_of_rom(E3_WIPE),
             len(arm), *snes_of_rom(E3_ARM)))"""
src = src.replace(old, new)

io.open(P, 'w', encoding='utf-8', newline='\n').write(src)
print('cnbuild5.py patched: %d -> %d bytes' % (len(orig), len(src)))