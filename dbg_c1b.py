"""reproduce the first C1 failure with a step trace"""
import io
import sim65816
import cnbuild5 as cb

src = io.open('verify16.py', encoding='utf-8', newline='').read()
pre = src[:src.index('skip = set()')]
g = {}
exec(compile(pre, 'verify16-head', 'exec'), g)

recs, addr, cell, rev, rom = g['recs'], g['addr'], g['cell'], g['rev'], g['rom']
is_cn, is_fx, message_at = g['is_cn'], g['is_fx'], g['message_at']
setup, run_from = g['setup'], g['run_from']

E3 = cb.E3_DRAWER
target = None
for r in recs:
    key = '%06X' % r['text_rom_off']
    if key not in addr or key in g.get('NO_TR', set()):
        continue
    msg = message_at(addr[key])
    for i, code in enumerate(msg):
        if code >= 0xF0:
            continue
        target = (key, msg, i)
        break
    if target:
        break
key, msg, i = target
print('entry %s byte %d code $%02X msg %s' % (key, i, msg[i], msg.hex(' ')[:40]))

cpu = setup(msg, i, 0, 0, 0)
w = cpu.bus.wram
hist = []
for n in range(6000):
    hist.append((cpu.pbr, cpu.pc, cpu.a, cpu.x, cpu.y, cpu.m8, cpu.x8, cpu.s))
    try:
        cpu.step()
    except NotImplementedError as exc:
        print('CRASH', exc)
        break
    if cpu.s > cpu.entry_s:
        print('returned to %02X:%04X after %d steps' % (cpu.pbr, cpu.pc, n))
        hist = hist[-20:]
        break
    if len(hist) > 30:
        hist.pop(0)
else:
    print('no return after 6000 steps; pc %02X:%04X' % (cpu.pbr, cpu.pc))
    hist = hist[-20:]
for pbr_, pc_, a_, x_, y_, m_, x8_, s_ in hist:
    print('  %02X:%04X A=%02X X=%04X Y=%04X m=%d x=%d s=%04X'
          % (pbr_, pc_, a_, x_, y_, m_, x8_, s_))