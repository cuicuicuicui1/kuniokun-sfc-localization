from pathlib import Path
import os,sys,json,subprocess,concurrent.futures,hashlib
ROOT=Path(__file__).resolve().parent;RUNNER=ROOT/'run_mesen_native.py';MESEN=Path(os.environ.get('MESEN_EXE','Mesen.exe'));ROM=ROOT/'new-build/native-rebuild-candidate.sfc';STATE=Path(os.environ.get('STATUS_STATE',str(ROOT/'qa/final-menu/final-menu.state'))).resolve();SCRIPT=ROOT/'mesen_native_status.lua';sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
cases=[('normal',0,0,False),('drunk',0,1,True),('paralysis',0,2,True),('riki-normal',1,0,True),('riki-drunk',1,1,True),('riki-paralysis',1,2,True)]
def run(c):
 name,player,cond,controlled=c;tag='native-status-'+name;out=ROOT/'qa/final-hud-status'/tag;out.mkdir(parents=True,exist_ok=True);env=dict(os.environ,PYTHONUTF8='1',UI_PLAYER=str(player) if controlled else '',UI_CONDITION=str(cond) if controlled else '')
 cmd=[sys.executable,str(RUNNER),'--rom',str(ROM),'--mesen',str(MESEN),'--script',str(SCRIPT),'--state',str(STATE),'--tag',tag,'--frames','750','--input','30-36:down;80-86:y;350-356:b;450-456:start','--shots','20,180,300,400,650,750','--out',str(out)]
 p=subprocess.run(cmd,capture_output=True,text=True,encoding='utf8',env=env,timeout=220);(out/'runner.log').write_text(p.stdout+p.stderr,encoding='utf8');assert p.returncode==0 and 'STATUS_RENDER_ENTRY' in p.stdout,(tag,p.stdout[-1500:]);print(tag,'pass',flush=True);return {'tag':tag,'player':player,'condition':cond,'controlled':controlled,'directory':str(out)}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,cases))
assert hashlib.sha256(ROM.read_bytes()).hexdigest()==sha
(ROOT/'qa/status-runtime-cases.json').write_text(json.dumps({'status':'pass','sha256':sha,'cases':results,'scope':'six state displays at original menu call; five one-time display-parameter overrides; not natural acquisition of drunk/paralysis'},ensure_ascii=False,indent=2),encoding='utf8')
