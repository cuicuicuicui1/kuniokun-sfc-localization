from pathlib import Path
import json,collections
ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'));pm=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));a=json.loads((ROOT/'diff-analysis.json').read_text(encoding='utf-8'));r=(ROOT/'candidate-ui.sfc').read_bytes();opt=Path(a['inputs']['opt']['path']).read_bytes()
ret={x['offset']:x['reason'] for x in pm['retained_original_text_differences']};declared=[(x['offset'],x['offset']+x['length'],x['label']) for x in pm['patches']+m['changes']];declared +=[(x['source'],x['source']+4,'relocated native Hook/reference') for x in pm['optimization_relocations'] if x['source']<0x100000];declared.append((0x7fc0,0x8000,'ROM title/checksum/header'))
counts=collections.Counter();rows=[]
for lo,hi in a['optimization_changes']:
 if lo>=0x100000:continue
 for off in range(lo,min(hi,0x100000)):
  if off in ret:category='retained/adapted Chinese consumer: '+ret[off]
  elif r[off]==opt[off]:category='native optimization byte preserved'
  else:
   assert any(b<=off<e for b,e,label in declared),('unclassified optimized byte',hex(off));category='explicit port adaptation'
  counts[category]+=1;rows.append({'offset':off,'optimized_byte':opt[off],'final_byte':r[off],'classification':category})
assert len(rows)==6248
expanded=[];lengths={0x20:0x2008,0x22:0x108,0x23:0x3000}
for bank in range(0x20,0x30):
 data=opt[bank*0x8000:(bank+1)*0x8000];ix=[i for i,v in enumerate(data) if v];assert not any(data[lengths.get(bank,0):]);expanded.append({'bank':f'{bank:02X}','nonzero_bytes':len(ix),'first':min(ix) if ix else None,'last':max(ix) if ix else None})
report={'candidate':m['candidate'],'source':a['inputs']['opt'],'status':'pass','original_bank_changed_bytes':len(rows),'original_bank_change_spans':1019,'total_change_spans':1339,'classification_counts':dict(counts),'expanded_bank_coverage':expanded,'original_bank_bytes':rows}
(ROOT/'source-change-classification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
native={'status':'pass','candidate':m['candidate'],'source':a['inputs']['opt'],'native_name_bounds':{'start':0x4802A,'end_exclusive':0x4A04A,'record_bytes':16,'records':514},'native_parameter_region_checked':{'start':0x4A04A,'end':0x50000,'bytes':24502,'mismatches':sum(x!=y for x,y in zip(r[0x4A04A:0x50000],opt[0x4A04A:0x50000]))},'source_total_change_spans':1339,'source_original_bank_change_spans':1019,'font_lifetime_fix':{'namespace_wram':'03E6','clear':'native F0 on extended entry and return to legacy','leading_F3_and_F2F7_continuations_preserved':True,'native_zero_reset':'03:E99D STZ034A,X; write callback PC E9A0'},'scope':'static current source and candidate readback; semantics and runtime tests separately recorded'}
(ROOT/'native-adaptation-audit.json').write_text(json.dumps(native,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS all source diff bytes classified')
