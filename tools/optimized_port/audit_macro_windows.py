from runtime_paths import source_tree
from pathlib import Path
import re,json,sys,os,itertools
ROOT=Path(__file__).resolve().parent;SRC=source_tree();sys.path.insert(0,str(SRC));os.chdir(SRC)
import cnbuild5 as cb
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'));cells=m['extended_glyphs']['cells'];common=m['dynamic_common_words'];bad=[];checked=0
for key,rec in m['extended_messages'].items():
 for segment in rec['text'].split('{F2F4}'):
  rows=re.split(r'\{F2(?:F6|F7|E2)\}',segment)
  for n in range(len(rows)):
   text=''.join(rows[n:n+3]);mac=[x for x in ('{ED}','{EE}') if x in text]
   for words in itertools.product(common.values(),repeat=len(mac)):
    full=text
    for macro,word in zip(mac,words):full=full.replace(macro,word)
    visible=cb.glyphs_of(full);slots={};checked+=1
    for ch in sorted(visible):
     if ch not in cells:continue
     slot=cells[ch][1]
     if slot in slots and slots[slot]!=ch:bad.append({'id':key,'rows':n,'words':words,'pair':[slots[slot],ch],'slot':slot,'text':full})
     slots[slot]=ch
assert not bad,('co-visible macro font collisions',bad[:2])
r={'status':'pass','candidate_sha256':__import__('hashlib').sha256((ROOT/'candidate-ui.sfc').read_bytes()).hexdigest(),'supported_common_terms':len(common),'windows':checked,'conflicts':bad};(ROOT/'macro-window-audit.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');print('WINDOWS',checked,'CONFLICTS',len(bad));print(json.dumps(bad[:8],ensure_ascii=False,indent=2))
