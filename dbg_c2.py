"""compare my delegated original path with the original drawer, byte by byte"""
import io
import sim65816
import cnbuild5 as cb

src = io.open('verify16.py', encoding='utf-8', newline='').read()
pre = src[:src.index('skip = set()')]
g = {}
exec(compile(pre, 'verify16-head', 'exec'), g)
setup, run_from = g['setup'], g['run_from']
rom = g['rom']

code = 0x09
msg = bytes([code, 0x12, 0x34, 0x56, 0x78, 0xF2])
row, col = 0, 0

c1 = setup(msg, 0, row, col, 0, base=cb.E3_DRAWER)
c1.db = 0x03
c1.bus.wram[0x12] = code
ok1, s1 = run_from(c1)

c2 = sim65816.CPU(rom)
c2.pbr, c2.pc = 0x03, 0xFA30
c2.m8 = c2.x8 = True
c2.db = 0x03
c2.bus.wram[0x03EA:0x03EA + len(msg)] = msg
c2.bus.wram[0x036E] = row
c2.bus.wram[0x036F] = col
c2.bus.wram[0x09DF] = 0
c2.bus.wram[0x12] = code
c2.a = code
c2.push8(0xFF)
c2.push8(0xFF)
c2.entry_s = c2.s
ok2, s2 = run_from(c2)

print('mine ok=%s steps=%d $09DF=$%02X' % (ok1, s1, c1.bus.wram[0x09DF]))
print('orig ok=%s steps=%d $09DF=$%02X' % (ok2, s2, c2.bus.wram[0x09DF]))
print('mine queue:', bytes(c1.bus.wram[0x0B00:0x0B00 + c1.bus.wram[0x09DF]]).hex(' '))
print('orig queue:', bytes(c2.bus.wram[0x0B00:0x0B00 + c2.bus.wram[0x09DF]]).hex(' '))
for k in (0x036E, 0x036F):
    print('  $%04X mine $%02X orig $%02X' % (k, c1.bus.wram[k], c2.bus.wram[k]))
print('  $09DD mine $%02X orig $%02X' % (c1.bus.wram[0x09DD], c2.bus.wram[0x09DD]))