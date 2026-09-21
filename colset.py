# -*- coding: utf-8 -*-
"""Shared pieces for the slot-colouring experiments.

The box is wiped at every message entry, so only one message is on screen at a
time: the real constraint is "characters that appear in the same message (or in
the same list screen window) must not share a slot".  These helpers rebuild the
exact translations the builder would encode and expose the colouring search with
a configurable slot budget.
"""
import json

import cnbuild5 as cb

_cache = {}


def data():
    """(tr, textrecs, fixed) with the builder's exact text pipeline applied."""
    if 'd' not in _cache:
        tr = json.load(open(cb.BASE + '/cn_translation.json', encoding='utf-8'))
        textrecs = json.load(open(cb.BASE + '/kuniokun_text.json', encoding='utf-8'))
        orig = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
        tbl_of = {'%06X' % r['text_rom_off']: r['table_rom_off'] for r in textrecs}
        fixed = {}
        for k, v in tr.items():
            if tbl_of.get(k) in cb.NO_TRANSLATE:
                continue
            fixed[k] = cb.wrap_segments(cb.align_tokens(orig[k], cb.reflow(v)))
        cb.derive_keep1(fixed.values())
        _cache['d'] = (tr, textrecs, fixed)
    return _cache['d']


def windows_for(textrecs, fixed, win_main, win_list):
    per_table = {}
    for ti, (table_off, count) in enumerate(cb.TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        if table_off in cb.NO_TRANSLATE:
            per_table[ti] = []
            continue
        per_table[ti] = [cb.glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    windows = []
    for ti, gs in per_table.items():
        win = win_main if ti == 0 else win_list
        for i in range(len(gs)):
            u = set()
            for j in range(i, min(i + win, len(gs))):
                u |= gs[j]
            windows.append(u)
    return windows


def per_char_of(windows):
    per_char = {}
    for w in windows:
        for ch in w:
            per_char.setdefault(ch, []).append(w)
    return per_char


def colour_with(per_char, nslots, order):
    """Greedy colouring: first fit into the least loaded free slot."""
    slot = {}
    load = [0] * nslots
    for ch in order:
        banned = set()
        for w in per_char.get(ch, ()):
            banned |= {slot[c] for c in w if c in slot}
        free = [s for s in range(nslots) if s not in banned]
        if not free:
            return None
        s = min(free, key=lambda x: (load[x], x))
        slot[ch] = s
        load[s] += 1
    return slot