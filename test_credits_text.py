"""Credits layout / token alignment / co-visible storage contracts."""
import json,re
from pathlib import Path
import cnbuild5 as cb
params=cb.load_build_params()
rom=Path('kuniokun_cn.smc').read_bytes()
source=json.loads(Path('kuniokun_text.json').read_text(encoding='utf8'))
cn=json.loads(Path('cn_translation.json').read_text(encoding='utf8'))
fixed={f"{r['text_rom_off']:06X}":cb.align_tokens(r['text'],cn[f"{r['text_rom_off']:06X}"]) for r in source};cell=json.loads(Path('cn_glyph_cell.json').read_text(encoding='utf8'))
# A new legal line break cannot shift an ED/EE macro or F3 into prose.
for orig,mine in [('{F0}{E2}:甲{ED}乙{F2F3}','{F0}{E2}:甲{F2F6}{ED}乙{F2F3}'),
                  ('{E2}甲{EE}乙{F2F4}{F3}','{E2}甲{F2F6}{EE}乙{F2F6}{F2F4}{F3}')]:
 assert cb.align_tokens(orig,mine)==mine
 assert cb.align_tokens(orig,mine).index('{F3}')==mine.index('{F3}') if '{F3}' in mine else True
assert cb.align_tokens('甲{F2F3}','汉字')=='汉字{F2F3}'
# Romanized proper names fit one original 26-cell cue; do not widen each
# ASCII letter into a full Chinese glyph or silently crop the last name.
names=0
for r in source[:694]:
 k=f"{r['text_rom_off']:06X}";t=cn[k]
 if 649<=r['index']<=693 and t.startswith('{F6}') and re.search('[A-Z]',re.sub(r'\{[0-9A-F]{2,4}\}','',t)):
  names+=1;prose=re.sub(r'\{[0-9A-F]{2,4}\}','',t)
  assert cb.ncells(prose)<=26,(k,cb.ncells(prose))
  assert ''.join(cb.units(prose))==prose
  assert len(cb.Encoder().encode(''))==0
assert names==30,names
# Sparse-title lifetime sets include actual non-neighbor IDs and their names.
main=[cb.glyphs_of(fixed[f"{r['text_rom_off']:06X}"]) for r in source[:694]]
windows=cb.credits_windows(main)
assert len(windows)==20 and main[0x2A8-1]|main[0x2AF-1]|main[0x2B0-1] in windows
for win in windows:
 slots=[cell[ch][1] for ch in win]
 assert len(slots)==len(set(slots)),('co-visible credits collision',win)
 assert all(0<=cell[ch][0]<cb.PAGES and cell[ch][1]<cb.SLOTS for ch in win)
# Every packed column is in bounds and unique; page0 fixed-glyph source
# remains protected by co-visibility, not a conservative capacity estimate.
assert len({tuple(v) for v in cell.values()})==len(cell)
assert cb.POOL_ROM+cb.PAGES*0x8000<=cb.CODE_ROM
assert cb.PREFIX0+cb.PAGES<=cb.ITEM_PREFIX
print('PASS: 30 single-cue staff readings, 20 real credits lifetime sets, token reflow + storage capacity')

# Independently reconstruct every source window, not just the solver's result.
assert cb.PAGES == params['pages']
assert len(source) == len(cn) == 1013
row_ids = set(params['rolling_row_messages'])
expected_rows = {r['index'] for r in source[:694] if r['index'] < 649
                 and len(fixed[f"{r['text_rom_off']:06X}"].split('{F2F6}')) > 3}
assert row_ids == expected_rows
all_windows = list(windows)
for ti, (table, count) in enumerate(cb.TABLES):
    if table == cb.ITEM_TABLE or table in cb.NO_TRANSLATE:
        continue
    recs = sorted((r for r in source if r['table_rom_off'] == table), key=lambda r:r['index'])
    assert len(recs) == count
    gs = [cb.glyphs_of(fixed[f"{r['text_rom_off']:06X}"]) for r in recs]
    width = params['colour_window_main'] if ti == 0 else params['colour_window_list']
    for i, rec in enumerate(recs):
        if ti == 0 and width == 1 and i in row_ids:
            rows = [cb.glyphs_of(t) for t in fixed[f"{rec['text_rom_off']:06X}"].split('{F2F6}')]
            all_windows.extend(set().union(*rows[j:j+3]) for j in range(len(rows)))
        else:
            all_windows.append(set().union(*gs[i:i+width]))
if cb.CMDWIN == 2:
    all_windows.append(set(''.join(t for _,_,t in cb.MENU_LABELS)))
for w in all_windows:
    assert len({cell[c][1] for c in w}) == len(w), ('complete window collision', w)
assert set(cell) == set().union(*all_windows, set(params['fixed']))
loads = [sum(v[1] == s for v in cell.values()) for s in range(cb.SLOTS)]
assert max(loads) <= cb.PAGES
print('PASS: every source/list/menu window; no alias, missing glyph or storage overflow')
