"""Bounded Mesen controller/screenshot/checkpoint runner. Never edits player saves.

Example: python tools/run_mesen_play.py --tag step2 --state hw/play/step1.state
         --input "10-14:start;90-94:a" --frames 300 --shots 30,120,300
ROM copies and states stay under hw/play (not for redistribution).
"""
from pathlib import Path
import argparse,os,subprocess,shutil,hashlib,json,zlib
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--rom',type=Path,default=ROOT/'kuniokun_cn.smc');p.add_argument('--tag',required=True)
 p.add_argument('--mesen',default=r'F:\emulators\mesen2\Mesen.exe')
 p.add_argument('--script',type=Path,default=ROOT/'hw/mesen_play.lua')
 p.add_argument('--state',type=Path);p.add_argument('--sram',type=Path)
 p.add_argument('--frames',type=int,default=300);p.add_argument('--input',default='')
 p.add_argument('--shots',default='30');p.add_argument('--trace',action='store_true')
 p.add_argument('--out',type=Path,default=ROOT/'hw/play');a=p.parse_args()
 assert a.tag and all(c.isalnum() or c in '-_' for c in a.tag)
 out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 if a.state and a.state.with_suffix('.json').exists():
  saved=json.loads(a.state.with_suffix('.json').read_text(encoding='utf-8'))
  assert saved['rom_crc32']==f'{zlib.crc32(a.rom.read_bytes()):08X}', 'state belongs to a different ROM; use a cold boot'
 watched=[a.rom.resolve()]+[x.resolve() for x in (a.state,a.sram) if x]
 before={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in watched}
 dest=out/(a.tag+'.smc');assert dest not in watched;shutil.copy2(a.rom,dest)
 env=dict(os.environ,PLAY_OUT=out.as_posix(),PLAY_TAG=a.tag,PLAY_FRAMES=str(a.frames),PLAY_INPUT=a.input,PLAY_SHOTS=a.shots,PLAY_TRACE='1' if a.trace else '',PLAY_STATE=a.state.resolve().as_posix() if a.state else '',PLAY_SRAM=a.sram.resolve().as_posix() if a.sram else '')
 r=subprocess.run([a.mesen,'--testRunner',str(a.script.resolve()),str(dest),'--doNotSaveSettings'],cwd=ROOT,env=env,timeout=max(180,a.frames//12),creationflags=0x08000000 if os.name=='nt' else 0)
 for x in watched:assert hashlib.sha256(x.read_bytes()).hexdigest()==before[str(x)],'source file modified'
 log=(out/(a.tag+'.log')).read_text(encoding='utf-8')
 assert r.returncode==0 and f'SAVED frames={a.frames}' in log,(r.returncode,log[-1000:])
 manifest={'script':str(a.script.resolve()),'rom_crc32':f'{zlib.crc32(a.rom.read_bytes()):08X}','frames':a.frames,'input':a.input,'state':str(a.state) if a.state else None,'sources_unchanged':before,'emulator_exit':r.returncode,'checkpoint':str(out/(a.tag+'.state')),'scope':'interactive trace, not automatic gameplay acceptance'}
 (out/(a.tag+'.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 print(log[-2200:],flush=True)
if __name__=='__main__':main()
