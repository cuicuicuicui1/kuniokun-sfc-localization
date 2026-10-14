"""Rebuild from the optimization original. Requires private ROM/font inputs.
Writes only declared private build files and candidate outputs under this tree.
"""
from pathlib import Path
import argparse,json,hashlib,os,sys,subprocess,shutil
ROOT=Path(__file__).resolve().parent;SRC=ROOT/'source';p=argparse.ArgumentParser();p.add_argument('--optimization',type=Path);p.add_argument('--japanese',type=Path);p.add_argument('--font',type=Path);a=p.parse_args()
config=json.loads((ROOT/'inputs.json').read_text(encoding='utf8'))
for key,arg in [('opt',a.optimization),('jp',a.japanese)]:
 path=(arg or Path(config[key]['path'])).resolve();data=path.read_bytes();assert len(data)==config[key]['size'] and hashlib.sha256(data).hexdigest()==config[key]['sha256'],('wrong source',key,path);config[key]['path']=str(path)
assert Path(config['opt']['path']).resolve()!= (SRC/'work_kuniokun_2mb.smc').resolve()
(ROOT/'inputs.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf8')
(SRC/'dl/roms').mkdir(parents=True,exist_ok=True);jp=Path(config['jp']['path']);dest=SRC/'dl/roms/kuniokun__SF8127.smc'
if jp.resolve()!=dest.resolve():shutil.copyfile(jp,dest)
if a.font:
 (SRC/'fonts').mkdir(exist_ok=True);fd=SRC/'fonts/unifont.hex.gz'
 if a.font.resolve()!=fd.resolve():shutil.copyfile(a.font,fd)
assert (SRC/'fonts/unifont.hex.gz').is_file(),'supply private --font input'
dep=json.loads((ROOT/'dependencies.json').read_text(encoding='utf8'))
assert hashlib.sha256((SRC/'fonts/unifont.hex.gz').read_bytes()).hexdigest()==dep['font']['sha256'],'font does not match reproducible release input'

raw=Path(config['opt']['path']).read_bytes();base=bytearray(raw)+bytes(0x400000-len(raw));base[0x7fd7]=12;base[0x7fdc:0x7fe0]=bytes(4);chk=(sum(base)+510)&65535;base[0x7fdc:0x7fe0]=(chk^65535).to_bytes(2,'little')+chk.to_bytes(2,'little');assert hashlib.sha256(base).hexdigest()==json.loads((ROOT/'native-base.json').read_text(encoding='utf8'))['private_base_sha256'];(SRC/'work_kuniokun_2mb.smc').write_bytes(base)
(ROOT/'new-build').mkdir(exist_ok=True);env=dict(os.environ,**dep['environment'])
for key in ['SLOTS_FORCE','KEEP1_OLD','CHARSTAT','ENC_TOTAL','BASE_ONLY','OUT_ROM']:
 env.pop(key,None)

for name in ['build_positional_components.py','patch_native.py']:
 subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,env=env,check=True)
print('Native rebuild complete. Output remains a candidate until applicable runtime QA passes.')
