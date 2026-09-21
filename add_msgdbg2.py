"""Debug round 2 for the message-blank hook: A/B the two VRAM channels.

Inside the blank branch, right after the clear loop, emit three markers:
  * CPU direct  -> tilemap word $7FFE   := $2CFF   (may be reverted)
  * CPU direct  -> pattern words $6008/9 := $FFFF  (tile 1, never rewritten)
  * engine queue-> tilemap word $7FFE   := $2CFF   (drawer's proven channel)
The probe reads all three, so one run separates 'CPU writes do not land' from
'the tilemap gets rewritten afterwards'.
"""
p = 'cnbuild5.py'
s = open(p, encoding='utf-8').read()

old = """        a.hexs('A2 FE 7F 8E 16 21')        # ldx #$7ffe / stx $2116
        a.hexs('A9 FF 2C 8D 18 21')        # lda #$2cff / sta $2118: probe word
"""
new = """        a.hexs('A2 FE 7F 8E 16 21')        # ldx #$7ffe / stx $2116
        a.hexs('A9 FF 2C 8D 18 21')        # lda #$2cff / sta $2118: tilemap probe
        a.hexs('A2 08 60 8E 16 21')        # ldx #$6008 / stx $2116
        a.hexs('A9 FF FF 8D 18 21')        # lda #$ffff / sta $2118 }
        a.hexs('8D 18 21')                 # sta $2118                } pattern probe
        a.hexs('E2 20 AD DF 09 C2 20 29 FF 00 AA')  # sep #$20 / lda $09df / rep #$20 / and #$00ff / tax
        a.hexs('A9 FE 7F 9D 00 0B')        # lda #$7ffe / sta $0b00,x
        a.hexs('E8 E8')                    # inx inx
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep #$20 / lda #$80 / sta $0b00,x / inx
        a.hexs('A9 02 9D 00 0B E8')        # lda #$02 / sta $0b00,x / inx
        a.hexs('A9 FF 9D 00 0B E8')        # lda #$ff / sta $0b00,x / inx
        a.hexs('A9 2C 9D 00 0B E8')        # lda #$2c / sta $0b00,x / inx
        a.hexs('8A E2 20 8D DF 09')        # txa / sep #$20 / sta $09df: queue probe
"""
assert s.count(old) == 1, 'marker block not unique'
s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched', p)

# probe: also watch the pattern probe words
q = 'hw/v62.lua'
t = open(q, encoding='utf-8').read()
old2 = """  local m1, m2, m3 = rd(0x0DF1), rd(0x0DF2), rd(0x0DF3)
  local mkr = vramw(0x7FFE)
  if m1 ~= prev_m1 or m2 ~= prev_m2 or m3 ~= prev_m3 or mkr ~= prev_mkr then
    log:write(string.format('F=%d MARKER entries=%d blanked=%d done=%d word7FFE=%04X\\n',
      frame, m1, m2, m3, mkr))
    prev_m1, prev_m2, prev_m3, prev_mkr = m1, m2, m3, mkr
  end"""
new2 = """  local m1, m2, m3 = rd(0x0DF1), rd(0x0DF2), rd(0x0DF3)
  local mkr = vramw(0x7FFE)
  local pat = vramw(0x6008) + vramw(0x6009) * 65536
  if m1 ~= prev_m1 or m2 ~= prev_m2 or m3 ~= prev_m3 or mkr ~= prev_mkr or pat ~= prev_mkr then
    log:write(string.format('F=%d MARKER entries=%d blanked=%d done=%d word7FFE=%04X pattern6008=%08X\\n',
      frame, m1, m2, m3, mkr, pat))
    prev_m1, prev_m2, prev_m3, prev_mkr = m1, m2, m3, mkr
  end"""
assert t.count(old2) == 1, 'probe marker block not unique'
t = t.replace(old2, new2)
open(q, 'w', encoding='utf-8', newline='').write(t)
print('patched', q)