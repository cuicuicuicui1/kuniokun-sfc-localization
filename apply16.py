"""Replace the stateful box wipe with a stateless message hook + scratch free drawer.

Why: the wipe state (WIPE_*/DRW_*, $0d40-$0d53) lives in WRAM the game itself
writes.  Real stores to those bytes inside the ROM:

    $01:88C0 STA $0D43     $01:81B9/$01:81FB/$01:8DAF STZ $0D43
    $0C:C793/$0C:C913 STZ $0D42      $01:831F STA $0D44
    $01:889C/$01:8DB2 STA/STZ $0D53  $01:8DAC STZ $0D54
    $01:8E71/$01:8EE0 STA $0D54      $01:8DA9 STA $0D55   $01:80B7 STZ $0D55
    $05:BCC1/$05:BCDE STA $0D40      $09:FF36 STA $0D51   $09:FF27 STA $0D54,X
    $00:EECB/$00:EEF0 STA $0D5D      $02:8029/$02:8180/$02:824E/$02:82FC STZ $0D5F
    $02:8328 STA $0D5F               $01:8D62/$01:8D86 STA $0D45,X

so the engine zeroed WIPE_PEND/WIPE_CUR between the arming and the staging: the
wipe never staged anything.  Rather than hunt for free WRAM (there is none: the
$1500-$17FF probe found no stable 16 byte run either), everything becomes
stateless:

  * the message hook at $03:EB9E (first line of a new entry, $0373 bit6 clear)
    blanks the box text area with CPU direct writes to $2116/$2118 - the exact
    technique the engine's own box opener uses at $03:E9B6
    (lda #$7800/sta $2116/lda #$2c00/sta $2118/inc $26), so no queue, no
    cross frame state, nothing that can be clobbered;
  * the drawer keeps no scratch at all: the glyph bank, id, and the two tile
    pairs live on the stack, the pool offset in Y, the queue cursor in X.
"""
import re
import io

SRC = 'cnbuild5.py'
s = io.open(SRC, encoding='utf-8', newline='').read()
orig = s

# ---------------------------------------------------------------- constants
old = "E3_WIPE = CODE_ROM + 0x600             # $3E:8600  staged box wipe\r\n"
if old not in s:
    old = "E3_WIPE = CODE_ROM + 0x600             # $3E:8600  staged box wipe\n"
assert s.count(old) == 1, 'E3_WIPE line'
new = ("E3_MSG = CODE_ROM + 0x800              # $3E:8800  new entry: blank the box,\r\n"
       "                                       #           then replay the eaten op\r\n")
s = s.replace(old, new, 1)

old = "E3_ARM = CODE_ROM + 0x800              # $3E:8700  message-entry hook (arms the wipe)\n"
if old not in s:
    old = "E3_ARM = CODE_ROM + 0x800              # $3E:8700  message-entry hook (arms the wipe)\r\n"
assert s.count(old) == 1, 'E3_ARM line'
s = s.replace(old, '', 1)

# the scratch block: drop every WIPE_*/DRW_* definition, keep GLYPH_COST
lines = s.split('\n')
out = []
for ln in lines:
    ls = ln.strip()
    if re.match(r'^(WIPE_|DRW_)[A-Z0-9]+ *= *0x0D', ls):
        continue
    if ls.startswith('ROW_WIPE ='):
        out.append('# box rows are blanked by $3E:8800, so ROW_WIPE and every wipe')
        out.append('# scratch byte are gone: nothing in this patch keeps state in WRAM.')
        continue
    out.append(ln)
s = '\n'.join(out)

# ---------------------------------------------------------------- functions
i0 = s.index('def build_drawer_copy():')
i1 = s.index('def build_sanitize():')
newfuncs = io.open('newfuncs16.txt', encoding='utf-8', newline='').read()
s = s[:i0] + newfuncs + s[i1:]
assert not re.findall(r'^\s*(WIPE_|DRW_)[A-Z0-9]+ *=', s, re.M), \
    'a wipe/scratch constant survived'

# ---------------------------------------------------------------- main()
old_install = """    drawer = build_drawer_copy()
    rom[E3_DRAWER:E3_DRAWER + len(drawer)] = drawer
    wipe = build_wipe()
    rom[E3_WIPE:E3_WIPE + len(wipe)] = wipe
    arm = build_arm()
    rom[E3_ARM:E3_ARM + len(arm)] = arm
    # the macro sanitizer is gone: its only callers copy kana only now, and its
    # range would swallow the one byte codes $d2..$df
    assert E3_SLOTPAIR + len(slotpairs) <= E3_DRAWER, (len(slotpairs),)
    assert E3_DRAWER + len(drawer) < E3_WIPE, (len(drawer),)
    assert E3_WIPE + len(wipe) < E3_ARM, (len(wipe),)
    assert E3_ARM + len(arm) < CODE_ROM + 0x8000, (len(arm),)
"""
assert s.count(old_install) == 1, 'install block'
new_install = """    drawer = build_drawer_copy()
    rom[E3_DRAWER:E3_DRAWER + len(drawer)] = drawer
    msg = build_msgclear()
    rom[E3_MSG:E3_MSG + len(msg)] = msg
    # the macro sanitizer is gone: its only callers copy kana only now, and its
    # range would swallow the one byte codes $d2..$df
    assert E3_SLOTPAIR + len(slotpairs) <= E3_DRAWER, (len(slotpairs),)
    assert E3_DRAWER + len(drawer) < E3_MSG, (len(drawer),)
    assert E3_MSG + len(msg) < CODE_ROM + 0x8000, (len(msg),)
    for name, code in (('drawer', drawer), ('message hook', msg)):
        bad = scratch_hits(code)
        assert not bad, '%s touches live game data: %r' % (name, bad)
"""
s = s.replace(old_install, new_install, 1)

old_log = """    print('drawer %d B @ROM 0x%06X ($%02X:%04X); wipe %d B ($%02X:%04X); '
          'arm %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(wipe), *snes_of_rom(E3_WIPE),
             len(arm), *snes_of_rom(E3_ARM)))
"""
assert s.count(old_log) == 1, 'log block'
new_log = """    print('drawer %d B @ROM 0x%06X ($%02X:%04X); message hook %d B ($%02X:%04X)'
          % (len(drawer), E3_DRAWER, db, da, len(msg), *snes_of_rom(E3_MSG)))
"""
s = s.replace(old_log, new_log, 1)

old_hook = """    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \\
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')   # untouched: the drawer calls the wipe
    ab, aa = snes_of_rom(E3_ARM)
"""
assert s.count(old_hook) == 1, 'driver hook assert'
new_hook = """    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \\
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')   # untouched: no hook needed
    ab, aa = snes_of_rom(E3_MSG)
"""
s = s.replace(old_hook, new_hook, 1)

old_pl = """    print('box wipe: stager $%02X:%04X called by the drawer, message hook at '
          '$%02X:%04X on $03:EB9E' % (*snes_of_rom(E3_WIPE), ab, aa))
"""
assert s.count(old_pl) == 1, 'wipe print'
new_pl = """    print('box blanking: $%02X:%04X on $03:EB9E blanks the box text area at '
          'every new entry (%d CPU writes per message)' % (ab, aa, 960))
"""
s = s.replace(old_pl, new_pl, 1)

# scratch_hits helper next to snes_of_rom
anchor = 'class Asm:'
assert s.count(anchor) == 1
helper = '''def scratch_hits(code):
    """Absolute accesses inside the game's live workspace $0d40-$0d5f."""
    absops = {0xAD: 'lda', 0x8D: 'sta', 0x9C: 'stz', 0xBD: 'lda,x', 0x9D: 'sta,x',
              0xB9: 'lda,y', 0x99: 'sta,y', 0xCD: 'cmp', 0xEE: 'inc', 0xCE: 'dec',
              0xCC: 'cpy', 0xEC: 'cpx', 0x2C: 'bit', 0x2E: 'rol', 0x4E: 'lsr',
              0x0C: 'tsb', 0x1C: 'trb', 0x0E: 'asl', 0x6E: 'ror'}
    hits = []
    for i in range(len(code) - 2):
        op = code[i]
        if op in absops:
            addr = code[i + 1] | (code[i + 2] << 8)
            if 0x0D40 <= addr <= 0x0D5F:
                hits.append((i, absops[op], '$%04X' % addr))
    return hits


'''
s = s.replace(anchor, helper + anchor, 1)

assert s != orig
io.open(SRC, 'w', encoding='utf-8', newline='').write(s)
print('cnbuild5.py patched: %d B -> %d B' % (len(orig), len(s)))