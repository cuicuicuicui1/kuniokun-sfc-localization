"""Keep the slot reels and Chinese yes/no prompt as separate VRAM owners.

Both native consumers reuse tiles $4A..$4F. The Chinese initial font and
yes/no refresh replace those pixels, while the native reel table still uses
them with four original palettes. Restore original reel icons on set 1.
"""
from ui_asm import Asm,snes_of_rom
CODE=0x187000
ORIGINAL_OPT_SHA='2008f9b34d2b48a168824c8c7d1e3c8924dbb0fa81de9a4eeff2823a635ffe08'
BASE_SHA='47685520673b973b8337e3235f299fdeda5805054b4031b2a0f154b4d2da5936'

def install(rom,original):
    import hashlib
    if len(original)!=0x180000 or hashlib.sha256(original).hexdigest()!=ORIGINAL_OPT_SHA:
        raise ValueError('Wrong original optimization ROM; requires CRC32 65D66D5D')
    if len(rom)!=0x400000 or hashlib.sha256(rom).hexdigest()!=BASE_SHA:
        raise ValueError('Wrong Chinese UI base; requires CRC32 8890880C')
    assert rom[0x1F3C9:0x1F3CF]==bytes.fromhex('5C 00 E1 30 EA EA')
    # Guard the real graphics consumers, not an assumed text-string table.
    for lo,hi in [(0x1F2D0,0x1F356),(0x1F4A7,0x1F4EB)]:
        assert rom[lo:hi]==original[lo:hi],('native slot consumer changed',hex(lo))
    a=Asm(CODE)
    a.hexs('08 C2 30 48 DA 5A E2 30 AD 95 03')
    a.far_rel(0xD0,'previous','row')
    a.hexs('AD 63 03 C9 01');a.far_rel(0xD0,'previous','set')
    # 128+16 glyph bytes + two 4-byte headers + original 68-byte map row.
    a.hexs('A9 DC 22 B6 9A 00');a.far_rel(0xB0,'busy','reserve')
    a.queue_load_x()
    blocks=[]
    for first,count in [(0x4A,8),(0x53,1)]:
        addr=0x6000+first*8
        a.hexs('C2 20 A9 %02X %02X 9F 00 0B 7E E8 E8 E2 20'%(addr&255,addr>>8))
        a.hexs('A9 80 9F 00 0B 7E E8 A9 %02X 9F 00 0B 7E E8'%(count*16))
        a.hexs('C2 20')
        off=0xF8000+first*16;data=original[off:off+count*16]
        assert len(data)==count*16
        for i in range(0,len(data),2):a.hexs('A9 %02X %02X 9F 00 0B 7E E8 E8'%(data[i],data[i+1]))
        blocks.append(dict(first_tile=first,tiles=count,original_rom_offset=off,sha256=hashlib.sha256(data).hexdigest()))
    a.queue_store_x();a.hexs('C2 30 7A FA 68 28');a.long_to(0x1F3D2)
    a.label('busy');a.hexs('C2 30 7A FA 68 28 38');a.long_to(0x1F3CF)
    a.label('previous');a.hexs('C2 30 7A FA 68 28');a.long_to(0x186100)
    code=a.done();assert CODE+len(code)<0x188000
    assert not any(rom[CODE:CODE+len(code)]),'slot gateway overlaps existing extension'
    rom[CODE:CODE+len(code)]=code
    bank,addr=snes_of_rom(CODE)
    rom[0x1F3C9:0x1F3CF]=bytes([0x5C,addr&255,addr>>8,bank,0xEA,0xEA])
    return dict(slot_code=CODE,slot_code_bytes=len(code),slot_first_row_reservation=220,
        slot_glyph_queue_bytes=152,blocks=blocks,excluded_tile=0x52,
        retained='Previous yes/no and complete STATUS12 code/data; all message and gameplay bytes',
        trigger='Original first map row with prompt-set 1; busy retries same row before any upload')
