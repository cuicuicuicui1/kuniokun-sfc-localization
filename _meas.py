import sys, io; sys.path.insert(0,'.')
import cnbuild5 as cb
import kuniokun_map as km
data = io.open(cb.ORIG_ROM,'rb').read()
drop = set(sys.argv[1:])
def codes_item():
    s = data[0x01DCA1:0x01E096]
    return set(b for b in (s if cb.HUD_ORIG else cb.rewrite_kana(s)) if 0 < b < 0xE0)
def codes_names():
    out = set()
    for i in range(560):
        for b in cb.rewrite_kana(data[0x4802A+i*16:0x4802A+i*16+4]):
            if b == 0: break
            if b < 0xE0: out.add(b)
    return out
def codes_stat():
    out = set()
    for s, e in cb.status_script_code_runs():
        out |= set(b for b in (data[s:e] if cb.HUD_ORIG else cb.rewrite_kana(data[s:e])) if 0 < b < 0xE0)
    return out
def f():
    c = set(cb.KEEP1_EXPLICIT.values()) | set(range(0x10, 0x1A))
    if 'item'  not in drop: c |= codes_item()
    if 'names' not in drop: c |= codes_names()
    if 'stat'  not in drop: c |= codes_stat()
    return c
cb.untranslated_codes = f
cb.PROTECT_CODES = None
prot = cb.protected_tiles()
free = cb.free_pairs()
slots = (len(free) - 2*(cb.LABEL_GLYPHS*cb.LABEL_SETS + cb.LABEL_NAME_GLYPHS*cb.LABEL_NAME_SETS)) // 2
print('%-20s prot=%3d pairs=%3d slots_max=%3d' % ('+'.join(sys.argv[1:]) or 'v13', len(prot), len(free), slots))
