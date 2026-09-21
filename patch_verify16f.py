"""Fix the F (arm hook) checks in verify16.py.

The hook replays `LDA #$40 / TSB $0373`, so bit 6 is always set afterwards -- the
check has to verify that and that no other bit was lost. `armed` must compare
against the pre-existing pending flag, otherwise "a wipe was already pending"
looks like "this hook armed it". WIPE_CUR gets a sentinel so that "left alone"
is distinguishable from "armed with row 0".
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
p = os.path.join(BASE, 'verify16.py')
s = open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')

old = """    w[cb.WIPE_PEND], w[cb.WIPE_TOP], w[cb.WIPE_BOT] = pend, top, bot
    cpu.push8(0x03)
    cpu.push8(0xBB)
"""
new = """    w[cb.WIPE_PEND], w[cb.WIPE_TOP], w[cb.WIPE_BOT] = pend, top, bot
    w[cb.WIPE_CUR] = 0x55                # sentinel: the hook must not touch it
    cpu.push8(0x03)
    cpu.push8(0xBB)
"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)

old = """    w = cpu.bus.wram
    if w[0x0373] & 0x40 != flag73 & 0x40:
        fail('F: $0373 = $%02X, the eaten TSB was not replayed' % w[0x0373])
    armed = w[cb.WIPE_PEND] == 1
    if armed != want_arm:
        fail('F: flag $%02X pend %d top %d bot %d armed %s want %s'
             % (flag73, pend, top, bot, armed, want_arm))
    if armed and (w[cb.WIPE_CUR] != (bot & 0x0F)):
        fail('F: cursor $%02X want $%02X' % (w[cb.WIPE_CUR], bot & 0x0F))
"""
new = """    w = cpu.bus.wram
    if not (w[0x0373] & 0x40):
        fail('F: the replayed TSB did not set bit 6 ($0373 = $%02X)' % w[0x0373])
    if (w[0x0373] & 0xBF) != (flag73 & 0xBF):
        fail('F: $0373 = $%02X lost bits of $%02X' % (w[0x0373], flag73))
    armed = (w[cb.WIPE_PEND] == 1) and (pend == 0)
    if armed != want_arm:
        fail('F: flag $%02X pend %d top %d bot %d armed %s want %s'
             % (flag73, pend, top, bot, armed, want_arm))
    if armed and (w[cb.WIPE_CUR] != (bot & 0x0F)):
        fail('F: cursor $%02X want $%02X' % (w[cb.WIPE_CUR], bot & 0x0F))
    if not armed and w[cb.WIPE_CUR] != 0x55:
        fail('F: cursor $%02X, a wipe that was not armed was moved'
             % w[cb.WIPE_CUR])
"""
assert s.count(old) == 1, s.count(old)
s = s.replace(old, new)
open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('F checks fixed')