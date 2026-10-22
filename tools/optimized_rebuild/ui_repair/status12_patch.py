"""STATUS-only Ark Pixel 12px renderer, using the existing paused font pool.

No WRAM allocation and no change to dialogue/HUD/menu fonts. The native STATUS
handler owns forced blank, stats, portrait, input, and screen restoration.
"""
from pathlib import Path
import hashlib

CODE=0x186800
DATA=0x1A0000
LIMIT=0x1E0000
LABELS=[
    (0x78C9,'等级',0x78CC),(0x7902,'最大体力',0x790A),
    (0x7942,'最大气力',0x794A),(0x7982,'经验',0x7985),
    (0x79C2,'武器',0x79C5),(0x7A02,'衬里',0x7A05),
    (0x7A42,'鞋',0x7A45),(0x7892,'状态',0x7899),
    (0x78D2,'体力',0x78D9),(0x7912,'气力',0x7919),
    (0x7952,'力',0x7959),(0x7992,'敏捷',0x7999),
    (0x79D2,'攻击力',0x79D9),(0x7A12,'防御力',0x7A19),
    (0x7A52,'运气',0x7A59)]

def install(rom,cb,params,layout,font_path):
    import pixelfonts as pf
    from sfc_tools import pack_8x8
    font_path=Path(font_path)
    font=dict(pf.load_bdf(str(font_path)))
    # Five missing characters are explicit 11x11 pixel designs. They never
    # fall back to a different size or silently lose strokes.
    custom={
        '券':['..#..#..#..','...#.#.#...','.#########.','....#......','###########','...#...#...','###.....###','..#######..','.....#..#..','....#...#..','..##..###..'],
        '拳':['..#..#..#..','...#.#.#...','.#########.','....#......','###########','..#.....#..','#######..##','.....#.....','.#########.','.....#.....','...###.....'],
        '拖':['.#...#.....','.#...#.....','####.######','.#..#......','.#.....#...','.#..#.###..','###.##.#.#.','.#..#..#.#.','.#..#..###.','.#..#.....#','##...######'],
        '然':['.#.....#.#.','.#####.#.#.','.#...######','#.#.#..#...','.#.#...#...','..#...#.#..','.#...#...#.','#...#.....#','...........','#..#..#..#.','#..#..#..#.'],
        '药':['...#...#...','###########','...#...#...','.#...#.....','.#...######','#.#.#.....#','##.#..#...#','.#.....#..#','###....#..#','..........#','###.....##.'],
    }
    for ch,rows in custom.items():
        assert len(rows)==11 and all(len(r)==11 for r in rows)
        font[ord(ch)]=((11,11,0,-2),[f'{int(r.replace(chr(35),chr(49)).replace(chr(46),chr(48)),2)<<5:04X}' for r in rows])
    def strips(text,width=None):
        width=width or ((len(text)*12+7)//8*8)
        assert len(text)*12<=width,(text,width)
        grid=[[0]*width for _ in range(16)]
        for i,ch in enumerate(text):
            assert ord(ch) in font,('missing 12px glyph',ch)
            bb,rows=font[ord(ch)];g=pf.bits_of_bdf(bb,rows)
            assert 0<len(g)<=12 and 0<len(g[0])<=12,(ch,bb)
            for y,row in enumerate(g):
                for x,b in enumerate(row):grid[y+2][i*12+x]=b
        return [pack_8x8([r[x:x+8] for r in grid[:8]])+
                pack_8x8([r[x:x+8] for r in grid[8:]]) for x in range(0,width,8)]

    # Decode the real native item table, rather than assume translation JSON
    # indices or borrow another build's dictionary. A changed encoding fails.
    rev={v:k for k,v in params['item_chars'].items()}
    keep={v:k for k,v in params['keep1'].items()}
    items=['']
    for i in range(1,111):
        ptr=int.from_bytes(rom[0x1DBC3+i*2:0x1DBC5+i*2],'little')
        assert 0x8000<=ptr<=0xFFFF
        off=0x10000+ptr;text=''
        for _ in range(24):
            c=rom[off];off+=1
            if c==0xF2:break
            if c==cb.ITEM_PREFIX:
                text+=rev[rom[off]];off+=1
            elif c==0:text+=' '
            else:
                assert c in keep,('unknown native item token',i,hex(c))
                text+=keep[c]
        else:raise AssertionError(('unterminated item',i))
        assert 0<len(text)<=6,(i,text)
        items.append(text)

    stride=layout['stride']
    lo=rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR+stride*2]
    hi=rom[cb.E3_SLOTHI:cb.E3_SLOTHI+stride*2]
    excluded=set(cb.hud_pairs())|{t+k for t in layout['static_hud_tiles'] for k in (0,1)}
    pairs=[];used=set()
    for i in range(stride*2):
        t=lo[i]+256*hi[i]
        if t>=255 or {t,t+1}&(excluded|used):continue
        pairs.append(t);used.update((t,t+1))
    # Dense 12px strips share identical eight-pixel slices. Thirty-three
    # additional pairs hold three complete six-character values + two fields.
    unique={}
    for _,text,_ in LABELS:
        for bitmap in strips(text):
            if bitmap not in unique:unique[bitmap]=pairs[len(unique)]
    static_count=len(unique)
    assert static_count+33<=len(pairs),(static_count,len(pairs))
    name_tiles=pairs[static_count:static_count+3]
    condition_tiles=pairs[static_count+3:static_count+6]
    item_tiles=[pairs[static_count+6+r*9:static_count+15+r*9] for r in range(3)]

    blob=bytearray();font_offsets={};commands=bytearray();runs=[]
    def store_bitmap(bitmap):
        if bitmap not in font_offsets:
            off=DATA+len(blob)
            # Each 32-byte vertical pair must fit in one LoROM bank.
            assert (off&0x7FFF)+32<=0x8000
            font_offsets[bitmap]=off;blob.extend(bitmap)
        return font_offsets[bitmap]
    def run(text,cell,tiles,width=None):
        index=len(commands);bitmaps=strips(text,width)
        assert len(bitmaps)<=len(tiles)
        rows=[]
        for k,(bitmap,tile) in enumerate(zip(bitmaps,tiles)):
            off=store_bitmap(bitmap);bank,addr=cb.snes_of_rom(off)
            commands.extend(addr.to_bytes(2,'little')+bytes([bank,tile])+(cell+k).to_bytes(2,'little'))
            rows.append(dict(cell=cell+k,tile=tile,font_offset=off))
        commands.extend(bytes(6))
        runs.append(dict(text=text,cell=cell,command=index,columns=rows))
        return index
    # One sentinel-terminated command stream for all constant labels.
    static_cmd=len(commands)
    for cell,text,_ in LABELS:
        bitmaps=strips(text)
        run(text,cell,[unique[b] for b in bitmaps])
        del commands[-6:]
    commands.extend(bytes(6))
    name_cmd=[run(t,0x788A,name_tiles,24) for t in ['国夫','力']]
    condition_cmd=[run(t,0x789B,condition_tiles,24) for t in ['普通','醉酒','麻痹']]
    item_cmd=[]
    for row in range(3):
        table=[run('空手' if row==0 else '无',[0x79C6,0x7A06,0x7A46][row],item_tiles[row],72)]
        for text in items[1:]:
            table.append(run(text,[0x79C6,0x7A06,0x7A46][row],item_tiles[row],72))
        item_cmd.append(table)
    if ((DATA+len(blob))&0x7FFF)+len(commands)+666>0x8000:
        blob.extend(bytes(0x8000-((DATA+len(blob))&0x7FFF)))
    cmd_base=DATA+len(blob);blob.extend(commands)
    ptr_base=DATA+len(blob)
    for table in item_cmd:
        for index in table:blob.extend(index.to_bytes(2,'little'))
    assert (cmd_base&0x7FFF)+len(commands)+666<=0x8000
    assert len(commands)<0x10000 and DATA+len(blob)<LIMIT
    assert not any(rom[DATA:DATA+len(blob)]),'STATUS data overlaps an existing extension'
    rom[DATA:DATA+len(blob)]=blob

    a=cb.Asm(CODE)
    def word(value):return '%02X %02X'%(value&255,value>>8)
    def lng(off):
        bank,addr=cb.snes_of_rom(off)
        return word(addr)+' %02X'%bank
    def invoke(index):
        a.hexs('E2 20 C2 10 A2 '+word(index));jsr('draw')
    def jsr(label):
        a.fix.append(('abs',len(a.b)+1,label));a.hexs('20 00 00')
    def map_pair(cell,tile,bottom=None):
        bottom=tile+1 if bottom is None else bottom
        a.hexs('A9 81 8D 15 21 C2 20 A9 '+word(cell)+' 8D 16 21 E2 20')
        a.hexs('A9 %02X 8D 18 21 A9 24 8D 19 21 A9 %02X 8D 18 21 A9 24 8D 19 21'%(tile,bottom))
    # Replacement for the native label interpreter. The native screen clear
    # and number renderer retain their original call sites and state.
    a.hexs('E2 30')
    # Literal title and punctuation still use the protected native bitmaps.
    at=cb.STATUS_SCRIPT
    while rom[at+1]!=255:
        cell=int.from_bytes(rom[at:at+2],'little');count=rom[at+2]
        if not count&128:
            for k,tile in enumerate(rom[at+3:at+3+count]):map_pair(cell+k,0,tile)
        at+=3+(count&127)
    colon=rom[0x1FB9E+9];bottom=rom[0x1FA9E+9]
    for _,_,cell in LABELS:
        a.hexs('A9 81 8D 15 21 C2 20 A9 '+word(cell)+' 8D 16 21 E2 20')
        a.hexs('A9 %02X 8D 18 21 A9 24 8D 19 21 A9 %02X 8D 18 21 A9 24 8D 19 21'%(colon,bottom))
    invoke(static_cmd);a.hexs('E2 30');a.long_to(0xF9DA)
    fixed_entry=a.base+len(a.b)
    # FBBB: native caller has selected a player. Only visual fields change.
    a.hexs('E2 30 AD A6 1B');a.rel(0xD0,'riki')
    invoke(name_cmd[0]);a.jmp_to('condition')
    a.label('riki');invoke(name_cmd[1])
    a.label('condition');a.hexs('E2 30 AE A6 1B BD EB 01 C9 01');a.rel(0xF0,'drunk')
    a.hexs('C9 02');a.rel(0xF0,'paralysis')
    invoke(condition_cmd[0]);a.jmp_to('fixed_finish')
    a.label('drunk');invoke(condition_cmd[1]);a.jmp_to('fixed_finish')
    a.label('paralysis');invoke(condition_cmd[2])
    a.label('fixed_finish');a.hexs('E2 30 A9 80 8D 15 21');a.long_to(0xFC21)
    item_entry=a.base+len(a.b)
    # FC75 is a status-only consumer. Render empty values in the same font;
    # unknown IDs retain the original decoder's behavior.
    a.hexs('E2 30')
    a.hexs('C9 6F');a.far_rel(0xB0,'unknown','known')
    a.hexs('C2 30 29 FF 00 0A AA E2 20 A5 20 C9 C6');a.rel(0xF0,'item0')
    a.hexs('C9 06');a.rel(0xF0,'item1')
    a.hexs('C2 20 BF '+lng(ptr_base+444));a.rel(0x80,'item_draw')
    a.label('item1');a.hexs('C2 20 BF '+lng(ptr_base+222));a.rel(0x80,'item_draw')
    a.label('item0');a.hexs('C2 20 BF '+lng(ptr_base))
    a.label('item_draw');a.hexs('AA E2 20');jsr('draw')
    a.hexs('E2 30 A9 81 8D 15 21');a.long_to(0xFCC6)
    a.label('unknown');a.hexs('0A AA BF C3 DB 03');a.long_to(0xFC7D)
    a.label('draw')
    # Six-byte ROM commands: source address/bank, tile pair, tile-map cell.
    # No direct-page scratch; caller X is an unsigned 16-bit command offset.
    a.hexs('E2 20 C2 10 A9 01 8D 20 43 A9 18 8D 21 43')
    a.label('next');a.hexs('BF '+lng(cmd_base+2));a.far_rel(0xF0,'done','have')
    a.hexs('8D 24 43 A9 80 8D 15 21 C2 20 BF '+lng(cmd_base+3)+' 29 FF 00 0A 0A 0A 09 00 60 8D 16 21')
    a.hexs('BF '+lng(cmd_base)+' 8D 22 43 A9 20 00 8D 25 43 E2 20 A9 04 8D 0B 42')
    a.hexs('A9 81 8D 15 21 C2 20 BF '+lng(cmd_base+4)+' 8D 16 21 E2 20')
    a.hexs('BF '+lng(cmd_base+3)+' 8D 18 21 A9 24 8D 19 21 BF '+lng(cmd_base+3)+' 1A 8D 18 21 A9 24 8D 19 21')
    a.hexs('E8 E8 E8 E8 E8 E8');a.jmp_to('next')
    a.label('done');a.hexs('60')
    code=a.done();assert CODE+len(code)<0x188000
    assert not any(rom[CODE:CODE+len(code)]),'STATUS code overlaps existing code'
    rom[CODE:CODE+len(code)]=code
    def hook(off,target,old):
        assert bytes(rom[off:off+len(old)])==old,(hex(off),rom[off:off+len(old)].hex())
        bank,addr=cb.snes_of_rom(target)
        rom[off:off+len(old)]=bytes([0x5C,addr&255,addr>>8,bank])+bytes([0xEA])*(len(old)-4)
    hook(0xF971,CODE,bytes.fromhex('A9 81 20 69 F9'))
    hook(0xFBBB,fixed_entry,bytes.fromhex('5C 00 D0 30 EA EA EA'))
    hook(0xFC75,item_entry,bytes.fromhex('F0 50 0A AA BF C3 DB 03'))
    return dict(status_font='Ark Pixel 12px original pixels, 12px advance',
                font_sha256=hashlib.sha256(font_path.read_bytes()).hexdigest(),
                status_code=CODE,status_code_bytes=len(code),status_data=DATA,status_data_bytes=len(blob),
                static_pairs=static_count,dynamic_pairs=33,available_pairs=len(pairs),
                item_count=110,names=['国夫','力'],conditions=['普通','醉酒','麻痹'],
                status_runs=runs,colon_cells=[c for _,_,c in LABELS],
                scope='All STATUS Chinese, native stats/portrait/input retained; no text/HUD font changes')
