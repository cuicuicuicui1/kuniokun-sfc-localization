"""Independent BG3 screenshot/VRAM mask check, not a full SNES PPU model."""
from pathlib import Path
from PIL import Image
import json,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--samples',type=Path,required=True,help='PNG/RAM/VRAM captures from one Mesen run')
parser.add_argument('--aligned',action='store_true',help='require complete16-pixel glyph-row boundaries')
parser.add_argument('--report',type=Path,help='optional JSON output; never overwrite an input capture')
args=parser.parse_args()
results=[]
for folder in [args.samples.resolve()]:
 for image in sorted(folder.glob('*.png')):
  raw=image.with_suffix('.ram').read_bytes();v=image.with_suffix('.vram').read_bytes()
  im=Image.open(image).convert('RGB')
  assert im.size==(256,224) and len(raw)>=0x3C3 and len(v)==0x10000,'unsupported/truncated capture'
  h=raw[0x3BF]+256*raw[0x3C0];vs=raw[0x3C1]+256*raw[0x3C2]
  def mask(x,y,bias=0):
   xx=(x+h)&255;yy=(y+vs+1+bias)&255
   at=0xF800+(yy//8*32+xx//8)*2
   cell=v[at]+256*v[at+1];tile=cell&0x3FF
   py=yy&7;px=xx&7
   if cell&0x8000:py=7-py
   if cell&0x4000:px=7-px
   addr=0xC000+tile*16+py*2
   # Existing palette1: indices1/3 are the light foreground; index2 is black.
   return bool(v[addr]&(0x80>>px))
  errors=[];wrong=[];lit=0
  for y in range(184,216):
   for x in range(24,232):
    actual=min(im.getpixel((x,y)))>120
    lit+=actual
    if mask(x,y)!=actual:errors.append((x,y))
    if mask(x,y,1)!=actual:wrong.append((x,y))
  assert not errors,(image.name,len(errors),errors[:10],hex(h),hex(vs))
  results.append({'image':image.name,'folder':str(folder),'pixels_checked':208*32,'lit_pixels':lit,'mismatches':len(errors),'wrong_plus_one_offset_mismatches':len(wrong),'physical_first_row':(184+vs+1)&255,'physical_last_row':(215+vs+1)&255})
assert results and any(x['wrong_plus_one_offset_mismatches']>0 for x in results),'empty pixel check'
for x in results:
 if args.aligned:
  assert x['physical_first_row']%16==0 and x['physical_last_row']%16==15
out={'status':'pass','scope':'game-specific BG3 light-foreground mask vs actual VRAM, 32 visible scanlines; not a full PPU emulator','samples':results}
if args.report:
 assert args.report.resolve().suffix.lower()=='.json','report must be JSON, not a capture'
 assert not args.report.exists(),'report already exists; use a fresh output path'
 args.report.write_text(json.dumps(out,indent=2),encoding='utf-8')
print('PASS',len(results),'screenshots',sum(x['pixels_checked'] for x in results),'pixel comparisons; distinct wrong-offset negative')
