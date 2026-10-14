from pathlib import Path
import sys,os,json,subprocess,concurrent.futures,hashlib
ROOT=Path(__file__).resolve().parent;RUNNER=ROOT/'run_mesen_native.py';MESEN=Path(os.environ.get('MESEN_EXE','Mesen.exe'))
ROM=ROOT/'new-build/native-rebuild-candidate.sfc';wanted=hashlib.sha256(ROM.read_bytes()).hexdigest();state=Path(os.environ.get('MESSAGE_STATE',str(ROOT/'qa/final-hud-cold/message-ready.state'))).resolve();assert state.exists()
cases=json.loads((ROOT/'message-cases.json').read_text(encoding='utf8'));template=(ROOT/'mesen_native_message_batch.lua').read_text(encoding='utf8');begin=template.index('local cases={');end=template.index('assert(maxf',begin)
def one(i):
 chunk=cases[i*12:(i+1)*12];tag=f'native-messages-{i+1:02d}';out=ROOT/'qa/final-hud-message-batches'/tag;out.mkdir(parents=True,exist_ok=True);script=out/'cases.lua';literal='\n'.join('{id=0x%03X,speaker=0x%04X,capture=%s,d=%d,e=%d},'%(c['id'],c['speaker'],'true' if c['capture'] else 'false',c.get('d',0),c.get('e',0)) for c in chunk);script.write_text(template[:begin]+'local cases={\n'+literal+'\n}\n'+template[end:],encoding='utf8')
 cmd=[sys.executable,str(RUNNER),'--rom',str(ROM),'--tag',tag,'--mesen',str(MESEN),'--script',str(script),'--state',str(state),'--frames',str(len(chunk)*600),'--shots',str(len(chunk)*600),'--out',str(out)]
 p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf8',env=dict(os.environ,PYTHONUTF8='1'),timeout=230);(out/'runner.log').write_text(p.stdout+p.stderr,encoding='utf8');print(tag,'exit',p.returncode,flush=True);assert p.returncode==0,(tag,(p.stdout+p.stderr)[-1500:]);result=json.loads((out/'message-runtime-results.json').read_text(encoding='utf8'));assert result['status']=='pass' and len(result['cases'])==len(chunk);return result
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(one,range((len(cases)+11)//12)))
assert hashlib.sha256(ROM.read_bytes()).hexdigest()==wanted
(ROOT/'qa/message-runtime-checks.json').write_text(json.dumps({'status':'pass','sha256':wanted,'count':len(cases),'chunks':results,'scope':'same-candidate cold checkpoint, controlled native message/speaker/macro parameters; not natural encounters'},ensure_ascii=False,indent=2),encoding='utf8');print('PASS',len(cases),'cases')
