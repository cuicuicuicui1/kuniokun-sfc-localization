"""Step the drawer in the simulator and print the machine state at the point
where it reads glyph data, so the stack layout can be checked against the
offsets the generated code uses."""
import sys
sys.path.insert(0, '.')
import cnbuild5 as cb

src = open('verify16.py', encoding='utf-8').read()
g = {'__name__': 'v16head'}
exec(compile(src[:src.index('# ------')], 'v16head', 'exec'), g)
chunk = src[src.index("print('C1 drawer simulation')"):src.index('skip = set()')]
exec(compile(chunk.split('\n', 1)[1], 'v16helpers', 'exec'), g)

find = sys.argv[1] if len(sys.argv) > 1 else '019974'
idx = int(sys.argv[2], 16) if len(sys.argv) > 2 else 2
addr = g['addr']
msg = g['message_at'](addr[find])
cpu = g['setup'](msg, idx, 2, 0, 0, code=msg[idx])
w = cpu.bus.wram

want_pc = {0x82C5: 'first glyph word read', 0x829A: 'DBR load',
           0x82A3: 'PA for the VMA', 0x82B0: 'store VMA', 0x82A7: 'mask PA'}
seen = 0
for n in range(4000):
    if cpu.pbr == 0x3E and cpu.pc in want_pc:
        st = ' '.join('%02X' % w[0x0100 + ((cpu.s + k) & 0xFFFF)] for k in range(6))
        print('%-22s pc $%04X  s $%04X  stack(S+0..5) %s  X $%04X Y $%04X A $%04X '
              'db $%02X m8 %s x8 %s' % (want_pc[cpu.pc], cpu.pc, cpu.s, st,
                                        cpu.x, cpu.y, cpu.a, cpu.db, cpu.m8, cpu.x8))
        seen += 1
        if seen > 12:
            break
    if cpu.s > cpu.entry_s:
        print('returned at pc $%04X' % cpu.pc)
        break
    cpu.step()