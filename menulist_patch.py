"""Queued two-row list renderer for $03:F95D (not the static command window).

The original reader copies encoded strings into 13-byte fields at $040A.
Each row's columns 0 and 13 are mandatory blank separators (names start at
1/14). They temporarily hold source/destination progress, then reset to zero.
No new global WRAM byte, direct VRAM write, or forced queue flush is used.
"""
MENU_LIST_ROM = 0x1F6000

def install(rom, Asm, slot_table, high_table, slots, pages, pool_bank, slot_stride, item_prefix=0xDE):
    assert slots >= 26, 'four live menu names need 26 layout slots'
    assert slot_stride >= slots, 'right-half table must follow every left-half slot'
    hook=0x1F95D
    assert rom[hook:hook+6] == bytes.fromhex('A9 70 22 B6 9A 00')
    a=Asm(MENU_LIST_ROM)
    def hx(s): a.hexs(s)
    def far(op,label): a.far_rel(op,label,'ml_'+label+'_'+str(len(a.b)))
    def get_pair(offset, target):
        addr=((slot_table+offset)&0x7FFF)|0x8000
        hi=((high_table+offset)&0x7FFF)|0x8000
        hx('E2 20 BF %02X %02X 3E EB BF %02X %02X 3E C2 20 85 %02X' % (hi&255, (hi>>8)&255, addr&255, (addr>>8)&255,target))
    def glyph_queue(tile,extra,size):
        # A/X/Y 16-bit throughout the copied words; source pointer is dp $1A.
        hx('C2 30 A5 %02X 0A 0A 0A 09 00 60 9D 00 0B E8 E8' % tile)
        hx('E2 20 A9 80 9D 00 0B E8 A9 %02X 9D 00 0B E8' % size)
        hx('C2 30 A0 %02X 00' % extra)
        for _ in range(size//2): hx('B7 1A 9D 00 0B E8 E8 C8 C8')
    def cell(tile,add):
        hx('C2 20 A5 20')
        if add: hx('1A')
        hx('9D 00 0B E8 E8 E2 20 A9 81 9D 00 0B E8 A9 04 9D 00 0B E8')
        hx('C2 20 A5 %02X 09 00 24 9D 00 0B E8 E8 1A 9D 00 0B E8 E8' % tile)
    # JML inherits the caller's bank-3 JSR return. The main five-choice command
    # window calls from F77E (stack return F780); it must retain its FA/FB codes.
    hx('08 C2 20 A3 02 C9 80 F7 E2 20')
    far(0xD0,'list')
    hx('28 A9 70 22 B6 9A 00')
    a.long_to(0x1F963)
    a.label('list')
    hx('8B C2 20')
    saved=list(range(0x14,0x30,2))
    for dp in saved: hx('A5 %02X 48' % dp)
    # NMI advances the READ cursor ($09DD), not the append cursor ($09DF).
    # The original allocator alone may reclaim consumed queue entries. Skipping
    # it leaves a full queue forever even though NMI has uploaded every byte.
    # Out-of-contract 16-bit cursors defer without invoking its 8-bit compare.
    hx('E2 20 AD E0 09');far(0xD0,'wait')
    hx('A9 58 22 B6 9A 00');far(0xB0,'wait')
    hx('E2 30 AD 9E 03 29 01')
    a.rel(0xF0,'rowzero');hx('A9 1A');a.rel(0x80,'rowbase')
    a.label('rowzero');hx('A9 00')
    a.label('rowbase');hx('85 14 AA BD 0A 04')
    far(0xD0,'ready')
    # Row-start clearing consumes 112 bytes, preserving the in-flight queue.
    hx('C2 20 AD DF 09 C9 90 00 E2 20');far(0xB0,'wait')
    hx('C2 30 AE DF 09')
    for extra in (0,32):
        hx('E2 20 AD 6E 03 C2 20 29 FF 00')
        for _ in range(6):hx('0A')
        hx('18 69 %02X 7C 9D 00 0B E8 E8' % (3+extra))
        hx('E2 20 A9 80 9D 00 0B E8 A9 34 9D 00 0B E8 C2 20 A9 00 2C')
        hx('A0 1A 00')
        label='clear'+str(extra);a.label(label)
        hx('9D 00 0B E8 E8 88');a.rel(0xD0,label)
    hx('8E DF 09 E2 30 A6 14 A9 01 9D 0A 04 9D 17 04')
    a.label('ready')
    hx('A6 14 BD 0A 04 85 15 BD 17 04 85 16')
    a.label('next')
    hx('A5 15 C9 1A');far(0xB0,'done')
    hx('18 65 14 AA BD 0A 04 85 17')
    far(0xF0,'endfield')
    # Source ends at the 13-byte boundary even if a malformed input lacks zero.
    hx('A5 15 C9 0D');far(0xF0,'endfield')
    # Cell address comes from the ORIGINAL row tables, word units.
    hx('AC 6E 03 B9 8E FA 18 65 16 85 20 B9 7E FA 69 00 85 21')
    # Distinct layout slots for each live row/column (not DSATUR text slots).
    # Physical row parity, NOT $039E (which stays zero for every single-row
    # scroll redraw). Otherwise the second scroll overwrites the other live
    # row's font and both visible rows show the newest names.
    hx('A5 16 4A 85 18 AD 6E 03 29 01');a.rel(0xF0,'slotzero')
    hx('A9 0D');a.rel(0x80,'slotadd');a.label('slotzero');hx('A9 00')
    a.label('slotadd');hx('18 65 18 AA')
    get_pair(0,0x1C);get_pair(slot_stride,0x1E)
    hx('E2 20 A5 17 C9 %02X' % item_prefix);far(0xF0,'item')
    hx('C9 C0');far(0x90,'kana')
    hx('C9 %02X' % (0xC0+pages));far(0xB0,'kana')
    hx('C2 20 AD DF 09 C9 A8 00 E2 20');far(0xB0,'wait')
    # X still holds the layout slot. Save the tile pairs before borrowing
    # $1A/$1B/$1C as a long glyph pointer ($1C becomes the source ROM bank).
    get_pair(0,0x28);get_pair(slot_stride,0x2A)
    hx('E2 20 A5 17 38 E9 C0 18 69 %02X 85 1C' % pool_bank)
    hx('A5 15 1A 18 65 14 AA BD 0A 04 C2 30 29 FF 00')
    for _ in range(6):hx('0A')
    hx('18 69 00 80 85 1A AE DF 09')
    glyph_queue(0x28,0,32);glyph_queue(0x2A,32,32)
    cell(0x28,0);cell(0x2A,1)
    hx('8E DF 09 E2 30 E6 15 E6 15 E6 16 E6 16')
    a.jmp_to('savewait')
    a.label('item')
    hx('C2 20 AD DF 09 C9 A8 00 E2 20');far(0xB0,'wait')
    # Same 16x16 layout ownership as techniques, separate $3F:A000 font table.
    get_pair(0,0x28);get_pair(slot_stride,0x2A)
    hx('E2 20 A9 3F 85 1C A5 15 1A 18 65 14 AA BD 0A 04 C2 30 29 FF 00')
    for _ in range(6):hx('0A')
    hx('18 69 00 A0 85 1A AE DF 09')
    glyph_queue(0x28,0,32);glyph_queue(0x2A,32,32)
    cell(0x28,0);cell(0x2A,1)
    hx('8E DF 09 E2 30 E6 15 E6 15 E6 16 E6 16')
    a.jmp_to('savewait')
    a.label('kana')
    hx('C2 20 AD DF 09 C9 F8 00 E2 20');far(0xB0,'wait')
    hx('A5 17 A8 B9 9E FB 85 28 B9 9E FA 85 29 C2 30 AE DF 09 A5 20 9D 00 0B E8 E8')
    hx('E2 20 A9 81 9D 00 0B E8 A9 04 9D 00 0B E8 A5 28 9D 00 0B E8 A9 24 9D 00 0B E8 A5 29 9D 00 0B E8 A9 24 9D 00 0B E8')
    hx('8E DF 09 E2 30 E6 15 E6 16')
    a.jmp_to('savewait')
    a.label('endfield')
    hx('A5 15 C9 0E');far(0xB0,'done')
    hx('A9 0E 85 15 85 16');a.jmp_to('next')
    a.label('savewait')
    hx('A6 14 A5 15 9D 0A 04 A5 16 9D 17 04')
    a.label('wait')
    finish='waitfinish';a.jmp_to(finish)
    a.label('done');hx('A6 14 A9 00 9D 0A 04 9D 17 04 EE 6E 03 AD 6E 03 29 0F 8D 6E 03')
    for dp in reversed(saved):hx('C2 20 68 85 %02X' % dp)
    hx('E2 20 AB 28 18');a.long_to(0x1F95C) # inherited bank-3 RTS
    a.label(finish)
    for dp in reversed(saved):hx('C2 20 68 85 %02X' % dp)
    hx('E2 20 AB 28 38');a.long_to(0x1F95C)
    code=a.done()
    assert MENU_LIST_ROM+len(code)<=0x1F7000, 'menu-list code exceeds reserved range'
    assert rom[MENU_LIST_ROM:MENU_LIST_ROM+len(code)] == bytes(len(code)), 'menu-list destination is occupied'
    rom[MENU_LIST_ROM:MENU_LIST_ROM+len(code)]=code
    rom[hook:hook+6]=bytes((0x5C,0,0xE0,0x3E,0xEA,0xEA))
    return {'rom':MENU_LIST_ROM,'bytes':len(code),'hook':hook,'progress':'040A/0417,0424/0431 blank separators','slot_owner':'13 slots per live list row'}
