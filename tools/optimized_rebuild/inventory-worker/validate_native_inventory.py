# -*- coding: utf-8 -*-
"""Independent validation of inventory-worker's native text inventory.

Recomputes every entry, boundary and denominator straight from the fixed
optimized ROM (SHA/CRC pinned below) and compares the result with
native-inventory.json / candidate-translations.json.  Includes negative
self-tests that prove the checks actually reject tampered inputs.

No third-party imports, no ROM writes, no network.

Run:  python validate_native_inventory.py
Writes: results.json next to this script.  Exit code 0 = PASS, 1 = FAIL.
"""

import copy
import hashlib
import json
import os
import re
import struct
import sys
import zlib
from collections import Counter

BASE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(BASE)

EXPECT_OPT_SHA = '2008f9b34d2b48a168824c8c7d1e3c8924dbb0fa81de9a4eeff2823a635ffe08'
EXPECT_OPT_CRC = 0x65D66D5D
EXPECT_OPT_SIZE = 1572864
EXPECT_JP_SHA = '8f289ac5677508f7c9de12a0117849ed55a0ac861abb0fcefb1e350af6978c04'
EXPECT_JP_CRC = 0x56C05339
EXPECT_JP_SIZE = 1048576

TABLES = [(0x193B5, 694, 0x1DBC5), (0x1DBC5, 110, 0x1E098),
          (0x1E098, 35, 0x1E1D5), (0x1E1D5, 50, 0x1E4CE), (0x1E4CE, 124, 0x1E982)]
EXT_TABLE_ROM = 0x110070
EXT_SLOTS = 76
EXT_TEXT_ROM0 = 0x118000
EXT_TEXT_LIMIT = 0x118740
EXT_PTR_MIN = 0x8000
EXT_PTR_MAX = 0x871D

TEXT_CHANGED = set([(0x193B5, i) for i in (
    109, 122, 136, 156, 316, 327, 352, 389, 390, 392, 393, 411, 449, 452,
    464, 480, 481, 501, 535, 536, 537, 622, 624, 627, 628, 629, 635, 642, 646)]
    + [(0x1E098, 16), (0x1E4CE, 78)])
POINTER_MOVED = set((0x193B5, i) for i in range(623, 628))
CHAINS = set([(0x193B5, i) for i in (389, 390, 392, 393, 627)])
CHAIN_F3_AT = {
    (0x193B5, 389): 0x1BEE0,
    (0x193B5, 390): 0x1BEE0,
    (0x193B5, 392): 0x1BF2C,
    (0x193B5, 393): 0x1BF2C,
    (0x193B5, 627): 0x1D770,
}
DEAD_PROSE_EXT = {'0x348'}
LEADING_F3_EXT = {'0x348'}
BORROWED_TERM_EXT = {'0x347'}
UNRESOLVED_ROWS = [(0x1E4CE, 78)]
TOKEN_MISMATCH_ROWS = [(0x193B5, 501)]
REALIGNED_ROWS = [(0x193B5, 109), (0x193B5, 122), (0x193B5, 452),
                  (0x193B5, 464), (0x1E098, 16)]
EXPECT_STATUS_COUNTS = {
    'reuse-exact': 982,
    'reuse-realigned-meaning-same': 5,
    'reuse-reviewed-updated': 24,
    'reuse-reviewed-updated+token-mismatch': 1,
    'unresolved-source-changed': 1,
    'null-slot-no-text': 1,
    'reuse-reviewed-new-block': 75,
}
EXPECT_TOTAL_ROWS = 1013 + EXT_SLOTS          # 1089
EXPECT_ROWS_WITH_CANDIDATE = 1087
EXPECT_UNRESOLVED = 1

FA_OFF = 0x01FA9E
FB_OFF = 0x01FB9E
TOKEN_RE = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')
CTRL_PREFIX = 0xF2
TERMINATOR = 0xF3


# ------------------------------------------------------------------ decoder
# Independent re-build of the byte -> char map (same documented derivation as
# source/kuniokun_map.py: FA/FB tile tables of the renderer).
def _tile_map():
    TILE = {0x00: ' '}
    TILE.update({0x01: '!', 0x02: '"', 0x03: '\u25bc', 0x04: '\u25b6', 0x05: '\u00d7',
                 0x06: '&', 0x07: "'", 0x08: '(', 0x09: ')', 0x0A: '#', 0x0B: '+',
                 0x0C: ',', 0x0D: '-', 0x0E: '.', 0x0F: '/'})
    for i in range(10):
        TILE[0x10 + i] = chr(ord('0') + i)
    TILE.update({0x1A: ':', 0x1B: ';', 0x1C: '<', 0x1D: '=', 0x1E: '>', 0x1F: '?'})
    TILE[0x20] = ' '
    for i in range(26):
        TILE[0x21 + i] = chr(ord('A') + i)
    TILE.update({0x3B: '[', 0x3C: '\\', 0x3D: ']', 0x3E: '^', 0x3F: '_'})
    TILE.update({0x60: '\u2663', 0x61: '\u2665', 0x62: '\u2660', 0x63: '\u2666',
                 0x64: '\u25a1', 0x65: '\u25a0'})
    TILE.update({0x66: '\u3092', 0x67: '\u3041', 0x68: '\u3043', 0x69: '\u3045',
                 0x6A: '\u3047', 0x6B: '\u3049', 0x6C: '\u3083', 0x6D: '\u3085',
                 0x6E: '\u3087', 0x6F: '\u3063'})
    for i, ch in enumerate('\u3042\u3044\u3046\u3048\u304a\u304b\u304d\u304f\u3051\u3053'
                           '\u3055\u3057\u3059\u305b\u305d\u305f\u3061\u3064\u3066\u3068'
                           '\u306a\u306b\u306c\u306d\u306e\u306f\u3072\u3075\u3078\u307b'
                           '\u307e\u307f\u3080\u3081\u3082\u3084\u3086\u3088'
                           '\u3089\u308a\u308b\u308c\u308d\u308f\u3093\u309b\u309c'):
        TILE[0x71 + i] = ch
    TILE[0xA0] = '\u30fc'
    for i, ch in enumerate('\u30a2\u30a4\u30a6\u30a8\u30aa\u30ab\u30ad\u30af\u30b1\u30b3'
                           '\u30b5\u30b7\u30b9\u30bb\u30bd\u30bf\u30c1\u30c4\u30c6\u30c8'
                           '\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d2\u30d5\u30d8\u30db'
                           '\u30de\u30df\u30e0\u30e1\u30e2\u30e4\u30e6\u30e8'
                           '\u30e9\u30ea\u30eb\u30ec\u30ed\u30ef\u30f3'):
        TILE[0xA1 + i] = ch
    TILE[0xD6] = '\u30f3'
    for i, ch in enumerate('\u30a1\u30a3\u30a5\u30a7\u30a9\u30e3\u30e5\u30e7\u30c3'):
        TILE[0xD7 + i] = ch
    TILE[0xD5] = '\u30fc'
    return TILE


TILE = _tile_map()
_DAKU = dict(zip('\u304b\u304d\u304f\u3051\u3053\u3055\u3057\u3059\u305b\u305d'
                 '\u305f\u3061\u3064\u3066\u3068\u306f\u3072\u3075\u3078\u307b',
                 '\u304c\u304e\u3050\u3052\u3054\u3056\u3058\u305a\u305c\u305e'
                 '\u3060\u3062\u3065\u3067\u3069\u3070\u3073\u3076\u3079\u307c'))
_HAND = dict(zip('\u306f\u3072\u3075\u3078\u307b', '\u3071\u3074\u3077\u307a\u307d'))
_KDAKU = dict(zip('\u30ab\u30ad\u30af\u30b1\u30b3\u30b5\u30b7\u30b9\u30bb\u30bd'
                  '\u30bf\u30c1\u30c4\u30c6\u30c8\u30cf\u30d2\u30d5\u30d8\u30db',
                  '\u30ac\u30ae\u30b0\u30b2\u30b4\u30b6\u30b8\u30ba\u30bc\u30be'
                  '\u30c0\u30c2\u30c5\u30c7\u30c9\u30d0\u30d3\u30d6\u30d9\u30dc'))
_KHAND = dict(zip('\u30cf\u30d2\u30d5\u30d8\u30db', '\u30d1\u30d4\u30d7\u30da\u30dd'))


def build_code(rom):
    fa = rom[FA_OFF:FA_OFF + 256]
    fb = rom[FB_OFF:FB_OFF + 256]
    code = {}
    for c in range(256):
        base = TILE.get(fa[c], '{%02X}' % fa[c])
        if fb[c] == 0x9E:
            base = _DAKU.get(base) or _KDAKU.get(base) or base
        elif fb[c] == 0x9F:
            base = _HAND.get(base) or _KHAND.get(base) or base
        code[c] = base
    for c in range(0xC5, 0x100):
        if c != CTRL_PREFIX:
            code[c] = '{%02X}' % c
    return code


def decode_window(data, off, length, code):
    out = []
    i = 0
    while i < length:
        c = data[off + i]
        if c == CTRL_PREFIX:
            if i + 1 < length:
                out.append('{F2%02X}' % data[off + i + 1])
                i += 2
            else:
                out.append('{F2}')
                i += 1
            continue
        out.append(code[c])
        i += 1
    return ''.join(out)


def token_list(text):
    return [m.group(1).upper() for m in TOKEN_RE.finditer(text)]


def token_check_recompute(cand, opt_text):
    ct = token_list(cand)
    ot = token_list(opt_text)
    if ct == ot:
        return 'match'
    ct2 = [t for t in ct if t != 'F2F6']
    ot2 = [t for t in ot if t != 'F2F6']
    if ct2 == ot2:
        return 'match-modulo-F2F6'
    it = iter(ot2)
    if all(t in it for t in ct2):
        return 'subset-subsequence'
    return 'mismatch'


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def rom_failures(rom, sha, crc, size, label):
    fails = []
    got_sha = hashlib.sha256(rom).hexdigest()
    got_crc = zlib.crc32(rom) & 0xFFFFFFFF
    if len(rom) != size:
        fails.append('%s size %d != %d' % (label, len(rom), size))
    if got_sha != sha:
        fails.append('%s sha256 %s != %s' % (label, got_sha, sha))
    if got_crc != crc:
        fails.append('%s crc32 %08X != %08X' % (label, got_crc, crc))
    return fails


# ------------------------------------------------------- structural checks
def table_failures(rom, inv, jp_by_identity, code):
    fails = []
    seen_changed = set()
    seen_moved = set()
    seen_chain = set()
    if len(inv['tables']) != len(TABLES):
        fails.append('table count %d != %d' % (len(inv['tables']), len(TABLES)))
        return fails
    for spec, t in zip(TABLES, inv['tables']):
        tbl, n, limit = spec
        if t['table_rom_off'] != tbl:
            fails.append('table order mismatch %06X' % t['table_rom_off'])
            continue
        recs = t['records']
        if len(recs) != n:
            fails.append('table %06X entries %d != %d' % (tbl, len(recs), n))
            continue
        prev_ptr = None
        for i, r in enumerate(recs):
            tag = 'table %06X idx %d' % (tbl, i)
            ptr = struct.unpack_from('<H', rom, tbl + 2 * i)[0]
            if r['ptr_value'] != '0x%04X' % ptr:
                fails.append('%s ptr_value %s != %04X' % (tag, r['ptr_value'], ptr))
                continue
            if not (0x8000 <= ptr <= 0xFFFF):
                fails.append('%s ptr out of range %04X' % (tag, ptr))
            start = 0x18000 + (ptr - 0x8000)
            nxt = (0x18000 + (struct.unpack_from('<H', rom, tbl + 2 * (i + 1))[0] - 0x8000)
                   if i + 1 < n else limit)
            if r['text_rom_off'] != '0x%06X' % start:
                fails.append('%s text_rom_off %s != %06X' % (tag, r['text_rom_off'], start))
            raw = rom[start:nxt]
            if r['raw_hex'] != raw.hex():
                fails.append('%s raw_hex mismatch' % tag)
                continue
            if r['nbytes'] != len(raw):
                fails.append('%s nbytes %d != %d' % (tag, r['nbytes'], len(raw)))
            f3i = raw.find(b'\xf3')
            borrowed = False
            if f3i < 0 and raw.endswith(b'\xf2') and start + len(raw) < len(rom) \
                    and rom[start + len(raw)] == 0xF3 and i + 1 < n:
                borrowed = True
                f3i = len(raw)
                raw_eff = raw + bytes([0xF3])
            else:
                raw_eff = raw
            if r['first_f3_byte_off'] != f3i:
                fails.append('%s first_f3 %s != %s' % (tag, r['first_f3_byte_off'], f3i))
            if r['terminator_borrowed_from_next_slice'] != borrowed:
                fails.append('%s borrowed flag mismatch' % tag)
            live = (f3i + 1) if f3i >= 0 else None
            if r['live_nbytes'] != live:
                fails.append('%s live_nbytes %s != %s' % (tag, r['live_nbytes'], live))
            dead = raw_eff[live:] if live is not None else b''
            if r['dead_len'] != len(dead) or r['dead_hex'] != dead[:512].hex():
                fails.append('%s dead span mismatch' % tag)
            if i + 1 >= n and f3i >= 0:
                text = decode_window(rom, start, live, code)
            else:
                text = decode_window(rom, start, len(raw_eff), code)
            slice_text = decode_window(rom, start, len(raw), code)
            if r['text'] != text:
                fails.append('%s text decode mismatch' % tag)
            if r['slice_text'] != slice_text:
                fails.append('%s slice_text mismatch' % tag)
            if r['tokens'] != token_list(text):
                fails.append('%s tokens mismatch' % tag)
            jp = jp_by_identity.get((tbl, i))
            if jp is None:
                fails.append('%s missing JP identity record' % tag)
            else:
                if r['jp_text_rom_off'] != '0x%06X' % jp['text_rom_off']:
                    fails.append('%s jp_text_rom_off mismatch' % tag)
                if r['jp_text'] != jp['text']:
                    fails.append('%s jp_text mismatch' % tag)
                if r['pointer_moved'] != (jp['ptr_value'] != ptr):
                    fails.append('%s pointer_moved mismatch' % tag)
                if r['text_changed'] != (text != jp['text']):
                    fails.append('%s text_changed mismatch' % tag)
                if r['pointer_moved']:
                    seen_moved.add((tbl, i))
                if r['text_changed']:
                    seen_changed.add((tbl, i))
            if i + 1 < n and not (start < nxt):
                fails.append('%s non-monotonic pointer %04X' % (tag, ptr))
            prev_ptr = ptr
    if seen_changed != TEXT_CHANGED:
        fails.append('text-changed set mismatch: missing %s extra %s'
                     % (sorted(TEXT_CHANGED - seen_changed), sorted(seen_changed - TEXT_CHANGED)))
    if seen_moved != POINTER_MOVED:
        fails.append('pointer-moved set mismatch: %s vs %s' % (sorted(seen_moved), sorted(POINTER_MOVED)))
    # chains
    for spec, t in zip(TABLES, inv['tables']):
        tbl, n, limit = spec
        for i, r in enumerate(t['records']):
            if r['first_f3_byte_off'] is not None and r['first_f3_byte_off'] < 0:
                seen_chain.add((tbl, i))
    if seen_chain != CHAINS:
        fails.append('chain set mismatch: %s vs %s' % (sorted(seen_chain), sorted(CHAINS)))
    # chain f3 location and run
    chain_records = {c['table_rom_off'] * 0x10000 + c['index']: c for c in inv['chains']}
    table_counts = dict((tb, cnt) for tb, cnt, _ in TABLES)
    table_limits = dict((tb, lm) for tb, _, lm in TABLES)
    for (tbl, i) in sorted(CHAINS):
        recs = next(t for t in inv['tables'] if t['table_rom_off'] == tbl)['records']
        start = int(recs[i]['text_rom_off'], 16)
        n = table_counts[tbl]
        limit = table_limits[tbl]
        hit = rom.find(b'\xf3', start, limit)
        key = tbl * 0x10000 + i
        if key not in chain_records:
            fails.append('chain record missing for %06X idx %d' % (tbl, i))
            continue
        cr = chain_records[key]
        if cr['f3_found_at'] != ('0x%06X' % hit) or hit != CHAIN_F3_AT[(tbl, i)]:
            fails.append('chain f3 %06X idx %d: %s/expected %06X'
                         % (tbl, i, cr['f3_found_at'], CHAIN_F3_AT[(tbl, i)]))
        consumed = []
        j = i + 1
        while j < n and int(recs[j]['text_rom_off'], 16) <= hit:
            consumed.append(recs[j]['index'])
            j += 1
        if cr['following_indexes_consumed'] != consumed:
            fails.append('chain consumed list mismatch %06X idx %d' % (tbl, i))
    if len(chain_records) != len(CHAINS):
        fails.append('chains list has %d records, expected %d' % (len(chain_records), len(CHAINS)))
    # duplicate pointer groups must be empty
    if inv['duplicate_pointers']['within_table_groups']:
        fails.append('duplicate within-table pointer groups recorded')
    if inv['duplicate_pointers']['cross_table_groups']:
        fails.append('duplicate cross-table pointer groups recorded')
    return fails


def extended_failures(rom, inv, new_text_src, code):
    fails = []
    ext = inv['extended_table']
    if ext['table_rom_off'] != EXT_TABLE_ROM or ext['slots'] != EXT_SLOTS:
        fails.append('extended table header mismatch')
    recs = ext['records']
    if len(recs) != EXT_SLOTS:
        fails.append('extended slots %d != %d' % (len(recs), EXT_SLOTS))
        return fails
    src_by_id = {e['id']: e for e in new_text_src}
    if len(src_by_id) != EXT_SLOTS - 1:
        fails.append('optimization-new-text.json entries %d != %d' % (len(src_by_id), EXT_SLOTS - 1))
    null_slot = recs[0]
    if not null_slot.get('null_slot') or null_slot['ptr_value'] != '0x0000':
        fails.append('slot 0 / id 0x300 is not the null slot (ptr %s)' % null_slot['ptr_value'])
    seen_dead = set()
    seen_leading = set()
    seen_borrowed = set()
    prev = None
    for i, r in enumerate(recs):
        idn = 0x300 + i
        tag = 'ext id 0x%03X' % idn
        ptr = struct.unpack_from('<H', rom, EXT_TABLE_ROM + 2 * i)[0]
        if r['id'] != '0x%03X' % idn:
            fails.append('%s id mismatch %s' % (tag, r['id']))
        if r['ptr_value'] != '0x%04X' % ptr:
            fails.append('%s ptr_value %s != %04X' % (tag, r['ptr_value'], ptr))
            continue
        if i == 0:
            if ptr != 0:
                fails.append('id 0x300 pointer %04X != 0' % ptr)
            continue
        if not (EXT_PTR_MIN <= ptr <= EXT_PTR_MAX):
            fails.append('%s ptr %04X out of [%04X,%04X]' % (tag, ptr, EXT_PTR_MIN, EXT_PTR_MAX))
        start = EXT_TEXT_ROM0 + (ptr - 0x8000)
        nxt = (EXT_TEXT_ROM0 + (struct.unpack_from('<H', rom, EXT_TABLE_ROM + 2 * (i + 1))[0] - 0x8000)
               if i + 1 < EXT_SLOTS else EXT_TEXT_LIMIT)
        if r['text_rom_off'] != '0x%06X' % start:
            fails.append('%s text_rom_off %s != %06X' % (tag, r['text_rom_off'], start))
        raw = rom[start:nxt]
        if r['raw_hex'] != raw.hex():
            fails.append('%s raw_hex mismatch' % tag)
            continue
        if r['nbytes'] != len(raw):
            fails.append('%s nbytes mismatch' % tag)
        f3i = raw.find(b'\xf3')
        borrowed = False
        if f3i < 0 and raw.endswith(b'\xf2') and start + len(raw) < len(rom) \
                and rom[start + len(raw)] == 0xF3:
            borrowed = True
            f3i = len(raw)
            raw_eff = raw + bytes([0xF3])
        else:
            raw_eff = raw
        if r['first_f3_byte_off'] != f3i:
            fails.append('%s first_f3 mismatch' % tag)
        if r['terminator_borrowed_from_next_slice'] != borrowed:
            fails.append('%s borrowed flag mismatch' % tag)
        live = (f3i + 1) if f3i >= 0 else None
        if r['live_nbytes'] != live:
            fails.append('%s live_nbytes mismatch' % tag)
        dead = raw_eff[live:] if live is not None else b''
        if r['dead_len'] != len(dead) or r['dead_hex'] != dead[:512].hex():
            fails.append('%s dead span mismatch' % tag)
        text = decode_window(rom, start, len(raw_eff), code)
        if r['text'] != text or r['tokens'] != token_list(text):
            fails.append('%s text/tokens mismatch' % tag)
        if r['slice_text'] != decode_window(rom, start, len(raw), code):
            fails.append('%s slice_text mismatch' % tag)
        dead_prose = False
        if f3i >= 0 and dead:
            for ch in decode_window(rom, start + f3i + 1, len(dead), code):
                if ch != ' ' and not ch.startswith('{'):
                    dead_prose = True
                    break
        if r['dead_has_prose'] != dead_prose:
            fails.append('%s dead_has_prose %s != %s' % (tag, r['dead_has_prose'], dead_prose))
        if dead_prose:
            seen_dead.add(r['id'])
        if raw.startswith(b'\xf3'):
            seen_leading.add(r['id'])
        if borrowed:
            seen_borrowed.add(r['id'])
        e = src_by_id.get(idn)
        if e is None:
            fails.append('%s missing in optimization-new-text.json' % tag)
            continue
        if e['offset'] != start or e['length'] != len(raw) or e['text'] != text:
            fails.append('%s source cross-check mismatch' % tag)
        if prev is not None and nxt != start:
            pass
        prev = start
    if seen_dead != DEAD_PROSE_EXT:
        fails.append('dead-prose ext set %s != %s' % (sorted(seen_dead), sorted(DEAD_PROSE_EXT)))
    if seen_leading != LEADING_F3_EXT:
        fails.append('leading-F3 set %s != %s' % (sorted(seen_leading), sorted(LEADING_F3_EXT)))
    if seen_borrowed != BORROWED_TERM_EXT:
        fails.append('borrowed-terminator set %s != %s' % (sorted(seen_borrowed), sorted(BORROWED_TERM_EXT)))
    # boundaries
    last = recs[-1]
    if last['id'] != '0x34B':
        fails.append('last extended id %s != 0x34B' % last['id'])
    if int(last['text_rom_off'], 16) + last['live_nbytes'] != EXT_TEXT_LIMIT:
        fails.append('last extended live end != 0x%06X' % EXT_TEXT_LIMIT)
    if any(b != 0 for b in rom[EXT_TEXT_LIMIT:EXT_TEXT_LIMIT + 0xC0]):
        fails.append('non-zero padding after the extended text block')
    if struct.unpack_from('<H', rom, EXT_TABLE_ROM + 2 * EXT_SLOTS)[0] != 0:
        fails.append('word after the extended table is not zero')
    if len(ext['source_cross_check_mismatches']) != 0:
        fails.append('extended source cross-check listed mismatches')
    # id relations sanity
    rel = inv['id_relations']['new_block_relations']
    if len(rel) != EXT_SLOTS or rel[0]['relation'] != 'null_boundary_slot':
        fails.append('new_block_relations list malformed')
    return fails


# ------------------------------------------------------ candidate checks
def candidate_failures(cand, inv, cn_reviewed, cn_existing, cn_new, jp_by_identity, rom, code):
    fails = []
    rows = cand['candidates']
    if len(rows) != EXPECT_TOTAL_ROWS:
        fails.append('candidate rows %d != %d' % (len(rows), EXPECT_TOTAL_ROWS))
    jp_index = {}
    for t in inv['tables']:
        for r in t['records']:
            jp_index[(t['table_rom_off'], r['index'])] = r
    table_counts = dict((tb, cnt) for tb, cnt, _ in TABLES)
    table_limits = dict((tb, lm) for tb, _, lm in TABLES)
    seen = set()
    status_counts = Counter()
    unresolved_rows = []
    mismatch_rows = []
    realigned_rows = []
    rows_with = 0
    for row in rows:
        ident = row['identity']
        tbl = ident.get('table_rom_off')
        key = (tbl, ident.get('index'), ident.get('slot'))
        if key in seen:
            fails.append('duplicate candidate identity %s' % (key,))
        seen.add(key)
        status = row['status']
        status_counts[status] += 1
        if row['candidate_cn'] is not None:
            rows_with += 1
            prov = row['provenance']
            c = row['candidate_cn']
            if prov == 'cn_translation.json':
                inv_row = jp_index[(tbl, ident['index'])]
                k = '%06X' % int(inv_row['jp_text_rom_off'], 16)
                if cn_reviewed.get(k) != c:
                    fails.append('candidate != cn_translation.json[%s]' % k)
            elif prov == 'optimization-existing-cn.json':
                k = '%03X' % int(ident['id'], 16)
                if cn_existing.get(k) != c:
                    fails.append('candidate != optimization-existing-cn.json[%s]' % k)
            elif prov == 'optimization-cn-text.json':
                k = '%03X' % int(ident['id'], 16)
                if cn_new.get(k) != c:
                    fails.append('candidate != optimization-cn-text.json[%s]' % k)
            else:
                fails.append('unknown provenance %r' % prov)
            # token check recompute (own slice)
            want = token_check_recompute(c, row['opt_text'])
            if row['token_check'] is None or row['token_check']['status'] != want:
                fails.append('token_check status %s != recomputed %s for %s'
                             % ((row['token_check'] or {}).get('status'), want, key))
            # chain-run check recompute
            tkey = (tbl, ident.get('index'))
            run_status = None
            if tkey in CHAINS and tbl in table_counts:
                recs = next(t for t in inv['tables'] if t['table_rom_off'] == tbl)['records']
                start = int(recs[ident['index']]['text_rom_off'], 16)
                hit = rom.find(b'\xf3', start, table_limits[tbl])
                if hit >= 0:
                    run_text = decode_window(rom, start, hit + 1 - start, code)
                    run_status = token_check_recompute(c, run_text)
                rec = row.get('chain_run_check')
                if rec is None or rec['status'] != run_status:
                    fails.append('chain_run_check %s != recomputed %s for %s'
                                 % ((rec or {}).get('status'), run_status, key))
            # the +token-mismatch suffix is only expected when the own-slice check
            # fails AND the chain run (if any) does not rescue the candidate
            expect_flag = (want == 'mismatch'
                           and (run_status is None
                                or run_status not in ('match', 'match-modulo-F2F6',
                                                      'subset-subsequence')))
            has_flag = 'token-mismatch' in status
            if has_flag != expect_flag:
                fails.append('token-mismatch flag %s but expected %s for %s'
                             % (has_flag, expect_flag, key))
            if has_flag:
                mismatch_rows.append(key)
        else:
            if status not in ('unresolved-source-changed', 'null-slot-no-text'):
                fails.append('row without candidate has status %s' % status)
            if row.get('token_check') is not None:
                fails.append('row without candidate has a token_check')
        if status == 'reuse-realigned-meaning-same':
            realigned_rows.append(key)
        if status.startswith('unresolved'):
            unresolved_rows.append(key)
    exp_mismatch = [(t, i, None) for t, i in TOKEN_MISMATCH_ROWS]
    if sorted(mismatch_rows) != sorted(exp_mismatch):
        fails.append('token-mismatch rows %s != expected %s' % (mismatch_rows, exp_mismatch))
    exp_real = [(t, i, None) for t, i in REALIGNED_ROWS]
    if sorted(realigned_rows) != sorted(exp_real):
        fails.append('realigned rows %s != expected %s' % (realigned_rows, exp_real))
    exp_uns = [(t, i, None) for t, i in UNRESOLVED_ROWS]
    if sorted(unresolved_rows) != sorted(exp_uns):
        fails.append('unresolved rows %s != expected %s' % (unresolved_rows, exp_uns))
    if dict(status_counts) != EXPECT_STATUS_COUNTS:
        fails.append('status counts %s != expected %s' % (dict(status_counts), EXPECT_STATUS_COUNTS))
    if rows_with != EXPECT_ROWS_WITH_CANDIDATE:
        fails.append('rows with candidate %d != %d' % (rows_with, EXPECT_ROWS_WITH_CANDIDATE))
    # unresolved list consistency
    unl = cand['unresolved']
    if len(unl) != EXPECT_UNRESOLVED:
        fails.append('unresolved list length %d != %d' % (len(unl), EXPECT_UNRESOLVED))
    else:
        u = unl[0]['identity']
        if (u['table_rom_off'], u['index']) != UNRESOLVED_ROWS[0]:
            fails.append('unresolved identity %s != %s' % (u, UNRESOLVED_ROWS[0]))
    # denominators block
    d = cand['meta']['denominators']
    if (d['table_entries'], d['extended_slots'], d['extended_text_entries'],
            d['candidate_rows'], d['rows_with_candidate'], d['rows_unresolved'],
            d['null_slot_rows']) != (1013, EXT_SLOTS, EXT_SLOTS - 1, EXPECT_TOTAL_ROWS,
                                     EXPECT_ROWS_WITH_CANDIDATE, EXPECT_UNRESOLVED, 1):
        fails.append('denominators block disagrees with expected totals')
    if sum(d['by_status'].values()) != EXPECT_TOTAL_ROWS:
        fails.append('by_status sum %d != %d' % (sum(d['by_status'].values()), EXPECT_TOTAL_ROWS))
    return fails


# ------------------------------------------------------------- selftests
def run_selftests(opt, jp, inv, cand, cn_reviewed, cn_existing, cn_new, jp_by_identity,
                  new_text_src, code):
    """Negative cases: each tampered copy must be rejected by the same checks."""
    cases = []

    def rec(name, detected):
        cases.append({'name': name, 'expect': 'detected', 'observed': 'detected' if detected else 'MISSED'})

    tam = bytearray(opt)
    tam[0x110070] ^= 0xFF
    rec('rom tamper breaks SHA check',
        len(rom_failures(bytes(tam), EXPECT_OPT_SHA, EXPECT_OPT_CRC, EXPECT_OPT_SIZE, 'opt')) > 0)

    inv2 = copy.deepcopy(inv)
    inv2['tables'][0]['records'][0]['ptr_value'] = '0x9922'
    rec('table pointer tamper detected', len(table_failures(opt, inv2, jp_by_identity, code)) > 0)

    inv3 = copy.deepcopy(inv)
    inv3['tables'][0]['records'][5]['raw_hex'] = 'ff' + inv3['tables'][0]['records'][5]['raw_hex'][2:]
    rec('recorded raw bytes tamper detected', len(table_failures(opt, inv3, jp_by_identity, code)) > 0)

    inv4 = copy.deepcopy(inv)
    inv4['extended_table']['records'][0]['ptr_value'] = '0x8000'
    rec('null boundary slot tamper detected',
        len(extended_failures(opt, inv4, new_text_src, code)) > 0)

    inv5 = copy.deepcopy(inv)
    inv5['extended_table']['records'][0x348 - 0x300]['dead_has_prose'] = False
    rec('dead-text flag tamper detected',
        len(extended_failures(opt, inv5, new_text_src, code)) > 0)

    cand2 = copy.deepcopy(cand)
    cand2['candidates'][0]['candidate_cn'] = (cand2['candidates'][0]['candidate_cn'] or '') + 'x'
    rec('candidate text tamper detected',
        len(candidate_failures(cand2, inv, cn_reviewed, cn_existing, cn_new, jp_by_identity,
                               opt, code)) > 0)

    cand3 = copy.deepcopy(cand)
    cand3['candidates'].pop()
    rec('row-count tamper detected',
        len(candidate_failures(cand3, inv, cn_reviewed, cn_existing, cn_new, jp_by_identity,
                               opt, code)) > 0)

    inv6 = copy.deepcopy(inv)
    for t in inv6['tables'][0]['records']:
        if t['index'] in (389, 390, 392, 393):
            t['first_f3_byte_off'] = 0
            t['dead_hex'] = ''
            t['dead_len'] = 0
    rec('chain entry tamper detected', len(table_failures(opt, inv6, jp_by_identity, code)) > 0)

    return cases


# ------------------------------------------------------------------ main
def main():
    results = {'generated_by': 'inventory-worker/validate_native_inventory.py'}
    checks = []
    hard_fails = []

    inputs = json.load(open(os.path.join(WORK, 'inputs.json'), encoding='utf-8'))
    opt = open(inputs['opt']['path'], 'rb').read()
    jp = open(inputs['jp']['path'], 'rb').read()

    f = rom_failures(opt, EXPECT_OPT_SHA, EXPECT_OPT_CRC, EXPECT_OPT_SIZE, 'optimized ROM')
    checks.append({'id': 'rom.opt.fixed_sha', 'desc': 'optimized ROM sha256/crc32/size fixed values',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f})
    hard_fails += f
    f = rom_failures(jp, EXPECT_JP_SHA, EXPECT_JP_CRC, EXPECT_JP_SIZE, 'jp ROM')
    checks.append({'id': 'rom.jp.fixed_sha', 'desc': 'JP ROM sha256/crc32/size fixed values',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f})
    hard_fails += f
    f = []
    if inputs['opt']['sha256'] != EXPECT_OPT_SHA or inputs['jp']['sha256'] != EXPECT_JP_SHA:
        f.append('inputs.json hashes disagree with the pinned values')
    checks.append({'id': 'inputs.cross_check', 'desc': 'inputs.json hashes agree with fixed values',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f})
    hard_fails += f

    code_opt = build_code(opt)
    code_jp = build_code(jp)
    f = [] if code_opt == code_jp else ['FA/FB decoder tables differ between JP and optimized ROM']
    checks.append({'id': 'decoder.stability', 'desc': 'FA/FB byte->char tables identical in both ROMs',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f})
    hard_fails += f

    inv = json.load(open(os.path.join(BASE, 'native-inventory.json'), encoding='utf-8'))
    cand = json.load(open(os.path.join(BASE, 'candidate-translations.json'), encoding='utf-8'))
    jp_records = json.load(open(os.path.join(WORK, 'source', 'kuniokun_text.json'), encoding='utf-8'))
    cn_reviewed = json.load(open(os.path.join(WORK, 'source', 'cn_translation.json'), encoding='utf-8'))
    cn_existing = json.load(open(os.path.join(WORK, 'optimization-existing-cn.json'), encoding='utf-8'))
    cn_new = json.load(open(os.path.join(WORK, 'optimization-cn-text.json'), encoding='utf-8'))
    new_text_src = json.load(open(os.path.join(WORK, 'optimization-new-text.json'), encoding='utf-8'))
    jp_by_identity = {(r['table_rom_off'], r['index']): r for r in jp_records}
    if len(jp_by_identity) != 1013:
        hard_fails.append('kuniokun_text.json identity count %d != 1013' % len(jp_by_identity))

    # decoder vs stored JP records (the previously verified extraction)
    f = []
    for r in jp_records:
        if decode_window(jp, r['text_rom_off'], r['nbytes'], code_jp) != r['text']:
            f.append('JP record %06X/%d decode mismatch' % (r['table_rom_off'], r['index']))
    checks.append({'id': 'decoder.jp_records', 'desc': 'JP text records re-decode with 0 mismatches',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f[:10]})
    hard_fails += f

    f = table_failures(opt, inv, jp_by_identity, code_opt)
    checks.append({'id': 'tables.entries', 'desc': 'five original tables: every pointer/offset/byte/'
                   'decode/token/dead-span/JID relation recomputed from the ROM',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f[:20]})
    hard_fails += f

    f = extended_failures(opt, inv, new_text_src, code_opt)
    checks.append({'id': 'extended.boundary', 'desc': 'extended $22:8070 table: 76 slots, null slot 0x300, '
                   'text block bounds, per-slot decode and source cross-check',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f[:20]})
    hard_fails += f

    f = candidate_failures(cand, inv, cn_reviewed, cn_existing, cn_new, jp_by_identity,
                           opt, code_opt)
    checks.append({'id': 'candidates.denominators', 'desc': 'candidate rows, provenance identity, token '
                   'checks, status partition, unresolved list and denominators',
                   'status': 'PASS' if not f else 'FAIL', 'detail': f[:20]})
    hard_fails += f

    selftests = run_selftests(opt, jp, inv, cand, cn_reviewed, cn_existing, cn_new,
                              jp_by_identity, new_text_src, code_opt)
    sel_fail = [c for c in selftests if c['observed'] != c['expect']]
    checks.append({'id': 'selftest.negatives', 'desc': 'tampered inputs (ROM byte, pointer, raw bytes, '
                   'null slot, dead flag, candidate text, row count, chain entry) are rejected',
                   'status': 'PASS' if not sel_fail else 'FAIL', 'detail': sel_fail})
    hard_fails += ['selftest %s not detected' % c['name'] for c in sel_fail]

    counts = {
        'tables_total_entries': 1013,
        'extended_slots': EXT_SLOTS,
        'extended_text_entries': EXT_SLOTS - 1,
        'candidate_rows': len(cand['candidates']),
        'rows_with_candidate': sum(1 for r in cand['candidates'] if r['candidate_cn'] is not None),
        'rows_unresolved': sum(1 for r in cand['candidates'] if r['status'].startswith('unresolved')),
        'text_changed_entries': len(TEXT_CHANGED),
        'pointer_moved_entries': len(POINTER_MOVED),
        'chains': len(CHAINS),
    }
    results['status'] = 'PASS' if not hard_fails else 'FAIL'
    results['checks'] = checks
    results['selftest'] = selftests
    results['counts'] = counts
    results['unresolved_reported'] = cand['unresolved']
    results['failures'] = hard_fails

    with open(os.path.join(BASE, 'results.json'), 'w', encoding='utf-8') as fh:
        json.dump(results, fh, ensure_ascii=False, indent=1)

    for c in checks:
        print('%-24s %s %s' % (c['id'], c['status'],
                               ('(%d detail rows)' % len(c['detail'])) if c['detail'] else ''))
    print('selftests:', ' '.join('%s=%s' % (c['name'].split()[0], c['observed']) for c in selftests))
    print('status:', results['status'])
    print('written: %s' % os.path.join(BASE, 'results.json'))
    return 0 if results['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
