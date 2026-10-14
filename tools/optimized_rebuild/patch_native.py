"""Independent localization post-writer. Input is freshly built native components.
No Chinese donor ROM participates. All relocations/bytes are checked.
"""
from pathlib import Path
import json,os,sys,hashlib,zlib
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'source';os.chdir(SRC);sys.path.insert(0,str(SRC))
import cnbuild5 as cb
cb.load_build_params();A=cb.Asm
base=Path(json.loads((ROOT/'inputs.json').read_text(encoding='utf8'))['opt']['path']).read_bytes();assert hashlib.sha256(base).hexdigest()=='2008f9b34d2b48a168824c8c7d1e3c8924dbb0fa81de9a4eeff2823a635ffe08'
rom=bytearray((SRC/'kuniokun_cn.smc').read_bytes());writes=[]
def put(off,data,label,old=None):
 if old is not None:assert bytes(rom[off:off+len(old)])==old,(label,hex(off),rom[off:off+len(old)].hex())
 rom[off:off+len(data)]=data;writes.append({'offset':off,'length':len(data),'label':label})
def install(a,label,limit):
 data=a.done();assert a.base+len(data)<=limit,(label,len(data),hex(a.base));put(a.base,data,label)
# Positional tile slots: three rolling rows, thirteen 16x16 glyph positions.
# 03E5/03E6 are text-context lane and last ring-row. Native context reset clears them.
a=A(0x184000);a.hexs('08 C2 30 48 5A E2 20') # save complete A/Y and widths
# Compute row/column after a possible automatic wrap; actual wrap remains native drawer.
a.hexs('AD 6F 03 C9 %02X'%cb.WRAP_COL);a.rel(0x90,'current')
a.hexs('AD 6E 03 1A 29 0F');a.rel(0x80,'row')
a.label('current');a.hexs('AD 6E 03 29 0F')
a.label('row');a.hexs('CD E6 03');a.rel(0xf0,'same')
a.hexs('8D E6 03 EE E5 03')
a.label('same');a.hexs('AD E5 03 C9 03');a.rel(0x90,'lane')
a.hexs('A9 00 8D E5 03')
a.label('lane');a.hexs('C2 20 29 FF 00 48')
# lane*13 = lane*8 + lane*4 + lane; stack source is a word.
a.hexs('0A 0A 18 63 01 0A 18 63 01 18 63 01 18 63 01 48') # lane*13
# select column after wrap; 16-bit loads explicitly mask neighboring bytes.
a.hexs('AD 6F 03 29 FF 00 C9 %02X 00'%cb.WRAP_COL);a.rel(0x90,'col')
a.hexs('A9 00 00')
a.label('col');a.hexs('4A 18 63 01 AA 68 68 7A 68 28 6B')
install(a,'positional glyph destination',0x184100)
# Generic main-message table. Bank03 remains the macro/native-table bank.
cells=json.loads((SRC/'cn_glyph_cell.json').read_text(encoding='utf8'));enc=cb.Encoder();enc.cell={k:tuple(v) for k,v in cells.items()}
messages=json.loads((ROOT/'native-dialogues.json').read_text(encoding='utf8'))
ptrs=bytearray();cursor=0x188001;rom[0x188000]=0xF3
readback=[]
for mid in range(0x34c):
 if str(mid) in messages:
  row=messages[str(mid)];data=enc.encode(row['text'])
  assert data and (0xf3 in data or mid in (0x186,0x187,0x189,0x18a,0x274)),(hex(mid),row)
  if 0xf3 in data:data=data[:data.index(0xf3)+1]
  if (cursor&0x7fff)+len(data)>0x8000:cursor=(cursor+0x7fff)&~0x7fff
  off=cursor;put(off,data,'main text %03X'%mid);cursor+=len(data)
  readback.append({'id':mid,'offset':off,'bytes':data.hex(),'cn':row['text'],'source':row['source']})
 else:off=0x188000
 bank,addr=cb.snes_of_rom(off);ptrs+=addr.to_bytes(2,'little')+bytes([bank])
assert cursor<0x1e0000,hex(cursor)
put(0x184100,ptrs,'main 3-byte pointer table')
a=A(0x184d00);a.hexs('08 C2 30 48 DA 5A AD 4A 03 29 FF 03 48 0A 18 63 01 AA 68')
a.hexs('BF 00 C1 30 8D 6A 03 7A FA 68 28')
a.long_to(0x1eb9a)
install(a,'main pointer loader',0x184e00)
put(0x1eb70,bytes.fromhex('5C 00 CD 30'),'native loader redirect',bytes.fromhex('5C 00 80 22'))
a=A(0x184e00);a.hexs('08 C2 30 48 DA AD 4A 03 29 FF 03 48 0A 18 63 01 AA 68 E2 20')
a.hexs('BF 02 C1 30 8B 48 AB B1 20 85 12 AB C2 30 FA 68 28 A5 12')
a.long_to(0x1ebbf)
install(a,'main streaming bank select',0x184f00)
put(0x1ebbb,bytes.fromhex('5C 00 CE 30'),'native stream redirect',bytes.fromhex('5C 50 80 22'))
# Preserve optimization's menu coordinates and replace its Japanese toggle redraw.
put(0x1f845,base[0x1f845:0x1f851],'native six-entry coordinates')
# extra state glyph uses a 13th resident command destination.
stride=cb.SLOTS+cb.LABEL_GLYPHS*cb.LABEL_SETS+cb.LABEL_NAME_GLYPHS*cb.LABEL_NAME_SETS
lo=rom[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR+stride*2];hi=rom[cb.E3_SLOTHI:cb.E3_SLOTHI+stride*2]
s=12;t=lo[s]+256*hi[s];u=lo[stride+s]+256*hi[stride+s];assert t<255 and u<255
codes=cb.CMDWIN_CODES[24:26]
for code,tile in zip(codes,(t,u)):
 rom[0x1fb9e+code]=tile;rom[0x1fa9e+code]=tile+1
page,gid=cells['开'];addr=0x8000+gid*64
record=(0x6000+t*8).to_bytes(2,'little')+(0x6000+u*8).to_bytes(2,'little')+addr.to_bytes(2,'little')+bytes([cb.POOL_BANK0+page])
put(cb.MENU_TAB+84,record,'mutual damage state glyph record')
put(0x1f743+26+17,bytes(codes),'mutual damage state display')
site=rom.find(bytes.fromhex('C9 0C'),cb.MENU_STUB,cb.MENU_TAB);assert site>=0
put(site+1,b'\x0d','13 menu glyphs',b'\x0c')
a=A(0x184f00);a.hexs('08 C2 20 48 E2 20 A5 15 C9 0C');a.rel(0xd0,'out')
a.hexs('A5 70');a.rel(0x10,'out')
page,gid=cells['关'];addr=0x8000+gid*64
a.hexs('A9 %02X 85 16 A9 %02X 85 17 A9 %02X 85 18'%(addr&255,addr>>8,cb.POOL_BANK0+page))
a.label('out');a.hexs('C2 20 68 28 A5 1A 85 1E 6B')
install(a,'mutual damage state font',0x185000)
site=rom.find(bytes.fromhex('A5 1A 85 1E'),cb.MENU_STUB,cb.MENU_TAB);assert site>=0
put(site,bytes.fromhex('22 00 CF 30'),'mutual damage font selector')
put(0x10109b,bytes.fromhex('5C 41 F7 03'),'native menu redraw keeps translated text',base[0x10109b:0x10109f])
# Native fixed player HUD names use the fresh speaker records.
for player in range(2):
 source=cb.NAME_RECORD_BASE+(512+player)*16
 put(0x73c7+player*4,rom[source:source+4],'fixed player HUD Hanzi records',base[0x73c7+player*4:0x73cb+player*4])
# Separate native STATUS consumer. Reuse its known drawing contract, with fresh tiles.
from cnfont8 import render8x16
from sfc_tools import pack_8x8
reserved=set(cb.status_label_slot_list(len(cb.status_label_hanzi())))|set(range(24,42))
chosen=[];used=set()
for i in range(stride*2):
 tile=lo[i]+256*hi[i]
 if i in reserved or tile>=255 or {tile,tile+1}&used:continue
 chosen.append(i);used.update((tile,tile+1))
 if len(chosen)==4:break
assert len(chosen)==4
assert not used&set(cb.hud_pairs())
tiles=[lo[i]+256*hi[i] for i in chosen]
fontoff=0x190000;glyph_addresses={' ':fontoff};font=bytearray(32)
for ch in '国夫力普通醉酒麻痹':
 glyph_addresses[ch]=fontoff+len(font);g=render8x16(ch,cb.FONT_PATH,thresh=cb.GLYPH8_THRESH,widen=cb.GLYPH_WIDEN);font+=pack_8x8(g[:8])+pack_8x8(g[8:])
assert rom[fontoff:fontoff+len(font)]==bytes(len(font));put(fontoff,font,'native STATUS 8x16 font')
# Player0 retains the native Japanese HUD glyphs. These kana tiles are
# already protected by KEEP1 and must match the optimized original bitmap.
import kuniokun_map as km
kunio_codes=base[0x73c7:0x73cb]
assert kunio_codes==bytes.fromhex('27 35 24 00')
kunio_pairs=[]
active_body_tiles={lo[i]+256*hi[i]+k for i in list(range(39))+list(range(stride,stride+39)) for k in (0,1)}
for code in kunio_codes:
 lower,upper=base[0x1fa9e+code],base[0x1fb9e+code]
 for tile in (lower,upper):
  assert tile not in active_body_tiles and tile not in cb.hud_pairs()
  assert rom[cb.FONT_ROM+tile*16:cb.FONT_ROM+(tile+1)*16]==base[cb.FONT_ROM+tile*16:cb.FONT_ROM+(tile+1)*16]
 kunio_pairs.extend((lower,upper))
# Riki is also 16x16: two resident halves in the two unused right-hand pairs.
# Neither body rows nor STATUS/name/command consumers own these pair entries.
static_hud_tiles=[lo[i]+256*hi[i] for i in (stride+39,stride+40)]
assert not {t+k for t in static_hud_tiles for k in (0,1)}&active_body_tiles
assert not set(static_hud_tiles)&set(tiles)
glyph=cb.glyph64('力')
for half,tile in enumerate(static_hud_tiles):
 put(cb.FONT_ROM+tile*16,glyph[half*32:half*32+32],'resident 16x16 Riki HUD half')
riki_pairs=[static_hud_tiles[0]+1,static_hud_tiles[0],static_hud_tiles[1]+1,static_hud_tiles[1],0,0,0,0]
put(0x185800,bytes(kunio_pairs+riki_pairs),'native Japanese Kunio and 16x16 Riki HUD pairs')
a=A(0x185700);a.hexs('08 A5 10 C9 02');a.rel(0xb0,'enemy')
a.hexs('A5 18 0A AA BF 00 D8 30 85 22 BF 01 D8 30 85 23 28 6B')
a.label('enemy');a.hexs('28 5C 00 D0 3E')
install(a,'player HUD native kana / full-width static gateway',0x185800)
put(0xc91,bytes.fromhex('22 00 D7 30'),'player/enemy separate HUD gateway',bytes.fromhex('22 00 D0 3E'))
# Enemy plates reuse the existing 16x16 uploader and its private 8 tile-pairs.
# Reserve the COMPLETE name + bar transaction before entering the drawer.
# Native allocation 0x52 + two 72-byte glyph uploads = 0xE2. Failing the
# allocator retains native dirty bits, so retry occurs on the next frame.
a=A(0x186000);a.hexs('A5 10 C9 02');a.rel(0x90,'native')
a.hexs('A9 E2');a.rel(0x80,'reserve')
a.label('native');a.hexs('A9 52')
a.label('reserve');a.hexs('22 B6 9A 00 6B')
install(a,'complete HUD queue reservation and original retry',0x186100)
put(0xae5,bytes.fromhex('22 00 E0 30 EA EA'),'HUD transaction allocation',bytes.fromhex('A9 E2 22 B6 9A 00'))
put(0xf9ed,bytes(5),'clear complete native STATUS name field',bytes.fromhex('1D 00 00 00 1D'))
statusoff=0x185000
a=cb.Asm(statusoff);a.hexs('E2 30 A9 01 8D 20 43 A9 18 8D 21 43')
def draw(ch,t,cell):
 source=glyph_addresses[ch];bank,addr=cb.snes_of_rom(source)
 a.hexs('A9 80 8D 15 21 C2 20 A9 %02X %02X 8D 16 21'%((0x6000+t*8)&255,(0x6000+t*8)>>8))
 a.hexs('A9 %02X %02X 8D 22 43 A9 20 00 8D 25 43 E2 20'%(addr&255,addr>>8))
 a.hexs('A9 %02X 8D 24 43 A9 04 8D 0B 42'%bank)
 a.hexs('A9 81 8D 15 21 C2 20 A9 %02X %02X 8D 16 21 E2 20'%(cell&255,cell>>8))
 a.hexs('A9 %02X 8D 18 21 A9 24 8D 19 21 A9 %02X 8D 18 21 A9 24 8D 19 21'%(t,t+1))
a.hexs('AD A6 1B');a.far_rel(0xd0,'riki','far_riki')
draw('国',tiles[0],0x788a);draw('夫',tiles[1],0x788b);a.jmp_to('condition')
a.label('riki');draw('力',tiles[0],0x788a);draw(' ',tiles[1],0x788b)
a.label('condition');a.hexs('AE A6 1B BD EB 01 C9 00');a.far_rel(0xd0,'check1','far_check1')
draw('普',tiles[2],0x789b);draw('通',tiles[3],0x789c);a.jmp_to('finish')
a.label('check1');a.hexs('C9 01');a.far_rel(0xd0,'check2','far_check2')
draw('醉',tiles[2],0x789b);draw('酒',tiles[3],0x789c);a.jmp_to('finish')
a.label('check2');a.hexs('C9 02');a.far_rel(0xd0,'native_unknown','far_native_unknown')
draw('麻',tiles[2],0x789b);draw('痹',tiles[3],0x789c);a.jmp_to('finish')
a.label('native_unknown');a.hexs('A9 80 8D 15 21 5C E3 FB 01')
a.label('finish');a.hexs('A9 80 8D 15 21 5C 21 FC 01');code=a.done();assert len(code)<0x700
put(statusoff,code,'native STATUS names and conditions')
put(0xfbbb,bytes.fromhex('5C 00 D0 30 EA EA EA'),'native STATUS fixed-field Hook',bytes.fromhex('A9 80 20 69 F9 E2 30'))
(ROOT/'new-build/ui-layout.json').write_text(json.dumps({'stride':stride,'reserved_pair_indices':sorted(reserved),'chosen_pair_indices':chosen,'tiles':tiles,'glyph_addresses':glyph_addresses,'static_hud_tiles':static_hud_tiles},ensure_ascii=False,indent=2),encoding='utf8')

rom[0x7fd7]=0x0c;rom[0x7fdc:0x7fe0]=bytes(4);checksum=(sum(rom)+0x1fe)&0xffff;rom[0x7fdc:0x7fe0]=(checksum^0xffff).to_bytes(2,'little')+checksum.to_bytes(2,'little');assert sum(rom)&0xffff==checksum
out=ROOT/'new-build/native-rebuild-candidate.sfc';out.write_bytes(rom)
manifest={'status':'candidate_not_yet_runtime_accepted','input_sha256':hashlib.sha256(base).hexdigest(),'output':str(out),'size':len(rom),'sha256':hashlib.sha256(rom).hexdigest(),'crc32':f'{zlib.crc32(rom):08X}','text_count':len(readback),'text_end':hex(cursor),'writes':writes}
(ROOT/'new-build/manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8');(ROOT/'new-build/main-readback.json').write_text(json.dumps(readback,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in manifest.items() if k!='writes'},indent=2))
