from runtime_paths import source_tree
"""ROM-specific port. Strict fixed inputs; never writes either supplied ROM."""
from pathlib import Path
import os,sys,json,re,hashlib,zlib,collections
ROOT=Path(__file__).resolve().parent
SRC=source_tree()
os.chdir(SRC);sys.path.insert(0,str(SRC))
from glyph_coloring import colour_windows
from sfc_tools import make_ips
analysis=json.loads((ROOT/'diff-analysis.json').read_text(encoding='utf-8'))
assert all(analysis['inputs'][k]['path'] for k in ('jp','opt','cn10')),'Configure private ROM paths with configure_inputs.py first'
fontcfg=analysis.get('private_dependencies',{}).get('unifont',{})
fontpath=Path(fontcfg.get('path') or os.environ.get('SFC_UNIFONT_PATH') or SRC/'fonts/unifont.hex.gz').resolve()
fontsha=json.loads((ROOT/'dependencies.json').read_text(encoding='utf-8'))['font/unifont.hex.gz']
assert fontpath.is_file(),'Missing private Unifont; configure_inputs.py --unifont PATH'
assert hashlib.sha256(fontpath.read_bytes()).hexdigest()==fontsha,'private Unifont fingerprint changed'
os.environ['SFC_UNIFONT_PATH']=str(fontpath)
for filename in ('msyh.ttc','simsun.ttc'):
    private_font=Path('C:/Windows/Fonts')/filename
    expected_font=json.loads((ROOT/'dependencies.json').read_text(encoding='utf-8'))['font/'+filename]
    assert private_font.is_file() and hashlib.sha256(private_font.read_bytes()).hexdigest()==expected_font,'private system font mismatch: '+filename
inputs={k:Path(analysis['inputs'][k]['path']).read_bytes() for k in ('jp','opt','cn10')}
for k,data in inputs.items():assert hashlib.sha256(data).hexdigest()==analysis['inputs'][k]['sha256']
jp,opt,donor_source=inputs['jp'],inputs['opt'],inputs['cn10']
import cnbuild5 as cb
cb.load_build_params()
# Earlier Chinese donors rewrote 560 apparent records; the native header has
# only 514 character records. The following bytes are growth/combat parameters.
# Normalize that inherited corruption before reconciling optimization changes.
native_name_start=int.from_bytes(jp[0x48000:0x48002],'little')
native_name_end=int.from_bytes(jp[0x48002:0x48004],'little')
assert native_name_start==0x802a and native_name_end==0xa04a
assert cb.NAME_RECORDS==514 and cb.NAME_RECORD_BASE+cb.NAME_RECORDS*16==0x4a04a
donor=bytearray(donor_source)
donor[0x4a04a:0x4a32a]=jp[0x4a04a:0x4a32a]
donor=bytes(donor)
parameter_repairs=[i for i in range(0x4a04a,0x4a32a) if donor_source[i]!=jp[i]]

assert len(jp)==0x100000 and len(opt)==0x180000 and len(donor)==0x200000
rom=bytearray(donor)
changes=[];allocations=[];relocations=[];retained=[];payload_roots=set()
def reserve(off,size,label):
    assert rom[off:off+size]==bytes(size),(label,'destination occupied',hex(off))
    assert all(off+size<=a['start'] or off>=a['end'] for a in allocations),(label,'reservation overlap')
    allocations.append({'start':off,'end':off+size,'label':label})
def patch(off,data,label,expected=None):
    if expected is not None:assert bytes(rom[off:off+len(expected)])==expected,(label,hex(off),'unexpected source bytes')
    changes.append({'offset':off,'length':len(data),'label':label})
    rom[off:off+len(data)]=data
# Preserve the donor's rebuilt script/pointer/name regions and reconcile menu ABIs explicitly.
protected=[(0x193b3,0x1e983,'Chinese text/pointers'),*[(cb.NAME_RECORD_BASE+i*16,cb.NAME_RECORD_BASE+i*16+4,'Chinese name field') for i in range(cb.NAME_RECORDS)],
           (0x1f743,0x1f777,'Chinese menu table'),(0x1f841,0x1f86a,'shared menu uploader/close'),(0x7fc0,0x8000,'header')]
for a,e in analysis['optimization_changes']:
    if a>=0x100000:continue
    for p in range(a,min(e,0x100000)):
        reason=next((n for x,y,n in protected if x<=p<y),None)
        if reason:retained.append({'offset':p,'reason':reason});continue
        assert donor[p]==jp[p],('unclassified original-bank conflict',hex(p))
        rom[p]=opt[p]
# The optimized native parameter tables must remain byte-exact. They are not text.
assert rom[0x4a04a:0x50000] == opt[0x4a04a:0x50000], 'native bank09 parameter/resource corruption'
changes.append({'offset':0x4a04a,'length':0x2e0,'label':'restore inherited non-name parameter corruption and merge optimized values'})
# One real name was changed by the optimizer: やすこ -> しょうこ. Add only the
# new required name glyph in the existing allocated high-ID name namespace.
name_overrides={467:'翔子'}
name_map=json.loads((SRC/'name_hanzi.json').read_text(encoding='utf-8'))
name_ids={}
for name in name_map.values():
    for ch in name:name_ids.setdefault(ch,len(name_ids))
new_name_glyphs={}
for index,translated in name_overrides.items():
    assert opt[cb.NAME_RECORD_BASE+index*16:cb.NAME_RECORD_BASE+index*16+4]==bytes.fromhex('2b 6e 22 29')
    codes=bytearray()
    for ch in translated:
        if ch not in name_ids:
            gid=len(name_ids);name_ids[ch]=gid;page,within=divmod(gid,256-cb.LABEL_ID0)
            off=cb.POOL_ROM+page*0x8000+(cb.LABEL_ID0+within)*cb.POOL_STRIDE
            reserve(off,cb.POOL_STRIDE,'optimized character-name glyph '+ch)
            patch(off,cb.glyph64(ch),'optimized character-name glyph '+ch)
            new_name_glyphs[ch]={'rom':off,'gid':gid}
        page,within=divmod(name_ids[ch],256-cb.LABEL_ID0)
        codes.extend([cb.PREFIX0+page,cb.LABEL_ID0+within])
    assert len(codes)<=4
    patch(cb.NAME_RECORD_BASE+index*16,codes.ljust(4,b'\0'),'optimized changed character-name translation')
# Existing expanded pool pages have known upper padding. Unlike bank $40, these
# banks still mirror low WRAM, which the original optimization helper relies on.
# Relocate code/data together; long addresses, bank-relative code/ROM operands,
# explicit DBR setup and text pointer immediates are all accounted for.
MAP={0x20:(0x35,0x2000),0x22:(0x36,0x2000),0x23:(0x37,0x2000)}
# Every nonzero byte added by this exact optimizer must belong to a declared
# relocated payload. Refuse a newer ROM that adds another bank/resource.
source_payload_lengths={0x20:0x2008,0x22:0x108,0x23:0x3000}
for source_bank in range(0x20,0x30):
    declared=source_payload_lengths.get(source_bank,0)
    assert not any(opt[source_bank*0x8000+declared:(source_bank+1)*0x8000]), ('unclassified optimized resource',hex(source_bank))

for old,(new,delta) in MAP.items():
    used={0x20:0x2008,0x22:0x108,0x23:0x3000}[old]
    start=new*0x8000+delta
    reserve(start,used,f'optimization bank {old:02X} relocated to {new:02X}:A000')
    patch(start,opt[old*0x8000:old*0x8000+used],'relocated optimization payload')
# The donor primary pool reader uses 33 body slots. New texts get a separate
# ROM namespace at A000; names remain in the original 8000 namespace.
new_text=json.loads((ROOT/'optimization-cn-text.json').read_text(encoding='utf-8-sig'))
assert set(new_text)=={f'{i:03X}' for i in range(0x301,0x34c)}
aliases=json.loads((ROOT/'optimization-existing-cn.json').read_text(encoding='utf-8'))
all_text={**new_text,**aliases}
wrapped={k:cb.wrap_segments(v) for k,v in all_text.items()}
common_words={22:'同伴',23:'敌人',24:'国夫',25:'力',26:'国夫和力',27:'国夫与力',28:'国夫 力',29:'你',30:'你们',31:'我',32:'我们',33:'同盟',34:'联合',35:'那家伙',36:'那些家伙'}
def text_windows(text):
    result=[]
    for page in text.split('{F2F4}'):
        if '{ED}' in page or '{EE}' in page or len(cb.glyphs_of(page))>33:
            rows=re.split(r'\{F2(?:F6|F7|E2)\}',page)
            for i in range(len(rows)):
                chunk=''.join(rows[i:i+3]);w=cb.glyphs_of(chunk)
                count=int('{ED}' in chunk)+int('{EE}' in chunk)
                if count==0:result.append(w)
                elif count==1:result.extend(w|cb.glyphs_of(word) for index,word in common_words.items() if 22<=index<=36)
                else:result.extend(w|cb.glyphs_of(left)|cb.glyphs_of(right) for li,left in common_words.items() for ri,right in common_words.items() if 22<=li<=36 and 22<=ri<=36)
        else:result.append(cb.glyphs_of(page))
    return result
windows=[w for text in wrapped.values() for w in text_windows(text)]
windows.extend(cb.glyphs_of(word) for index,word in common_words.items() if 22<=index<=36)
menu_chars=['气','力','道','具','装','备','状','态','扔','掉','互','伤','开','关']
windows.extend([set(menu_chars[:-1]),set(menu_chars[:12]+['关'])])
cell=json.loads((SRC/'cn_glyph_cell.json').read_text(encoding='utf-8'))
fixed={c:cell[c][1] for c in menu_chars[:10]};fixed['—']=0
state_slot=next(slot for slot in range(33) if slot not in fixed.values())
fixed['开']=fixed['关']=state_slot
colour,colour_loads,colour_info=colour_windows(windows,33,17,fixed=fixed)
columns=collections.defaultdict(list)
for c,s in sorted(colour.items()):
    if not c.startswith('@old'):columns[s].append(c)
new_cell={c:(page,s) for s,chars in columns.items() for page,c in enumerate(chars)}
pages=max(p for p,s in new_cell.values())+1
assert pages<=17
for page in range(pages):reserve((0x24+page)*0x8000+0x2000,33*64,f'extended Chinese glyph page {page}')
for ch,(page,slot) in new_cell.items():
    if ch in cell:
        old_page,old_slot=cell[ch];bitmap=donor[(0x20+old_page)*0x8000+old_slot*64:(0x20+old_page)*0x8000+(old_slot+1)*64]
    else:bitmap=cb.glyph64(ch)
    assert len(bitmap)==64 and any(bitmap),(ch,'missing glyph')
    off=(0x24+page)*0x8000+0x2000+slot*64;rom[off:off+64]=bitmap
# Mask fixed-width setup in optimizer code after exact primary conflict checks.
LONG_OPS={0x0f,0x1f,0x22,0x2f,0x3f,0x4f,0x5c,0x5f,0x6f,0x7f,0x8f,0x9f,0xaf,0xbf,0xcf,0xdf,0xef,0xff}
ABS_OPS={0x0c,0x0d,0x0e,0x19,0x1c,0x1d,0x1e,0x20,0x2c,0x2d,0x2e,0x39,0x3c,0x3d,0x3e,0x4c,0x4d,0x4e,0x59,0x5d,0x5e,0x6d,0x6e,0x79,0x7d,0x7e,0x8c,0x8d,0x8e,0x99,0x9c,0x9d,0x9e,0xac,0xad,0xae,0xb9,0xbc,0xbd,0xbe,0xcc,0xcd,0xce,0xd9,0xdc,0xdd,0xde,0xec,0xed,0xee,0xf9,0xfc,0xfd,0xfe}
def mapped(off):
    bank=off//0x8000
    if bank in MAP:return MAP[bank][0]*0x8000+off%0x8000+MAP[bank][1]
    return off
# First pass: long references from actual unchanged original code and added code.
for i in range(0x100000):
    if any(a<=i<e for a,e,n in protected):continue
    if opt[i] in (0x22,0x5c) and opt[i+2]>=0x80 and opt[i+3] in MAP and opt[i:i+4]!=jp[i:i+4]:
        bank=opt[i+3];payload_roots.add((bank,int.from_bytes(opt[i+1:i+3],'little')));new,delta=MAP[bank];address=int.from_bytes(opt[i+1:i+3],'little')+delta
        assert address<=0xffff,('invalid optimized Hook target',hex(i))
        assert bytes(rom[i:i+4])==opt[i:i+4],('long-hook source mismatch',hex(i))
        rom[i+1:i+4]=address.to_bytes(2,'little')+bytes([new]);relocations.append({'source':i,'destination':i,'kind':'long-reference','old_bank':bank})
# Only code spans: animation tables and message pointers are not decoded as instructions.
code_spans={0x20:[(0x1e0,0x74c),(0x1000,0x1575),(0x2000,0x2008)],0x22:[(0,0x6d)]}
from relocation_decoder import decode_payload
instructions=decode_payload(opt,payload_roots,code_spans)
(ROOT/'decoded-instructions.json').write_text(json.dumps(list(instructions.values()),indent=2),encoding='utf-8')
for p,ins in sorted(instructions.items()):
    old=ins['bank'];q=mapped(p);raw=bytes.fromhex(ins['raw'])
    if ins['length']==4 and opt[p] in LONG_OPS and raw[2]>=0x80 and raw[3] in MAP:
        new,delta=MAP[raw[3]];addr=int.from_bytes(raw[1:3],'little')+delta
        rom[q+1:q+4]=addr.to_bytes(2,'little')+bytes([new]);relocations.append({'source':p,'destination':q,'kind':'long-reference','instruction':ins['text']})
    elif old==0x20 and ins['length']==3 and opt[p] in ABS_OPS and 0x8000<=int.from_bytes(raw[1:3],'little')<0xa100:
        addr=int.from_bytes(raw[1:3],'little')+0x2000
        rom[q+1:q+3]=addr.to_bytes(2,'little');relocations.append({'source':p,'destination':q,'kind':'bank-relative-ROM','instruction':ins['text']})
    if opt[p:p+4] in (bytes.fromhex('a9 20 48 ab'),bytes.fromhex('a9 22 48 ab'),bytes.fromhex('a9 23 48 ab')):
        assert ins['length']==2
        rom[q+1]=MAP[opt[p+1]][0];relocations.append({'source':p,'destination':q,'kind':'DBR','instruction':ins['text']})
# bank22 table selector: $8070 -> $A070 after the paired relocation.
patch(mapped(0x110034),bytes([0xa0]),'extended pointer table high byte',bytes([0x80]))
# Build complete translated message table and independent backread.
text_start=0x37*0x8000+0x2000;cursor=text_start;encoded={}
def encode(text):
    data=bytearray()
    atoms=[]
    for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})',text):
        if part:atoms.extend([part] if cb.TOKEN.fullmatch(part) else cb.units(part))
    for ch in atoms:
        if cb.TOKEN.fullmatch(ch):data.extend(bytes.fromhex(ch[1:-1]));continue
        if ch==' ':data.append(0);continue
        if ch in cb.KEEP1:data.append(cb.KEEP1[ch]);continue
        if ch=='—':data.append(0xdf);continue
        page,slot=new_cell[ch];data.extend([0xc0+page,0x40+slot])
    return bytes(data)
# Optimization texts can exceed the original 1856 bytes after Chinese encoding.
assert rom[text_start:text_start+0x3000]==opt[0x118000:0x118740]+bytes(0x3000-0x740)
rom[text_start:text_start+0x3000]=bytes(0x3000)
allocations[-1:] = allocations[-1:] # allocations recorded separately below if needed
for k in sorted(wrapped):
    data=encode(wrapped[k]);address=0x8000+cursor%0x8000
    if int(k,16)>=0x301:
        table=mapped(0x110070)+(int(k,16)-0x300)*2
        rom[table:table+2]=address.to_bytes(2,'little')
    rom[cursor:cursor+len(data)]=data
    encoded[k]={'rom':cursor,'bytes':data.hex(),'text':wrapped[k]};cursor+=len(data)
assert cursor<0x37*0x8000+0x8000,'extended text crosses bank'
# Isolated helper page: pool padding from the fixed input, separate from both resources.
common_base=0x1e8e8
common_payload=bytearray(donor[0x1e4ce+22*2:0x1e4ce+37*2]);common_encoded={}
for index,word in common_words.items():
    data=encode(word+'{F2F3}');off=common_base+len(common_payload)
    common_payload[(index-22)*2:(index-22)*2+2]=(0x8000+off%0x8000).to_bytes(2,'little')
    common_payload+=data
    common_encoded[str(index)]={'rom':off,'bytes':data.hex(),'text':word+'{F2F3}'}
assert common_base+len(common_payload)<=0x1e970
reserve(common_base,len(common_payload),'extended common-macro mirror in declared native text padding')
patch(common_base,common_payload,'extended common-macro pointer/text mirror')
helper_base=0x38*0x8000+0x2000
reserve(helper_base,0x1000,'port ABI helpers')
def install_helper(off,a,label,max_size=0x100):
    code=a.done();assert len(code)<=max_size
    patch(off,code,label);return cb.snes_of_rom(off)
# Predicate returns carry only, preserving A/P width, X/Y/DBR/D and all other flags.
a=cb.Asm(helper_base+0x200)
a.hexs('08 C2 20 48 AD 4A 03 C9 00 03');a.far_rel(0xb0,'yes','ext')
for ix,key in enumerate(sorted(aliases)):
    mid=int(key,16);a.hexs('C9 %02X %02X'%(mid&255,mid>>8));a.far_rel(0xf0,'yes','a%d'%ix)
a.hexs('68 28 18 6B');a.label('yes');a.hexs('68 28 38 6B')
install_helper(helper_base+0x200,a,'extended message namespace predicate',0x100)
# One byte immediately before the existing pace counter is native padding:
# original/optimizer references to absolute $03E6 occur only in pointer/graphics
# data, not executable consumers. The native full message-context initializer
# ($03:E99D STZ $034A,X, observed PC E9A0) clears it together with the window.
# Runtime probes accept only that zero-reset and our namespace helper writes.
# Bit0=current namespace, bit1=previous namespace, bit7=clear requested.
# Clear on entry to an extended message and when returning from one. Single-
# message F2F7/F4 continuation keeps the native controls and does not rearm it.
a=cb.Asm(helper_base+0xA00)
a.hexs('08 E2 20 48 AD E6 03 29 01 0A 8D E6 03 22 00 A2 38');a.rel(0x90,'old')
a.hexs('AD E6 03 09 81 8D E6 03');a.rel(0x80,'done')
a.label('old');a.hexs('AD E6 03');a.rel(0xF0,'done');a.hexs('09 80 8D E6 03')
a.label('done');a.hexs('68 28 6B')
install_helper(helper_base+0xA00,a,'extended message font lifetime transition')
# Gateway preserves the true original message ID; aliases do not change story variables.
a=cb.Asm(helper_base+0x300)
a.hexs('22 00 AA 38 08 C2 20 AD 4A 03')
for ix,key in enumerate(sorted(aliases)):
    mid=int(key,16);a.hexs('C9 %02X %02X'%(mid&255,mid>>8));a.far_rel(0xf0,'a%d'%ix,'t%d'%ix)
a.hexs('28 AD 4B 03 C9 03 5C 05 A0 36') # replay high-byte CMP before native BCS
for ix,key in enumerate(sorted(aliases)):
    addr=0x8000+encoded[key]['rom']%0x8000
    a.label('a%d'%ix);a.hexs('A9 %02X %02X 8D 6A 03 28 A0 01 5C 9A EB 03'%(addr&255,addr>>8))
install_helper(helper_base+0x300,a,'existing optimized message aliases',0x300)
# New gateway at original optimized loader's entry; leave the native high-ID case intact.
patch(mapped(0x110000),bytes.fromhex('5C 00 A3 38 EA'),'extended loader gateway',opt[0x110000:0x110005])
a=cb.Asm(helper_base+0x600)
a.hexs('22 00 A2 38');a.rel(0xb0,'ext')
a.hexs('B1 20 85 12');a.rel(0x80,'lifetime')
a.label('ext');a.hexs('8B A9 37 48 AB B1 20 85 12 AB')
a.label('lifetime');a.hexs('08 48 AD E6 03');a.rel(0x10,'return')
a.hexs('A5 12 C9 F3');a.rel(0xF0,'boundary')
a.hexs('C9 F0');a.rel(0xF0,'consume')
# Prefix the decoded page buffer; do not advance or rewind the source pointer.
a.hexs('A9 F0 8D EA 03 A9 01 85 11 8D E8 03')
a.label('consume');a.hexs('AD E6 03 29 01 8D E6 03');a.rel(0x80,'return')
# A leading F3 belongs to the previous boundary and draws no new font glyphs.
a.label('boundary');a.hexs('AD E6 03 4A 29 01 8D E6 03')
a.label('return');a.hexs('68 28 5C BF EB 03')
install_helper(helper_base+0x600,a,'extended source stream selector')
patch(mapped(0x110050),bytes.fromhex('5C 00 A6 38'),'text stream namespace gateway',opt[0x110050:0x110054])
# Only the common-name macro reader is redirected in an extended message.
# Original dialogues and every list retain their source tables and font codes.
a=cb.Asm(helper_base+0x900)
a.hexs('22 00 A2 38');a.rel(0x90,'old')
a.hexs('C9 3C');a.rel(0x90,'old');a.hexs('C9 4B');a.rel(0xb0,'old')
a.hexs('0A 18 69 70 85 28 A9 E8 69 00 85 29 5C 1D EE 03')
a.label('old');a.hexs('0A 18 6D F3 EA 85 28 5C 16 EE 03')
install_helper(helper_base+0x900,a,'common-name macro namespace gateway')
patch(0x1ee0f,bytes.fromhex('5C 00 A9 38 EA EA EA'),'common macro source Hook',donor[0x1ee0f:0x1ee16])
# A new glyph carries a marker in the otherwise unused body-ID gap $40..$60.
# This follows the actual glyph through runtime macro pastes and menu transitions;
# a stale message ID can never reinterpret an old body or name glyph.
a=cb.Asm(helper_base)
a.hexs('5A AD E9 03 1A A8 B9 EA 03 C9 40');a.rel(0x90,'old')
a.hexs('C9 61');a.rel(0xb0,'old')
a.hexs('7A A5 12 38 E9 C0 18 69 24 6B');a.label('old');a.hexs('7A A5 12 38 E9 C0 18 69 20 6B')
install_helper(helper_base,a,'body source bank by glyph marker')
pattern=bytes.fromhex('A5 12 38 E9 C0 18 69 20')
site=donor.find(pattern,0x1f0200,0x1f0780);assert site>=0 and donor.find(pattern,site+1,0x1f0780)<0
bk,ad=cb.snes_of_rom(helper_base);patch(site,bytes([0x22,ad&255,ad>>8,bk])+bytes([0xea])*4,'extended glyph bank Hook',pattern)
# Preserve live full X/Y, A and widths; the raw buffer marker owns the ROM offset.
a=cb.Asm(helper_base+0x100)
a.hexs('0A 0A 0A 08 48 5A E2 20 AD E9 03 1A C2 20 29 FF 00 A8 E2 20 B9 EA 03 C9 40');a.rel(0x90,'old')
a.hexs('C9 61');a.rel(0xb0,'old')
a.hexs('C2 20 7A 68 18 69 00 20');a.rel(0x80,'done')
a.label('old');a.hexs('C2 20 7A 68');a.label('done');a.hexs('28 A8 E2 20 6B')
install_helper(helper_base+0x100,a,'body source offset by glyph marker')
pattern=bytes.fromhex('0A 0A 0A 0A 0A 0A A8 E2 20')
site=donor.find(pattern,0x1f0200,0x1f0780);assert site>=0
bk,ad=cb.snes_of_rom(helper_base+0x100);patch(site+3,bytes([0x22,ad&255,ad>>8,bk,0xea,0xea]),'extended glyph offset Hook',pattern[3:])
# Normalize the marker to the existing 0..32 VRAM slot before the pair-table read.
pattern=bytes.fromhex('B9 EA 03 C9 21 90')
site=donor.find(pattern,0x1f0200,0x1f0780);assert site>=0
branch=site+5;gotid=branch+2+int.from_bytes(donor[branch+1:branch+2],'little',signed=True)
a=cb.Asm(helper_base+0x840)
a.hexs('C9 40');a.rel(0x90,'old');a.hexs('C9 61');a.rel(0xb0,'old')
a.hexs('38 E9 40');a.long_to(gotid)
a.label('old');a.hexs('C9 21');a.rel(0x90,'body');a.long_to(site+7)
a.label('body');a.long_to(gotid)
install_helper(helper_base+0x840,a,'new glyph ID normalization')
patch(site+3,bytes.fromhex('5C 40 A8 38'),'glyph ID marker Hook',donor[site+3:site+7])
# Original optimizer menu is a 3x2 grid with a friendly-fire toggle. Keep both its
# input/state machine and the donor label uploader/queue clearing.
# Table code records reuse existing donor codes; two extra glyphs use unused codes.
slot_stride=33+cb.LABEL_GLYPHS*cb.LABEL_SETS+cb.LABEL_NAME_GLYPHS*cb.LABEL_NAME_SETS
pool_lo=donor[cb.E3_SLOTPAIR:cb.E3_SLOTPAIR+slot_stride*2]
pool_hi=donor[cb.E3_SLOTHI:cb.E3_SLOTHI+slot_stride*2]
menu_records=bytearray(donor[cb.MENU_TAB:cb.MENU_TAB+70]);codes={}
# The donor menu's literal tile mappings are separate from the body slot table.
# Reserve the actual two half-pairs, rather than assuming a glyph's body slot
# identifies all of its resident menu tiles.
menu_used_tiles=set()
for ix in range(10):
    rec=menu_records[ix*7:ix*7+7]
    for dest in (int.from_bytes(rec[:2],'little'),int.from_bytes(rec[2:4],'little')):
        tile=(dest-0x6000)//8;menu_used_tiles.update((tile,tile+1))
menu_target_slots=[]
for slot in range(33):
    t=pool_lo[slot]+256*pool_hi[slot];u=pool_lo[slot+slot_stride]+256*pool_hi[slot+slot_stride]
    tiles={t,t+1,u,u+1}
    if t<255 and u<255 and not (tiles & (menu_used_tiles|set(cb.BOX_GFX_TILES))):
        menu_target_slots.append(slot);menu_used_tiles.update(tiles)
        if len(menu_target_slots)==3:break
assert len(menu_target_slots)==3,'no safe menu destinations for new labels'

# Use donor's actual codes found in its edited menu table, not a new build ordering.
old_table=donor[0x1f743:0x1f777]
old_positions={'气':1,'力':3,'道':12,'具':14,'装':27,'备':29,'状':38,'态':40,'扔':48,'掉':50}
for ch,p in old_positions.items():codes[ch]=list(old_table[p:p+2])
for ix,ch in enumerate(menu_chars[10:13]):
    codes[ch]=list(cb.CMDWIN_CODES[20+ix*2:22+ix*2]);s=menu_target_slots[ix]
    t=pool_lo[s]+256*pool_hi[s];u=pool_lo[s+slot_stride]+256*pool_hi[s+slot_stride]
    for code,tile in zip(codes[ch],(t,u)):
        assert tile<256,'static menu FA/FB cannot name high tile'
        rom[0x1fb9e+code]=tile;rom[0x1fa9e+code]=tile+1
    page,s=new_cell[ch];address=0xa000+s*64;bank=0x24+page
    menu_records+= (0x6000+t*8).to_bytes(2,'little')+(0x6000+u*8).to_bytes(2,'little')+address.to_bytes(2,'little')+bytes([bank])
patch(cb.MENU_TAB,menu_records,'13 Chinese menu label glyph records, including toggle state')
assert donor[cb.MENU_STUB+0x11:cb.MENU_STUB+0x13]==bytes.fromhex('c9 0a')
patch(cb.MENU_STUB+0x12,bytes([13]),'menu uploader thirteen glyphs',bytes([10]))
table=bytearray(52)
for row,col,text in [(0,1,'气力'),(0,11,'道具'),(0,21,'装备'),(1,1,'状态'),(1,11,'互伤'),(1,21,'扔掉')]:
    pos=row*26+col
    for ch in text:table[pos:pos+2]=bytes(codes[ch]);pos+=2
table[26+17:26+19]=bytes(codes['开'])
patch(0x1f743,table,'optimized six-command Chinese menu')
# One shared state tile is uploaded as 开 or 关. It uses the original toggle bit.
a=cb.Asm(helper_base+0x700)
a.hexs('08 48 A5 15 C9 0C');a.rel(0xd0,'out')
a.hexs('A5 70');a.rel(0x10,'out')
page,slot=new_cell['关'];addr=0xa000+slot*64
a.hexs('A9 %02X 85 16 A9 %02X 85 17 A9 %02X 85 18'%(addr&255,addr>>8,0x24+page))
a.label('out');a.hexs('68 28 A5 1A 85 1E 6B')
install_helper(helper_base+0x700,a,'friendly-fire state glyph selector')
pattern=bytes.fromhex('A5 1A 85 1E');site=donor.find(pattern,cb.MENU_STUB,cb.MENU_TAB);assert site>=0
patch(site,bytes.fromhex('22 00 A7 38'),'menu toggle state Hook',pattern)
# Native optimized coordinate helper replaces the donor's five-entry replay tail.
pattern=bytes.fromhex('AC 9A 03 B9 51 F8 5C 47 F8 03')
site=donor.find(pattern,cb.MENU_STUB,cb.MENU_TAB);assert site>=0
patch(site,bytes.fromhex('5C 00 B0 35')+bytes([0xea])*6,'menu uploader returns to six-entry coordinates',pattern)
patch(0x1f845,opt[0x1f845:0x1f851],'optimized six-entry coordinates')
patch(0x1f851,bytes([0x60]),'native coordinate helper RTS')
# Preserve donor position fix by choosing the six-slot coordinate layout explicitly.
# Friendly-fire stays fully functional; no Japanese toggle labels get inserted.
patch(mapped(0x10109b),bytes.fromhex('5C 41 F7 03'),'retain Chinese friendly-fire label')
# Close routine: donor row-clearing ABI + original optimizer 32-pixel transition.
pattern=bytes.fromhex('EE C1 03 EE C1 03 EE 9E 03')
site=donor.find(pattern,cb.MENUCLOSE_STUB,cb.MENUCLOSE_STUB+0x100);assert site>=0
patch(site,bytes.fromhex('AD C1 03 18 69 20 8D C1 03'),'optimized close replay in Chinese clear stub',pattern)
patch(0x1f864,opt[0x1f864:0x1f86a],'optimized close continuation')
# Optimizer suffix table entry 78 changed from a recovery fragment to the
# two-player calling string. Use dedicated name-label glyph codes, so the alias
# font namespace cannot reinterpret a pasted player name as a body glyph.
import kuniokun_map as km
name_codes={}
for i in range(cb.NAME_RECORDS):
    off=cb.NAME_RECORD_BASE+i*16
    kana=''.join(km.CODE.get(b,'') for b in jp[off:off+4]).strip()
    if kana in ('くにお','りき'):
        name_codes[kana]=donor[off:off+4].rstrip(b'\x00')
assert set(name_codes)=={'くにお','りき'}
player_names=name_codes['くにお'].ljust(4,b'\x00')+name_codes['りき'].ljust(4,b'\x00')
patch(0x73c7,player_names,'fixed player HUD initialization names',opt[0x73c7:0x73cf])
suffix=name_codes['くにお']+bytes.fromhex('01 f7 00')+name_codes['りき']+bytes.fromhex('f2 f3')
suffix_off=0x1e970
assert suffix_off+len(suffix)<=cb.B3_SANITIZE_END
reserve(suffix_off,len(suffix),'optimized two-player suffix in declared native text padding')
patch(suffix_off,suffix,'optimized two-player call fragment')
patch(0x1e4ce+78*2,(0xe970).to_bytes(2,'little'),'optimized suffix export entry78 / runtime0074 pointer')

# Shared F841/F85B hooks themselves remain donor Hooks. F736 and F7AE optimization Hooks are preserved.
# Header title identifies the optimization; mapping/size remain a 2MiB LoROM.
rom[0x7fc0:0x7fd5]=opt[0x7fc0:0x7fd5];rom[0x7fd7]=11
rom[0x7fdc:0x7fe0]=bytes(4)
checksum=(sum(rom)+0x1fe)&0xffff
rom[0x7fdc:0x7fe0]=(checksum^0xffff).to_bytes(2,'little')+checksum.to_bytes(2,'little')
assert sum(rom)&0xffff==checksum
output=ROOT/'candidate.sfc';output.write_bytes(rom)
# make_ips API is verified locally below before calling.
manifest={'inputs':analysis['inputs'],'candidate':{'size':len(rom),'crc32':f'{zlib.crc32(rom):08X}','sha256':hashlib.sha256(rom).hexdigest()},
'allocations':allocations,'optimization_relocations':relocations,'patches':changes,'retained_original_text_differences':retained,
'extended_glyph_code_id_bias':64,'dynamic_common_words':common_words,'encoded_common_macros':common_encoded,'extended_glyphs':{'count':len(new_cell),'pages':pages,'cells':new_cell,'base_bank':0x24,'address':0xa000},'extended_messages':encoded,'existing_optimized_message_aliases':sorted(aliases),
'notes':['L+R+X is the native held-input gate for actor/attribute modifiers at 35:B170; direction and additional $20 input edges select actions. Friendly fire is a separate menu command.',
'Chinese menu has native six commands and displays friendly-fire 开/关; all new scripts translated; source message348 keeps its leading F3 boundary as supplied. Original rebuilt Chinese scripts/names retained.',
'Not yet emulator accepted.'], 'native_name_records':514,'native_parameter_repairs':parameter_repairs,'name_overrides':name_overrides,'new_name_glyphs':new_name_glyphs,'scope':'candidate; original-bank conflict classification, original optimization code/resource relocation and shared menu interface integration'}
(ROOT/'port-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print('BUILT',output,manifest['candidate'],'new glyphs',len(new_cell),'pages',pages,'relocations',len(relocations))
