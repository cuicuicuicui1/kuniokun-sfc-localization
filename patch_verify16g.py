# -*- coding: utf-8 -*-
"""Teach verify16 about the one byte codes, the kana rewrite and the removed
macro sanitizer."""
import io
P = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/verify16.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')

# ---- builder state fed from the build params -------------------------------
old = """cb.SLOTS = par['slots']
cb.PAGES = par['pages']"""
assert s.count(old) == 1
s = s.replace(old, """cb.SLOTS = par['slots']
cb.PAGES = par['pages']
cb.FIXED0 = par['fixed0']
cb.FIXED_N = par['fixed_n']
cb.FIXED_CODES.clear()
cb.FIXED_CODES.update(par['fixed'])""")

old = """def is_cn(b):
    return cb.PREFIX0 <= b < cb.PREFIX0 + cb.PAGES"""
assert s.count(old) == 1
s = s.replace(old, """def is_cn(b):
    return cb.PREFIX0 <= b < cb.PREFIX0 + cb.PAGES


def is_fx(b):
    return cb.FIXED0 <= b < cb.FIXED0 + cb.FIXED_N""")

# ---- A: the sanitizer is gone ---------------------------------------------
old = """         (cb.HOOK_COPY1, bytes([0x20, sa & 0xFF, sa >> 8]), 'sanitize JSR 1'),
         (cb.HOOK_COPY2, bytes([0x20, sa & 0xFF, sa >> 8]), 'sanitize JSR 2'),"""
assert s.count(old) == 1
s = s.replace(old, """         (cb.HOOK_COPY1, orig[cb.HOOK_COPY1:cb.HOOK_COPY1 + 3],
          'macro sanitizer call removed 1'),
         (cb.HOOK_COPY2, orig[cb.HOOK_COPY2:cb.HOOK_COPY2 + 3],
          'macro sanitizer call removed 2'),""")

old = """if rom[cb.B3_SANITIZE:cb.B3_SANITIZE + 14] != cb.build_sanitize():
    fail('sanitizer bytes differ')
"""
assert s.count(old) == 1
s = s.replace(old, """sb, sa = cb.snes_of_rom(cb.B3_SANITIZE)          # unused now
""")

# ---- B: one byte codes and the kana rewrite --------------------------------
old = """        elif c in cb.KEEP1:
            out.append(cb.KEEP1[c])
            i += 1
        else:"""
assert s.count(old) == 1
s = s.replace(old, """        elif c in cb.KEEP1:
            out.append(cb.KEEP1[c])
            i += 1
        elif c in cb.FIXED_CODES:
            out.append(cb.FIXED_CODES[c])
            i += 1
        else:""")

old = """        a_, b_ = _act(off), _act(off, orig)
        if a_ != b_:
            fail('entry %s (japanese table) was modified' % key)"""
assert s.count(old) == 1
s = s.replace(old, """        a_, b_ = _act(off), _act(off, orig)
        want_jp = cb.rewrite_kana(bytes(b_))        # katakana -> hiragana
        if bytes(a_) != want_jp:
            fail('entry %s (japanese table) differs from the kana rewrite: '
                 '%s want %s' % (key, bytes(a_)[:12].hex(' '), want_jp[:12].hex(' ')))""")
old = """        elif any(is_cn(x) for x in a_[:-1]):"""
assert s.count(old) == 1
s = s.replace(old, """        elif any(is_cn(x) or is_fx(x) for x in a_[:-1]):""")

# ---- C1: the fixed code path ----------------------------------------------
old = """        cn = is_cn(code)
        # ---- model the wrap the drawer itself does for a 2 cell glyph
        if cn and col >= cb.WRAP_COL:"""
assert s.count(old) == 1
s = s.replace(old, """        cn = is_cn(code)
        fx = is_fx(code)
        # ---- model the wrap the drawer itself does for a 2 cell glyph
        if (cn or fx) and col >= cb.WRAP_COL:""")

old = """        staged = b''
        if cn:"""
assert s.count(old) == 1
s = s.replace(old, """        staged = b''
        if cn or fx:""")

old = """                if w[0x036F] != col:
                    fail('entry %s byte %d: deferred but the column moved'
                         % (key, i))"""
assert s.count(old) == 1
s = s.replace(old, """                if w[0x036F] != col:
                    fail('entry %s byte %d: deferred but the column moved'
                         % (key, i))
                if w[0x03E9] != i:
                    fail('entry %s byte %d: deferred but $03E9 moved' % (key, i))""")

old = """            ch = rev[(code - cb.PREFIX0, msg[i + 1])]
            pa, pb = LEFT[cell[ch][1]], RIGHT[cell[ch][1]]"""
assert s.count(old) == 1
s = s.replace(old, """            if cn:
                ch = rev[(code - cb.PREFIX0, msg[i + 1])]
                slot = cell[ch][1]
            else:
                ch = rev[(0, code - cb.FIXED0)]
                slot = code - cb.FIXED0
            pa, pb = LEFT[slot], RIGHT[slot]""")

old = """            if w[0x03E9] != ((i + 1) & 0xFF):
                fail('entry %s byte %d: the id byte was not consumed '
                     '($03E9 = $%02X)' % (key, i, w[0x03E9]))"""
assert s.count(old) == 1
s = s.replace(old, """            want_e9 = (i + 1) & 0xFF if cn else i
            if w[0x03E9] != want_e9:
                fail('entry %s byte %d: $03E9 = $%02X want $%02X'
                     % (key, i, w[0x03E9], want_e9))""")

old = """        want_col = col + (2 if cn else 1)"""
assert s.count(old) == 1
s = s.replace(old, """        want_col = col + (2 if (cn or fx) else 1)""")

# ---- C2: only the two byte codes are mine ---------------------------------
old = """        if code >= 0xF0 or is_cn(code):
            continue"""
assert s.count(old) == 1
s = s.replace(old, """        if code >= 0xF0 or is_cn(code) or is_fx(code):
            continue""")

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('verify16 patched')