"""For a failing message byte, print what the drawer staged and find which pool
offset those bytes actually came from.

Loads only the data tables and the drawer-simulation helpers out of verify16.py
(the full verifier would run every check and then SystemExit).
"""
import sys
sys.path.insert(0, '.')
import sim65816
import cnbuild5 as cb

roman = open('kuniokun_cn.smc', 'rb').read()

src = open('verify16.py', encoding='utf-8').read()
find = sys.argv[1] if len(sys.argv) > 1 else '019974'
g = {'__name__': 'v16head'}
exec(compile(src[:src.index('# ------')], 'v16head', 'exec'), g)
chunk = src[src.index("print('C1 drawer simulation')"):src.index('skip = set()')]
exec(compile(chunk.split('\n', 1)[1], 'v16helpers', 'exec'), g)

recs, addr, cell, rev = g['recs'], g['addr'], g['cell'], g['rev']
LEFT, RIGHT = g['LEFT'], g['RIGHT']
setup, run_from, pool_half = g['setup'], g['run_from'], g['pool_half']
message_at = g['message_at']

idx = int(sys.argv[2], 16) if len(sys.argv) > 2 else 2
rec = [r for r in recs if '%06X' % r['text_rom_off'] == find][0]
msg = message_at(addr[find])
code = msg[idx]
print('message %s byte %d: $%02X $%02X (len %d)' % (find, idx, code, msg[idx + 1],
                                                    len(msg)))
print('msg:', msg.hex(' '))
ch = rev[(code - cb.PREFIX0, msg[idx + 1])]
page, slot = cell[ch]
print('char %s: page %d slot %d  LEFT $%02X RIGHT $%02X'
      % (ch, page, slot, LEFT[slot], RIGHT[slot]))

cpu = setup(msg, idx, 2, 0, 0, code=code)
ok, steps = run_from(cpu)
print('drawer returned:', ok, 'stack $%04X entry $%04X  ($03E9 = $%02X, col %d)'
      % (cpu.s, cpu.entry_s, cpu.bus.wram[0x03E9], cpu.bus.wram[0x036F]))
got = bytes(cpu.bus.wram[0x0B00:0x0B00 + 88])
print('staged:', got.hex(' '))
print('entry0: vma $%04X count %d' % (got[0] | got[1] << 8, got[3]))
print('entry1: vma $%04X count %d' % (got[36] | got[37] << 8, got[39]))

for half, data in (('left (TL/BL)', got[4:36]), ('right (TR/BR)', got[40:72])):
    want = pool_half(ch, 0 if half.startswith('left') else 1)
    hit = []
    for p in range(0, 13):
        base = cb.POOL_ROM + p * 0x8000
        for i in range(0, 0x8000 - 32):
            if roman[base + i:base + i + 32] == data:
                hit.append('page %d id %d off+%d' % (p, i // 64, i % 64))
    print('%s want: %s' % (half, want.hex(' ')))
    print('%s staged found at: %s' % (half, hit[:6] or 'NOWHERE in the pool'))
print('expected pool offset: page %d id %d => bank $%02X offset $%04X'
      % (page, slot, 0x21 + page, 0x8000 + slot * 64))