from runtime_paths import mesen_paths
from pathlib import Path
import json,sys,os,subprocess,concurrent.futures,hashlib
ROOT=Path(__file__).resolve().parent;WORKSPACE=ROOT.parents[1]
RUNNER,MESEN=mesen_paths()
allcases=json.loads((ROOT/'message-cases.json').read_text(encoding='utf-8'))
template=(ROOT/'mesen_message_batch_v2.lua').read_text(encoding='utf-8');a=template.index('local cases={');b=template.index('assert(maxf',a)
# Bound each process independently. Retain earlier unsuccessful diagnostics.
def run(chunk_index):
 cases=allcases[chunk_index*12:(chunk_index+1)*12];tag=f'messages-{chunk_index+1:02d}';out=ROOT/'final-message-chunks'/tag;out.mkdir(parents=True,exist_ok=True)
 literal='\n'.join('{id=0x%03X,speaker=0x%04X,capture=%s,d=%d,e=%d},'%(c['id'],c['speaker'],'true' if c['capture'] else 'false',c.get('d',0),c.get('e',0)) for c in cases)
 script=out/'message-cases.lua';script.write_text(template[:a]+'local cases={\n'+literal+'\n}\n'+template[b:],encoding='utf-8')
 cmd=[sys.executable,str(RUNNER),'--rom',str(ROOT/'candidate-ui.sfc'),'--tag',tag,'--mesen',str(MESEN),'--script',str(script),'--state',str(ROOT/'final-cold/message-ready.state'),'--frames',str(len(cases)*600),'--shots',str(len(cases)*600),'--out',str(out)]
 proc=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8',env=dict(os.environ,PYTHONUTF8='1'),timeout=210)
 (out/'runner.log').write_text(proc.stdout+proc.stderr,encoding='utf-8');print(tag,'exit',proc.returncode,flush=True)
 assert proc.returncode==0,(tag,(proc.stdout+proc.stderr)[-2000:])
 result=json.loads((out/'message-runtime-results.json').read_text(encoding='utf-8'));manifest=json.loads((out/(tag+'.json')).read_text(encoding='utf-8'))
 candidate=json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate']
 assert result['status']=='pass' and len(result['cases'])==len(cases)
 assert manifest['rom_crc32']==candidate['crc32'] and manifest['emulator_exit']==0
 for expected,actual in zip(cases,result['cases']):assert int(actual['id'],16)==expected['id'] and actual['speaker']==expected['speaker'] and actual['status']=='pass'
 return {'chunk':tag,'frames':len(cases)*600,'cases':result['cases'],'manifest':manifest}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(run,range((len(allcases)+11)//12)))
assert sum(len(r['cases']) for r in results)==len(allcases)
final={'status':'pass','candidate':json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate'],'total_cases':len(allcases),'unique_difference_messages':107,'additional_dynamic_name_cases':20,'additional_macro_cases':21,'frames':sum(r['frames'] for r in results),'checkpoint':str(ROOT/'final-cold/message-ready.state'),'checkpoint_sha256':hashlib.sha256((ROOT/'final-cold/message-ready.state').read_bytes()).hexdigest(),'scope':'Controlled message and speaker parameters through native loader/renderer. Each original call must be observed after restore, draw glyphs, and finish within 600 frames. Not natural encounters or hardware.','chunks':results}
(ROOT/'message-runtime-checks.json').write_text(json.dumps(final,ensure_ascii=False,indent=2),encoding='utf-8');print('PASS '+str(len(allcases))+' native message display cases',flush=True)
