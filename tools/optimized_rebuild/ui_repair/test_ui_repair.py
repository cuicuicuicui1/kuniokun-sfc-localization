from pathlib import Path
import argparse,hashlib,json,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'source'))
import dialogue_model as dm
from build_ui_repair import build
p=argparse.ArgumentParser(description='Native CPU and upload-queue regression for the exact UI repair')
p.add_argument('--base',required=True,type=Path);p.add_argument('--rom',required=True,type=Path)
p.add_argument('--font',required=True,type=Path);p.add_argument('--report',required=True,type=Path)
a=p.parse_args()
old=a.base.read_bytes();new=a.rom.read_bytes();expected,layout=build(old,a.font)
assert expected==new
def call(cpu,bank,pc):
    cpu.pbr=cpu.db=bank;cpu.pc=pc;cpu.s=0x1ff;cpu.m8=cpu.x8=True
    cpu.push8(0xDF);cpu.push8(0xFF)
    for _ in range(150000):
        if (cpu.pbr,cpu.pc)==(bank,0xE000):
            assert cpu.s==0x1ff and cpu.db==bank and cpu.m8 and cpu.x8
            return
        cpu.step()
    raise AssertionError(('native timeout',hex(pc)))

# Original prompt consumer, zero/near-full/full queue and both prompt sets.
pressure=[]
for row in [0,1,2]:
    for prompt in [0,1]:
        for pending in [0,1,30,47,48,80,136,180,240]:
            cpu=dm.make_cpu(new);w=cpu.bus.wram;w[0x395]=row;w[0x363]=prompt
            w[0x9DD]=0;w[0x9DF]=pending
            w[0x9DE]=0x9A;w[0x9E0:0x9E2]=b'\xf8\xff'
            w[0xB00:0xC00]=bytes([0xA5])*256;before=bytes(w[0xB00:0xC00])
            demand=208 if row==0 and prompt==0 else 68
            busy=pending+demand>=256
            call(cpu,3,0xF3C9)
            assert w[0x9DE]==0x9A and w[0x9E0:0x9E2]==b'\xf8\xff'
            if busy:
                assert w[0x395]==row and w[0x9DF]==pending and bytes(w[0xB00:0xC00])==before
                w[0x9DD]=w[0x9DF]=0;call(cpu,3,0xF3C9)
            assert w[0x395]==row+1
            assert w[0x9DF]==(demand if busy else pending+demand)
            pressure.append((row,prompt,pending,busy))

# Deliberately stale option bitmaps: old writer leaves them stale, new first
# row refreshes them through three nonempty native NMI queue records.
poison_results={}
for tag,rom in [('old',old),('new',new)]:
    cpu=dm.make_cpu(rom)
    for first,count in [(0x44,3),(0x4A,2),(0x4D,3)]:
        cpu.vram[0x6000+first*8:0x6000+(first+count)*8]=[0xA55A]*(count*8)
    entries=[]
    for row in range(3):
        assert cpu.bus.wram[0x395]==row
        call(cpu,3,0xF3C9);entries+=dm.flush(cpu)
    same=True
    for first,count in [(0x44,3),(0x4A,2),(0x4D,3)]:
        actual=b''.join(v.to_bytes(2,'little') for v in cpu.vram[0x6000+first*8:0x6000+(first+count)*8])
        same &= actual==rom[0xF8000+first*16:0xF8000+(first+count)*16]
    poison_results[tag]=same
    if tag=='new':assert len([e for e in entries if 0x6000<=e[0]<0x6800])==3
assert poison_results==dict(old=False,new=True)

def pixels(cpu,run):
    for col in run['columns']:
        tile=col['tile'];cell=col['cell'];off=col['font_offset']
        assert cpu.vram[cell]==0x2400+tile,(run['text'],hex(cell),cpu.vram[cell])
        assert cpu.vram[cell+32]==0x2401+tile
        actual=b''.join(v.to_bytes(2,'little') for v in cpu.vram[0x6000+tile*8:0x6000+tile*8+16])
        assert actual==new[off:off+32],(run['text'],hex(cell),'font pixels')
runs=layout['status_runs']
cpu=dm.make_cpu(new);call(cpu,1,0xF971)
for run in runs[:15]:pixels(cpu,run)
at=0xF9DB
while new[at+1]!=255:
    cell=int.from_bytes(new[at:at+2],'little');n=new[at+2]
    if not n&128:
        for k,tile in enumerate(new[at+3:at+3+n]):
            assert cpu.vram[cell+k]==0x2400 and cpu.vram[cell+k+32]==0x2400+tile
    at+=3+(n&127)
fixed=0
for player in range(2):
    for cond in range(3):
        cpu=dm.make_cpu(new);w=cpu.bus.wram;w[0x1BA6]=player;w[0x1EB+player]=cond
        for row in range(3):w[0x1E5+row*2+player]=0
        call(cpu,1,0xFBBB)
        pixels(cpu,runs[15+player]);pixels(cpu,runs[17+cond])
        for row in range(3):pixels(cpu,runs[20+row*111])
        fixed+=1
equipment=0
for row in range(3):
    for idx in range(111):
        cpu=dm.make_cpu(new);cell=[0x79C6,0x7A06,0x7A46][row]
        cpu.a=idx;cpu.bus.wram[0x20:0x22]=cell.to_bytes(2,'little')
        call(cpu,1,0xFC75);pixels(cpu,runs[20+row*111+idx]);equipment+=1
allowed=[(0x7FDC,0x7FE0),(0xF971,0xF976),(0xFBBB,0xFBC2),(0xFC75,0xFC7D),
         (0x1F169,0x1F16A),(0x1F3C9,0x1F3CF),(0x186100,0x187000),(0x1A0000,0x1E0000)]
changed=[i for i,(a,b) in enumerate(zip(old,new)) if a!=b]
assert all(any(lo<=i<hi for lo,hi in allowed) for i in changed)
assert old[0x184100:0x186000]==new[0x184100:0x186000]
assert old[0x188000:0x190000]==new[0x188000:0x190000]
assert old[0x1F582A]==new[0x1F582A]
result=dict(status='pass',sha256=hashlib.sha256(new).hexdigest(),native_choice_queue_cases=len(pressure),
            old_stale_options_fail_new_pass=poison_results,native_status_labels=15,
            native_status_player_condition_cases=fixed,native_equipment_cases=equipment,
            original_message_pointer_and_text_bytes='unchanged',changed_bytes=len(changed),
            scope='Native CPU/queue consumer model; no PPU timing claim')
a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False,indent=2))
