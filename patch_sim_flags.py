"""Give the simulator's LDX/LDY/TAX/TAY/TSX/INX/INY/DEX/DEY/PLX/PLY proper Z/N.

Only LDA updated Z/N, so `LDX $0D43 / BEQ ...` kept the Z flag of whatever ran
before it: in the drawer's queue guard that turned "88 bytes needed" into "200
bytes needed" and the guard deferred every glyph once the queue held 32 bytes.
On hardware LDX sets Z/N like any other load, so the ROM was right and the model
was wrong.
"""
import io

P = 'sim65816.py'
s = io.open(P, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def sub(old, new, tag):
    global s
    assert s.count(old) == 1, (tag, s.count(old))
    s = s.replace(old, new)
    print('patched', tag)


sub("""        if self.m8:
            self.a = v & 0xFF""",
    """        if self.m8:
            self.a = v & 0xFF""", 'anchor set_m')   # no-op anchor, keeps the file stable

# helpers next to set_m
anchor = """    def set_m(self, v):"""
helper = """    def set_x(self, v):
        \"\"\"Load X and set Z/N (the index registers flag like the accumulator).\"\"\"
        self.x = v & (0xFF if self.x8 else 0xFFFF)
        self.z = (self.x == 0)
        self.n = bool(self.x & (0x80 if self.x8 else 0x8000))

    def set_y(self, v):
        \"\"\"Load Y and set Z/N.\"\"\"
        self.y = v & (0xFF if self.x8 else 0xFFFF)
        self.z = (self.y == 0)
        self.n = bool(self.y & (0x80 if self.x8 else 0x8000))

    def set_m(self, v):"""
sub(anchor, helper, 'helpers')

sub("""            self.y = v if self.x8 else (v | (self.fetch() << 8))""",
    """            self.set_y(v if self.x8 else (v | (self.fetch() << 8)))""", 'LDY #imm')
sub("""            self.x = v if self.x8 else (v | (self.fetch() << 8))""",
    """            self.set_x(v if self.x8 else (v | (self.fetch() << 8)))""", 'LDX #imm')
sub("""            self.x = self.a & 0xFF if self.x8 else self.a & 0xFFFF""",
    """            self.set_x(self.a)""", 'TAX')
sub("""            self.y = self.a & 0xFF if self.x8 else self.a & 0xFFFF""",
    """            self.set_y(self.a)""", 'TAY')
sub("""            self.x = self.s & (0xFF if self.x8 else 0xFFFF)""",
    """            self.set_x(self.s)""", 'TSX')
sub("""            self.y = (self.y + 1) & (0xFF if self.x8 else 0xFFFF)
            self.z = (self.y == 0)""",
    """            self.set_y(self.y + 1)""", 'INY')
sub("""            self.x = (self.x + 1) & (0xFF if self.x8 else 0xFFFF)
            self.z = (self.x == 0)""",
    """            self.set_x(self.x + 1)""", 'INX')
sub("""            if op == 0x88:
                self.y = (self.y - 1) & (0xFF if self.x8 else 0xFFFF)
                v = self.y
            else:
                self.x = (self.x - 1) & (0xFF if self.x8 else 0xFFFF)
                v = self.x""",
    """            if op == 0x88:
                self.set_y(self.y - 1)
                v = self.y
            else:
                self.set_x(self.x - 1)
                v = self.x""", 'DEY/DEX')
sub("""            self.y = v & (0xFF if self.x8 else 0xFFFF)
            self.z = (self.y == 0)
            self.n = bool(self.y & (0x80 if self.x8 else 0x8000))""",
    """            self.set_y(v)""", 'LDY abs,X')
sub("""            self.y = lo | (hi << 8)""", """            self.set_y(lo | (hi << 8))""", 'PLY')
sub("""            self.x = lo | (hi << 8)""", """            self.set_x(lo | (hi << 8))""", 'PLX')
sub("""        elif op == 0xA6:                     # LDX dp
            ad = self.dp + self.fetch()
            self.x = self.bus.rd(self.db, ad)""",
    """        elif op == 0xA6:                     # LDX dp
            ad = self.dp + self.fetch()
            self.set_x(self.bus.rd(self.db, ad))""", 'LDX dp')
sub("""        elif op == 0xA4:                     # LDY dp
            ad = self.dp + self.fetch()
            self.y = self.bus.rd(self.db, ad)""",
    """        elif op == 0xA4:                     # LDY dp
            ad = self.dp + self.fetch()
            self.set_y(self.bus.rd(self.db, ad))""", 'LDY dp')
sub("""        elif op == 0xAC:                     # LDY abs
            ad = self.fetch16()
            self.y = self.bus.rd(self.db, ad)
            if not self.x8:
                self.y |= self.bus.rd(self.db, ad + 1) << 8""",
    """        elif op == 0xAC:                     # LDY abs
            ad = self.fetch16()
            v = self.bus.rd(self.db, ad)
            if not self.x8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_y(v)""", 'LDY abs')
sub("""        elif op == 0xAE:                     # LDX abs
            ad = self.fetch16()
            self.x = self.bus.rd(self.db, ad)
            if not self.x8:
                self.x |= self.bus.rd(self.db, ad + 1) << 8""",
    """        elif op == 0xAE:                     # LDX abs
            ad = self.fetch16()
            v = self.bus.rd(self.db, ad)
            if not self.x8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_x(v)""", 'LDX abs')

io.open(P, 'w', encoding='utf-8', newline='\n').write(s)
print('written', P)