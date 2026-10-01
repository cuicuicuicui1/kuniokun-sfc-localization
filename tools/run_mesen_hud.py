"""Run actual HUD code in Mesen using a throw-away diagnostic ROM copy.

python tools/run_mesen_hud.py kuniokun_cn.smc --mesen F:/emulators/mesen2/Mesen.exe
These are CPU/queue regressions, NOT an end-to-end gameplay acceptance test.
"""
from pathlib import Path
import argparse,json,os,subprocess,zlib

ROOT=Path(__file__).resolve().parents[1]

def validate(rom,ram,rec,slot,cursor):
    par=json.loads((ROOT/'cn_build_params.json').read_text(encoding='utf-8'))
    first=par['slots']+2*par.get('label_sets',2);n=first+par.get('label_name_glyphs',4)
    def tile(g,h):
        if par.get('hud_pairs'):
            i=(slot & (1 if par.get('hud_orig', True) else 3))*2+g
            return par['hud_pairs'][i+h*(len(par['hud_pairs'])//2)]
        i=first+g+h*n
        return rom[0x1F0180+i]|rom[0x1F0700+i]<<8
    end=int.from_bytes(ram[0x9DF:0x9E1],'little');q=ram[0xB00:0xC00]
    assert cursor<=end<=255 and ram[0xC00]==0x6D,'queue bounds'
    assert ram[0x1E:0x20]==bytes.fromhex('EF BE'),'borrowed direct-page bytes'
    assert q[:cursor]==b'\xA5'*cursor,'previous queue entries overwritten'
    entries=[];i=cursor
    while i<end:
        address=int.from_bytes(q[i:i+2],'little');mode,size=q[i+2:i+4]
        assert mode==0x80 and size in (2,32) and i+4+size<=end,'queue entry corrupt'
        entries.append((address,q[i+4:i+4+size]));i+=4+size
    assert i==end
    base=int.from_bytes(rom[0xC2C+slot*2:0xC2E+slot*2],'little')-4
    expected_cells=[];expected_glyphs={}
    for k in range(4):
        g,h=k//2,k%2
        if rec[2*g]>=0xC0:
            up=tile(g,h);down=up+1
            if h==0:
                off=(par.get("pool_bank0",0x21)+rec[g*2]-0xC0)*0x8000+rec[g*2+1]*64
                for half in range(2):expected_glyphs[0x6000+tile(g,half)*8]=rom[off+half*32:off+(half+1)*32]
        else:up=rom[0x1FA9E+rec[k]];down=rom[0x1FB9E+rec[k]]
        # FA/FB are originally bottom/top; Chinese pools are top/bottom.
        if rec[2*g] < 0xC0: up,down=down,up
        expected_cells.extend(((base+k,bytes((down,0x24))),(base+k-32,bytes((up,0x24)))))
    assert [e for e in entries if len(e[1])==2]==expected_cells,'tilemap cells/header placement'
    uploads=[e for e in entries if len(e[1])==32]
    for address,data in uploads:assert expected_glyphs.get(address)==data,'wrong glyph or half'
    if cursor<=32:assert dict(uploads)==expected_glyphs,'missing glyph upload'
    return {'queue_bytes':end-cursor,'glyph_uploads':len(uploads),'cell_entries':8}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',type=Path)
    p.add_argument('--mesen',default=os.getenv('MESEN_EXE',r'F:\emulators\mesen2\Mesen.exe'))
    p.add_argument('--out',type=Path,default=ROOT/'hw/hud-regression')
    p.add_argument('--tag',default='candidate')
    a=p.parse_args();source=a.rom.resolve();rom=source.read_bytes();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Reset only this diagnostic copy into a native-mode harness. It calls the
    # ORIGINAL complete $00:8C34 function, then stops at a known return site.
    test=bytearray(rom)
    code=bytes.fromhex('78 18 FB E2 20 A9 00 8D 00 42 C2 30 A9 00 00 5B A2 FF 01 9A E2 30 A9 00 48 AB A2 5A 20 34 8C')
    done=0xF2AA+len(code)
    test[0x72AA:0x72AA+len(code)+3]=code+bytes.fromhex('EA 80 FE')
    test[0x7FFC:0x7FFE]=(0xF2AA).to_bytes(2,'little')
    fixture=out/(a.tag+'-fixture.smc');fixture.write_bytes(test)
    first=rom[0x4802A:0x4802E]
    names=[rom[0x4802A+i*16:0x4802E+i*16] for i in range(560)]
    cross=next(rec for rec in names if rec[0]>=0xC0 and rec[2]>=0xC0 and rec[0]!=rec[2])
    cases=[('two-hanzi',first,0,0),('one-hanzi',first[:2]+b'\0\0',0,0),('cross-page',cross,3,0),('queued-32',first,0,32),('busy-200',first,0,200),('kana',bytes.fromhex('00 00 47 26'),0,0)]
    results=[]
    for name,rec,slot,cursor in cases:
        tag=a.tag+'-'+name
        env=dict(os.environ,HUD_OUT=out.as_posix(),HUD_TAG=tag,HUD_DONE=str(done),HUD_SLOT=str(slot),HUD_CURSOR=str(cursor),HUD_REC=rec.hex())
        proc=subprocess.run([a.mesen,'--testRunner',str(ROOT/'hw/mesen_hud_regression.lua'),str(fixture),'--doNotSaveSettings'],env=env,cwd=ROOT,timeout=45,creationflags=0x08000000 if os.name=='nt' else 0)
        log=(out/(tag+'.log')).read_text(encoding='utf-8')
        result={'case':name,'record':rec.hex(),'slot':slot,'cursor':cursor,'exit':proc.returncode,'log':log}
        try:
            assert proc.returncode==0 and 'RETURNED' in log,'callee did not return'
            result.update(validate(rom,(out/(tag+'.wram')).read_bytes(),rec,slot,cursor));result['pass']=True
        except AssertionError as exc:result.update({'pass':False,'error':str(exc)})
        results.append(result);print(name, 'PASS' if result['pass'] else 'FAIL',result.get('error',result.get('queue_bytes')),flush=True)
    assert source.read_bytes()==rom,'source ROM was changed'
    manifest={'source_crc32':f'{zlib.crc32(rom):08X}','instrumented_copy':True,'full_original_hud_function':True,'results':results}
    (out/(a.tag+'.json')).write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return 0 if all(r['pass'] for r in results) else 1

if __name__=='__main__':raise SystemExit(main())
