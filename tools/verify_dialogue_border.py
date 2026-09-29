"""Fail-closed audit of dialogue-border A/B captures and gameplay ownership traces.

python tools/verify_dialogue_border.py --evidence PATH
The captures are produced with hw/mesen_dialogue_border.lua via run_mesen_play.
"""
import argparse,csv,collections,hashlib,json
from pathlib import Path
from PIL import Image,ImageChops

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args();root=a.evidence.resolve();report={}
allowed={('read','00','BDA8'),('write','00','BDA8'),('write','03','E9A0'),('write','03','EBAF'),('read','3E','D819'),('read','3E','D81E'),('write','3E','D81E'),('write','3E','D827'),('write','3E','D82C')}
def audit_trace(tag,fixed,expected_frames):
    manifest=json.loads((root/(tag+'.json')).read_text(encoding='utf-8'))
    assert manifest['emulator_exit']==0 and manifest['frames']==expected_frames,(tag,'incomplete run')
    rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader((root/(tag+'-border.csv')).open())]
    assert len(rows)==expected_frames and [r['frame'] for r in rows]==list(range(1,expected_frames+1)),(tag,'missing frame samples')
    visible=[r for r in rows if r['bg3_v']==224 and r['hdma_mask']&128]
    hist=collections.Counter(r['bg3_h'] for r in visible)
    if fixed: assert all(r['bg3_h']==r['hdma_h']==0 for r in visible),(tag,'bottom edge moved')
    users=collections.Counter()
    for r in csv.DictReader((root/(tag+'-ownership.csv')).open()):
        if int(r['address'],16)&0x1fff!=0x3e7: continue
        key=(r['kind'],r['bank'],r['pc']);users[key]+=int(r['count'])
        assert key in allowed,(tag,'unexpected counter owner',key)
    if tag.endswith('normal-audit'):
        assert users,(tag,'missing physical WRAM evidence during active typewriter test')
    # A short gameplay segment with no active dialogue legitimately has zero
    # accesses; preserve that observation instead of inventing an owner.
    report[tag]={'frames':len(rows),'rom_crc32':manifest['rom_crc32'],'bottom_display_frames':len(visible),'actual_hscroll_histogram':dict(hist),'counter_access':[{'kind':k[0],'bank':k[1],'pc':k[2],'count':v} for k,v in sorted(users.items())]}
    return hist
old=audit_trace('rc2-normal-audit',False,4200)
assert any(k for k in old),'negative test did not reproduce drift'
audit_trace('rc3-normal-audit',True,4200);audit_trace('jp-normal-audit',True,4200)
for core in ('mesen','snes9x'):
    old_patterns=set();new_patterns=set();changed=0
    for f in range(2540,2621,2):
        if core=='mesen':p1=root/f'rc2-normal-audit-{f}.png';p2=root/f'rc3-normal-audit-{f}.png'
        else:p1=root/f'snes9x-old-normal/frame-{f}.png';p2=root/f'snes9x-fixed-normal/frame-{f}.png'
        before=Image.open(p1).convert('RGB');after=Image.open(p2).convert('RGB')
        assert before.size==after.size==(256,224)
        assert ImageChops.difference(before.crop((0,0,256,215)),after.crop((0,0,256,215))).getbbox() is None,(core,f,'changed above bottom scanlines')
        x=before.crop((0,216,256,224)).tobytes();y=after.crop((0,216,256,224)).tobytes()
        old_patterns.add(x);new_patterns.add(y);changed+=x!=y
    assert len(old_patterns)>1 and len(new_patterns)==1 and changed>0,(core,'A/B not demonstrated')
    report[core+'_pixels']={'samples':41,'old_bottom_patterns':len(old_patterns),'new_bottom_patterns':len(new_patterns),'changed_frames':changed,'outside_bottom_changed_frames':0}
segments=json.loads((root/'game-segments.json').read_text(encoding='utf-8'))
assert len(segments)==6 and sum(s['frames'] for s in segments)==22360,'game route incomplete'
for s in segments:audit_trace(s['tag'],True,s['frames'])
for name,frames in (('snes9x-rc3-cold',15120),('snes9x-rc3-game',7240)):
    m=json.loads((root/name/'report.json').read_text(encoding='utf-8'))
    assert m['frames']==frames and m['rom_crc32']=='AB1795B9'
    assert m['shots'] and max(x['colors'] for x in m['shots'])>20,'all gameplay samples blank'
    # Scripted fades can end with only dialogue visible; do not treat a color
    # threshold as playthrough acceptance. Screen content is reviewed separately.
    report[name]={'frames':frames,'core':m['name']+' '+m['version'],'final_colors':m['shots'][-1]['colors']}
report['result']='PASS';report['scope']='Border stability + bounded gameplay regression, not a full-playthrough or full-localization acceptance.'
(root/'border-acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: negative old ROM; fixed/reference bottom scroll; Mesen/Snes9x pixel A/B; all cold/gameplay trace segments and counter ownership')
