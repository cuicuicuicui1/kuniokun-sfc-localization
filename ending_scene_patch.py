"""Release stale GAMEPLAY train state only at eventAC's station reveal.

The original credits VM owns its station vignette with $1DA8 bit20 set.
Native FB28 deliberately suppresses new gameplay trains under this flag, but
an inherited NONZERO phase still runs FB01 physics and its APU requests. Clear
only DE1/DE2 at the exact reveal. Forcing phase80 would wrongly start a train:
a cold Japanese counterexample had phase0, fixed pillars and no station SFX.
Do not replace physics, APU data, timers, actors, queues or HDMA tables.
"""
SCENE_ROM = 0x1F5D00  # explicit NEW page in the builder's expanded code bank
SCENE_LIMIT = SCENE_ROM + 0x100
HOOK = 0x395A9        # 07:95A9, original opcode51 scene reveal
ORIGINAL = bytes.fromhex('22 B7 9C 00')
INDENT_ROM = SCENE_ROM + 0x80
INDENT_HOOK = 0x1FD56
INDENT_ORIGINAL = bytes.fromhex('AD 74 03 09 08')


def build(Asm):
    a = Asm(SCENE_ROM)
    # Save full A/B and P, never narrow X/Y. Long addresses ignore the caller's
    # DBR/DP; the native callee still receives those registers unchanged.
    a.hexs('08 C2 20 48 E2 20')
    for address, value in ((0x0900, 0x27), (0x1D23, 0xAC),
                           (0x1D20, 0xB8), (0x1D21, 0xFE)):
        a.hexs('AF %02X %02X 7E C9 %02X' % (address & 255, address >> 8, value))
        a.rel(0xD0, 'native')
    # With native cutscene flag20 active, phase0 leaves the original VM in
    # charge. Do NOT force80/FB73: that adds motion and repeated sound fades.
    a.hexs('A9 00 8F E1 0D 7E A9 00 8F E2 0D 7E')
    a.label('native')
    a.hexs('C2 20 68 28')
    a.hexs(ORIGINAL.hex())
    a.op(0x6B)
    code = a.done()
    assert len(code) <= SCENE_LIMIT - SCENE_ROM
    return code


def build_indent(Asm):
    """F6 erases/indents FIVE cells, it is NOT a newline or centering.

    Original 8x16 Japanese names included enough leading spaces to fit.
    Pool/ASCII-pair names can be 24 cells; don't steal their first five.
    Only eventAC skips F6 via the original CLC/RTS exit at 03:FCE8.
    """
    a=Asm(INDENT_ROM)
    a.hexs('08 C2 20 48 E2 20 AF 23 1D 7E C9 AC')
    a.rel(0xD0,'ordinary')
    a.hexs('C2 20 68 28')
    a.long_to(0x1FCE8)
    a.label('ordinary')
    a.hexs('C2 20 68 28')
    a.hexs(INDENT_ORIGINAL.hex())
    a.long_to(INDENT_HOOK+5)
    return a.done()


def install(rom, Asm):
    assert len(rom) == 0x200000, 'expected expanded unheadered project ROM'
    assert rom[HOOK:HOOK + 4] == ORIGINAL, 'original opcode51 consumer changed'
    assert rom[INDENT_HOOK:INDENT_HOOK+5] == INDENT_ORIGINAL, 'original F6 consumer changed'
    # This reservation follows garage 1F5C00..5CFF and precedes the list
    # renderer at 1F6000. It is expanded code-bank ownership, NOT an original
    # zero-filled resource inferred to be free. Check the whole new page.
    assert rom[SCENE_ROM:SCENE_LIMIT] == bytes(0x100), 'ending scene page occupied'
    code = build(Asm)
    rom[SCENE_ROM:SCENE_ROM + len(code)] = code
    rom[HOOK:HOOK + 4] = bytes.fromhex('22 00 DD 3E')
    indent=build_indent(Asm)
    assert SCENE_ROM+len(code)<=INDENT_ROM and INDENT_ROM+len(indent)<=SCENE_LIMIT
    rom[INDENT_ROM:INDENT_ROM+len(indent)]=indent
    rom[INDENT_HOOK:INDENT_HOOK+5]=bytes.fromhex('5C 80 DD 3E EA')
    return {'rom': SCENE_ROM, 'limit': SCENE_LIMIT, 'hook': HOOK,
            'bytes': len(code)+len(indent), 'indent_rom': INDENT_ROM, 'indent_hook': INDENT_HOOK, 'event': 0xAC, 'vm': 0xFEB8, 'map': 0x27}
