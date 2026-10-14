from pathlib import Path
import os,sys,json,re,math
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'source';os.chdir(SRC);sys.path.insert(0,str(SRC))
import cnbuild5 as cb
candidates=json.loads((ROOT/'inventory-worker/candidate-translations.json').read_text(encoding='utf-8'))['candidates'];native=json.loads((ROOT/'inventory-worker/native-inventory.json').read_text(encoding='utf-8'));original=json.loads((SRC/'kuniokun_text.json').read_text(encoding='utf-8'));rows={(r['table_rom_off'],r['index']):r for r in original};bycandidate={(c['identity']['table_rom_off'],c['identity']['index']):c for c in candidates if c['identity'].get('table_rom_off')!=0x110070};tr={};records=[];main={}
for table in native['tables']:
 for rec in table['records']:
  old=rows[(rec['table_rom_off'],rec['index'])];key=f"{old['text_rom_off']:06X}";c=bycandidate[(rec['table_rom_off'],rec['index'])];text=c['candidate_cn']
  if text is None:
   assert rec['table_rom_off']==0x1e4ce and rec['index']==78
   text='国夫!{F7} 力{F2F3}'
  if rec.get('id')=='0x1F6':text=text.replace('{F2F4}可{ED}','{F2F6}可{ED}')
  text=cb.align_tokens(rec['text'],text)
  if rec.get('id') in ('0x186','0x187','0x189','0x18A','0x274'):
   # Entry ends in F2/F2F7 and falls through into the NEXT native message.
   # Previous merged review strings appended the following entry's prose.
   last=list(cb.TOKEN.finditer(text))[-1];text=text[:last.end()]
  tr[key]=text;copy=old.copy();copy['text']=rec['text'];records.append(copy)
  if rec['table_rom_off']==0x193b5:main[int(rec['id'],16)]={'text':text,'source':rec['text'],'key':key}
new=json.loads((ROOT/'optimization-cn-text.json').read_text(encoding='utf-8'))
for rec in native['extended_table']['records']:
 if rec['null_slot']:continue
 mid=int(rec['id'],16);main[mid]={'text':cb.align_tokens(rec['text'],new[f'{mid:03X}']),'source':rec['text'],'key':rec['id']}
(SRC/'cn_translation.json').write_text(json.dumps(tr,ensure_ascii=False,indent=2),encoding='utf-8');(SRC/'kuniokun_text.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8');(ROOT/'native-dialogues.json').write_text(json.dumps(main,ensure_ascii=False,indent=2),encoding='utf-8')
# Reuse encoding/format knowledge, not its static colour/lifetime assumptions.
class NativeEncoder(cb.Encoder):
 def colour(self,windows):
  chars=sorted(set().union(*windows));fixed=list(sorted(cb.FIXED_CODES,key=lambda x:cb.FIXED_CODES[x]));self.order=fixed+[x for x in chars if x not in fixed];self.slot={ch:i for i,ch in enumerate(self.order)};self.load=[math.ceil(len(self.order)/128)]*cb.SLOTS
 def pack_pool(self):self.cell={ch:(i//128,i%128) for i,ch in enumerate(self.order)}
 def encode(self,s):
  out=bytearray()
  for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})',s):
   if not part:continue
   if cb.TOKEN.fullmatch(part):out.extend(bytes.fromhex(part[1:-1]));continue
   for ch in cb.units(part):
    if ch==' ':out.append(0)
    elif ch in cb.KEEP1:out.append(cb.KEEP1[ch])
    elif ch in cb.FIXED_CODES:out.append(cb.FIXED_CODES[ch])
    else:
     page,gid=self.cell[ch];out.extend([0xc0+page,gid])
  return bytes(out)
 def encode_item(self,s):return super().encode_item(s)
cb.Encoder=NativeEncoder
cb.MENU_LABELS=[(0,1,'气力'),(0,11,'道具'),(0,21,'装备'),(1,1,'状态'),(1,11,'互伤'),(1,21,'扔掉')]

allchars=set()
for text in list(tr.values())+[r['text'] for r in main.values()]:allchars.update(cb.glyphs_of(text))
for row,col,text in cb.MENU_LABELS:allchars.update(cb.glyphs_of(text))
allchars.update('互伤开关')
def choose(per_table,main_row_windows=None):
 enc=NativeEncoder();enc.colour([allchars]);return enc,[allchars],0,0
cb.choose_windows=choose
# Menu uploader resolves ROM glyph cells independently of the pool's VRAM slot.
cb.main()
