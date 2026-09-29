"""Exercise the real $03:EE70 tick: held vs edge input, release and queue safety.

$00:BBF7 keeps P1 held A/X in $031A and B/Y in $031C. $0316/$0318
are edge bytes, NOT held state. PACE is message ticks, not video frames.
"""
import json
from pathlib import Path
from dialogue_model import make_cpu, tick, flush

rom = Path('kuniokun_cn.smc').read_bytes()
params = json.loads(Path('cn_build_params.json').read_text())
pace = params['pace']
counter = params.get('pace_counter', 0x03C4)
assert rom[0x1EEE5:0x1EEEB] == bytes.fromhex('22 00 D8 3E EA EA')
assert rom[0x1F5800:0x1F5804] == bytes.fromhex('08 E2 30 48')

# Normal speed: first attempt immediate, next character every PACE ticks.
c = make_cpu(rom)
for f in range(61):
    tick(c)
    assert c.bus.wram[0x3E9] == 1+f//pace, ('pacing', f, c.bus.wram[0x3E9])
    flush(c)

# Sustained A or B (edge bytes zero), plus a press in every countdown phase.
for button in (0x31A,0x31C):
    for countdown in range(pace+1):
        c = make_cpu(rom); w=c.bus.wram
        w[counter]=countdown; w[button]=0x80
        for f in range(3):
            tick(c)
            assert w[0x3E9]==3*(f+1), ('held input',hex(button),countdown,f,w[0x3E9])
            assert w[counter]==0, 'bypass must discard the old countdown'
            flush(c)
        w[button]=0
        for f in range(15):
            tick(c)
            assert w[0x3E9]==10+f//pace, ('release',f,w[0x3E9])
            flush(c)

# X/Y, another player's buttons and edge-only bits must not engage P1 A/B fast mode.
for address,mask in ((0x31A,0x40),(0x31C,0x40),(0x31B,0x80),(0x31D,0x80),(0x316,0x80),(0x318,0x80)):
    c=make_cpu(rom);c.bus.wram[address]=mask
    for f in range(15):
        tick(c)
        assert c.bus.wram[0x3E9]==1+f//pace, ('wrong fast-forward trigger',hex(address),f)
        flush(c)

# The original queue-space allocator still produces one intact cell entry.
c=make_cpu(rom); c.bus.wram[0x36F]=1;tick(c)
expected=[rom[0x1FA8E]+1,rom[0x1FA7E],0x81,4,rom[0x1FB9E+0x41],0x24,rom[0x1FA9E+0x41],0x24]
assert list(c.bus.wram[0xB00:0xB08])==expected
assert c.bus.wram[0x9DF]==8
flush(c)

# Invisible exhausted-buffer fill remains unpaced and resets the count.
c=make_cpu(rom);w=c.bus.wram;w[0x3E9]=200;w[counter]=pace
for i in range(4):
    tick(c)
    assert w[0x36F]==3*(i+1), 'blank fill must remain unpaced'
    assert w[counter]==0
    flush(c)
print('PASS: PACE=%d message ticks; held A/B, every release phase, X/Y/edge isolation, queue, filler'%pace)
