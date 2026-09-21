"""Is the 6th pointer table (0x01E982, used by macro $EA) remapped in my build?

If my build repacked the main text region but left these pointers at their
original values, the $EA macro jumps into the middle of packed text.
"""
import json
import os

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
orig = open(BASE + '/dl/roms/kuniokun__SF8127.smc', 'rb').read()
mine = open(BASE + '/kuniokun_cn.smc', 'rb').read()
amap = json.load(open(BASE + '/cn_addr_map.json', encoding='utf-8'))
bmap = json.load(open(BASE + '/cn_build_params.json', encoding='utf-8'))

TBL6 = 0x01E982
print('table6 (0x%06X) pointers:' % TBL6)
old_new = {}
for i in range(0, 40):
    o = TBL6 + 2 * i
    po = orig[o] | (orig[o + 1] << 8)
    pm = mine[o] | (mine[o + 1] << 8)
    if po == 0 and pm == 0:
        break
    old_new[po] = pm
    flag = 'SAME' if po == pm else 'changed'
    print('  [%2d] orig 0x%04X  mine 0x%04X  %s' % (i, po, pm, flag))

print()
print('do the ORIGINAL pointers land on entry starts of the original text?')
# entry start offsets in the original = the 694 main-table entries
recs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))
starts = set(r['text_rom_off'] for r in recs)
tgt = set(old_new.keys())
print('  orig pointers that are main-table entry starts: %d/%d'
      % (len(tgt & starts), len(tgt)))

print('do MY pointers land on entry starts of MY text?')
newstarts = {}
for r in recs:
    key = '%06X' % r['text_rom_off']
    if key in amap:
        newstarts[amap[key]] = r['text_rom_off']
print('  mine pointers that are new entry starts: %d/%d'
      % (len([p for p in old_new.values() if p in newstarts]), len(old_new)))
for po, pm in list(old_new.items())[:8]:
    want = amap.get('%06X' % po)
    print('  orig 0x%04X -> expected new 0x%04X, table says 0x%04X %s'
          % (po, want if want else -1, pm,
             'OK' if want == pm else 'MISMATCH' if want else '(orig ptr not an entry start)'))