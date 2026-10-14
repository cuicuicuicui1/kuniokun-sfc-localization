# -*- coding: utf-8 -*-
"""Native text inventory of the player's optimized ROM ("初代熱血硬派 V4.1e").

This script re-extracts every native text entry straight from the optimized
ROM (no patch-over of any older Chinese build):

  * the five original pointer tables in bank $03 (ROM 0x193B5 / 0x1DBC5 /
    0x1E098 / 0x1E1D5 / 0x1E4CE, counts 694/110/35/50/124), resolved through
    their own resolvers ($03:EB7F, $03:ED08, $03:EDB5, $03:EDCC, $03:EE11,
    each adding a per-table base word stored at $03:EAEB..$03:EAF3);
  * the optimizer's extended pointer table at CPU $22:8070 (ROM 0x110070),
    76 slots indexed by (message id - 0x300) for ids 0x300..0x34B; slot 0
    (id 0x300) is the null/boundary slot; the text lives in bank $23
    (ROM 0x118000..0x118740).

Engine semantics used for the F3/dead-text bookkeeping (verified by linear
disassembly of the optimized ROM, $03:EB9E..$03:EBCE):

    03:EBBF  CMP #$F3 / BEQ $EBDB      -> the loader stops at the FIRST $F3
    03:EBC3  CMP #$F0 / BCS $EBD0      -> $F0-$FF are control bytes
    03:EBC7  CMP #$E0 / BCC $EBD0      -> $C5-$DF and $00-$DF: plain codes
    03:EBCB  JSR $EBFC                 -> $E0-$EF macro dispatch
    the $F2 byte returns from the loader (pace/step); the byte AFTER $F2 is
    classified on the next call -- so the conventional "{F2xx}" display token
    is really two independent bytes.

Every byte behind the first $F3 of an entry is dead (the loader has already
left).  Entries whose slice contains no $F3 chain into the following entries'
bytes until the next $F3 (the optimizer did this on purpose for ids 186, 187,
189, 18A and 274 -- see the chain report).

Outputs (written next to this script):
    native-inventory.json      - full per-entry inventory + relations/notes
    candidate-translations.json- reviewed-Chinese reuse candidates per entry

Reads (all read-only):
    ../inputs.json
    the optimized ROM (path+SHA fixed in inputs.json, re-verified here)
    the JP ROM (only for the ID-relation cross-check and the decoder check)
    ../source/kuniokun_text.json        (original JP text records)
    ../source/cn_translation.json       (reviewed CN, keyed by JP text offset)
    ../optimization-existing-cn.json    (reviewed CN for changed originals, by id)
    ../optimization-cn-text.json        (CN for the new block, by id)
    ../optimization-new-text.json       (cross-check of the new block)

Standard library only.
"""

import hashlib
import json
import os
import re
import struct
import sys
import zlib
from collections import Counter, OrderedDict, defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.dirname(BASE)

EXPECT_OPT_SHA = '2008f9b34d2b48a168824c8c7d1e3c8924dbb0fa81de9a4eeff2823a635ffe08'
EXPECT_OPT_CRC = 0x65D66D5D
EXPECT_JP_SHA = '8f289ac5677508f7c9de12a0117849ed55a0ac861abb0fcefb1e350af6978c04'
EXPECT_JP_CRC = 0x56C05339

# (table_rom_off, count, text_region_limit) -- limit is the first byte that
# cannot belong to the table's text (the next table or the $EA macro table).
TABLES = [
    (0x193B5, 694, 0x1DBC5),
    (0x1DBC5, 110, 0x1E098),
    (0x1E098, 35, 0x1E1D5),
    (0x1E1D5, 50, 0x1E4CE),
    (0x1E4CE, 124, 0x1E982),
]
TABLE_RESOLVERS = {
    0x193B5: {'resolver_cpu': '$03:EB7F', 'base_word_cpu': '$03:EAEB'},
    0x1DBC5: {'resolver_cpu': '$03:ED08', 'base_word_cpu': '$03:EAED'},
    0x1E098: {'resolver_cpu': '$03:EDB5', 'base_word_cpu': '$03:EAEF'},
    0x1E1D5: {'resolver_cpu': '$03:EDCC', 'base_word_cpu': '$03:EAF1'},
    0x1E4CE: {'resolver_cpu': '$03:EE11', 'base_word_cpu': '$03:EAF3'},
}

EXT_TABLE_ROM = 0x110070          # CPU $22:8070
EXT_TABLE_SLOTS = 76              # ids 0x300..0x34B
EXT_ID_BASE = 0x300
EXT_TEXT_ROM0 = 0x118000          # CPU $23:8000
EXT_TEXT_LIMIT = 0x118740         # first byte after the new text block
EXT_RESOLVER_CPU = '$22:8000'     # LDA $034B / CMP #$03 / BCS new path
EXT_READER_CPU = '$22:8050'       # bank $23 byte reader for ids >= 0x300

CTRL_PREFIX = 0xF2                # pace/step byte: loader returns after it
TERMINATOR = 0xF3                 # loader stops at the first $F3 byte

# ------------------------------------------------------------------ decoding
# Byte -> character table, exactly as source/kuniokun_map.py (verified against
# the rendered font glyphs): tilemap entry = FB[code] | FA[code] | 0x2400,
# FA = ROM 0x01FA9E, FB = ROM 0x01FB9E.  Both tables are byte-identical in the
# JP and the optimized ROM, so the optimized ROM's own tables are used here.
FA_OFF = 0x01FA9E
FB_OFF = 0x01FB9E

TILE = {0x00: ' '}
TILE.update({0x01: '!', 0x02: '"', 0x03: '\u25bc', 0x04: '\u25b6', 0x05: '\u00d7',
             0x06: '&', 0x07: "'", 0x08: '(', 0x09: ')', 0x0A: '#', 0x0B: '+',
             0x0C: ',', 0x0D: '-', 0x0E: '.', 0x0F: '/'})
for _i in range(10):
    TILE[0x10 + _i] = chr(ord('0') + _i)
TILE.update({0x1A: ':', 0x1B: ';', 0x1C: '<', 0x1D: '=', 0x1E: '>', 0x1F: '?'})
TILE[0x20] = ' '
for _i in range(26):
    TILE[0x21 + _i] = chr(ord('A') + _i)
TILE.update({0x3B: '[', 0x3C: '\\', 0x3D: ']', 0x3E: '^', 0x3F: '_'})
TILE.update({0x60: '\u2663', 0x61: '\u2665', 0x62: '\u2660', 0x63: '\u2666',
             0x64: '\u25a1', 0x65: '\u25a0'})
TILE.update({0x66: '\u3092', 0x67: '\u3041', 0x68: '\u3043', 0x69: '\u3045',
             0x6A: '\u3047', 0x6B: '\u3049', 0x6C: '\u3083', 0x6D: '\u3085',
             0x6E: '\u3087', 0x6F: '\u3063'})
_HIRA = ('\u3042\u3044\u3046\u3048\u304a\u304b\u304d\u304f\u3051\u3053'
         '\u3055\u3057\u3059\u305b\u305d\u305f\u3061\u3064\u3066\u3068'
         '\u306a\u306b\u306c\u306d\u306e\u306f\u3072\u3075\u3078\u307b'
         '\u307e\u307f\u3080\u3081\u3082\u3084\u3086\u3088'
         '\u3089\u308a\u308b\u308c\u308d\u308f\u3093\u309b\u309c')
for _i, _ch in enumerate(_HIRA):
    TILE[0x71 + _i] = _ch
TILE[0xA0] = '\u30fc'
_KATA = ('\u30a2\u30a4\u30a6\u30a8\u30aa\u30ab\u30ad\u30af\u30b1\u30b3'
         '\u30b5\u30b7\u30b9\u30bb\u30bd\u30bf\u30c1\u30c4\u30c6\u30c8'
         '\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d2\u30d5\u30d8\u30db'
         '\u30de\u30df\u30e0\u30e1\u30e2\u30e4\u30e6\u30e8'
         '\u30e9\u30ea\u30eb\u30ec\u30ed\u30ef\u30f3')
for _i, _ch in enumerate(_KATA):
    TILE[0xA1 + _i] = _ch
TILE[0xD6] = '\u30f3'
for _i, _ch in enumerate('\u30a1\u30a3\u30a5\u30a7\u30a9\u30e3\u30e5\u30e7\u30c3'):
    TILE[0xD7 + _i] = _ch
TILE[0xD5] = '\u30fc'

_DAKU = dict(zip('\u304b\u304d\u304f\u3051\u3053\u3055\u3057\u3059\u305b\u305d'
                 '\u305f\u3061\u3064\u3066\u3068\u306f\u3072\u3075\u3078\u307b',
                 '\u304c\u304e\u3050\u3052\u3054\u3056\u3058\u305a\u305c\u305e'
                 '\u3060\u3062\u3065\u3067\u3069\u3070\u3073\u3076\u3079\u307c'))
_HAND = dict(zip('\u306f\u3072\u3075\u3078\u307b',
                 '\u3071\u3074\u3077\u307a\u307d'))
_KDAKU = dict(zip('\u30ab\u30ad\u30af\u30b1\u30b3\u30b5\u30b7\u30b9\u30bb\u30bd'
                  '\u30bf\u30c1\u30c4\u30c6\u30c8\u30cf\u30d2\u30d5\u30d8\u30db',
                  '\u30ac\u30ae\u30b0\u30b2\u30b4\u30b6\u30b8\u30ba\u30bc\u30be'
                  '\u30c0\u30c2\u30c5\u30c7\u30c9\u30d0\u30d3\u30d6\u30d9\u30dc'))
_KHAND = dict(zip('\u30cf\u30d2\u30d5\u30d8\u30db',
                  '\u30d1\u30d4\u30d7\u30da\u30dd'))


def _combine(base, overlay):
    if overlay == 0x9E:
        return _DAKU.get(base) or _KDAKU.get(base) or base
    if overlay == 0x9F:
        return _HAND.get(base) or _KHAND.get(base) or base
    return base


def build_code(rom):
    """CODE[byte] -> char or '{XX}' placeholder, from the ROM's FA/FB tables."""
    fa = rom[FA_OFF:FA_OFF + 256]
    fb = rom[FB_OFF:FB_OFF + 256]
    code = {}
    for c in range(256):
        base = TILE.get(fa[c], '{%02X}' % fa[c])
        code[c] = _combine(base, fb[c])
    for c in range(0xC5, 0x100):
        if c != CTRL_PREFIX:
            code[c] = '{%02X}' % c
    return code


TOKEN_RE = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')


def decode_window(data, off, length, code):
    """Decode exactly `length` bytes starting at `off` (no over-read).

    Conventional display tokens: [$F2 b] -> one '{F2xx}' token; a trailing
    lone $F2 with no byte after it inside the window is reported as '{F2}'.
    """
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


def prose(text):
    # TOKEN_RE.split keeps the tokens as odd-indexed elements; prose is even
    return ''.join(TOKEN_RE.split(text)[0::2])


def fold(s):
    """Normalisation for meaning comparison: drop spaces, fold katakana."""
    out = []
    for ch in s:
        if ch.isspace():
            continue
        o = ord(ch)
        if 0x30A1 <= o <= 0x30F6:      # katakana -> hiragana
            ch = chr(o - 0x60)
        out.append(ch)
    return ''.join(out)


def cpu_of(rom_off):
    return '$%02X:%04X' % (rom_off // 0x8000, 0x8000 + (rom_off % 0x8000))


def find_next_f3(rom, start, limit):
    i = rom.find(b'\xf3', start, limit)
    return i


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    inputs = json.load(open(os.path.join(WORK, 'inputs.json'), encoding='utf-8'))
    opt_path = inputs['opt']['path']
    jp_path = inputs['jp']['path']

    opt = open(opt_path, 'rb').read()
    jp = open(jp_path, 'rb').read()
    opt_sha = sha256_of(opt_path)
    jp_sha = sha256_of(jp_path)
    opt_crc = zlib.crc32(opt) & 0xFFFFFFFF
    jp_crc = zlib.crc32(jp) & 0xFFFFFFFF
    checks = {
        'opt_sha_match': opt_sha == EXPECT_OPT_SHA,
        'opt_crc_match': opt_crc == EXPECT_OPT_CRC,
        'opt_size': len(opt),
        'jp_sha_match': jp_sha == EXPECT_JP_SHA,
        'jp_crc_match': jp_crc == EXPECT_JP_CRC,
        'jp_size': len(jp),
    }
    if not (checks['opt_sha_match'] and checks['opt_crc_match']):
        raise SystemExit('optimized ROM does not match the fixed SHA/CRC')

    code_opt = build_code(opt)
    code_jp = build_code(jp)
    decoder_equal = FA_OFF is not None and code_opt == code_jp

    # ------------------------------------------------------ source readers
    jp_records = json.load(open(os.path.join(WORK, 'source', 'kuniokun_text.json'),
                                encoding='utf-8'))
    jp_by_identity = {}
    for r in jp_records:
        jp_by_identity[(r['table_rom_off'], r['index'])] = r
    cn_reviewed = json.load(open(os.path.join(WORK, 'source', 'cn_translation.json'),
                                 encoding='utf-8'))
    cn_existing = json.load(open(os.path.join(WORK, 'optimization-existing-cn.json'),
                                 encoding='utf-8'))
    cn_new = json.load(open(os.path.join(WORK, 'optimization-cn-text.json'),
                            encoding='utf-8'))
    new_text_src = json.load(open(os.path.join(WORK, 'optimization-new-text.json'),
                                  encoding='utf-8'))

    # ------------------------------------------- decoder self-verification
    decoder_mismatches = []
    for r in jp_records:
        dec = decode_window(jp, r['text_rom_off'], r['nbytes'], code_jp)
        if dec != r['text']:
            decoder_mismatches.append({'table': r['table_rom_off'],
                                       'index': r['index'],
                                       'record': r['text'], 'decoded': dec})

    # ------------------------------------------------------- five tables
    tables_out = []
    dup_groups_all = []
    cross_ptr = defaultdict(list)
    for tbl, n, limit in TABLES:
        ptrs = [struct.unpack_from('<H', opt, tbl + 2 * i)[0]
                for i in range(n)]
        entries = []
        region_start = None
        region_end = None
        dup_groups = defaultdict(list)
        for i, p in enumerate(ptrs):
            dup_groups[p].append(i)
            cross_ptr[p].append((tbl, i))
        for i in range(n):
            p = ptrs[i]
            start = 0x18000 + (p - 0x8000)
            if i + 1 < n:
                nxt = 0x18000 + (ptrs[i + 1] - 0x8000)
            else:
                nxt = limit
            length = nxt - start
            raw = opt[start:nxt]
            f3i = raw.find(TERMINATOR)
            borrowed_terminator = False
            if f3i < 0 and raw.endswith(b'\xf2') and start + length < len(opt) \
                    and opt[start + length] == TERMINATOR and i + 1 < n:
                # the entry's "$F2 pace" is the slice's last byte and the $F3 that
                # ends it is the first byte of the following entry (pointer collision)
                borrowed_terminator = True
                f3i = length
                raw_eff = raw + bytes([TERMINATOR])
            else:
                raw_eff = raw
            if f3i >= 0:
                live_len = f3i + 1
                dead = raw_eff[live_len:]
            else:
                live_len = None
                dead = b''
            slice_text = decode_window(opt, start, length, code_opt)
            # last entry of a table: its slice runs to the region limit, so the
            # entry's text is the live span (the JP records use the same rule)
            if i + 1 >= n and f3i >= 0:
                text = decode_window(opt, start, live_len, code_opt)
            else:
                text = decode_window(opt, start, len(raw_eff), code_opt)
            dead_prose = ''.join(ch for ch in decode_window(opt, start + (f3i + 1), len(dead), code_opt)
                                 if ch not in (' ',) and not ch.startswith('{')) if f3i >= 0 else ''
            # chain scan: when the slice has no F3 the loader runs on
            jp_rec = jp_by_identity.get((tbl, i))
            idn = (i + 1) if tbl == TABLES[0][0] else None
            rec = OrderedDict()
            rec['table_rom_off'] = tbl
            rec['table_cpu'] = cpu_of(tbl)
            rec['index'] = i
            rec['id'] = ('0x%03X' % idn) if idn is not None else None
            rec['ptr_value'] = '0x%04X' % p
            rec['ptr_cpu'] = cpu_of(0x18000 + (p - 0x8000))
            rec['text_rom_off'] = '0x%06X' % start
            rec['text_cpu'] = cpu_of(start)
            rec['nbytes'] = length
            rec['raw_hex'] = raw.hex()
            rec['slice_text'] = slice_text
            rec['text'] = text
            rec['tokens'] = token_list(text)
            rec['first_f3_byte_off'] = f3i          # index into the slice
            rec['terminator_borrowed_from_next_slice'] = borrowed_terminator
            rec['live_nbytes'] = live_len
            rec['dead_hex'] = dead[:512].hex()
            rec['dead_len'] = len(dead)
            rec['dead_has_prose'] = bool(dead_prose)
            if jp_rec is not None:
                rec['jp_text_rom_off'] = '0x%06X' % jp_rec['text_rom_off']
                rec['jp_text'] = jp_rec['text']
                rec['jp_ptr_value'] = '0x%04X' % jp_rec['ptr_value']
                rec['pointer_moved'] = (jp_rec['ptr_value'] != p)
                rec['text_changed'] = (text != jp_rec['text'])
            else:
                rec['jp_text_rom_off'] = None
                rec['jp_text'] = None
                rec['pointer_moved'] = None
                rec['text_changed'] = None
            entries.append(rec)
            if region_start is None:
                region_start = start
            region_end = start + (live_len if live_len is not None else length)
        dup_only = {('0x%04X' % v): idx for v, idx in dup_groups.items() if len(idx) > 1}
        for v, idx in dup_only.items():
            dup_groups_all.append({'table_rom_off': tbl, 'ptr': v, 'indexes': idx})
        tables_out.append(OrderedDict([
            ('table_rom_off', tbl),
            ('table_cpu', cpu_of(tbl)),
            ('resolver', TABLE_RESOLVERS[tbl]),
            ('entries', n),
            ('region_rom_start', '0x%06X' % region_start),
            ('region_rom_live_end', '0x%06X' % region_end),
            ('duplicate_pointer_groups', dup_only),
            ('records', entries),
        ]))

    # --------------------------------------------------- extended table
    ext_ptrs = [struct.unpack_from('<H', opt, EXT_TABLE_ROM + 2 * i)[0]
                for i in range(EXT_TABLE_SLOTS)]
    ext_entries = []
    ext_dups = defaultdict(list)
    for i, v in enumerate(ext_ptrs):
        ext_dups[v].append(i)
    src_by_id = {e['id']: e for e in new_text_src}
    ext_mismatches = []
    for i, v in enumerate(ext_ptrs):
        idn = EXT_ID_BASE + i
        rec = OrderedDict()
        rec['slot'] = i
        rec['id'] = '0x%03X' % idn
        rec['ptr_value'] = '0x%04X' % v
        rec['ptr_rom_off'] = '0x%06X' % (EXT_TABLE_ROM + 2 * i)
        rec['ptr_cpu'] = cpu_of(EXT_TABLE_ROM + 2 * i)
        if v == 0:
            rec['text_rom_off'] = None
            rec['text_cpu'] = None
            rec['nbytes'] = 0
            rec['raw_hex'] = ''
            rec['slice_text'] = None
            rec['text'] = None
            rec['tokens'] = []
            rec['first_f3_byte_off'] = None
            rec['terminator_borrowed_from_next_slice'] = False
            rec['live_nbytes'] = None
            rec['dead_hex'] = ''
            rec['dead_len'] = 0
            rec['dead_has_prose'] = False
            rec['null_slot'] = True
        else:
            start = EXT_TEXT_ROM0 + (v - 0x8000)
            if i + 1 < EXT_TABLE_SLOTS and ext_ptrs[i + 1] != 0:
                nxt = EXT_TEXT_ROM0 + (ext_ptrs[i + 1] - 0x8000)
            else:
                nxt = EXT_TEXT_LIMIT
            length = nxt - start
            raw = opt[start:nxt]
            f3i = raw.find(TERMINATOR)
            borrowed_terminator = False
            if f3i < 0 and raw.endswith(b'\xf2') and start + length < len(opt) \
                    and opt[start + length] == TERMINATOR:
                borrowed_terminator = True
                f3i = length
                raw_eff = raw + bytes([TERMINATOR])
            else:
                raw_eff = raw
            if f3i >= 0:
                live_len = f3i + 1
                dead = raw_eff[live_len:]
            else:
                live_len = None
                dead = b''
            text = decode_window(opt, start, len(raw_eff), code_opt)
            slice_text = decode_window(opt, start, length, code_opt)
            dead_prose = ''.join(ch for ch in decode_window(opt, start + (f3i + 1), len(dead), code_opt)
                                 if ch not in (' ',) and not ch.startswith('{')) if f3i >= 0 else ''
            rec['text_rom_off'] = '0x%06X' % start
            rec['text_cpu'] = cpu_of(start)
            rec['nbytes'] = length
            rec['raw_hex'] = raw.hex()
            rec['slice_text'] = slice_text
            rec['text'] = text
            rec['tokens'] = token_list(text)
            rec['first_f3_byte_off'] = f3i
            rec['terminator_borrowed_from_next_slice'] = borrowed_terminator
            rec['live_nbytes'] = live_len
            rec['dead_hex'] = dead[:512].hex()
            rec['dead_len'] = len(dead)
            rec['dead_has_prose'] = bool(dead_prose)
            rec['null_slot'] = False
            e = src_by_id.get(idn)
            if e is None:
                ext_mismatches.append({'id': rec['id'], 'reason': 'missing in optimization-new-text.json'})
            else:
                if e['offset'] != start or e['length'] != length:
                    ext_mismatches.append({'id': rec['id'], 'reason': 'offset/length differ',
                                           'src': [e['offset'], e['length']],
                                           'rom': [start, length]})
                if e['text'] != text:
                    ext_mismatches.append({'id': rec['id'], 'reason': 'text differs',
                                           'src': e['text'], 'rom': text})
        ext_entries.append(rec)
    for v, idx in sorted(ext_dups.items()):
        if len(idx) > 1:
            dup_groups_all.append({'table_rom_off': EXT_TABLE_ROM,
                                   'ptr': '0x%04X' % v, 'indexes': idx})

    ext_out = OrderedDict([
        ('table_rom_off', EXT_TABLE_ROM),
        ('table_cpu', cpu_of(EXT_TABLE_ROM)),
        ('resolver_cpu', EXT_RESOLVER_CPU),
        ('reader_cpu', EXT_READER_CPU),
        ('slots', EXT_TABLE_SLOTS),
        ('id_base', '0x%03X' % EXT_ID_BASE),
        ('id_range', '0x%03X..0x%03X' % (EXT_ID_BASE, EXT_ID_BASE + EXT_TABLE_SLOTS - 1)),
        ('text_region_rom', '0x%06X..0x%06X' % (EXT_TEXT_ROM0, EXT_TEXT_LIMIT)),
        ('text_region_cpu', cpu_of(EXT_TEXT_ROM0)),
        ('index_transform', 'index = message_id - 0x300 (verified at $22:8000)'),
        ('boundary_slot', 'slot 0 / id 0x300 = 0x0000 null (no text)'),
        ('source_cross_check_mismatches', ext_mismatches),
        ('duplicate_pointer_groups', {('0x%04X' % v): idx for v, idx in ext_dups.items() if len(idx) > 1}),
        ('records', ext_entries),
    ])

    # ------------------------------------------------- chain report
    chains = []
    chain_run_text = {}
    limits_of = dict((tb, lm) for tb, _, lm in TABLES)
    for t in tables_out:
        tbl = t['table_rom_off']
        recs = t['records']
        for i, rec in enumerate(recs):
            if rec['first_f3_byte_off'] is not None and rec['first_f3_byte_off'] < 0:
                start = int(rec['text_rom_off'], 16)
                limit = limits_of[tbl]
                hit = find_next_f3(opt, start, limit)
                consumed = []
                j = i + 1
                while j < len(recs) and int(recs[j]['text_rom_off'], 16) <= hit:
                    consumed.append(recs[j]['index'])
                    j += 1
                run_len = (hit + 1 - start) if hit >= 0 else (limit - start)
                chain_run_text[(tbl, rec['index'])] = decode_window(opt, start, run_len, code_opt)
                chains.append(OrderedDict([
                    ('table_rom_off', tbl),
                    ('index', rec['index']),
                    ('id', rec['id']),
                    ('slice_rom', rec['text_rom_off']),
                    ('f3_found_at', ('0x%06X' % hit) if hit >= 0 else None),
                    ('following_indexes_consumed', consumed),
                    ('run_nbytes', run_len),
                    ('note', 'no F3 in own slice -> loader chains into the following '
                             'entries until %s' % ('the F3 at 0x%06X' % hit if hit >= 0 else 'none')),
                ]))

    # ------------------------------------ new-block vs original relations
    import difflib
    jp_text_index = defaultdict(list)
    jp_prose_pool = []
    for r in jp_records:
        jp_text_index[r['text']].append({'table_rom_off': r['table_rom_off'],
                                         'index': r['index'],
                                         'id': '0x%03X' % (r['index'] + 1) if r['table_rom_off'] == TABLES[0][0] else None})
        jp_prose_pool.append((fold(prose(r['text'])), r))
    relations = []
    for rec in ext_out['records']:
        if rec['null_slot']:
            relations.append(OrderedDict([
                ('id', rec['id']), ('relation', 'null_boundary_slot'),
                ('jp_match', None), ('note', 'slot before the extended range; pointer 0x0000'),
            ]))
            continue
        t = rec['text']
        entry = OrderedDict([('id', rec['id'])])
        exact = jp_text_index.get(t)
        if exact:
            entry['relation'] = 'exact_text_match'
            entry['jp_match'] = exact
            entry['note'] = 'identical text exists in the original tables'
        else:
            folded = fold(prose(t))
            best = None
            best_ratio = 0.0
            for fp, r in jp_prose_pool:
                if not fp or not folded:
                    continue
                m = difflib.SequenceMatcher(None, folded, fp)
                if m.real_quick_ratio() < best_ratio or m.quick_ratio() < best_ratio:
                    continue
                ratio = m.ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best = r
            if best is not None and best_ratio >= 0.70:
                entry['relation'] = 'similar_text'
                entry['jp_match'] = [{'table_rom_off': best['table_rom_off'],
                                      'index': best['index'],
                                      'id': '0x%03X' % (best['index'] + 1) if best['table_rom_off'] == TABLES[0][0] else None,
                                      'prose_ratio': round(best_ratio, 3)}]
                entry['note'] = ('reworded/derived from the original entry '
                                 '(prose similarity %.2f)' % best_ratio)
            else:
                entry['relation'] = 'new_text_no_match'
                entry['jp_match'] = []
                entry['note'] = 'not found byte-for-byte or by prose similarity in the original tables'
        relations.append(entry)

    # --------------------------------------------------- control census
    def census(recs, skip_null=True):
        c = Counter()
        for r in recs:
            if skip_null and r.get('null_slot'):
                continue
            for tok in r['tokens']:
                c[tok] += 1
        return c

    census_all = Counter()
    for t in tables_out:
        census_all.update(census(t['records']))
    census_ext = census(ext_out['records'])
    single_byte = {k: v for k, v in census_all.items() if len(k) == 2}
    pair_byte = {k: v for k, v in census_all.items() if len(k) == 4}
    census_ext_single = {k: v for k, v in census_ext.items() if len(k) == 2}
    census_ext_pair = {k: v for k, v in census_ext.items() if len(k) == 4}

    # token set differences for the new block vs the old corpus
    old_set = set(census_all)
    new_set = set(census_ext)
    token_diff = OrderedDict([
        ('tokens_only_in_new_block', sorted(new_set - old_set)),
        ('tokens_only_in_old_tables', sorted(old_set - new_set)),
        ('new_block_pair_codes', sorted(census_ext_pair)),
        ('old_tables_pair_codes', sorted(pair_byte)),
    ])

    # ------------------------------------------- control sequence changes
    seq_changes = []
    for t in tables_out:
        for r in t['records']:
            if r['text_changed']:
                jp_tok = token_list(r['jp_text'])
                opt_tok = r['tokens']
                if jp_tok != opt_tok:
                    seq_changes.append(OrderedDict([
                        ('table_rom_off', r['table_rom_off']),
                        ('index', r['index']),
                        ('id', r['id']),
                        ('jp_tokens', jp_tok),
                        ('opt_tokens', opt_tok),
                    ]))

    # ------------------------------------------------------ dynamic macros
    dynamic_consumers = OrderedDict([
        ('E0', {'cells': 1, 'consumer': 'macro dispatch $03:EC0D -> $EC2D',
                'detail': 'single-cell runtime macro (exact slot unresolved in sources)'}),
        ('E1', {'cells': 1, 'consumer': 'macro dispatch $03:EC0D -> $EC3C',
                'detail': 'single-cell runtime macro (handler writes $24/$25 then $EC65/$EC95)'}),
        ('E2', {'cells': 4, 'consumer': 'speaker-name macro; name records at ROM $4802A, 514 x 16 bytes, first 4 bytes are the kana record',
                'detail': 'prints the current speaker name (dynamic)'}),
        ('E3', {'cells': 4, 'consumer': '$03:ECD3; copies up to 4 bytes from a bank $09 record',
                'detail': 'string macro (dynamic name)'}),
        ('E4', {'cells': 4, 'consumer': '$03:ECD7', 'detail': 'string macro'}),
        ('E5', {'cells': 4, 'consumer': '$03:ECDB', 'detail': 'string macro'}),
        ('E6', {'cells': 4, 'consumer': '$03:ECDF', 'detail': 'string macro'}),
        ('E7', {'cells': 4, 'consumer': '$03:ECEB', 'detail': 'string macro (used for the poison/HP stat owner in {E7}の どすうは {EF}だ)'}),
        ('E8', {'cells': 4, 'consumer': '$03:ECEF', 'detail': 'string macro'}),
        ('E9', {'cells': 4, 'consumer': '$03:ECF3', 'detail': 'string macro'}),
        ('EA', {'cells': 8, 'consumer': '$03:ED43', 'detail': '8-cell string macro'}),
        ('EB', {'cells': 12, 'consumer': '$03:EDAE', 'detail': 'list macro: copies the first line of a list entry (item/technique name); exact list slot not resolved here'}),
        ('EC', {'cells': 12, 'consumer': '$03:EDC5', 'detail': 'list macro (see $EDC5); exact list slot not resolved here'}),
        ('ED', {'cells': 12, 'consumer': '$03:EE05 reads $035D, index*2 + base $03:E4CC (table 0x1E4CE region)',
                'detail': 'list macro: entry name drawn from the table-5 text region (index from RAM $035D)'}),
        ('EE', {'cells': 12, 'consumer': '$03:EE0A reads $035E, index*2 + base $03:E4CC',
                'detail': 'list macro: entry name drawn from the table-5 text region (index from RAM $035E)'}),
        ('EF', {'cells': 5, 'consumer': '$03:EE21', 'detail': 'number (up to five digits)'}),
        ('F2E2', {'cells': None, 'consumer': 'byte $F2 (pace) followed by the $E2 speaker-name macro',
                  'detail': 'mid-sentence speaker-name paste; two independent bytes, not one token'}),
        ('F0', {'cells': 0, 'consumer': '$03:EBD0 path (control byte)',
                'detail': 'box/line control seen 445x; single byte'}),
        ('F3', {'cells': 0, 'consumer': 'loader stop at $03:EBBF',
                'detail': 'terminator byte; bare F3 appears after {F2F4} at message ends'}),
        ('F4', {'cells': 0, 'consumer': '$03:EBD0 path', 'detail': 'rare single-byte control'}),
        ('F5', {'cells': 0, 'consumer': '$03:EBD0 path', 'detail': 'rare single-byte control'}),
        ('F6', {'cells': 0, 'consumer': '$03:EBD0 path', 'detail': 'single-byte control (in-box line break family)'}),
        ('F7', {'cells': 0, 'consumer': '$03:EBD0 path', 'detail': 'single-byte control (pause family)'}),
        ('F2F3', {'cells': 0, 'consumer': '$F2 pace + $F3 stop', 'detail': 'standard end-of-message pair'}),
        ('F2F4', {'cells': 0, 'consumer': '$F2 pace + $F4 control', 'detail': 'page-break pair'}),
        ('F2F6', {'cells': 0, 'consumer': '$F2 pace + $F6 control', 'detail': 'in-box line break pair'}),
        ('F2F7', {'cells': 0, 'consumer': '$F2 pace + $F7 control', 'detail': 'pause pair; the optimizer uses it mid-entry and at former entry ends (chains)'}),
    ])

    # --------------------------------------------------------- anomalies
    anomalies = []
    anomalies.append(OrderedDict([
        ('kind', 'boundary_null_slot'),
        ('where', 'extended table slot 0 / id 0x300, ROM 0x110070'),
        ('detail', 'pointer is 0x0000 (no text). ids < 0x300 are routed to the old '
                   'resolver; id 0x300 is the first extended id and reads the null '
                   'pointer. Recorded as the empty/boundary slot.'),
    ]))
    leading = []
    for rec in ext_out['records']:
        if not rec['null_slot'] and rec['raw_hex'].startswith('f3'):
            leading.append(rec['id'])
    if leading:
        anomalies.append(OrderedDict([
            ('kind', 'leading_F3_entry'),
            ('where', 'extended ids %s' % ', '.join(leading)),
            ('detail', 'the entry begins with the terminator byte 0xF3 (loader test at '
                       '$03:EBBF returns immediately). id 0x347 ends with "$F2" whose $F3 '
                       'is the shared boundary byte at ROM 0x1186D0, and the pointer of '
                       '0x348 points at that same byte, so 0x348 renders empty while its '
                       'text (24 dead bytes after the leading F3) stays unreachable '
                       'through this id. Flagged for the rebuild to decide, not fixed here.'),
        ]))
    anomalies.append(OrderedDict([
        ('kind', 'chain_entries'),
        ('where', ', '.join('%s (table 0x%06X idx %d)' % (c['id'], c['table_rom_off'], c['index'])
                            for c in chains)),
        ('detail', 'no F3 inside their own slice; the loader continues into the next '
                   'entries until the next F3. The optimizer changed {F2F3} into '
                   '{F2F7} on ids 186/187/189/18A and ends id 274 with a lone $F2; the '
                   'original JP tables have no such entries.'),
    ]))
    anomalies.append(OrderedDict([
        ('kind', 'mixed_terminator_macro_swap'),
        ('where', 'text-changed entries listed in candidate notes'),
        ('detail', 'optimizer swapped list macros (ED<->EE, E3->ED/EE/E0), dropped '
                   'leading F0 on some entries and moved {F2F6} breaks; the reviewed CN '
                   'must be re-aligned to the optimized token stream before reuse.'),
    ]))

    # ---------------------------------------------------------- inventory
    inventory = OrderedDict()
    inventory['meta'] = OrderedDict([
        ('generated_by', 'inventory-worker/extract_native.py'),
        ('note', 'native text inventory extracted directly from the optimized ROM; '
                 'no bytes of the ROM itself are embedded here'),
        ('opt_rom', OrderedDict([
            ('path', opt_path), ('sha256', opt_sha), ('crc32', '0x%08X' % opt_crc),
            ('size', len(opt))])),
        ('jp_rom', OrderedDict([
            ('path', jp_path), ('sha256', jp_sha), ('crc32', '0x%08X' % jp_crc),
            ('size', len(jp))])),
        ('checks', OrderedDict(checks)),
        ('decoder', OrderedDict([
            ('fa_off', '0x%06X' % FA_OFF), ('fb_off', '0x%06X' % FB_OFF),
            ('fa_fb_identical_between_jp_and_opt', code_opt == code_jp),
            ('jp_record_decode_mismatches', len(decoder_mismatches)),
        ])),
    ])
    inventory['engine_model'] = OrderedDict([
        ('terminator', 'the loader stops at the first 0xF3 byte ($03:EBBF CMP #$F3/BEQ)'),
        ('pace_byte', '0xF2 makes the loader return and resume on the next call; the '
                      'byte after it is classified independently'),
        ('macro_range', '0xE0-0xEF -> JSR $03:EBFC (dispatch table at $03:EC0D)'),
        ('control_range', '0xF0-0xFF (except F3 stop) -> $03:EBD0 path'),
        ('dead_text_rule', 'every byte behind the first 0xF3 of an entry is dead'),
        ('main_id_rule', 'main table message id = index + 1 (resolver $03:EB7F adds '
                         'id*2 to the base word $03:EAEB = $93B3 = $03:93B5 - 2)'),
        ('extended_id_rule', 'id >= 0x300 uses $22:8000: index = id - 0x300, table at '
                             '$22:8070, text read from bank $23 ($22:8050)'),
    ])
    inventory['tables'] = tables_out
    inventory['extended_table'] = ext_out
    inventory['id_relations'] = OrderedDict([
        ('main_table', 'message id = index + 1 (ids 0x001..0x2B6 for the 694 entries)'),
        ('extended_range', '0x301..0x34B supplied by the optimized block; id 0x300 is the '
                           'null boundary slot; 0x2B7..0x2FF have no entries anywhere'),
        ('other_tables', 'tables 0x1DBC5/0x1E098/0x1E1D5/0x1E4CE have their own resolvers '
                         '($03:ED08/$03:EDB5/$03:EDCC/$03:EE11) with base words '
                         '$DBC3/$E096/$E1D3/$E4CC; their id spaces are not enumerated here '
                         '(explicit unresolved)'),
        ('new_block_relations', relations),
    ])
    inventory['control_token_census'] = OrderedDict([
        ('old_tables_single_byte', single_byte),
        ('old_tables_pair_codes', pair_byte),
        ('new_block_single_byte', census_ext_single),
        ('new_block_pair_codes', census_ext_pair),
        ('differences', token_diff),
    ])
    inventory['control_sequence_changes'] = seq_changes
    inventory['dynamic_consumers'] = dynamic_consumers
    inventory['chains'] = chains
    inventory['anomalies'] = anomalies
    cross_table_dups = []
    for v, hits in sorted(cross_ptr.items()):
        tables_hit = {t for t, _ in hits}
        if len(tables_hit) > 1:
            cross_table_dups.append({'ptr': '0x%04X' % v,
                                     'hits': [{'table_rom_off': t, 'index': i} for t, i in hits]})
    inventory['duplicate_pointers'] = OrderedDict([
        ('within_table_groups', dup_groups_all),
        ('cross_table_groups', cross_table_dups),
        ('note', 'duplicate pointer groups across the five original tables in the '
                 'optimized ROM (shared strings); the extended table has none'),
    ])
    stats = OrderedDict([
        ('tables_total_entries', sum(n for _, n, _ in TABLES)),
        ('extended_slots', EXT_TABLE_SLOTS),
        ('extended_text_entries', EXT_TABLE_SLOTS - 1),
        ('entries_total', sum(n for _, n, _ in TABLES) + EXT_TABLE_SLOTS - 1),
        ('text_changed_entries', sum(1 for t in tables_out for r in t['records'] if r['text_changed'])),
        ('pointer_moved_entries', sum(1 for t in tables_out for r in t['records'] if r['pointer_moved'])),
        ('dead_text_entries', sum(1 for t in tables_out for r in t['records'] if r['dead_has_prose'])
                               + sum(1 for r in ext_entries if r['dead_has_prose'])),
        ('chain_entries', len(chains)),
    ])
    inventory['stats'] = stats

    with open(os.path.join(BASE, 'native-inventory.json'), 'w', encoding='utf-8') as f:
        json.dump(inventory, f, ensure_ascii=False, indent=1)

    # --------------------------------------------------- candidates
    def token_check(cand, opt_text):
        ct = token_list(cand)
        ot = token_list(opt_text)
        if ct == ot:
            return OrderedDict([('status', 'match'), ('candidate_tokens', ct),
                                ('opt_tokens', ot)])
        ct2 = [t for t in ct if t != 'F2F6']
        ot2 = [t for t in ot if t != 'F2F6']
        if ct2 == ot2:
            return OrderedDict([('status', 'match-modulo-F2F6'), ('candidate_tokens', ct),
                                ('opt_tokens', ot)])
        # subsequence = the reviewed text only dropped tokens; the build's
        # align_tokens step restores them from the original sequence
        it = iter(ot2)
        is_sub = all(t in it for t in ct2)
        if is_sub:
            return OrderedDict([('status', 'subset-subsequence'), ('candidate_tokens', ct),
                                ('opt_tokens', ot),
                                ('note', 'candidate only omits tokens; align_tokens can '
                                         'restore the original sequence')])
        missing = [t for t in ot2 if t not in ct2]
        extra = [t for t in ct2 if t not in ot2]
        return OrderedDict([('status', 'mismatch'), ('candidate_tokens', ct),
                            ('opt_tokens', ot), ('missing_from_candidate', missing),
                            ('extra_in_candidate', extra)])

    cand_rows = []
    unresolved = []
    for t in tables_out:
        tbl = t['table_rom_off']
        for r in t['records']:
            row = OrderedDict()
            row['identity'] = OrderedDict([
                ('table_rom_off', tbl), ('table_cpu', cpu_of(tbl)),
                ('index', r['index']), ('id', r['id']),
                ('text_rom_off', r['text_rom_off']),
            ])
            row['opt_text'] = r['text']
            row['opt_tokens'] = r['tokens']
            row['source_text_changed'] = r['text_changed']
            row['pointer_moved'] = r['pointer_moved']
            row['dead_after_f3'] = OrderedDict([
                ('dead_len', r['dead_len']), ('dead_has_prose', r['dead_has_prose']),
            ])
            row['chain_entry'] = (r['first_f3_byte_off'] is not None
                                  and r['first_f3_byte_off'] < 0)
            cand = None
            prov = None
            status = None
            notes = []
            key_cn = '%06X' % int(r['jp_text_rom_off'], 16) if r['jp_text_rom_off'] else None
            reviewed = cn_reviewed.get(key_cn) if key_cn else None
            if not r['text_changed']:
                if reviewed is not None:
                    cand, prov, status = reviewed, 'cn_translation.json', 'reuse-exact'
                else:
                    status = 'unresolved-no-reviewed-cn'
                    notes.append('no reviewed CN under JP key %s' % key_cn)
            else:
                idn = r['id']
                ex_key = None
                if idn and tbl == TABLES[0][0]:
                    ex_key = '%03X' % int(idn, 16)
                ex = cn_existing.get(ex_key) if ex_key else None
                if ex is not None:
                    cand, prov, status = ex, 'optimization-existing-cn.json', 'reuse-reviewed-updated'
                    notes.append('optimizer changed this text; reviewed CN for the new text')
                elif reviewed is not None:
                    same_meaning = fold(prose(r['jp_text'])) == fold(prose(r['text']))
                    if same_meaning:
                        cand, prov, status = reviewed, 'cn_translation.json', 'reuse-realigned-meaning-same'
                        notes.append('control positions/orthography changed only; '
                                     'reviewed CN meaning unchanged, re-align tokens')
                    else:
                        cand, prov, status = None, None, 'unresolved-source-changed'
                        notes.append('optimized text differs in meaning; old CN kept as '
                                     'reference only')
                        notes.append('reference_cn: %s' % reviewed)
                        notes.append('reference_from: cn_translation.json[%s]' % key_cn)
                else:
                    status = 'unresolved-source-changed'
                    notes.append('optimized text differs; no reviewed CN available')
            row['candidate_cn'] = cand
            row['provenance'] = prov
            row['status'] = status
            row['notes'] = notes
            if cand is not None:
                row['token_check'] = token_check(cand, r['text'])
                # a chain entry renders together with the following entries up to
                # the next F3; record that comparison separately
                run = chain_run_text.get((tbl, r['index']))
                row['chain_run_check'] = token_check(cand, run) if run is not None else None
                run_clean = (row['chain_run_check'] is not None
                             and row['chain_run_check']['status']
                             in ('match', 'match-modulo-F2F6', 'subset-subsequence'))
                if run_clean:
                    notes.append('candidate covers the chained run (own slice + '
                                 'following entries up to the next F3)')
                if row['token_check']['status'] == 'mismatch' and not run_clean:
                    if status == 'reuse-realigned-meaning-same':
                        notes.append('token mismatch expected: candidate was aligned to the '
                                     'original sequence; rebuild must re-align to the '
                                     'optimized stream')
                    else:
                        row['status'] = status + '+token-mismatch'
                        notes.append('candidate token sequence does not match the optimized '
                                     'entry; must be re-aligned or reviewed')
            else:
                row['token_check'] = None
                row['chain_run_check'] = None
            cand_rows.append(row)
            if status is None or status.startswith('unresolved'):
                unresolved.append(OrderedDict([
                    ('identity', row['identity']),
                    ('status', row['status']),
                    ('opt_text', r['text']),
                    ('notes', notes),
                ]))

    for r in ext_out['records']:
        row = OrderedDict()
        row['identity'] = OrderedDict([
            ('table_rom_off', EXT_TABLE_ROM), ('table_cpu', cpu_of(EXT_TABLE_ROM)),
            ('slot', r['slot']), ('id', r['id']),
            ('text_rom_off', r['text_rom_off']),
        ])
        row['opt_text'] = r['text']
        row['opt_tokens'] = r['tokens']
        row['source_text_changed'] = None
        row['pointer_moved'] = None
        row['dead_after_f3'] = OrderedDict([
            ('dead_len', r['dead_len']), ('dead_has_prose', r['dead_has_prose']),
        ])
        row['chain_entry'] = ((not r['null_slot']) and r['first_f3_byte_off'] is not None
                              and r['first_f3_byte_off'] < 0)
        if r['null_slot']:
            row['candidate_cn'] = None
            row['provenance'] = None
            row['status'] = 'null-slot-no-text'
            row['notes'] = ['boundary slot before the extended range; nothing to translate']
            row['token_check'] = None
            cand_rows.append(row)
            continue
        key = '%03X' % int(r['id'], 16)
        cand = cn_new.get(key)
        row['candidate_cn'] = cand
        if cand is not None:
            row['provenance'] = 'optimization-cn-text.json'
            row['status'] = 'reuse-reviewed-new-block'
            row['notes'] = ['CN prepared for the optimizer block; keep control codes']
            row['token_check'] = token_check(cand, r['text'])
            row['chain_run_check'] = None
            if row['token_check']['status'] == 'mismatch':
                row['status'] = 'reuse-reviewed-new-block+token-mismatch'
                row['notes'].append('candidate token sequence does not match; must be '
                                    're-aligned or reviewed')
        else:
            row['provenance'] = None
            row['status'] = 'unresolved-no-cn-for-new-block'
            row['notes'] = ['no reviewed CN in optimization-cn-text.json']
            row['token_check'] = None
            row['chain_run_check'] = None
        if r['raw_hex'].startswith('f3'):
            row['notes'].append('LEADING F3: entry begins with the terminator; renders '
                                'empty under the confirmed loader semantics')
        if r['dead_has_prose']:
            row['notes'].append('dead bytes after the first F3 contain renderable text')
        cand_rows.append(row)
        if row['status'].startswith('unresolved'):
            unresolved.append(OrderedDict([
                ('identity', row['identity']),
                ('status', row['status']),
                ('opt_text', r['text']),
                ('notes', row['notes']),
            ]))

    status_counts = Counter(r['status'] for r in cand_rows)
    candidates = OrderedDict()
    candidates['meta'] = OrderedDict([
        ('generated_by', 'inventory-worker/extract_native.py'),
        ('purpose', 'candidate reviewed-Chinese reuse per native entry; association is by '
                    'message id / table-entry identity, never by JP text offset of a moved '
                    'pointer; reviewed wording is copied verbatim, never rewritten here'),
        ('sources', OrderedDict([
            ('cn_translation.json', {'entries': len(cn_reviewed),
                                     'key': 'JP ROM text offset (hex, 6 digits)',
                                     'note': 'reviewed CN of the original tables'}),
            ('optimization-existing-cn.json', {'entries': len(cn_existing),
                                               'key': 'main-table message id (hex)',
                                               'note': 'reviewed CN updated for optimizer-changed originals'}),
            ('optimization-cn-text.json', {'entries': len(cn_new),
                                           'key': 'extended message id (hex)',
                                           'note': 'CN for the new block'}),
        ])),
        ('denominators', OrderedDict([
            ('table_entries', sum(n for _, n, _ in TABLES)),
            ('extended_slots', EXT_TABLE_SLOTS),
            ('extended_text_entries', EXT_TABLE_SLOTS - 1),
            ('candidate_rows', len(cand_rows)),
            ('rows_with_candidate', sum(1 for r in cand_rows if r['candidate_cn'] is not None)),
            ('rows_unresolved', sum(1 for r in cand_rows if r['status'].startswith('unresolved'))),
            ('null_slot_rows', status_counts.get('null-slot-no-text', 0)),
            ('by_status', dict(status_counts)),
        ])),
        ('rules', [
            'unchanged optimized text -> cn_translation.json by identity key (reuse-exact)',
            'changed original with a reviewed update -> optimization-existing-cn.json (reuse-reviewed-updated)',
            'changed original without update but same meaning -> old CN with re-align note',
            'changed original with different meaning -> unresolved, old CN kept as reference',
            'new block -> optimization-cn-text.json (reuse-reviewed-new-block)',
            'control tokens are never modified; token checks flag re-alignment needs',
        ]),
    ])
    candidates['candidates'] = cand_rows
    candidates['unresolved'] = unresolved

    with open(os.path.join(BASE, 'candidate-translations.json'), 'w', encoding='utf-8') as f:
        json.dump(candidates, f, ensure_ascii=False, indent=1)

    # ------------------------------------------------------------- report
    print('optimized ROM  : %s' % ('OK' if checks['opt_sha_match'] and checks['opt_crc_match'] else 'MISMATCH'))
    print('jp ROM         : %s' % ('OK' if checks['jp_sha_match'] and checks['jp_crc_match'] else 'MISMATCH'))
    print('decoder        : JP record mismatches = %d, jp/opt FA-FB equal = %s'
          % (len(decoder_mismatches), code_opt == code_jp))
    print('tables         : %s' % ', '.join('%d' % n for _, n, _ in TABLES))
    print('extended       : %d slots, %d text entries, %d null' %
          (EXT_TABLE_SLOTS, EXT_TABLE_SLOTS - 1, 1))
    print('new-block src mismatches: %d' % len(ext_mismatches))
    print('text-changed entries: %d, pointer-moved: %d'
          % (stats['text_changed_entries'], stats['pointer_moved_entries']))
    print('chains: %s' % [('%s idx %d' % (c['id'], c['index'])) for c in chains])
    print('dead-text entries: %d' % stats['dead_text_entries'])
    print('duplicate pointer groups: %d' % len(dup_groups_all))
    print('candidate status: %s' % dict(status_counts))
    print('unresolved rows: %d' % len(unresolved))
    print('written: %s' % os.path.join(BASE, 'native-inventory.json'))
    print('written: %s' % os.path.join(BASE, 'candidate-translations.json'))


if __name__ == '__main__':
    main()
