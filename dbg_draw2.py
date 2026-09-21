"""trace one drawer call: python dbg_draw2.py <kind> <row> <col> <stage> [code]"""
import io
import sys
import cnbuild5 as cb

src = io.open('verify16.py', encoding='utf-8', newline='').read()
pre = src[:src.index('skip = set()')]
g = {}
exec(compile(pre, 'verify16-head', 'exec'), g)
setup = g['setup']

kind = sys.argv[1] if len(sys.argv) > 1 else 'cn'
row = int(sys.argv[2], 0) if len(sys.argv) > 2 else 3
col = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0
stage = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0
code = int(sys.argv[5], 0) if len(sys.argv) > 5 else None

# pick a message byte of the wanted kind
msg = None
for r in g['recs']:
    key = '%06X' % r['text_rom_off']
    if key not in g['addr']:
        continue
    m = g['message_at'](g['addr'][key])
    for i, c in enumerate(m):
        if c >= 0xF0:
            continue
        if kind == 'cn' and (g['is_cn'](c) or g['is_fx'](c)):
            msg, idx = m, i
            break
        if kind == 'occ' and not (g['is_cn'](c) or g['is_fx'](c)):
            msg, idx = m, i
            break
    if msg:
        break
cpu = setup(msg, idx, row, col, stage, code=code)
w = cpu.bus.wram
print('case %s row %d col %d stage $%02X code $%02X (byte %d of %s)'
      % (kind, row, col, stage, w[0x12], idx, '%06X' % r['text_rom_off']))
print('entry_s $%04X' % cpu.entry_s)
hist = []
for n in range(9000):
    hist.append((cpu.pbr, cpu.pc, cpu.a, cpu.x, cpu.y, cpu.m8, cpu.x8, cpu.s))
    if len(hist) > 40:
        hist.pop(0)
    cpu.step()
    if cpu.s > cpu.entry_s or cpu.s < 0x0100:
        break
print('stopped after %d steps: %02X:%04X s $%04X (entry_s $%04X)'
      % (n, cpu.pbr, cpu.pc, cpu.s, cpu.entry_s))
printf = '  %02X:%04X A=%02X X=%04X Y=%04X m=%d x=%d s=%04X'
for h in hist[-24:]:
    print(printf % h)
print('queue: %s' % bytes(w[0x0B00:0x0B00 + w[0x09DF]]).hex(' ')[:120])
print('$09DF=$%02X $09DD=$%02X $03E9=$%02X $036F=$%02X'
      % (w[0x09DF], w[0x09DD], w[0x03E9], w[0x036F]))