from pathlib import Path
import json,subprocess,sys,re
import argparse
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description='Replay cold/game route in bounded same-ROM checkpoint segments with border tracing.')
p.add_argument('--out',type=Path,default=root/'hw/border-regression');p.add_argument('--mesen',default=r'F:\emulators\mesen2\Mesen.exe');a=p.parse_args()
out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);state=None;segments=[]
for route,prefix in [('hp-cold','rc3-cold'),('hp-game','rc3-play')]:
 data=json.loads((root/f'hw/regression_routes/{route}.json').read_text(encoding='utf-8'))
 for seg,start in enumerate(range(0,data['frames'],5000)):
  end=min(start+5000,data['frames']);tag=f'{prefix}-{seg+1}';events=[]
  for lo,hi,keys in re.findall(r'(\d+)-(\d+):([\w,+]+)',data['input']):
   lo,hi=max(int(lo),start),min(int(hi),end)
   if lo<hi:events.append(f'{lo-start}-{hi-start}:{keys}')
  shots=[f-start for f in data['shots'] if start<f<=end]
  cmd=[sys.executable,str(root/'tools/run_mesen_play.py'),'--mesen',a.mesen,'--rom',str(root/'kuniokun_cn.smc'),'--script',str(root/'hw/mesen_dialogue_border.lua'),'--tag',tag,'--frames',str(end-start),'--input',';'.join(events),'--shots',','.join(map(str,shots+[end-start])),'--out',str(out)]
  cmd+=['--state',str(state)] if state else ['--sram',str(root/'hw/seed-v38.srm')]
  subprocess.run(cmd,check=True);state=out/(tag+'.state')
  segments.append({'route':route,'tag':tag,'route_start':start,'route_end':end,'frames':end-start,'checkpoint':str(state)})
  (out/'game-segments.json').write_text(json.dumps(segments,indent=2),encoding='utf-8')
print('ALL GAMEPLAY SEGMENTS COMPLETED')
