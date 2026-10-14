"""初代熱血硬派くにおくん (SF8127) text code table.

Verified against rendered font glyphs (font at ROM 0x0F8000, 2bpp, 16B/tile,
row-interleaved) and against decoded in-game text.

The renderer at ROM 0x00FC8E writes, for each text byte `code`:
    tilemap entry 1 = FB[code] | 0x2400
    tilemap entry 2 = FA[code] | 0x2400
FA = ROM 0x01FA9E (base glyph tile), FB = ROM 0x01FB9E (overlay glyph tile:
0x9E = dakuten, 0x9F = handakuten, 0x00 = none).
"""

ROM = 'dl/roms/kuniokun__SF8127.smc'
FONT = 0x0F8000
FA_OFF = 0x01FA9E
FB_OFF = 0x01FB9E

_d = open(ROM, 'rb').read()
FA = _d[FA_OFF:FA_OFF + 256]
FB = _d[FB_OFF:FB_OFF + 256]

# ---------------------------------------------------------------- tile -> char
TILE = {0x00: ' '}
TILE.update({0x01: '!', 0x02: '"', 0x03: '\u25bc', 0x04: '\u25b6', 0x05: '\u00d7',
             0x06: '&', 0x07: "'", 0x08: '(', 0x09: ')', 0x0A: '#', 0x0B: '+',
             0x0C: ',', 0x0D: '-', 0x0E: '.', 0x0F: '/'})
for i in range(10):
    TILE[0x10 + i] = chr(ord('0') + i)
TILE.update({0x1A: ':', 0x1B: ';', 0x1C: '<', 0x1D: '=', 0x1E: '>', 0x1F: '?'})
TILE[0x20] = ' '          # renders blank in text; codes 0xC5-0xFF all use this tile
for i in range(26):
    TILE[0x21 + i] = chr(ord('A') + i)
TILE.update({0x3B: '[', 0x3C: '\\', 0x3D: ']', 0x3E: '^', 0x3F: '_'})
# card suits / boxes (graphic tiles 0x60-0x65)
TILE.update({0x60: '\u2663', 0x61: '\u2665', 0x62: '\u2660', 0x63: '\u2666',
             0x64: '\u25a1', 0x65: '\u25a0'})
# small kana + wo, tiles 0x66-0x6F (0x66 is を; verified from 'ちからを かしてください')
TILE.update({0x66: '\u3092', 0x67: '\u3041', 0x68: '\u3043', 0x69: '\u3045',
             0x6A: '\u3047', 0x6B: '\u3049', 0x6C: '\u3083', 0x6D: '\u3085',
             0x6E: '\u3087', 0x6F: '\u3063'})
# hiragana block 0x71-0x9F (no dakuten forms: those come from FB overlay)
HIRA = ('\u3042\u3044\u3046\u3048\u304a\u304b\u304d\u304f\u3051\u3053'
        '\u3055\u3057\u3059\u305b\u305d\u305f\u3061\u3064\u3066\u3068'
        '\u306a\u306b\u306c\u306d\u306e\u306f\u3072\u3075\u3078\u307b'
        '\u307e\u307f\u3080\u3081\u3082\u3084\u3086\u3088'
        '\u3089\u308a\u308b\u308c\u308d\u308f\u3093\u309b\u309c')
for i, ch in enumerate(HIRA):
    TILE[0x71 + i] = ch
TILE[0xA0] = '\u30fc'                       # ー
KATA = ('\u30a2\u30a4\u30a6\u30a8\u30aa\u30ab\u30ad\u30af\u30b1\u30b3'
        '\u30b5\u30b7\u30b9\u30bb\u30bd\u30bf\u30c1\u30c4\u30c6\u30c8'
        '\u30ca\u30cb\u30cc\u30cd\u30ce\u30cf\u30d2\u30d5\u30d8\u30db'
        '\u30de\u30df\u30e0\u30e1\u30e2\u30e4\u30e6\u30e8'
        '\u30e9\u30ea\u30eb\u30ec\u30ed\u30ef\u30f3')
for i, ch in enumerate(KATA):
    TILE[0xA1 + i] = ch
# 0xD6 is a second ン; 0xD7-0xDF are the small katakana
TILE[0xD6] = '\u30f3'
for i, ch in enumerate('\u30a1\u30a3\u30a5\u30a7\u30a9\u30e3\u30e5\u30e7\u30c3'):
    TILE[0xD7 + i] = ch
TILE[0xD5] = '\u30fc'                       # second long-vowel tile

# ------------------------------------------------------------- dakuten tables
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


def combine(base, overlay):
    if overlay == 0x9E:
        return _DAKU.get(base) or _KDAKU.get(base) or base
    if overlay == 0x9F:
        return _HAND.get(base) or _KHAND.get(base) or base
    return base


CODE = {}
for c in range(256):
    base = TILE.get(FA[c], '{%02X}' % FA[c])
    CODE[c] = combine(base, FB[c])

# 0xC5-0xFF all render as the same blank box tile, but they are distinct
# runtime placeholders (speaker-name slot, name box, line/page codes...).
# Keep them explicit so a translation can preserve them byte for byte.
for _c in range(0xC5, 0x100):
    if _c not in (0xF2,):
        CODE[_c] = '{%02X}' % _c

# controls: 0xF2 is followed by a one-byte parameter
CTRL = 0xF2


def decode(data, off, maxlen=4096):
    """Decode a code stream starting at `off`; returns (text, end_offset)."""
    out = []
    i = 0
    while i < maxlen and off + i < len(data):
        c = data[off + i]
        if c == CTRL:
            p = data[off + i + 1]
            out.append('{%02X%02X}' % (c, p))
            i += 2
            continue
        out.append(CODE[c])
        i += 1
    return ''.join(out), off + i


if __name__ == '__main__':
    for base in range(0, 256, 16):
        row = ' '.join('%02X=%s' % (base + k, CODE[base + k]) for k in range(16))
        print(row)
