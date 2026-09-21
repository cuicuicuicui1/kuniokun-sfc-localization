"""Simulator and verifier fixes found while debugging the 16x16 build.

1. sim65816 had no PHP (0x08) / PLP (0x28) -- the wipe stager starts with PHP and
   the text driver's epilogue ends with PLP.
2. verify16.flush() must drop the DMA log: the engine flusher legitimately uses
   DMA channel 0, only the drawer itself may not.
3. E/F ran the hooked code with `run_from`, which insists the routine returns to
   $03:0000 -- both hooks deliberately hand control back into the engine, so they
   need their own exit checks.
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- sim65816
p = os.path.join(BASE, 'sim65816.py')
s = open(p, encoding='utf-8').read()
old = """        elif op == 0x68:                     # PLA
"""
new = """        elif op == 0x08:                     # PHP
            self.push8((0x80 if self.n else 0) | (0x40 if self.v else 0) |
                       (0x20 if self.m8 else 0) | (0x10 if self.x8 else 0) |
                       (0x08 if self.d else 0) | (0x04 if self.i else 0) |
                       (0x02 if self.z else 0) | (0x01 if self.c else 0))
        elif op == 0x28:                     # PLP
            v = self.pop8()
            self.n = bool(v & 0x80)
            self.v = bool(v & 0x40)
            self.m8 = bool(v & 0x20)
            self.x8 = bool(v & 0x10)
            self.d = bool(v & 0x08)
            self.i = bool(v & 0x04)
            self.z = bool(v & 0x02)
            self.c = bool(v & 0x01)
        elif op == 0x68:                     # PLA
"""
assert s.count(old) == 1
s = s.replace(old, new)
open(p, 'w', encoding='utf-8').write(s)
print('sim65816: PHP/PLP added')

# ---------------------------------------------------------------- verify16
p = os.path.join(BASE, 'verify16.py')
s = open(p, encoding='utf-8').read()

old = """        if cpu.s > entry_s:
            return cpu.pbr == 0x00 and cpu.pc == 0xFFFF, steps
    return False, steps
"""
new = """        if cpu.s > entry_s:
            cpu.dma_log = []                # the flusher DMAs; the drawer may not
            return cpu.pbr == 0x00 and cpu.pc == 0xFFFF, steps
    return False, steps
"""
assert s.count(old) == 1
s = s.replace(old, new)

old = """def pool_half(ch, k):"""
new = """def run_to(cpu, pbr, pc, limit=40000):
    \"\"\"Run until control reaches pbr:pc (used by the hooks that hand control
    back into the engine instead of returning).\"\"\"
    steps = 0
    while steps < limit:
        if cpu.pbr == pbr and cpu.pc == pc:
            return True, steps
        cpu.step()
        steps += 1
    return False, steps


def pool_half(ch, k):"""
assert s.count(old) == 1
s = s.replace(old, new)

# E: the stager JMLs into the driver at $03:EE74
old = """    cpu = wipe_setup(pend, cur, top, bot, 0)
    ok, steps = run_from(cpu)
    if not ok:
        fail('E: the stager did not return to bank $03 (pc $%02X:%04X)'
             % (cpu.pbr, cpu.pc))
        continue
    if cpu.s != cpu.entry_s:
        fail('E: the stager left the stack unbalanced ($%04X want $%04X)'
             % (cpu.s, cpu.entry_s))
"""
new = """    cpu = wipe_setup(pend, cur, top, bot, 0)
    ok, steps = run_to(cpu, 0x03, 0xEE74)
    if not ok:
        fail('E: the stager did not hand control back to the driver '
             '(pc $%02X:%04X)' % (cpu.pbr, cpu.pc))
        continue
    # the stager deliberately leaves its PHP/PHB pushes for the driver epilogue
    if cpu.s != ((cpu.entry_s - 2) & 0xFFFF):
        fail('E: the stager stack is $%04X want $%04X' % (cpu.s,
                                                          (cpu.entry_s - 2) & 0xFFFF))
"""
assert s.count(old) == 1
s = s.replace(old, new)

# F: the arm hook JMLs back into the per line loader at $03:EBA3
old = """    cpu = arm_setup(flag73, pend, top, bot)
    ok, steps = run_from(cpu)
    if not ok:
        fail('F: the arm hook did not return to bank $03 (pc $%02X:%04X)'
             % (cpu.pbr, cpu.pc))
        continue
    if cpu.s != cpu.entry_s:
        fail('F: the arm hook left the stack unbalanced')
"""
new = """    cpu = arm_setup(flag73, pend, top, bot)
    ok, steps = run_to(cpu, 0x03, 0xEBA3)
    if not ok:
        fail('F: the arm hook did not hand control back to the loader '
             '(pc $%02X:%04X)' % (cpu.pbr, cpu.pc))
        continue
    if cpu.s != cpu.entry_s:
        fail('F: the arm hook left the stack unbalanced')
"""
assert s.count(old) == 1
s = s.replace(old, new)

open(p, 'w', encoding='utf-8').write(s)
print('verify16: flush dma log cleared, E/F exit checks fixed')