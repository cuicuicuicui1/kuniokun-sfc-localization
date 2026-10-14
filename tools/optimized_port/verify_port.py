from runtime_paths import source_tree
from pathlib import Path
import sys,os,json,zlib,hashlib,collections
ROOT=Path(__file__).resolve().parent
SRC=source_tree()
os.chdir(SRC);sys.path.insert(0,str(SRC))
import sim65816 as S
import cnbuild5 as cb
cb.load_build_params()
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))
r=(ROOT/'candidate.sfc').read_bytes()
inputs={k:Path(m['inputs'][k]['path']).read_bytes() for k in ('jp','opt','cn10')}
for key,data in inputs.items():assert hashlib.sha256(data).hexdigest()==m['inputs'][key]['sha256'],key
assert hashlib.sha256(r).hexdigest()==m['candidate']['sha256']
assert len(r)==0x200000 and r[0x7fd7]==11 and (sum(r)&0xffff)==int.from_bytes(r[0x7fde:0x7fe0],'little')
opt,donor,jp=inputs['opt'],inputs['cn10'],inputs['jp']
changed_stats=0
for i in range(514):
    o=0x4802a+i*16
    if str(i) not in m['name_overrides']:assert r[o:o+4]==donor[o:o+4]
    assert r[o+4:o+16]==opt[o+4:o+16]
    changed_stats+=sum(a!=b for a,b in zip(jp[o+4:o+16],r[o+4:o+16]))
for i in range(0x193b3,0x1e983):
    if 0x1e56a<=i<0x1e56c or 0x1e8e8<=i<0x1e982:continue
    assert r[i]==donor[i],('unclassified donor text change',hex(i))
assert r[0x4a04a:0x50000]==opt[0x4a04a:0x50000], 'native parameter tables changed'
assert len(m['native_parameter_repairs'])==160
# All classified relocated instruction operands must match the source after the
# declared bank/offset transformation. No relocation may start inside an operand.
ins={x['offset']:x for x in json.loads((ROOT/'decoded-instructions.json').read_text())}
for change in m['optimization_relocations']:
    a,b=change['source'],change['destination'];kind=change['kind']
    if a>=0x100000:assert a in ins,(hex(a),'non-instruction relocation')
    if kind=='DBR':assert r[b+1]=={0x20:0x35,0x22:0x36,0x23:0x37}[opt[a+1]]
    elif kind=='bank-relative-ROM':assert int.from_bytes(r[b+1:b+3],'little')==int.from_bytes(opt[a+1:a+3],'little')+0x2000
    elif kind=='long-reference':
        assert r[b+3]=={0x20:0x35,0x22:0x36,0x23:0x37}[opt[a+3]]
        assert int.from_bytes(r[b+1:b+3],'little')==int.from_bytes(opt[a+1:a+3],'little')+0x2000
# No old glyph/name bitmap is overwritten; only declared zero padding is used.
for block in m['allocations']:
    assert donor[block['start']:block['end']]==bytes(block['end']-block['start']),block
for page in range(30):
    off=(0x20+page)*0x8000
    assert r[off:off+33*64]==donor[off:off+33*64]
# Resident menu half-pairs must be distinct, including the retained donor
# mappings and all newly added labels. Source font slots do not imply targets.
menu_tiles=set()
for ix in range(13):
    rec=r[cb.MENU_TAB+ix*7:cb.MENU_TAB+(ix+1)*7]
    for dest in (int.from_bytes(rec[:2],'little'),int.from_bytes(rec[2:4],'little')):
        assert 0x6000<=dest<0x6800 and (dest-0x6000)%8==0
        tile=(dest-0x6000)//8
        assert not ({tile,tile+1}&menu_tiles),('menu glyph half overlap',ix,tile)
        menu_tiles.update((tile,tile+1))
# Independent new-code readback and co-visible slot identity check.
cells=m['extended_glyphs']['cells'];reverse={tuple(v):k for k,v in cells.items()}
for mid,record in {**m['extended_messages'],**{'macro'+k:v for k,v in m['encoded_common_macros'].items()}}.items():
    raw=bytes.fromhex(record['bytes']);off=record['rom'];assert r[off:off+len(raw)]==raw
    parts=[];i=0
    while i<len(raw):
        b=raw[i];i+=1
        if b==0xf2:parts.append('{F2%02X}'%raw[i]);i+=1
        elif b>=0xe0:parts.append('{%02X}'%b)
        elif b==0xdf:parts.append('—')
        elif 0xc0<=b<0xc0+12:
            parts.append(reverse[(b-0xc0,raw[i]-64)]);i+=1
        elif b==0:parts.append(' ')
        else:
            rev={v:k for k,v in cb.KEEP1.items()};parts.append(rev[b])
    canonical=lambda text:''.join({v:k for k,v in cb.KEEP1.items()}.get(cb.KEEP1.get(ch),ch) for ch in text)
    assert ''.join(parts)==canonical(record['text']),(mid,''.join(parts),canonical(record['text']))
aliases={int(x,16) for x in m['existing_optimized_message_aliases']}
def extended(mid):return mid>=0x300 or mid in aliases
def newcpu(mid,pc=0xa200,bank=0x38,m8=True,x8=True):
    c=S.CPU(r);c.pc=pc;c.pbr=bank;c.db=3;c.m8=m8;c.x8=x8
    c.a=0xa5c7;c.x=0x71 if x8 else 0xa571;c.y=0x59 if x8 else 0xb959
    c.n=True;c.z=False;c.v=True;c.c=False
    c.bus.wram[0x34a:0x34c]=mid.to_bytes(2,'little')
    return c
def call(c,limit=2000):
    c.push8(0);c.push8(0xf0);c.push8(0xff)
    for n in range(limit):
        c.step()
        if (c.pbr,c.pc)==(0,0xf100):break
    else:raise AssertionError(('helper return',c.pbr,c.pc))
    assert c.s==0x1ff
# Exhaustive namespace discrimination across all real messages and all native widths.
for mid in range(0x34c):
 for m8 in [True,False]:
  for x8 in [True,False]:
    c=newcpu(mid,m8=m8,x8=x8);before=(c.a,c.x,c.y,c.db,c.m8,c.x8,c.n,c.z,c.v)
    call(c);assert c.c==extended(mid),hex(mid)
    assert (c.a,c.x,c.y,c.db,c.m8,c.x8,c.n,c.z,c.v)==before,'predicate ABI'
# True original IDs are preserved through aliased and high-ID pointer loading.
for mid in range(1,0x34c):
    c=newcpu(mid,0xa000,0x36);before=bytes(c.bus.wram[0x34a:0x34c])
    for _ in range(2000):
        c.step()
        if (c.pbr,c.pc) in [(3,0xeb74),(3,0xeb9a)]:break
    else:raise AssertionError(('loader return',mid,c.pbr,c.pc))
    assert bytes(c.bus.wram[0x34a:0x34c])==before and c.s==0x1ff and c.db==3,hex(mid)
    key=f'{mid:03X}'
    if key in m['extended_messages']:
        ptr=int.from_bytes(c.bus.wram[0x36a:0x36c],'little')
        assert ptr==0x8000+m['extended_messages'][key]['rom']%0x8000,(hex(mid),hex(ptr))
    elif mid<0x300:assert (c.pbr,c.pc)==(3,0xeb74)
# Full X/Y survive the font offset helper, including high-ID speaker glyphs.
for mid in [0x20,0x09d,0x161,0x26f,0x28a,0x303,0x320]:
 for gid in [0,1,32,128,255]:
    c=newcpu(mid,0xa100,m8=False,x8=False);c.a=gid*8;c.x=0xb523;c.bus.wram[0x3e9]=0;c.bus.wram[0x3eb]=gid+64 if extended(mid) and gid<33 else gid;call(c)
    want=gid*64+(0x2000 if extended(mid) and gid<33 else 0)
    assert c.y==want and c.a==want and c.x==0xb523 and c.m8 and not c.x8,(mid,gid,c.y,want)
# Execute the complete live extended ROM stream reader, including its old path.
for mid in [0x20,0x09d,0x186,0x26f,0x303,0x320]:
    c=newcpu(mid,0xa050,0x36);c.y=0;c.bus.wram[0x20:0x22]=bytes.fromhex('00 a0')
    for _ in range(1000):
        c.step()
        if (c.pbr,c.pc)==(3,0xebbf):break
    else:raise AssertionError('stream reader return')
    expected=r[(0x37 if extended(mid) else 3)*0x8000+0x2000]
    assert c.bus.wram[0x12]==expected and c.db==3 and c.s==0x1ff,hex(mid)
# Real primary message tick: every new marker and every inherited body glyph.
from dialogue_model import make_cpu,tick,flush
old_cells=json.loads((SRC/'cn_glyph_cell.json').read_text(encoding='utf-8'))
full_draw_cases=0
for extended_case,table in [(False,old_cells),(True,cells)]:
    for ch,(page,slot) in table.items():
        code=[0xc0+page,slot+(64 if extended_case else 0)]
        c=make_cpu(r,codes=code);c.bus.wram[0x9e0:0x9e2]=bytes.fromhex('f8 ff')
        c.bus.wram[0x34a:0x34c]=(0x320).to_bytes(2,'little') # stale/new ID cannot select an old glyph's ROM
        tick(c)
        q=c.bus.wram;entries=[];cursor=0
        while cursor<q[0x9df]:
            size=q[0xb00+cursor+3]
            if size==32:entries.append(bytes(q[0xb00+cursor+4:0xb00+cursor+4+size]))
            cursor+=4+size
        assert len(entries)==2,(ch,'glyph upload missing',entries)
        off=((0x24 if extended_case else 0x20)+page)*0x8000+slot*64+(0x2000 if extended_case else 0)
        assert b''.join(entries)==r[off:off+64],(ch,'wrong glyph source',extended_case)
        assert q[0x9e0:0x9e2]==bytes.fromhex('f8 ff'),'queue damaged train state'
        flush(c);full_draw_cases+=1
# Native common-suffix reader: both source namespaces, all124 actual table IDs.
for mid in [0x20,0x09d,0x28a,0x305]:
 for index in range(1,162):
    c=newcpu(mid,0xee0f,3);c.a=index
    for _ in range(1000):
        c.step()
        if (c.pbr,c.pc) in [(3,0xee16),(3,0xee1d)]:break
    else:raise AssertionError('common macro gateway return')
    if extended(mid) and 0x3c<=index<0x4b:
        want=0xe8e8+(index-0x3c)*2
        assert int.from_bytes(c.bus.wram[0x28:0x2a],'little')==want
    else:
        base=int.from_bytes(r[0x1eaf3:0x1eaf5],'little')
        assert c.bus.wram[0x28]==(base+index*2)&255
    assert c.s==0x1ff and c.db==3 and c.m8 and c.x8,'macro gateway ABI'
result={'status':'pass','candidate':m['candidate'],'input_hashes_unchanged':True,'name_records':514,'native_parameter_tables_preserved':True,
'player_name_initialization':r[0x73c7:0x73cf].hex(),'optimization_stat_bytes_preserved':changed_stats,'decoded_instructions':len(ins),'relocations':len(m['optimization_relocations']),
'new_messages':75,'existing_message_aliases':len(aliases),'text_roundtrips':len(m['extended_messages']),
'predicate_cases':0x34c*4,'loader_cases':0x34b,'glyph_offset_cases':35,'stream_reader_cases':6,'complete_glyph_tick_cases':full_draw_cases,'common_macro_cases':4*161,'menu_glyph_half_pairs':26,
'scope':'static/65816-model contracts; runtime acceptance is separate'}
(ROOT/'static-checks.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
