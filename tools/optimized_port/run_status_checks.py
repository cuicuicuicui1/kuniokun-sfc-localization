from runtime_paths import mesen_paths
from pathlib import Path
import os,sys,subprocess,json,concurrent.futures
ROOT=Path(__file__).resolve().parent;WORKSPACE=ROOT.parents[1]
RUNNER,MESEN=mesen_paths()
state=ROOT/'final-cold/menu-ready.state'
assert state.exists()
cases=[('v14-status',0,0,False),('v14-drunk',0,1,True),('v14-paralysis',0,2,True),('v14-riki',1,0,True),('v14-riki-drunk',1,1,True),('v14-riki-paralysis',1,2,True)]
def run_case(case):
 tag,player,condition,controlled=case
 env=dict(os.environ,PYTHONUTF8='1',UI_PLAYER=str(player) if controlled else '',UI_CONDITION=str(condition) if controlled else '')
 frames=750 if not controlled else 550
 input='30-36:down;80-86:y;350-356:b'+(';450-456:start' if not controlled else '')
 shots='20,180,300,400,500,650,750' if not controlled else '180,300,450,550'
 cmd=[sys.executable,str(RUNNER),'--rom',str(ROOT/'candidate-ui.sfc'),'--tag',tag,'--mesen',str(MESEN),'--script',str(ROOT/'mesen_status_fixture.lua'),'--state',str(state),'--frames',str(frames),'--input',input,'--shots',shots,'--out',str(ROOT/tag)]
 result=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding='utf-8',timeout=210)
 (ROOT/(tag+'-runner.log')).write_text(result.stdout,encoding='utf-8')
 print(tag,'exit',result.returncode,flush=True)
 assert result.returncode==0,(tag,result.stdout[-2000:])
 return {'tag':tag,'player':player,'condition':condition,'controlled_parameter_override':controlled,'exit':result.returncode}
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(run_case,cases))
(ROOT/'ui-emulator-exits.json').write_text(json.dumps({'status':'pass','cases':results},ensure_ascii=False,indent=2),encoding='utf-8')
