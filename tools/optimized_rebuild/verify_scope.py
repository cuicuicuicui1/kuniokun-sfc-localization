"""Check the previously localized scope against the actual native ROM.
File/naming UI and title graphics are expressly outside the approved scope.
"""
from pathlib import Path
import hashlib, json, os, re, sys, zlib
ROOT = Path(__file__).resolve().parent
SRC = ROOT / 'source'
os.chdir(SRC)
sys.path.insert(0, str(SRC))
import cnbuild5 as cb
import kuniokun_map as km
import dialogue_model as dm
cb.load_build_params()
rom = (ROOT / 'new-build/native-rebuild-candidate.sfc').read_bytes()
p = json.loads((SRC / 'cn_build_params.json').read_text(encoding='utf8'))
inputs = json.loads((ROOT / 'inputs.json').read_text(encoding='utf8'))
opt = Path(inputs['opt']['path']).read_bytes()
assert hashlib.sha256(opt).hexdigest() == inputs['opt']['sha256']
inv = json.loads((ROOT / 'inventory-worker/native-inventory.json').read_text(encoding='utf8'))
translations = json.loads((SRC / 'cn_translation.json').read_text(encoding='utf8'))
cells = json.loads((SRC / 'cn_glyph_cell.json').read_text(encoding='utf8'))
rev_cell = {tuple(v): k for k,v in cells.items()}
rev_item = {v:k for k,v in p['item_chars'].items()}
rev_single = {v:k for k,v in p['keep1'].items()}
rev_single.update({v:k for k,v in p['fixed'].items()})
rev_single[0] = ' '

def decode(off, item):
    out = []
    start = off
    while off - start < 800:
        b = rom[off]; off += 1
        if b >= 0xE0:
            if b == 0xF2:
                nxt = rom[off]; off += 1
                out.append('{%02X%02X}' % (b,nxt))
                if nxt == 0xF3: return ''.join(out)
            else:
                out.append('{%02X}' % b)
                if b == 0xF3: return ''.join(out)
        elif item and b == 0xDE:
            out.append(rev_item[rom[off]]); off += 1
        elif 0xC0 <= b < 0xDE:
            out.append(rev_cell[(b-0xC0,rom[off])]); off += 1
        else:
            out.append(rev_single[b])
    raise AssertionError(('no terminator', hex(start)))

def live(s):
    m = re.search(r'\{(?:F2)?F3\}',s)
    assert m, s
    return s[:m.end()]

readback = []
for table in inv['tables'][1:]:
    for rec in table['records']:
        ptrsite = rec['table_rom_off'] + 2*rec['index']
        ptr = int.from_bytes(rom[ptrsite:ptrsite+2],'little')
        assert 0x8000 <= ptr <= 0xFFFF
        decoded = decode(0x10000+ptr,rec['table_rom_off']==0x1DBC5)
        key = '%06X' % int(rec['text_rom_off'],16)
        assert decoded == live(translations[key]), (hex(ptrsite),decoded,translations[key])
        assert not re.search('[\u3040-\u30FF]',cb.TOKEN.sub('',decoded)), decoded
        readback.append({'table':hex(rec['table_rom_off']),'index':rec['index'],'cn':decoded})
assert len(readback) == 319

# Status labels use their own code-to-8x16 table, not the body code map.
rev8 = {v:k for k,v in p['item_chars'].items()}
at = 0xF9DB
labels = []
while rom[at+1] != 0xFF:
    addr = int.from_bytes(rom[at:at+2],'little'); count = rom[at+2]
    vals = rom[at+3:at+3+(count&127)]
    if count&128 and addr != 0x7889:
        text = ''.join(' ' if b==0 else ':' if b==9 else rev8[rom[0x1F4F00+b]] for b in vals)
        assert text == cb.STATUS_LABELS[addr], (hex(addr),text)
        labels.append({'vram':hex(addr),'cn':text})
    at += 3+(count&127)
assert len(labels) == 15

# Every actor record, including optimized-only actors, must use the approved
# name and preserve its twelve gameplay bytes. Verify the uploaded HUD pixels
# through the original native caller for both enemy plates.
names = json.loads((SRC/'name_hanzi.json').read_text(encoding='utf8'))
ids = {ch:i for i,ch in enumerate(dict.fromkeys(''.join(names.values())))}
records = []

def call(cpu, pc):
    cpu.pbr=cpu.db=0; cpu.pc=pc; cpu.s=0x1FF; cpu.m8=cpu.x8=True
    cpu.push8(0xDF); cpu.push8(0xFF)
    for _ in range(80000):
        if (cpu.pbr,cpu.pc)==(0,0xE000):
            assert cpu.s==0x1FF and cpu.db==0 and cpu.m8 and cpu.x8
            return
        cpu.step()
    raise AssertionError(('native HUD timeout',hex(pc)))

for i in range(514):
    off = 0x4802A + i*16
    kana = ''.join(km.CODE.get(b,'') for b in opt[off:off+4]).strip()
    cn = names[kana]
    expected = bytes(v for ch in cn for v in (0xC0+ids[ch]//128,128+ids[ch]%128)).ljust(4,b'\0')
    assert len(expected)==4 and rom[off:off+4]==expected, (i,kana,cn)
    assert rom[off+4:off+16]==opt[off+4:off+16], i
    for plate in (2,3):
        c=dm.make_cpu(rom); w=c.bus.wram
        w[0x10]=plate; w[0x1C03+plate]=0x20
        w[0x1B46+plate*4:0x1B4A+plate*4]=expected
        call(c,0x8C34); dm.flush(c)
        for g,ch in enumerate(cn):
            idx=ids[ch];page,gid=divmod(idx,128)
            for half in (0,1):
                pairindex=(plate&1)*2+g+half*4
                tile=p['hud_pairs'][pairindex]
                pixels=b''.join(v.to_bytes(2,'little') for v in c.vram[0x6000+tile*8:0x6000+tile*8+16])
                source=p['pool_rom']+page*0x8000+(128+gid)*64+half*32
                assert pixels==rom[source:source+32], (i,plate,ch,half)
    records.append({'index':i,'jp':kana,'cn':cn})
assert rom[0x4A04A:0x50000] == opt[0x4A04A:0x50000]
assert rom[0x10000:0x18000] == opt[0x10000:0x18000], 'out-of-scope file UI changed'
assert rom[0xD47E0:0xD5FE0] == opt[0xD47E0:0xD5FE0], 'out-of-scope title changed'

main=json.loads((ROOT/'native-dialogues.json').read_text(encoding='utf8'))
assert len(main)==769
assert all(not re.search('[\u3040-\u30FF]',cb.TOKEN.sub('',v['text'])) for v in main.values())
assert cb.tokens(main['502']['source']) == cb.tokens(main['502']['text'])
result={
    'status':'pass','date':'2026-10-13',
    'scope':'previously localized content, including optimized changes consumed by those paths',
    'target':{'sha256':hashlib.sha256(rom).hexdigest(),'crc32':'%08X'%zlib.crc32(rom)},
    'counts':{'main_messages':769,'other_table_entries':319,'identified_total':1088,
              'actor_records':514,'native_enemy_hud_calls':1028,'status_labels':15},
    'scope_exclusions':['file/load/naming UI','title logo and unrelated scene graphics'],
    'unchanged_excluded_regions':['bank02','title logo resource'],
    'worker_dispositions':{'1F6_replace_pattern':'false alarm; exact match and correct F2F6/EE/ED in final ROM',
                           '1DB_mamoru':'verb meaning protect, translation retained',
                           'staff_ascii':'approved romanized credits retained',
                           'ending_78':'optimized wording already translated; no new honorific added',
                           'status_module':'not installed; existing status writer already owns this resource'},
    'other_table_readback':readback,'names_readback':records,'status_labels':labels,
    'runtime_limit':'HUD subroutine CPU model; not PPU timing or natural whole-game completion'
}
(ROOT/'qa').mkdir(exist_ok=True)
(ROOT/'qa/scope-coverage.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print('PASS: 319 other-table entries, 514 actor names, 1028 native enemy HUD calls, 15 status labels; excluded UI unchanged')
