"""Run the menu-label uploader in the 65816 model and check what it stages.

The stub copies glyphs from the pool into the upload queue a few per call.  This
executes it directly with a hand-made WRAM state (an empty queue, the pending
counter armed) and inspects the queue entries it produced, so a wrong VRAM
address, a wrong source address or a wrong byte count shows up without needing
to reach the menu in an emulator.

    python test_menuload.py <rom built with CMDWIN=2>
"""
import sys
sys.path.insert(0, '.')
import cnbuild5 as cb
import sim65816

path = sys.argv[1] if len(sys.argv) > 1 else cb.OUT_ROM
rom = open(path, 'rb').read()
cb.load_build_params()
if cb.CMDWIN != 2:
    raise SystemExit('build with CMDWIN=2 first')

# the table the stub reads: [vram t][vram u][pool addr][pool bank]
tab = rom[cb.MENU_TAB:cb.MENU_TAB + 70]
nglyph = 10
# the pool's glyph for each entry, from the build's own glyph64()
par_cell = None
import json
par = json.load(open(cb.BASE + '/cn_build_params.json', encoding='utf-8'))
chars = []
for _r, _c, txt in cb.MENU_LABELS:
    for ch in txt:
        if ch not in chars:
            chars.append(ch)

cpu = sim65816.CPU(rom)
w = cpu.bus.wram
w[cb.MENU_LOAD] = 1                       # armed, start from the first glyph
w[0x09DF] = 0x00                          # empty queue, page $0B00
w[0x09DE] = 0xA5  # unrelated graphics queue state
w[0x09E0:0x09E2] = bytes.fromhex('f8ff')  # live negative train displacement

cpu.pbr = cb.MENU_STUB >> 15
cpu.pc = 0x8000 + (cb.MENU_STUB & 0x7FFF)
cpu.db = 0x03
cpu.s = 0x01FF
cpu.push8(0xFF)                           # a fake caller return address
cpu.push8(0xFF)
entry_s = cpu.s
cpu.m8 = cpu.x8 = True

steps = 0
while steps < 200000 and cpu.s <= entry_s:
    cpu.step()
    steps += 1
print('stub ran %d steps, s=%04X pc=%02X:%04X' % (steps, cpu.s, cpu.pbr, cpu.pc))

assert w[0x09DE] == 0xA5 and w[0x09E0:0x09E2] == bytes.fromhex('f8ff'), 'menu uploader changed neighboring graphics/train state'

# the first call stages three glyphs = six 36 byte entries, at the queue page
Q = 0x0B00
cur = 0
fail = 0
for i in range(3):
    t = tab[7 * i] | (tab[7 * i + 1] << 8)          # the table holds the VRAM
    u = tab[7 * i + 2] | (tab[7 * i + 3] << 8)      # word addresses directly
    want = cb.glyph64(chars[i])
    for half, tile in ((0, t), (1, u)):
        hdr = w[Q + cur] | (w[Q + cur + 1] << 8)
        vmain = w[Q + cur + 2]
        cnt = w[Q + cur + 3]
        data = bytes(w[Q + cur + 4 + k] for k in range(32))
        want_hdr = tile
        want_data = want[half * 32:(half + 1) * 32]
        ok = hdr == want_hdr and vmain == 0x80 and cnt == 32 and data == want_data
        if not ok:
            fail += 1
            print('  glyph %d half %d (%r): hdr %04X want %04X, $2115 %02X, count %d, data %s'
                  % (i, half, chars[i], hdr, want_hdr, vmain, cnt,
                     'ok' if data == want_data else 'WRONG'))
        cur += 36
print('queue cursor now $%04X (want $%04X)' % (w[0x09DF], cur))
print('pending counter $%02X (want %02X)' % (w[cb.MENU_LOAD], 1 + 3))
if w[0x09DF] != cur:
    fail += 1
    print('  the stub did not commit the cursor the entries need')
if w[cb.MENU_LOAD] != 4:
    fail += 1
    print('  the pending counter did not advance by three')
print()
if fail:
    raise SystemExit('%d uploader check(s) FAILED' % fail)
print('OK: the uploader stages the pool glyphs into the slot tiles')
