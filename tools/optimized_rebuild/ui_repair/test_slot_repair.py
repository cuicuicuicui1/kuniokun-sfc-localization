"""Native first-row queue contracts, all reel symbols, and owner alternation."""
from pathlib import Path
import sys,argparse,hashlib,json
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT.parent/'source'))
import dialogue_model as dm
from build_slot_repair import build

def call(cpu,pc):
    cpu.pbr=cpu.db=3;cpu.pc=pc;cpu.s=0x1FF;cpu.m8=cpu.x8=True
    cpu.push8(0xDF);cpu.push8(0xFF)
    for _ in range(100000):
        if (cpu.pbr,cpu.pc)==(3,0xE000):
            assert cpu.s==0x1FF and cpu.db==3 and cpu.m8 and cpu.x8
            return
        cpu.step()
    raise AssertionError(('native timeout',hex(pc)))

def words(cpu,tile,count=1):
    return b''.join(v.to_bytes(2,'little') for v in cpu.vram[0x6000+tile*8:0x6000+(tile+count)*8])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True,type=Path)
    p.add_argument('--rom',required=True,type=Path);p.add_argument('--optimization',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path);a=p.parse_args()
    old=a.base.read_bytes();new=a.rom.read_bytes();opt=a.optimization.read_bytes()
    expected,meta=build(old,opt);assert new==expected
    pressure=0
    for prompt in (0,1):
        for row in range(3):
            for pending in (0,1,23,24,35,36,47,48,68,136,180,240):
                cpu=dm.make_cpu(new);w=cpu.bus.wram
                w[0x363]=prompt;w[0x395]=row;w[0x9DD]=0;w[0x9DF]=pending
                w[0x9DE]=0x9A;w[0x9E0:0x9E2]=b'\xFE\xFF'
                w[0xB00:0xC00]=bytes([0xA5])*256;before=bytes(w[0xB00:0xC00])
                amount=(220 if prompt==1 else 208) if row==0 else 68
                busy=pending+amount>=256
                call(cpu,0xF3C9)
                assert w[0x9DE]==0x9A and w[0x9E0:0x9E2]==b'\xFE\xFF'
                if busy:
                    assert w[0x395]==row and w[0x9DF]==pending and bytes(w[0xB00:0xC00])==before
                    w[0x9DD]=w[0x9DF]=0;call(cpu,0xF3C9)
                assert w[0x395]==row+1 and w[0x9DF]==(amount if busy else amount+pending)
                pressure+=1
    # Previous repair fails the actual second prompt. New one refreshes
    # every native reel symbol, not just the two Chinese labels.
    old_new={}
    for label,rom in [('old',old),('new',new)]:
        cpu=dm.make_cpu(rom);w=cpu.bus.wram
        for tile in range(256):
            cpu.vram[0x6000+tile*8:0x6000+(tile+1)*8]=[int.from_bytes(rom[0xF8000+tile*16+j:0xF8000+tile*16+j+2],'little') for j in range(0,16,2)]
        w[0x363]=1
        for row in range(3):call(cpu,0xF3C9);dm.flush(cpu)
        old_new[label]=all(words(cpu,tile)==opt[0xF8000+tile*16:0xF8000+(tile+1)*16] for tile in list(range(0x4A,0x52))+[0x53])
    assert old_new==dict(old=False,new=True)
    cpu=dm.make_cpu(new);w=cpu.bus.wram;entries=[];symbols=set()
    for iteration in range(20):
        for prompt in (1,0):
            w[0x363]=prompt;w[0x395]=0
            # Keep a sentinel in tile52, owned by the literal STATUS title.
            cpu.vram[0x6290:0x6298]=[0xAC53]*8
            for row in range(3):call(cpu,0xF3C9);entries+=dm.flush(cpu)
            assert cpu.vram[0x6290:0x6298]==[0xAC53]*8
            if prompt==1:
                for tile in list(range(0x4A,0x52))+[0x53]:assert words(cpu,tile)==opt[0xF8000+tile*16:0xF8000+(tile+1)*16]
                for symbol in range(8):
                    w[0x397:0x39A]=bytes([symbol])*3;call(cpu,0xF2D0);dm.flush(cpu)
                    pair=int.from_bytes(opt[0x1F32F+symbol*2:0x1F331+symbol*2],'little')
                    assert cpu.vram[0x7BD3]==pair and cpu.vram[0x7BD5]==pair and cpu.vram[0x7BD7]==pair
                    symbols.add(symbol)
            else:
                for first,count in [(0x44,3),(0x4A,2),(0x4D,3)]:assert words(cpu,first,count)==new[0xF8000+first*16:0xF8000+(first+count)*16]
    result=dict(status='pass',sha256=meta['sha256'],queue_pressure_cases=pressure,
                actual_reel_old_fails_new_pass=old_new,native_reel_symbol_ids=sorted(symbols),
                yesno_reels_switches=40,protected_status_title_tile='unchanged',
                scope='Original 65816 consumers and modeled NMI queue; not PPU timing')
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
