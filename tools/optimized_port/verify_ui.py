from pathlib import Path
import sys,os,json,hashlib,zlib
from runtime_paths import source_tree
ROOT=Path(__file__).resolve().parent;SRC=source_tree();os.chdir(SRC);sys.path.insert(0,str(SRC))
import sim65816 as S
r=(ROOT/'candidate-ui.sfc').read_bytes();m=json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'));base=Path(m['input']['path']).read_bytes()
assert hashlib.sha256(base).hexdigest()==m['input']['sha256'] and hashlib.sha256(r).hexdigest()==m['candidate']['sha256']
assert len(r)==len(base)==0x200000 and (sum(r)&65535)==int.from_bytes(r[0x7fde:0x7fe0],'little')
allowed=set(range(0x7fdc,0x7fe0))
for change in m['changes']:
 a,n=change['offset'],change['length'];assert base[a:a+n].hex()==change['before'] and r[a:a+n].hex()==change['after'];allowed.update(range(a,a+n))
assert all(a==b or i in allowed for i,(a,b) in enumerate(zip(base,r))),'unclassified ROM change'
assert r[0x73c7:0x73cf]==base[0x73c7:0x73cf] and r[0x4802a:0x4a32a]==base[0x4802a:0x4a32a],'global names/parameters changed'
for page in range(30):
 off=(0x20+page)*0x8000;assert r[off:off+33*64]==base[off:off+33*64],'inherited body glyph changed'
for i in range(514):
 rec=r[0x4802a+i*16:0x4802e+i*16]
 for prefix,ident in zip(rec[::2],rec[1::2]):
  if prefix>=0xc0:
   off=(0x20+prefix-0xc0)*0x8000+ident*64
   assert r[off:off+64]==base[off:off+64],('inherited HUD bitmap changed',i)
tiles=m['layout']['chosen_base_tiles'];sources=m['glyph_sources'];cases=[]
assert r[0xf9ea:0xf9f2] == bytes.fromhex('89 78 85 00 00 00 00 00')
assert r[0x1fa9e] == r[0x1fb9e] == 0
# Execute the actual native script consumer with stale tiles in both rows,
# then the fixed-field hook. This checks the full name field, not only its glyphs.
def name_clear(c):
 c.pbr=c.db=1;c.pc=0xf97a;c.y=15;c.vmain=0x81
 for addr in range(0x7889,0x788e):
  c.vram[addr]=0x243b;c.vram[addr+32]=0x243d
 for step in range(500):
  c.step()
  if (c.pbr,c.pc,c.y)==(1,0xf97a,23):break
 else:raise AssertionError(('native name script did not continue',c.pbr,c.pc,c.y))
 for addr in range(0x7889,0x788e):
  assert c.vram[addr]==c.vram[addr+32]==0x2400, ('stale native name marker',hex(addr))
 c.pc=0xfbbb

for player in (0,1):
 for condition in range(4):
  c=S.CPU(r);c.pbr=c.db=1;c.pc=0xfbbb;c.s=0x1ff;c.m8=c.x8=True
  c.bus.wram[0x1ba6]=player;c.bus.wram[0x1eb+player]=condition;c.bus.wram[0x1b46:0x1b4e]=bytes.fromhex('c0a6c0f5c29a0000');before=bytes(c.bus.wram[0x1b46:0x1b4e]);name_clear(c)
  for steps in range(1500):
   c.step()
   if (c.pbr,c.pc) in [(1,0xfc21),(1,0xfbe3)]:break
  else:raise AssertionError(('status consumer did not continue',player,condition,c.pbr,c.pc))
  assert c.s==0x1ff and c.db==1 and c.m8 and c.x8 and c.vmain==0x80,'status caller/PPU increment contract'
  assert bytes(c.bus.wram[0x1b46:0x1b4e])==before,'runtime names modified'
  chars=('国夫' if player==0 else '力 ')+({0:'普通',1:'醉酒',2:'麻痹'}.get(condition,''))
  for ix,ch in enumerate(chars):
   dest=0x6000+tiles[ix]*8
   actual=b''.join(x.to_bytes(2,'little') for x in c.vram[dest:dest+16]);off=sources[ch]
   assert actual==r[off:off+32],('wrong status bitmap',player,condition,ch)
   cell=[0x788a,0x788b,0x789b,0x789c][ix]
   assert c.vram[cell]==0x2400+tiles[ix] and c.vram[cell+32]==0x2400+tiles[ix]+1,'wrong two-row map'
  for addr in (0x7889,0x788c,0x788d):
   assert c.vram[addr]==c.vram[addr+32]==0x2400, ('name border not blank',player,condition,hex(addr))
  if condition<3:assert (c.pbr,c.pc)==(1,0xfc21) and len(c.dma_log)==4
  else:assert (c.pbr,c.pc)==(1,0xfbe3) and len(c.dma_log)==2
  assert all(x[0]==2 and x[-1]==32 for x in c.dma_log),'unexpected DMA size/channel'
  cases.append({'player':player,'condition':condition,'status':'pass','fallback':condition==3})
result={'status':'pass','candidate':m['candidate'],'changed_bytes':sum(a!=b for a,b in zip(base,r)),'status_cases':cases,'status_pair_slots':m['layout']['chosen_pair_indices'],'full_native_name_field_clear':True,'global_names_unchanged':True,'original_item_continuation':True,'unknown_condition_original_fallback':True}
(ROOT/'ui-static-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))