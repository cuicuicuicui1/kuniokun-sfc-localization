"""Repair the mini CPU's register-store opcodes.

STX/STY/STZ with a 16 bit index register write two bytes on real hardware and
go through the I/O window when the address is a PPU/DMA register.  The
simulator wrote one byte straight to WRAM, so the new box blanking hook (which
uses `stx $2116` / `sty $2118` in 16 bit mode) would have looked like it wrote
nothing at all.
"""
import io
import sys

P = 'sim65816.py'
s = io.open(P, encoding='utf-8', newline='').read()
orig = s

# ---- STA per mode: $94 is STY dp,X and $96 is STX dp,Y, not STA
old = """        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95, 0x94, 0x96):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X',
                         0x94: 'dp,Y', 0x96: 'dp,Y'}[op], self.read_m())
"""
new = """        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X'}[op], self.read_m())
        elif op in (0x94, 0x96):             # STY dp,X / STX dp,Y
            self._reg_store_dp(0x94, 'dp,X' if op == 0x94 else 'dp,Y')
"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- STZ honours M and reaches the I/O window
old = """        elif op in (0x64, 0x74):             # STZ dp
            ad = self.dp + self.fetch()
            self.bus.wr(self.db, ad, 0)
        elif op == 0x9C:                     # STZ abs
            ad = self.fetch16()
            self.bus.wr(self.db, ad, 0)
"""
new = """        elif op in (0x64, 0x74):             # STZ dp / STZ dp,X
            if op == 0x74:
                ad = (self.dp + self.fetch() + self.x) & 0xFFFF
            else:
                ad = self.dp + self.fetch()
            self._io_or_wram(self.db, ad, 0)
            if not self.m8:
                self._io_or_wram(self.db, (ad + 1) & 0xFFFF, 0)
        elif op in (0x9C, 0x9E):             # STZ abs / STZ abs,X
            ad = self.fetch16()
            if op == 0x9E:
                ad = (ad + self.x) & 0xFFFF
            self._io_or_wram(self.db, ad, 0)
            if not self.m8:
                self._io_or_wram(self.db, (ad + 1) & 0xFFFF, 0)
"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- STY/STX dp and abs honour the index register width
old = """        elif op == 0x84:                     # STY dp
            ad = self.dp + self.fetch()
            self.bus.wr(self.db, ad, self.y & 0xFF)
        elif op == 0x86:                     # STX dp
            ad = self.dp + self.fetch()
            self.bus.wr(self.db, ad, self.x & 0xFF)
        elif op == 0x8E:                     # STX abs
            ad = self.fetch16()
            self.bus.wr(self.db, ad, self.x & 0xFF)
"""
new = """        elif op == 0x84:                     # STY dp
            ad = self.dp + self.fetch()
            self._reg_store(self.db, ad, self.y)
        elif op == 0x86:                     # STX dp
            ad = self.dp + self.fetch()
            self._reg_store(self.db, ad, self.x)
        elif op in (0x8C, 0x8E):             # STY abs / STX abs
            ad = self.fetch16()
            self._reg_store(self.db, ad, self.y if op == 0x8C else self.x)
"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- helpers
old = """    def _store(self, mode, val):
        bk, ad = self._ea(mode)
        self._write(bk, ad, val)
"""
new = """    def _store(self, mode, val):
        bk, ad = self._ea(mode)
        self._write(bk, ad, val)

    def _reg_store_dp(self, op, mode):
        \"\"\"STY dp,X / STX dp,Y: the register width, not M, decides the size.\"\"\"
        self._reg_store(self.db, self._ea(mode)[1],
                        self.y if op == 0x94 else self.x)

    def _io_or_wram(self, bk, ad, val):
        if 0x2100 <= ad <= 0x21FF or 0x4200 <= ad <= 0x44FF:
            self.io_write(ad, val & 0xFF)
        else:
            self.bus.wr(bk, ad, val & 0xFF)

    def _reg_store(self, bk, ad, val):
        self._io_or_wram(bk, ad, val)
        if not self.x8:
            self._io_or_wram(bk, (ad + 1) & 0xFFFF, (val >> 8) & 0xFF)
"""
assert s.count(old) == 1
s = s.replace(old, new)

# ---- keep the reader fast: cache the register width on the CPU
old = """    def inc_vram(self):"""
assert s.count(old) >= 1

if s == orig:
    print('nothing changed')
    sys.exit(0)
io.open(P, 'w', encoding='utf-8', newline='').write(s)
print('patched %s' % P)