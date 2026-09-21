"""Add the stack relative opcodes the new drawer needs ($A3 LDA sr,S, $83 STA
sr,S) and keep the ALU table honest about the mode.

The drawer copies values off its own stack with `lda $03,s`; without these two
opcodes the simulator stops at the first one.
"""
import io

P = 'sim65816.py'
s = io.open(P, encoding='utf-8', newline='').read()
orig = s

# ---- mode support in the effective address decoder
old = """        if mode == '(dp,X)':"""
new = """        if mode in ('sr,S', 'sr,S,Y'):
            off = self.fetch()
            ad = (self.s + off) & 0xFFFF
            if mode.endswith(',Y'):
                ad = (ad + self.x) & 0xFFFF        # X, not Y: 65816 quirk
            return self.db, ad
        if mode == '(dp,X)':"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- LDA sr,S ($A3) next to the other LDA forms
old = """        elif op in (0xAF, 0xB2, 0xA1, 0xB5, 0xBE):   # LDA long/(dp)/(dp,X)/dp,X/abs,Y
            self.set_m(self._operand({0xAF: 'long', 0xB2: '(dp)', 0xA1: '(dp,X)',
                                      0xB5: 'dp,X', 0xBE: 'abs,Y'}[op]))"""
new = """        elif op in (0xAF, 0xB2, 0xA1, 0xB5, 0xBE, 0xA3):  # LDA long/(dp)/(dp,X)/dp,X/abs,Y/sr,S
            self.set_m(self._operand({0xAF: 'long', 0xB2: '(dp)', 0xA1: '(dp,X)',
                                      0xB5: 'dp,X', 0xBE: 'abs,Y',
                                      0xA3: 'sr,S'}[op]))"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- STA sr,S ($83)
old = """        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X'}[op], self.read_m())"""
new = """        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95, 0x83):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X',
                         0x83: 'sr,S'}[op], self.read_m())"""
assert s.count(old) == 1
s = s.replace(old, new)

if s != orig:
    io.open(P, 'w', encoding='utf-8', newline='').write(s)
    print('patched %s' % P)