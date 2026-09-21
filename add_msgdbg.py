"""Add runtime markers to the message-blank hook so a probe can tell
'hook never ran' apart from 'VRAM writes do not land'.

Markers (all `inc abs`, which is M/X width independent):
  $0DF1  hook entries                 (before the bit6 test)
  $0DF2  blank branch taken           (bit6 was clear = new message)
  $0DF3  blank loop finished
Plus one unique VRAM word write at $7FFE (row 31 col 62, inside the box text
area, far below any real text) so we can see whether a CPU direct VRAM write
from this context lands at all.
"""
import re

p = 'cnbuild5.py'
s = open(p, encoding='utf-8').read()

# 1. the debug switch next to INSTRUMENT
m = re.search(r'^INSTRUMENT = (True|False)\s*$', s, re.M)
assert m, 'INSTRUMENT not found'
if 'MSG_DEBUG' not in s:
    s = s[:m.end()] + '\nMSG_DEBUG = False        # per-message hook: count markers + a VRAM probe word' + s[m.end():]

# 2. entry counter: first statement of build_msgclear
old = "    a = Asm(E3_MSG)\n    a.hexs('AD 73 03 29 40')               # lda $0373 / and #$40"
new = ("    a = Asm(E3_MSG)\n"
       "    if MSG_DEBUG:\n"
       "        a.hexs('EE F1 0D')                 # inc $0df1: debug entry counter\n"
       "    a.hexs('AD 73 03 29 40')               # lda $0373 / and #$40")
assert s.count(old) == 1, 'entry site not unique'
s = s.replace(old, new)

# 3. blank branch counter + loop completion counter + VRAM probe word
old2 = "    a.rel(0xD0, 'noarm')                   # bne noarm (a continuation line)\n"
new2 = ("    a.rel(0xD0, 'noarm')                   # bne noarm (a continuation line)\n"
        "    if MSG_DEBUG:\n"
        "        a.hexs('EE F2 0D')                 # inc $0df2: blank branch taken\n")
assert s.count(old2) == 1, 'branch site not unique'
s = s.replace(old2, new2)

old3 = "    a.rel(0x90, 'clr')                     # bcc clr\n    a.hexs('E2 30 28')                     # sep #$30 / plp\n"
new3 = ("    a.rel(0x90, 'clr')                     # bcc clr\n"
        "    if MSG_DEBUG:\n"
        "        a.hexs('EE F3 0D')                 # inc $0df3: loop finished\n"
        "        a.hexs('A2 FE 7F 8E 16 21')        # ldx #$7ffe / stx $2116\n"
        "        a.hexs('A9 FF 2C 8D 18 21')        # lda #$2cff / sta $2118: probe word\n"
        "    a.hexs('E2 30 28')                     # sep #$30 / plp\n")
assert s.count(old3) == 1, 'loop end site not unique'
s = s.replace(old3, new3)

open(p, 'w', encoding='utf-8', newline='').write(s)
print('patched', p)