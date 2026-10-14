from pathlib import Path
import json,hashlib,zlib
ROOT=Path(__file__).resolve().parent;PORT=ROOT
r=(ROOT/'candidate-ui.sfc').read_bytes();m=json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))
assert hashlib.sha256(r).hexdigest()==m['candidate']['sha256']
cold=json.loads((ROOT/'final-cold/final-cold.json').read_text(encoding='utf-8'))
assert cold['rom_crc32']==m['candidate']['crc32'] and cold['state'] is None and cold['emulator_exit']==0
import re
menu_frame=int(re.search(r'MENU_READY (\d+)',(ROOT/'final-cold/final-cold.log').read_text(encoding='utf-8')).group(1))
checkpoint=ROOT/'final-cold/menu-ready.state'
provenance={'rom_crc32':cold['rom_crc32'],'rom_sha256':m['candidate']['sha256'],'source':'final-cold natural pad-only cold boot','frame':menu_frame,'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
checkpoint.with_suffix('.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
cases=json.loads((ROOT/'ui-emulator-exits.json').read_text(encoding='utf-8'))['cases']
tiles=m['layout']['chosen_base_tiles'];sources=m['glyph_sources'];checks=[]
for case in cases:
 tag=case['tag'];player=case['player'];condition=case['condition']
 meta=json.loads((ROOT/tag/(tag+'.json')).read_text(encoding='utf-8'))
 assert meta['rom_crc32']==cold['rom_crc32'] and meta['emulator_exit']==0
 assert Path(meta['state']).resolve()==checkpoint.resolve()
 log=(ROOT/tag/(tag+'.log')).read_text(encoding='utf-8')
 assert 'ppu.forcedBlank=true' in log and 'ppu.screenBrightness=0' in log
 ram=(ROOT/tag/(tag+'-300.ram')).read_bytes();v=(ROOT/tag/(tag+'-300.vram')).read_bytes()
 assert ram[0x1ba6]==player and ram[0x1eb+player]==condition
 def cell(a):return int.from_bytes(v[a*2:a*2+2],'little')
 # Native code 00 uses the same single 2bpp 8x8 tile for both rows: 16 bytes.
 assert v[0xc000:0xc010]==bytes(16), 'native blank tile has nonzero pixels'
 for addr in (0x7889,0x788c,0x788d):
  assert cell(addr)==cell(addr+32)==0x2400, (tag,'leftover name placeholder',hex(addr))
 chars=('国夫' if player==0 else '力 ')+['普通','醉酒','麻痹'][condition]
 for ix,ch in enumerate(chars):
  t=tiles[ix];off=sources[ch];dest=(0x6000+t*8)*2
  assert v[dest:dest+32]==r[off:off+32],(tag,'wrong bitmap',ch)
  addr=[0x788a,0x788b,0x789b,0x789c][ix]
  assert cell(addr)==0x2400+t and cell(addr+32)==0x2400+t+1,(tag,'wrong two-row map',ch)
 for addr in (0x789d,0x789e):
  assert (cell(addr)&0x3ff)==(cell(addr+32)&0x3ff)==0,(tag,'condition trailing residue')
 assert ('observation only; no RAM writes' in log)==(not case['controlled_parameter_override'])
 checks.append({**case,'whole_name_field_and_blank_pixels':'pass','all_condition_glyphs_and_trailing_space':'pass'})
# Actual original six-item menu survives entry/return. Derive every bitmap from
# its ROM descriptor, including the toggle state and the extended donor glyph.
port=json.loads((PORT/'port-manifest.json').read_text(encoding='utf-8'))
menu_checks=[]
for capture in (ROOT/'final-cold/final-cold-menu',ROOT/'v14-status/v14-status-650'):
 ram=capture.with_suffix('.ram').read_bytes();v=capture.with_suffix('.vram').read_bytes();used=set()
 for ix,ch in enumerate('气力道具装备状态扔掉互伤开'):
  rec=r[0x1f4700+ix*7:0x1f4700+(ix+1)*7]
  t,u=int.from_bytes(rec[:2],'little'),int.from_bytes(rec[2:4],'little')
  source=rec[6]*0x8000+int.from_bytes(rec[4:6],'little')%0x8000
  if ix==12 and ram[0x70]&0x80:
   ch='关';page,slot=port['extended_glyphs']['cells'][ch];source=(0x24+page)*0x8000+0x2000+slot*64
  assert v[t*2:t*2+32]+v[u*2:u*2+32]==r[source:source+64],(str(capture),ch,'menu bitmap changed')
  for tile in (t,u):
   pair={tile*2,tile*2+16};assert not pair&used;used.update(pair)
 menu_checks.append({'capture':str(capture),'status':'pass','glyphs':13})
snes=json.loads((ROOT/'snes-status/report.json').read_text(encoding='utf-8'))
assert snes['rom_crc32']==cold['rom_crc32']
result={'status':'pass','candidate':m['candidate'],'character_table_guard':json.loads((ROOT/'character-table-regression.json').read_text(encoding='utf-8'))['status'],'mesen_cases':checks,'whole_name_field_checked':True,'menu_before_and_after_status':menu_checks,'snes9x':f'independent cold boot normal pad input, {snes["frames"]} frames; visual review recorded separately','natural_scope':'cold boot/opening/menu/status entry-return/menu reopening','controlled_scope':'two players x three displayed conditions; normal Kunio uses original state, other five use one-time display parameters','unverified':['hardware','old saves','natural acquisition of drunk/paralysis','full game completion','values outside the native three-entry display table']}
(ROOT/'ui-runtime-checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
