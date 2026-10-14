"""Apply this port BPS to the exact supplied optimization ROM; never overwrite input."""
from pathlib import Path
import argparse,hashlib
from bps_codec import decode
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('source',type=Path)
parser.add_argument('--out',type=Path)
args=parser.parse_args()
source=args.source.resolve();output=(args.out or source.with_name(source.stem+'_汉化移植.sfc')).resolve()
if output==source:raise SystemExit('拒绝覆盖原ROM')
if output.exists():raise SystemExit('输出文件已存在，请换一个输出文件名')
root=Path(__file__).resolve().parent
patches=list(root.glob('*.bps'))
if len(patches)!=1:raise SystemExit('补丁目录必须恰好有一个 BPS，请确认交付包')
patch=patches[0]
raw=source.read_bytes();target=decode(patch.read_bytes(),raw)
output.parent.mkdir(parents=True,exist_ok=True)
with output.open('xb') as f:f.write(target)
assert source.read_bytes()==raw
print(output)
print('SHA256',hashlib.sha256(target).hexdigest())
