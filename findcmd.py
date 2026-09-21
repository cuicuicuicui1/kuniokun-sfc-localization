"""Locate the command-window (Start menu) labels in the ROM by their kana codes."""
rom = open('dl/roms/kuniokun__SF8127.smc', 'rb').read()

K = {' ': 0x00, '!': 0x01, ':': 0x09, '?': 0x0C, '-': 0x1D,
     'あ': 0x20, 'い': 0x21, 'う': 0x22, 'え': 0x23, 'お': 0x24,
     'か': 0x25, 'き': 0x26, 'く': 0x27, 'け': 0x28, 'こ': 0x29,
     'さ': 0x2A, 'し': 0x2B, 'す': 0x2C, 'せ': 0x2D, 'そ': 0x2E,
     'た': 0x2F, 'ち': 0x30, 'つ': 0x31, 'て': 0x32, 'と': 0x33,
     'な': 0x34, 'に': 0x35, 'ぬ': 0x36, 'ね': 0x37, 'の': 0x38,
     'は': 0x39, 'ひ': 0x3A, 'ふ': 0x3B, 'へ': 0x3C, 'ほ': 0x3D,
     'ま': 0x3E, 'み': 0x3F, 'む': 0x40, 'め': 0x41, 'も': 0x42,
     'や': 0x43, 'ゆ': 0x44, 'よ': 0x45, 'ら': 0x46, 'り': 0x47,
     'る': 0x48, 'れ': 0x49, 'ろ': 0x4A, 'わ': 0x4B, 'を': 0x4C,
     'ん': 0x4D, 'が': 0x4E, 'ぎ': 0x4F, 'ぐ': 0x50, 'げ': 0x51,
     'ご': 0x52, 'ざ': 0x53, 'じ': 0x54, 'ず': 0x55, 'ぜ': 0x56,
     'ぞ': 0x57, 'だ': 0x58, 'ぢ': 0x59, 'づ': 0x5A, 'で': 0x5B,
     'ど': 0x5C, 'ば': 0x5D, 'び': 0x5E, 'ぶ': 0x5F, 'べ': 0x60,
     'ぼ': 0x61, 'ぱ': 0x62, 'ぽ': 0x66, 'ぁ': 0x67, 'ぃ': 0x68,
     'ぅ': 0x69, 'ぇ': 0x6A, 'ぉ': 0x6B, 'ゃ': 0x6C, 'ゅ': 0x6D,
     'ょ': 0x6E, 'っ': 0x6F}


def code(s):
    return bytes(K[c] for c in s)


targets = ['きりょくをつかう', 'どうくをつかう', 'もうびする',
           'すてーたすをみる', 'すてる', 'すてーたす', 'きりょく', 'どうく']
for t in targets:
    b = code(t)
    hits = []
    i = 0
    while True:
        p = rom.find(b, i)
        if p < 0:
            break
        hits.append(p)
        i = p + 1
    print('%-16s %s  ->  %s' % (t, b.hex(' ').upper(), ' '.join('%06X' % h for h in hits[:8]) or 'NOT FOUND'))

print()
print('--- terminator bytes after each menu label ---')
for t in ['きりょくをつかう', 'どうくをつかう', 'もうびする', 'すてーたすをみる', 'すてる']:
    b = code(t)
    p = rom.find(b)
    if p >= 0:
        print('%06X  %-16s  +0..%d: %s' % (p, t, len(b) + 4,
              ' '.join('%02X' % x for x in rom[p - 2:p + len(b) + 4])))
