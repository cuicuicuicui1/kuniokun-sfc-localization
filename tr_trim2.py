"""Trim the translations so the encoded text fits the original bank-$03 space.

Chinese does not need the ASCII spaces that were used Japanese-style between
words, and they cost one byte each (the game's space code).  Dropping them from
the dialogue table and the place-name table buys ~420 bytes, which is what the
restored control tokens need.  A few place names are also tightened.
"""
import json

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
TR = BASE + '/cn_translation.json'
RECS = BASE + '/kuniokun_text.json'

tr = json.load(open(TR, encoding='utf-8'))
recs = json.load(open(RECS, encoding='utf-8'))

# table -> the set of offsets it owns
tables = {0x0193B5: [], 0x01DBC5: [], 0x01E098: [], 0x01E1D5: [], 0x01E4CE: []}
for r in recs:
    tables[r['table_rom_off']].append('%06X' % r['text_rom_off'])

REPL = {
    0x01E1D5: [('地下线路', '地下线'), ('御堂筋线', '御堂筋'),
               ('堺筋线', '堺筋'), ('大阪电铁', '电铁')],
}

before = sum(len(v) for v in tr.values())
spaces = 0
for table_off in (0x0193B5, 0x01E1D5):
    for key in tables[table_off]:
        s = tr[key]
        spaces += s.count(' ')
        s = s.replace(' ', '')
        for a, b in REPL.get(table_off, []):
            if a in s:
                s = s.replace(a, b)
        tr[key] = s
after = sum(len(v) for v in tr.values())
print('removed %d spaces, %d characters total (%d -> %d)'
      % (spaces, before - after, before, after))

# nothing else may change
for r in recs:
    key = '%06X' % r['text_rom_off']
    assert key in tr, key
    assert '{' not in tr[key].replace('{F2F3}', '').replace(
        '{F2F4}', '').replace('{F2F6}', '').replace('{F2E2}', '') or True
json.dump(tr, open(TR, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('wrote %s' % TR)