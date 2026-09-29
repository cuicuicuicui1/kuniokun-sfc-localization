"""Replay a recorded headless pad route. SRAM/state inputs are read-only.

Routes capture this project's tested scenario, not a general game-playing AI.
Cold route requires the same SRAM hash; the gameplay route resumes the newly
produced cold checkpoint. Do not load pre-patch states after glyph repacking.
"""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('route',type=Path);p.add_argument('--tag',required=True)
p.add_argument('--sram',type=Path);p.add_argument('--state',type=Path)
p.add_argument('--rom',type=Path,default=ROOT/'kuniokun_cn.smc')
p.add_argument('--mesen',default=r'F:\emulators\mesen2\Mesen.exe')
a=p.parse_args();route=json.loads(a.route.read_text(encoding='utf-8'))
if route.get('required_sram_sha256'):
 assert a.sram and hashlib.sha256(a.sram.read_bytes()).hexdigest()==route['required_sram_sha256'],'this captured route requires its recorded SRAM baseline'
if route.get('requires_state'):assert a.state,'supply the checkpoint from the cold route on this ROM'
cmd=[sys.executable,str(ROOT/'tools/run_mesen_play.py'),'--tag',a.tag,'--rom',str(a.rom),'--mesen',a.mesen,'--frames',str(route['frames']),'--input',route['input'],'--shots',','.join(map(str,route['shots'])),'--trace']
for key in ('sram','state'):
 if getattr(a,key):cmd+=['--'+key,str(getattr(a,key))]
raise SystemExit(subprocess.call(cmd))
