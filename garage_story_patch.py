"""Synchronize event15's final zero-enemy wait with ORIGINAL battle teardown.

For this ROM only: 07:8E1A is the AC wait success path. In garage event95,
VM=B94B, the original 07:F57E may still be closing reward messages and will
clear player cinematic locks. Do not start the following movement until it
has completed. No NPC removal, HP edits, event/door flags, timer or new WRAM.
"""
SYNC_ROM = 0x1F5C00  # 3E:DC00; reserved page between pace and list renderer
SYNC_LIMIT = SYNC_ROM + 0x100
HOOK = 0x38E1A
ORIGINAL = bytes.fromhex('A9 01 1C 25 1D')


def build(Asm):
    a = Asm(SYNC_ROM)
    # M8 at the original consumer; preserve full A including hidden B, P,
    # X/Y widths, DBR, DP. Never SEP #$10 (would truncate X/Y).
    a.hexs('08 C2 20 48 E2 20')
    for address, value in ((0x0900, 0x4B), (0x1D23, 0x95),
                           (0x1D20, 0x4B), (0x1D21, 0xB9)):
        a.hexs('AD %02X %02X C9 %02X' % (address & 255, address >> 8, value))
        a.rel(0xD0, 'advance')
    a.hexs('AD A9 1D')  # threshold must be ZERO, not a mid-battle count wait
    a.rel(0xD0, 'advance')
    a.hexs('AD 2B 12 0D 2D 12 0D D7 08')
    a.rel(0xD0, 'busy')
    a.label('advance')
    a.hexs('C2 20 68 28')
    a.hexs(ORIGINAL.hex())
    a.long_to(0x38E1F)
    a.label('busy')
    a.hexs('C2 20 68 28')
    # Original wait-busy path pops the enclosing JSR and returns to the
    # interpreter without clearing bit01 of 1D25 or advancing the VM PC.
    a.long_to(0x38E20)
    code = a.done()
    assert len(code) <= SYNC_LIMIT - SYNC_ROM
    return code


def install(rom, Asm):
    assert len(rom) == 0x200000, 'expected expanded unheadered project ROM'
    assert rom[HOOK:HOOK + len(ORIGINAL)] == ORIGINAL, 'garage wait consumer changed'
    # This page belongs to the builder's explicitly expanded code bank, not
    # an inferred hole in original game resources. Check the full reservation.
    assert rom[SYNC_ROM:SYNC_LIMIT] == bytes(SYNC_LIMIT - SYNC_ROM), 'garage sync page occupied'
    code = build(Asm)
    rom[SYNC_ROM:SYNC_ROM + len(code)] = code
    rom[HOOK:HOOK + len(ORIGINAL)] = bytes.fromhex('5C 00 DC 3E EA')
    return {'rom': SYNC_ROM, 'limit': SYNC_LIMIT, 'hook': HOOK,
            'bytes': len(code), 'event': 0x95, 'vm': 0xB94B, 'map': 0x4B}
