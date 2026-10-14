"""Validate actual Mesen STATUS VRAM dumps against ROM glyph resources."""
from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent;rom=(ROOT/'new-build/native-rebuild-candidate.sfc').read_bytes();sha=hashlib.sha256(rom).hexdigest();m=json.loads((ROOT/'new-build/ui-layout.json').read_text(encoding='utf8'));run=json.loads((ROOT/'qa/status-runtime-cases.json').read_text(encoding='utf8'));assert run['sha256']==sha;checks=[]
for case in run['cases']:
 out=Path(case['directory']);tag=case['tag'];ram=(out/(tag+'-180.ram')).read_bytes();v=(out/(tag+'-180.vram')).read_bytes();assert ram[0x1ba6]==case['player'] and ram[0x1eb+case['player']]==case['condition'];chars=('国夫' if not case['player'] else '力 ')+['普通','醉酒','麻痹'][case['condition']]
 def word(a):return int.from_bytes(v[a*2:a*2+2],'little')
 for i,ch in enumerate(chars):
  tile=m['tiles'][i];addr=[0x788a,0x788b,0x789b,0x789c][i]
  assert word(addr)==0x2400+tile and word(addr+32)==0x2401+tile,(tag,ch,hex(addr),hex(word(addr)))
  src=m['glyph_addresses'][ch];assert v[0xc000+tile*16:0xc000+tile*16+32]==rom[src:src+32],(tag,ch,'wrong bitmap')
 for a in [0x7889,0x788c,0x788d,0x789d]:assert word(a)&1023==0 and word(a+32)&1023==0,(tag,'name/condition residue',hex(a))
 checks.append({'tag':tag,'name':chars[:2],'condition':chars[2:],'all_glyphs_and_blank_field':'pass'})
(ROOT/'qa/status-vram-checks.json').write_text(json.dumps({'status':'pass','sha256':sha,'cases':checks},ensure_ascii=False,indent=2),encoding='utf8');print('PASS',len(checks),'native STATUS VRAM cases')
