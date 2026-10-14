from runtime_paths import source_tree
"""Continuous old/extended text must clear via the original F0 interpreter."""
from pathlib import Path
import json,sys,os
ROOT=Path(__file__).resolve().parent;SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
from dialogue_model import make_cpu,tick,flush
rom=(ROOT/'candidate-ui.sfc').read_bytes()
def call(c,pc):
 c.pbr=c.db=3;c.pc=pc;c.s=0x1ff;c.m8=c.x8=True;c.push8(0xdf);c.push8(0xff)
 for i in range(30000):
  if (c.pbr,c.pc)==(3,0xe000):assert c.s==0x1ff;return
  c.step()
 raise AssertionError(('native loader timeout',hex(pc)))
def load(rom,mid,previous):
 c=make_cpu(rom);w=c.bus.wram;w[0x373]=0;w[0x34a:0x34c]=mid.to_bytes(2,'little');w[0x34c:0x34e]=(0x11f).to_bytes(2,'little');w[0x3e6]=previous;w[0x3e5]=0xa5;w[0x3e7]=0x5a
 call(c,0xeb68);assert w[0x3e5]==0xa5 and w[0x3e7]==0x5a,'namespace helper clobbered neighbor'
 call(c,0xeb9e);assert w[0x3e5]==0xa5,'stream helper clobbered neighbor'
 return c,bytes(w[0x3ea:0x3ea+w[0x3e8]])
checks=[]
for mid in [0x032,0x1df,0x308,0x31c,0x31d,0x186,0x187,0x348]:
 for previous in (0,1):
  c,buf=load(rom,mid,previous)
  if mid==0x348:
   assert not buf and c.bus.wram[0x3e6]==previous,'leading F3 boundary was changed'
  elif mid in [0x308,0x31c,0x186,0x187] or previous==1:
   assert buf[0]==0xf0,(hex(mid),previous,'missing lifetime clear',buf.hex())
  checks.append({'id':f'{mid:03X}','previous_namespace':previous,'buffer_prefix':buf[:12].hex(),'namespace':c.bus.wram[0x3e6]})
# A new action message appended to a legacy window was the shipping failure.
negative_path=ROOT.parent/'port-full-v14b-20261012/candidate-ui.sfc'
negative_checked=negative_path.exists()
if negative_checked:
 bad=negative_path.read_bytes();_,oldbuf=load(bad,0x31c,0)
 assert oldbuf and oldbuf[0]!=0xf0,'negative candidate unexpectedly has fix'
# The serialized F0 is the native clear command; the first real tick must take
# that command before any new font upload, resetting row/column and consuming it.
c,buf=load(rom,0x31c,0);w=c.bus.wram;w[0x373]=0xc0;w[0x36e]=4;w[0x36f]=7;w[0x9e0:0x9e2]=bytes.fromhex('f8 ff')
tick(c)
assert w[0x3e9]==1,'new glyph was consumed before clear';assert w[0x374]&0x80 and w[0x390]==8,'native F0 clear was not scheduled'
flush(c)
# Preserve F2F7 continuations inside the same letter: the message gateway is
# not reentered, so the second decoded slice has no synthetic F0.
c,first=load(rom,0x186,0);assert first[0]==0xf0
w=c.bus.wram;assert w[0x3e6]==1
# The decoder already consumed F2; advance over its F7 argument only.
assert first[-1]==0xf2
w[0x36a]=(w[0x36a]+1)&255
if w[0x36a]<1:w[0x36b]=(w[0x36b]+1)&255
call(c,0xeb9e);continuation=bytes(w[0x3ea:0x3ea+w[0x3e8]])
assert continuation and continuation[0]!=0xf0,'letter continuation unnecessarily cleared'
result={'status':'pass','candidate':json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate'],'namespace_wram':'03E6','cases':checks,'prior_candidate_without_clear_rejected':negative_checked,'native_F0_before_font_upload':True,'F2F7_continuation_retained':True,'scope':'native loader/page buffer/tick model; runtime VRAM and field ownership checked separately'}
(ROOT/'font-lifetime-model-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS continuous font lifetime, native F0, F2F7 continuation; optional historical negative='+str(negative_checked))
