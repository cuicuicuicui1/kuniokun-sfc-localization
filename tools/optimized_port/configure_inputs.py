from runtime_paths import source_tree
"""Configure private local inputs after unpacking. Never changes expected hashes."""
from pathlib import Path
import argparse,json,hashlib,os,shutil
ROOT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--jp',type=Path,required=True);ap.add_argument('--opt',type=Path,required=True);ap.add_argument('--cn10',type=Path,required=True);ap.add_argument('--unifont',type=Path,required=True);ap.add_argument('--source-tree',type=Path,default=source_tree());a=ap.parse_args()
f=ROOT/'diff-analysis.json';m=json.loads(f.read_text(encoding='utf-8'))
inputs={'jp':a.jp.resolve(),'opt':a.opt.resolve(),'cn10':a.cn10.resolve()}
for k,path in inputs.items():
 data=path.read_bytes()
 if hashlib.sha256(data).hexdigest()!=m['inputs'][k]['sha256']:raise ValueError('wrong input fingerprint: '+k)
 m['inputs'][k]['path']=str(path)
font=a.unifont.resolve();expected=json.loads((ROOT/'dependencies.json').read_text(encoding='utf-8'))['font/unifont.hex.gz']
if hashlib.sha256(font.read_bytes()).hexdigest()!=expected:raise ValueError('wrong private Unifont fingerprint')
m['private_dependencies']={'unifont':{'path':str(font),'sha256':expected}}
base=a.source_tree.resolve()/'dl/roms/kuniokun__SF8127.smc'
if base.exists():
 if base.read_bytes()!=inputs['jp'].read_bytes():raise ValueError('existing private base is different; refuse overwrite')
else:base.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(inputs['jp'],base)
f.write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8');print('Inputs configured. Set SFC_RECON_SOURCE to',a.source_tree.resolve())
