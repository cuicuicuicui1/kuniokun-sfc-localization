"""Two scoped UI repairs, independent of message text and external edits.

The choice box re-stages its protected glyphs through the native NMI queue.
The separate STATUS module uniformly draws 12px Chinese using paused slots.
"""
CHOICE_CODE=0x186100
STATUS_CODE=0x186800

def install(rom,cb,params,layout,font_path):
    A=cb.Asm
    def put(off,data,old=None):
        if old is not None:assert bytes(rom[off:off+len(old)])==old,(hex(off),'unexpected consumer')
        else:assert not any(rom[off:off+len(data)]),(hex(off),'new code space occupied')
        rom[off:off+len(data)]=data

    # The original choice caller retries the same row when the allocator fails.
    # First row: 3 glyph writes = 140 bytes, then the original 68-byte map row.
    # Reserve the full transaction before touching the queue; no private WRAM.
    a=A(CHOICE_CODE)
    a.hexs('08 C2 30 48 DA 5A E2 30 AD 95 03')
    a.far_rel(0xD0,'native','row')
    a.hexs('AD 63 03');a.far_rel(0xD0,'native','set')
    a.hexs('A9 D0 22 B6 9A 00');a.far_rel(0xB0,'busy','queue')
    a.queue_load_x()
    for first,count in [(0x44,3),(0x4A,2),(0x4D,3)]:
        addr=0x6000+first*8;source=0x8000+first*16
        a.hexs('C2 20 A9 %02X %02X 9F 00 0B 7E E8 E8 E2 20'%(addr&255,addr>>8))
        a.hexs('A9 80 9F 00 0B 7E E8 A9 %02X 9F 00 0B 7E E8'%(count*16))
        a.hexs('C2 20')
        data=rom[cb.FONT_ROM+first*16:cb.FONT_ROM+(first+count)*16]
        for i in range(0,len(data),2):
            a.hexs('A9 %02X %02X 9F 00 0B 7E E8 E8'%(data[i],data[i+1]))
    a.queue_store_x()
    a.hexs('C2 30 7A FA 68 28')
    a.long_to(0x1F3D2)  # Native map-row writer, after successful allocation.
    a.label('busy');a.hexs('C2 30 7A FA 68 28 38')
    a.long_to(0x1F3CF)  # Original busy return; do not advance row or scroll.
    a.label('native');a.hexs('C2 30 7A FA 68 28 A9 44 22 B6 9A 00')
    a.long_to(0x1F3CF)
    code=a.done();assert CHOICE_CODE+len(code)<STATUS_CODE
    put(CHOICE_CODE,code)
    bank,addr=cb.snes_of_rom(CHOICE_CODE)
    put(0x1F3C9,bytes([0x5C,addr&255,addr>>8,bank,0xEA,0xEA]),bytes.fromhex('A9 44 22 B6 9A 00'))
    assert rom[0x1F169] in (0x4A,0x50)
    rom[0x1F169]=0x50  # Show the complete 16px choices and original borders.

    from status12_patch import install as install_status12
    result=install_status12(rom,cb,params,layout,font_path)
    result.update(choice_hook=0x1F3C9,choice_code=CHOICE_CODE,choice_queue_glyph_bytes=140,
                  choice_total_reservation=208,choice_scroll_limit=0x50)
    return result
