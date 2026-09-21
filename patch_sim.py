import re

p = 'sim65816.py'
s = open(p, encoding='utf-8').read()
if 'ALU_MODES' in s:
    raise SystemExit('already patched')

HELPERS = '''
    # ---- generic addressing-mode decoding for the ALU / load-store families ----
    ALU_MODES = {}
    for _b, _n in ((0x00, 'ORA'), (0x20, 'AND'), (0x40, 'EOR'),
                   (0x60, 'ADC'), (0xC0, 'CMP'), (0xE0, 'SBC')):
        ALU_MODES[_b + 0x01] = (_n, '(dp,X)')
        ALU_MODES[_b + 0x05] = (_n, 'dp')
        ALU_MODES[_b + 0x09] = (_n, '#')
        ALU_MODES[_b + 0x0D] = (_n, 'abs')
        ALU_MODES[_b + 0x0F] = (_n, 'long')
        ALU_MODES[_b + 0x11] = (_n, '(dp),Y')
        ALU_MODES[_b + 0x15] = (_n, 'dp,X')
        ALU_MODES[_b + 0x19] = (_n, 'abs,Y')
        ALU_MODES[_b + 0x1D] = (_n, 'abs,X')

    def _ea(self, mode):
        """Decode an operand address (advancing pc).  Returns (bank, addr)."""
        if mode == 'dp':
            return self.db, (self.dp + self.fetch()) & 0xFFFF
        if mode == 'dp,X':
            return self.db, (self.dp + self.fetch() + self.x) & 0xFFFF
        if mode == 'dp,Y':
            return self.db, (self.dp + self.fetch() + self.y) & 0xFFFF
        if mode == 'abs':
            return self.db, self.fetch16()
        if mode == 'abs,X':
            return self.db, (self.fetch16() + self.x) & 0xFFFF
        if mode == 'abs,Y':
            return self.db, (self.fetch16() + self.y) & 0xFFFF
        if mode == '(dp,X)':
            d = (self.dp + self.fetch() + self.x) & 0xFFFF
            ad = self.bus.rd(self.db, d) | (self.bus.rd(self.db, d + 1) << 8)
            return self.db, ad & 0xFFFF
        if mode == '(dp),Y':
            d = (self.dp + self.fetch()) & 0xFFFF
            ad = self.bus.rd(self.db, d) | (self.bus.rd(self.db, d + 1) << 8)
            return self.db, (ad + self.y) & 0xFFFF
        if mode == '(dp)':
            d = (self.dp + self.fetch()) & 0xFFFF
            ad = self.bus.rd(self.db, d) | (self.bus.rd(self.db, d + 1) << 8)
            return self.db, ad & 0xFFFF
        if mode == 'long':
            ad = self.fetch() | (self.fetch() << 8)
            return self.fetch(), ad & 0xFFFF
        if mode == 'long,X':
            ad = self.fetch() | (self.fetch() << 8)
            bk = self.fetch()
            return bk, (ad + self.x) & 0xFFFF
        raise NotImplementedError('mode ' + mode)

    def _operand(self, mode):
        """Value addressed by `mode` (or the immediate value for '#')."""
        m = 0xFF if self.m8 else 0xFFFF
        if mode == '#':
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            return v & m
        bk, ad = self._ea(mode)
        v = self.bus.rd(bk, ad)
        if not self.m8:
            v |= self.bus.rd(bk, (ad + 1) & 0xFFFF) << 8
        return v & m

    def _write(self, bk, ad, val):
        ad &= 0xFFFF
        if 0x2100 <= ad <= 0x21FF or 0x4200 <= ad <= 0x44FF:
            self.io_write(ad, val & 0xFF)
            if not self.m8:
                self.io_write((ad + 1) & 0xFFFF, (val >> 8) & 0xFF)
        else:
            self.bus.wr(bk, ad, val & 0xFF)
            if not self.m8:
                self.bus.wr(bk, (ad + 1) & 0xFFFF, (val >> 8) & 0xFF)

    def _store(self, mode, val):
        bk, ad = self._ea(mode)
        self._write(bk, ad, val)

    def _rmw(self, mode, fn, width8):
        """Read-modify-write through one decoded address (for INC/DEC/ASL/LSR)."""
        bk, ad = self._ea(mode)
        cur = self.bus.rd(bk, ad)
        if not width8:
            cur |= self.bus.rd(bk, (ad + 1) & 0xFFFF) << 8
        nv = fn(cur) & (0xFF if width8 else 0xFFFF)
        self.bus.wr(bk, ad, nv & 0xFF)
        if not width8:
            self.bus.wr(bk, (ad + 1) & 0xFFFF, (nv >> 8) & 0xFF)
        self.z = (nv == 0)
        self.n = bool(nv & (0x80 if width8 else 0x8000))

'''

anchor = '    def step(self):'
assert anchor in s, 'step() anchor not found'
s = s.replace(anchor, HELPERS + anchor, 1)

NEW = '''        elif op in self.ALU_MODES:           # ORA/AND/EOR/ADC/CMP/SBC (all modes)
            name, mode = self.ALU_MODES[op]
            v = self._operand(mode)
            m = 0xFF if self.m8 else 0xFFFF
            a = self.read_m()
            if name == 'ADC':
                r = a + v + (1 if self.c else 0)
                self.c = r > m
            elif name == 'SBC':
                r = a - v - (0 if self.c else 1)
                self.c = (a - v - (0 if self.c else 1)) >= 0
            elif name == 'ORA':
                r = a | v
            elif name == 'AND':
                r = a & v
            elif name == 'EOR':
                r = a ^ v
            else:                            # CMP
                r = a - v
                self.c = a >= v
            r &= m
            self.z = (r == 0)
            self.n = bool(r & (0x80 if self.m8 else 0x8000))
            if name != 'CMP':
                self.set_m(r)
        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95, 0x94, 0x96):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X',
                         0x94: 'dp,Y', 0x96: 'dp,Y'}[op], self.read_m())
        elif op in (0xAF, 0xB2, 0xA1, 0xB5, 0xBE):   # LDA long/(dp)/(dp,X)/dp,X/abs,Y
            self.set_m(self._operand({0xAF: 'long', 0xB2: '(dp)', 0xA1: '(dp,X)',
                                      0xB5: 'dp,X', 0xBE: 'abs,Y'}[op]))
            self.z = (self.read_m() == 0)
            self.n = bool(self.read_m() & (0x80 if self.m8 else 0x8000))
        elif op in (0xBC, 0xBB):             # LDY abs,X
            v = self._operand('abs,X')
            self.y = v & (0xFF if self.x8 else 0xFFFF)
            self.z = (self.y == 0)
            self.n = bool(self.y & (0x80 if self.x8 else 0x8000))
        elif op in (0xEE, 0xEF, 0xFE, 0xE7, 0xF7, 0xCE, 0xDE, 0xC7, 0xD7):
            isinc = op in (0xEE, 0xEF, 0xFE, 0xE7, 0xF7)
            md = {0xEE: 'abs', 0xEF: 'long', 0xFE: 'abs,X', 0xE7: 'dp', 0xF7: 'dp,X',
                  0xCE: 'abs', 0xDE: 'abs,X', 0xC7: 'dp', 0xD7: 'dp,X'}[op]
            step = 1 if isinc else -1
            self._rmw(md, lambda c: c + step, self.m8)
        elif op in (0x88, 0xCA):             # DEY / DEX
            if op == 0x88:
                self.y = (self.y - 1) & (0xFF if self.x8 else 0xFFFF)
                v = self.y
            else:
                self.x = (self.x - 1) & (0xFF if self.x8 else 0xFFFF)
                v = self.x
            self.z = (v == 0)
            self.n = bool(v & (0x80 if self.x8 else 0x8000))
        elif op == 0x98:                     # TYA
            self.set_m(self.y)
            self.z = (self.read_m() == 0)
            self.n = bool(self.read_m() & (0x80 if self.m8 else 0x8000))
        elif op in (0x4A, 0x2A, 0x6A):       # LSR A / ROL A / ROR A
            a = self.read_m()
            m = 0xFF if self.m8 else 0xFFFF
            top = 0x80 if self.m8 else 0x8000
            if op == 0x4A:
                self.c = bool(a & 1)
                r = (a >> 1) & m
            elif op == 0x2A:
                r = ((a << 1) | (1 if self.c else 0)) & m
                self.c = bool(a & top)
            else:
                r = ((a >> 1) | (top if self.c else 0)) & m
                self.c = bool(a & 1)
            self.set_m(r)
            self.z = (r == 0)
            self.n = bool(r & top)
        elif op in (0x0E, 0x4E):             # ASL abs / LSR abs
            if op == 0x0E:
                def _fn(c, _t=0x80 if self.m8 else 0x8000, _s=self):
                    _s.c = bool(c & _t)
                    return c << 1
            else:
                def _fn(c, _s=self):
                    _s.c = bool(c & 1)
                    return c >> 1
            self._rmw('abs', _fn, self.m8)
        elif op == 0x2C:                     # BIT abs
            v = self._operand('abs')
            self.z = ((self.read_m() & v) & (0xFF if self.m8 else 0xFFFF)) == 0
            self.n = bool(v & (0x80 if self.m8 else 0x8000))
        elif op in (0xEC, 0xCC):             # CPX abs / CPY abs
            v = self._operand('abs')
            r = self.x if op == 0xEC else self.y
            self.c = r >= v
            d = (r - v) & (0xFF if self.x8 else 0xFFFF)
            self.z = (d == 0)
            self.n = bool(d & (0x80 if self.x8 else 0x8000))
        elif op == 0x7C:                     # JMP (abs,X)
            ad = (self.fetch16() + self.x) & 0xFFFF
            self.pc = self.bus.rd(self.pbr, ad) | (self.bus.rd(self.pbr, ad + 1) << 8)
'''
anchor2 = "        elif op in (0xF0, 0xD0, 0x90, 0xB0, 0x10, 0x30, 0x80):"
assert anchor2 in s, 'branch anchor not found'
s = s.replace(anchor2, NEW + anchor2, 1)

open(p, 'w', encoding='utf-8').write(s)
print('simulator patched')