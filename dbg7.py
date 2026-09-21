"""Single step the drawer for one Chinese character and log the script writes."""
import json
import sim65816
import cnbuild5 as cb

rom = open(cb.OUT_ROM, 'rb').read()
recs = json.load(open(cb.BASE + '/kuniokun_text.json', encoding='utf-8'))
params = json.load(open(cb.BASE + '/cn_build_params.json', encoding='utf-8'))
cell = {k: tuple(v) for k, v in params['cell'].items()}
cb.KEEP1.clear()
cb.KEEP1.update(params['keep1'])
cb.SLOTS = params['slots']
cb.PAGES = params['pages']

addr = json.load(open(cb.BASE + '/cn_addr_map.json', encoding='utf-8'))
key = '019921'
off = addr[key]
print('entry', key, 'rebuilt at %06X' % off)
msg = bytearray()
i = off
while rom[i] != 0xF2:
    msg.append(rom[i])
    i += 1
print('message bytes:', msg.hex(' '))

# which byte do we want?  byte 1 is the first Chinese prefix
gi = 1
code = msg[gi]
print('drawing byte %d: code %02X id %02X' % (gi, code, msg[gi + 1]))
# figure out the character via the reverse table
rev = {}
for ch, (p, s) in cell.items():
    rev.setdefault((p, s), ch)
ch = rev[(code - cb.PREFIX0, msg[gi + 1])]
print('character:', ch, 'page/slot', cell[ch])

cpu = sim65816.CPU(rom)
cpu.pbr = cb.E3_DRAWER // 0x8000
cpu.pc = 0x8000 + (cb.E3_DRAWER % 0x8000)
cpu.m8 = True
cpu.x8 = True
cpu.db = 0x03
w = cpu.bus.wram
w[0x03EA:0x03EA + len(msg)] = msg
w[0x03E8] = len(msg) & 0xFF
w[0x03E9] = gi
w[0x036E] = 0
w[0x036F] = 1
w[0x09DF] = 8
w[0x12] = code
cpu.a = code

log = []


def snapshot():
    return (cpu.pc, cpu.a & 0xFF, cpu.x, cpu.y, cpu.db, cpu.m8, cpu.x8)


import mos65xx
blob = cb.build_drawer_copy()
RTS_SITES = [ins.address for ins in mos65xx.disassemble(blob, address=0x8000 + (cb.E3_DRAWER % 0x8000)) if ins.mnemonic == 'rts']
print('RTS sites', [hex(a) for a in RTS_SITES])
seen = set()
steps = 0
while steps < 4000:
    if cpu.pc in RTS_SITES:
        break
    before = snapshot()
    before_script = bytes(w[0x0B00:0x0B40])
    cpu.step()
    steps += 1
    after = snapshot()
    after_script = bytes(w[0x0B00:0x0B40])
    if after_script != before_script:
        diff = [(k, before_script[k], after_script[k])
                for k in range(0x40) if before_script[k] != after_script[k]]
        log.append(('%04X->%04X A=%02X X=%02X Y=%02X' % (before[0], after[0], before[1], before[2], before[3]),
                    diff))
print('steps', steps, 'final pc %04X' % cpu.pc)
for tag, diff in log:
    print(' script write at', tag, diff)
print('vram-needle: pair for ch =', cb.build_slotpair()[0][cell[ch][1]])
print('$0B00..$0B30:', bytes(w[0x0B00:0x0B30]).hex(' '))
print('$09DF=%02X $036E=%02X $036F=%02X $03E9=%02X' % (
    w[0x09DF], w[0x036E], w[0x036F], w[0x03E9]))
print('$0BE6=%02X $0BE7=%02X $4212 snap=%02X' % (w[0x0BE6], w[0x0BE7], w[0x0BE7]))