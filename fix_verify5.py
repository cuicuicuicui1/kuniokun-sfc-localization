"""Update verify5 for the restructured drawer copy.

The copy no longer contains the original routine (it JMLs into bank $03 for
every job), so "the drawer returned" can no longer be detected by watching for
one of its RTS addresses.  The harness now runs until the SP pops the emulated
caller's return address AND asserts the program bank came back to $03 -- the
exact class of bug that froze the game (an RTS executed under PBR = $3E).
"""
PATH = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/verify5.py'
s = open(PATH, encoding='utf-8').read()

old_defs = """def rts_sites(base, blob):
    import mos65xx
    out = []
    for ins in mos65xx.disassemble(blob, address=0x8000 + (base % 0x8000)):
        if ins.mnemonic == 'rts':
            out.append(ins.address)          # bank-local PC, as cpu.pc reports
    return out


RTS_SITES = rts_sites(cb.E3_DRAWER, cb.build_drawer_copy())
RTS = RTS_SITES[-1]
"""
new_defs = '''DRAWER_BANK = 0x03            # every exit of the patched drawer returns here


def run_drawer(cpu, limit=5000):
    """Run until the drawer returns to its caller.  The hook is a JML, so the
    copy must jump (not RTS) back into bank $03 for every job; the emulated
    caller's return address is the marker that we are back, and the program bank
    must be the engine's again.  Returns (ok, steps)."""
    steps = 0
    while steps < limit:
        cpu.step()
        steps += 1
        if cpu.s > cpu.entry_s:              # the RTS popped the fake return addr
            return (cpu.pbr == DRAWER_BANK and cpu.pc in (0x0000, 0x10000)), steps
        if cpu.s < 0x0100:                   # stack ran away
            break
    return False, steps
'''
assert old_defs in s
s = s.replace(old_defs, new_defs)

old_c1 = """        cpu = setup(msg, i, row, col, stage)
        steps = 0
        while cpu.pc not in RTS_SITES and steps < 5000:
            cpu.step()
            steps += 1
        if cpu.pc not in RTS_SITES:
            fail('entry %s byte %d: drawer did not return (pc $%04X)' % (key, i, cpu.pc))
            break
        if cpu.s != cpu.entry_s:
            fail('entry %s byte %d: stack unbalanced (s $%04X want $%04X)'
                 % (key, i, cpu.s, cpu.entry_s))
            break
"""
new_c1 = """        cpu = setup(msg, i, row, col, stage)
        ok, steps = run_drawer(cpu)
        if not ok:
            fail('entry %s byte %d: drawer did not return to bank $03 '
                 '(pc $%02X:%04X s $%04X)' % (key, i, cpu.pbr, cpu.pc, cpu.s))
            break
        if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
            fail('entry %s byte %d: stack unbalanced (s $%04X want $%04X)'
                 % (key, i, cpu.s, (cpu.entry_s + 2) & 0xFFFF))
            break
"""
assert old_c1 in s
s = s.replace(old_c1, new_c1)

old_loop = """        for base, src, rts in ((ORIG_DRAWER, orig, ORIG_RTS),
                               (cb.E3_DRAWER, rom, RTS_SITES)):"""
new_loop = """        for base, src in ((ORIG_DRAWER, orig), (cb.E3_DRAWER, rom)):"""
assert old_loop in s
s = s.replace(old_loop, new_loop)

old_c2 = """                steps = 0
                while cpu.pc != rts and not (isinstance(rts, list) and cpu.pc in rts) and steps < 5000:
                    cpu.step()
                    steps += 1
                if cpu.s != cpu.entry_s:
                    fail('stack unbalanced in %s on %s (s $%04X)' % (base, key, cpu.s))
"""
new_c2 = """                ok, steps = run_drawer(cpu)
                if not ok:
                    fail('%06X on %s byte %d: no return to bank $03 (pc $%02X:%04X)'
                         % (base, key, i, cpu.pbr, cpu.pc))
                    break
                if cpu.s != ((cpu.entry_s + 2) & 0xFFFF):
                    fail('stack unbalanced in %06X on %s (s $%04X)'
                         % (base, key, cpu.s, (cpu.entry_s + 2) & 0xFFFF))
"""
assert old_c2 in s
s = s.replace(old_c2, new_c2)
s = s.replace("""ORIG_RTS = 0x8000 + (ORIG_DRAWER % 0x8000) + 78 - 1
""", "")
open(PATH, 'w', encoding='utf-8').write(s)
print('verify5 patched for the JML-based drawer')
print('  build_drawer_copy called from:', [l.strip() for l in open(
    'C:/Users/<user>/.zcode/workspace/default/sfc-recon/cnbuild5.py',
    encoding='utf-8').read().split('\\n') if 'build_drawer_copy()' in l or 'build_slotpair(' in l])