"""Bounded segmented real-game replay; menu fixtures are explicitly opt-in.

python tools/replay_runtime_names.py --sram COPY.srm --out ISOLATED_DIR
Optional --include-menu-fixtures injects level/inventory in disposable WRAM,
then opens/closes/scrolls the real menus by pad input. Never writes player saves.
"""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,zlib
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=ROOT/'kuniokun_cn.smc')
    p.add_argument('--sram',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--mesen',default=r'F:\emulators\mesen2\Mesen.exe')
    p.add_argument('--include-menu-fixtures',action='store_true')
    p.add_argument('--route',type=Path,default=ROOT/'hw/regression_routes/runtime-names-rc4.json')
    a=p.parse_args();route=json.loads(a.route.read_text(encoding='utf-8'))
    assert hashlib.sha256(a.sram.read_bytes()).hexdigest()==route['required_sram_sha256'], 'route requires its known read-only SRAM seed'
    a.out=a.out.resolve();a.out.mkdir(parents=True,exist_ok=True)
    states={};reports=[]
    for spec in route['stages']:
        controlled=spec.get('scope','').startswith('controlled')
        if controlled and not a.include_menu_fixtures:
            print('SKIP controlled runtime fixture: '+spec['name'],flush=True);continue
        name=spec['name'];out=a.out/name
        script='mesen_menu_names_fixture.lua' if spec.get('fixture') else 'mesen_runtime_names.lua'
        cmd=[sys.executable,str(ROOT/'tools/run_mesen_play.py'),'--rom',str(a.rom.resolve()),'--mesen',a.mesen,'--tag',name,'--out',str(out),'--frames',str(spec['frames']),'--input',spec['input'],'--shots',','.join(map(str,spec['shots'])),'--script',str(ROOT/'hw'/script)]
        if spec.get('state_from'):cmd+=['--state',str(states[spec['state_from']])]
        else:cmd+=['--sram',str(a.sram.resolve())]
        env=dict(os.environ,RUNTIME_FIXTURE='menus' if spec.get('fixture') else '')
        rc=subprocess.call(cmd,cwd=ROOT,env=env)
        if rc:return rc
        states[name]=out/(name+'.state')
        report=json.loads((out/(name+'.json')).read_text(encoding='utf-8'))
        report['verification_scope']=spec['scope'];report['runtime_fixture']=bool(spec.get('fixture'))
        reports.append(report)
    (a.out/'route-report.json').write_text(json.dumps({'rom_crc32':f'{zlib.crc32(a.rom.read_bytes()):08X}','menu_fixtures_enabled':a.include_menu_fixtures,'stages':reports},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Replay complete. Inspect scene images and VRAM; frame counts alone are not acceptance.',flush=True)
    return 0

if __name__=='__main__':raise SystemExit(main())
