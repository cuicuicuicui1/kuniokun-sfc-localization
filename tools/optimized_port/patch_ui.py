from runtime_paths import source_tree
"""Scoped UI patch on the fully audited optimization port base. Never changes the baseline ROM."""
from pathlib import Path
import os,sys,json,hashlib,zlib,argparse
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'candidate.sfc');parser.add_argument('--output',type=Path,default=ROOT/'candidate-ui.sfc');parser.add_argument('--source-tree',type=Path,default=source_tree());args=parser.parse_args()
SRC=args.source_tree.resolve();os.chdir(SRC);sys.path.insert(0,str(SRC))
import cnbuild5 as cb
from cnfont8 import render8x16
from sfc_tools import pack_8x8
cb.load_build_params()
base=args.input.read_bytes();assert len(base)==0x200000 and hashlib.sha256(base).hexdigest()==json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))['candidate']['sha256'],'wrong audited port baseline'
assert args.output.resolve()!=args.input.resolve(),'refuse to overwrite baseline'
r=bytearray(base);changes=[]
def patch(off,data,label,expected=None):
 if expected is not None:assert base[off:off+len(expected)]==expected,(label,hex(off),'source mismatch')
 changes.append({'offset':off,'length':len(data),'label':label,'before':base[off:off+len(data)].hex(),'after':bytes(data).hex()});r[off:off+len(data)]=data
# Clear the whole native five-cell name field through its existing two-row
# text interpreter. Its old end markers use font tiles now shared with Chinese
# labels, so their bottom halves appear as stray characters beside the name.
assert base[0x1fa9e] == base[0x1fb9e] == 0, 'native blank mapping changed'
patch(0xf9ed, bytes(5), 'clear native name placeholders in all five two-row cells',
      bytes.fromhex('0D 00 00 00 0E'))
layout=json.loads((ROOT/'ui-layout.json').read_text(encoding='utf-8'));tiles=layout['chosen_base_tiles'];assert len(tiles)==4
# Verify targets still use distinct existing 8x16 pool pairs and do not collide
# with status labels/items/native HUD. Numeric/source font mappings are untouched.
assert len({x for t in tiles for x in (t,t+1)})==8
stride=layout['pool_stride']
for i,t in zip(layout['chosen_pair_indices'],tiles):assert base[cb.E3_SLOTPAIR+i]+256*base[cb.E3_SLOTHI+i]==t
assert not set(layout['chosen_pair_indices'])&set(layout['status_reserved_pair_indices'])
fontoff=0x1c4800;glyphs='国夫力普通醉酒麻痹';font=bytearray(32)
glyph_addresses={' ':fontoff}
for ch in glyphs:
 g=render8x16(ch,cb.FONT_PATH,thresh=cb.GLYPH8_THRESH,widen=cb.GLYPH_WIDEN)
 glyph_addresses[ch]=fontoff+len(font);font+=pack_8x8(g[:8])+pack_8x8(g[8:])
assert base[fontoff:fontoff+len(font)]==bytes(len(font));patch(fontoff,font,'status names and native-condition 8x16 glyphs')
# Restore only player HUD output. Runtime actor names and story macro inputs stay
# Chinese. Enemy plates continue through the original tested 3E:D000 hook.
hudoff=0x1c3600;tableoff=hudoff+0x100
assert base[hudoff:hudoff+0x108]==bytes(0x108)
a=cb.Asm(hudoff)
a.hexs('08 A5 10 C9 02');a.rel(0xb0,'enemy')
a.hexs('A5 18 AA');bank,addr=cb.snes_of_rom(tableoff);a.hexs('BF %02X %02X %02X AA'%(addr&255,addr>>8,bank))
a.hexs('BF 9E FA 03 85 22 BF 9E FB 03 85 23 28 6B')
a.label('enemy');a.hexs('28 5C 00 D0 3E');assert len(a.done())<0x100
patch(hudoff,a.done(),'native kana output for the two player HUD plates')
patch(tableoff,bytes.fromhex('27 35 24 00 47 26 00 00'),'original optimization HUD names: kunio/riki')
patch(0xc91,bytes.fromhex('22 00 B6 38'),'player-only HUD output gateway',bytes.fromhex('22 00 D0 3E'))
# Native status setup runs during its original blanked drawing phase. Reuse
# four inactive existing font pairs; channel2 matches the current label drawer.
statusoff=0x1c3800;assert base[statusoff:statusoff+0x700]==bytes(0x700)
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
patch(statusoff,code,'Chinese status name and condition display, original item continuation')
patch(0xfbbb,bytes.fromhex('5C 00 B8 38 EA EA EA'),'status fixed-field gateway',bytes.fromhex('A9 80 20 69 F9 E2 30'))
r[0x7fdc:0x7fe0]=bytes(4);checksum=(sum(r)+0x1fe)&0xffff;r[0x7fdc:0x7fe0]=(checksum^0xffff).to_bytes(2,'little')+checksum.to_bytes(2,'little');assert sum(r)&0xffff==checksum
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(r);assert args.input.read_bytes()==base
manifest={'input':{'path':str(args.input.resolve()),'sha256':hashlib.sha256(base).hexdigest(),'crc32':f'{zlib.crc32(base):08X}'},'candidate':{'size':len(r),'sha256':hashlib.sha256(r).hexdigest(),'crc32':f'{zlib.crc32(r):08X}'},'changes':changes,'layout':layout,'glyph_sources':glyph_addresses,'status_names':{'0':'国夫','1':'力'},'native_conditions':{'0':{'jp':'ふつう','cn':'普通'},'1':{'jp':'でいすい','cn':'醉酒'},'2':{'jp':'まひ','cn':'麻痹'}},'name_field':{'first_cell':0x7889,'width':5,'rows':2,'blank_code':0},'scope':'clear native name field before Chinese names; player HUD display only; separate native status-name/status-condition consumers; unknown condition falls through original renderer'}
(ROOT/'ui-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest['candidate'],indent=2),'status bytes',len(code))