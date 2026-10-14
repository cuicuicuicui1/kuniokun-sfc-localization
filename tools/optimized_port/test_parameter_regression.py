from pathlib import Path
import json,hashlib
from test_character_tables import validate_character_tables,END
ROOT=Path(__file__).resolve().parent
m=json.loads((ROOT/'port-manifest.json').read_text(encoding='utf-8'))
source=Path(m['inputs']['opt']['path']).read_bytes();jp=Path(m['inputs']['jp']['path']).read_bytes();cn=Path(m['inputs']['cn10']['path']).read_bytes();rom=(ROOT/'candidate-ui.sfc').read_bytes()
assert hashlib.sha256(rom).hexdigest()==json.loads((ROOT/'ui-manifest.json').read_text(encoding='utf-8'))['candidate']['sha256']
positive=validate_character_tables(rom,source);validate_character_tables(jp,jp)
v13path=ROOT.parent/'port-ui-v13-20261012/candidate-ui.sfc';bad=bytearray(rom);bad[END+7]^=1
header=bytearray(rom);header[0x48002]^=1
negative=[]
cases=[('inherited-cn10',cn,jp),('damaged-parameter',bad,source),('changed-boundary',header,source)]
if v13path.exists():cases.insert(0,('old-v13',v13path.read_bytes(),source))
for name,data,base in cases:
 try:validate_character_tables(data,base)
 except ValueError as e:negative.append({'case':name,'rejected':True,'reason':str(e)})
 else:raise AssertionError(name+' wrongly passed')
r={'status':'pass','positive':positive,'negative':negative}
(ROOT/'character-table-regression.json').write_text(json.dumps(r,indent=2),encoding='utf-8');print(json.dumps(r,indent=2))
