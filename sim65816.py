"""Minimal 65816 interpreter (only the opcodes this patch needs) + PPU model.

Purpose: verify the Chinese-patch renderer hooks end-to-end WITHOUT an emulator,
by executing the patched code and rendering the resulting VRAM tilemap to a PNG.
"""
import sys

ROM_BANKS_HI = 0x40  # LoROM banks $00-$3F / $80-$BF map ROM in $8000-$FFFF


class Bus:
    def __init__(self, rom):
        self.rom = rom
        self.wram = bytearray(0x20000)   # $7E0000-$7FFFFF

    def rd(self, bank, addr):
        a = addr & 0xFFFF
        b = bank & 0xFF
        if 0x8000 <= a <= 0xFFFF and (b & 0x7F) < ROM_BANKS_HI:
            off = (b & 0x7F) * 0x8000 + (a - 0x8000)
            return self.rom[off] if off < len(self.rom) else 0
        # WRAM / low RAM
        if b in (0x7E, 0x7F):
            return self.wram[((b - 0x7E) << 16) + a] if a < 0x10000 else 0
        return self.wram[a]          # low RAM of banks 0-0x3F

    def wr(self, bank, addr, val):
        a = addr & 0xFFFF
        b = bank & 0xFF
        if b in (0x7E, 0x7F):
            self.wram[((b - 0x7E) << 16) + a] = val & 0xFF
        else:
            self.wram[a] = val & 0xFF


class CPU:
    def __init__(self, rom):
        self.bus = Bus(rom)
        self.a = 0
        self.x = 0
        self.y = 0
        self.s = 0x01FF
        self.d = 0
        self.db = 0x00
        self.pbr = 0x00
        self.pc = 0
        self.m8 = True
        self.x8 = True
        self.n = self.z = self.c = self.v = self.i = False
        self.vram = [0] * 0x8000      # 32K words
        self.vmain = 0x80
        self.vaddr = 0
        self.vlow = 0
        self.dma_regs = {}
        self.dma_log = []
        self.steps = 0
        self.trace = []

    # ---- helpers -----------------------------------------------------
    @property
    def dp(self):
        return self.d

    def rb(self, bank, addr):
        return self.bus.rd(bank, addr)

    def fetch(self):
        v = self.bus.rd(self.pbr, self.pc)
        self.pc = (self.pc + 1) & 0xFFFF
        return v

    def fetch16(self):
        lo = self.fetch()
        hi = self.fetch()
        return lo | (hi << 8)

    def push8(self, v):
        self.bus.wr(0, self.s, v & 0xFF)
        self.s = (self.s - 1) & 0xFFFF

    def pop8(self):
        self.s = (self.s + 1) & 0xFFFF
        return self.bus.rd(0, self.s)

    def read_m(self):
        """Read a value of the current accumulator width (M flag)."""
        if self.m8:
            return self.a & 0xFF
        return self.a & 0xFFFF

    def set_x(self, v):
        """Load X and set Z/N (the index registers flag like the accumulator)."""
        self.x = v & (0xFF if self.x8 else 0xFFFF)
        self.z = (self.x == 0)
        self.n = bool(self.x & (0x80 if self.x8 else 0x8000))

    def set_y(self, v):
        """Load Y and set Z/N."""
        self.y = v & (0xFF if self.x8 else 0xFFFF)
        self.z = (self.y == 0)
        self.n = bool(self.y & (0x80 if self.x8 else 0x8000))

    def set_m(self, v):
        """Load the accumulator and set Z/N exactly as a 65816 LDA would.

        Missing the flag update here made `LDA $abs / BEQ target` follow the
        stale Z of whichever CMP ran before it.
        """
        if self.m8:
            self.a = v & 0xFF
            self.z = (self.a == 0)
            self.n = bool(self.a & 0x80)
        else:
            self.a = v & 0xFFFF
            self.z = (self.a == 0)
            self.n = bool(self.a & 0x8000)

    def inc_vram(self):
        inc = {0: 1, 1: 32, 2: 128, 3: 128}[(self.vmain >> 0) & 3]
        self.vaddr = (self.vaddr + inc) & 0x7FFF

    def io_write(self, addr, val):
        addr &= 0xFFFF
        val &= 0xFF
        if addr in (0x2116, 0x2117):
            if addr == 0x2116:
                self.vaddr = (self.vaddr & 0xFF00) | val
            else:
                self.vaddr = (self.vaddr & 0x00FF) | (val << 8)
        elif addr == 0x2118:
            self.vlow = val
        elif addr == 0x2119:
            self.vram[self.vaddr & 0x7FFF] = self.vlow | (val << 8)
            if self.vmain & 0x80:
                self.vaddr = (self.vaddr & 0x7F00) | ((self.vaddr + {0: 1, 1: 32, 2: 128, 3: 128}[self.vmain & 3]) & 0xFF)
            else:
                self.inc_vram()
        elif addr == 0x2115:
            self.vmain = val
        elif 0x4300 <= addr <= 0x437F:
            self.dma_regs[addr] = val
        elif addr == 0x420B:
            self.do_dma(val)
        elif addr == 0x2100:
            self.brightness = val

    def do_dma(self, mask):
        for ch in range(8):
            if not (mask >> ch) & 1:
                continue
            base = 0x4300 + ch * 0x10
            dmap = self.dma_regs.get(base + 0, 0)
            bbad = self.dma_regs.get(base + 1, 0)
            src_lo = self.dma_regs.get(base + 2, 0)
            src_hi = self.dma_regs.get(base + 3, 0)
            src_bk = self.dma_regs.get(base + 4, 0)
            size = self.dma_regs.get(base + 5, 0) | (self.dma_regs.get(base + 6, 0) << 8)
            if size == 0:
                size = 0x10000
            src = src_lo | (src_hi << 8)
            mode = dmap & 7
            self.dma_log.append((ch, mode, bbad, src, src_bk, size))
            if mode == 1 and bbad == 0x18:
                # two registers: $2118 then $2119, one VRAM word per 2 source bytes
                for i in range(0, size, 2):
                    b0 = self.bus.rd(src_bk, (src + i) & 0xFFFF)
                    b1 = self.bus.rd(src_bk, (src + i + 1) & 0xFFFF)
                    self.vram[self.vaddr & 0x7FFF] = b0 | (b1 << 8)
                    self.inc_vram()

    # ---- main loop ---------------------------------------------------
    def run(self, max_steps=100000):
        while self.steps < max_steps:
            self.step()
            self.steps += 1
        return self.steps


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
        ALU_MODES[_b + 0x03] = (_n, 'sr,S')      # stack relative

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
        if mode in ('sr,S', 'sr,S,Y'):
            off = self.fetch()
            ad = (self.s + off) & 0xFFFF
            if mode.endswith(',Y'):
                ad = (ad + self.x) & 0xFFFF        # X, not Y: 65816 quirk
            return self.db, ad
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

    def _reg_store_dp(self, op, mode):
        """STY dp,X / STX dp,Y: the register width, not M, decides the size."""
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

    def step(self):
        op = self.fetch()
        pc0 = (self.pc - 1) & 0xFFFF
        if op == 0xEA:                       # NOP
            pass
        elif op == 0xE2:                     # SEP
            v = self.fetch()
            if v & 0x20:
                self.m8 = True
            if v & 0x10:
                self.x8 = True
        elif op == 0xC2:                     # REP
            v = self.fetch()
            if v & 0x20:
                self.m8 = False
            if v & 0x10:
                self.x8 = False
        elif op == 0xA9:                     # LDA #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            self.set_m(v)
        elif op == 0xA0:                     # LDY #imm
            v = self.fetch()
            self.set_y(v if self.x8 else (v | (self.fetch() << 8)))
        elif op == 0xA2:                     # LDX #imm
            v = self.fetch()
            self.set_x(v if self.x8 else (v | (self.fetch() << 8)))
        elif op == 0xA5:                     # LDA dp
            ad = self.dp + self.fetch()
            v = self.bus.rd(self.db, ad)
            if not self.m8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_m(v)
        elif op == 0x85:                     # STA dp
            ad = self.dp + self.fetch()
            v = self.read_m()
            self.bus.wr(self.db, ad, v & 0xFF)
            if not self.m8:
                self.bus.wr(self.db, ad + 1, (v >> 8) & 0xFF)
        elif op == 0x8D:                     # STA abs
            ad = self.fetch16()
            v = self.read_m()
            if 0x2100 <= ad <= 0x21FF or 0x4200 <= ad <= 0x44FF:
                self.io_write(ad, v & 0xFF)
                if not self.m8:
                    self.io_write(ad + 1, (v >> 8) & 0xFF)
            else:
                self.bus.wr(self.db, ad, v & 0xFF)
                if not self.m8:
                    self.bus.wr(self.db, ad + 1, (v >> 8) & 0xFF)
        elif op == 0xAD:                     # LDA abs
            ad = self.fetch16()
            v = self.bus.rd(self.db, ad)
            if not self.m8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_m(v)
        elif op == 0xBD:                     # LDA abs,X
            ad = (self.fetch16() + self.x) & 0xFFFF
            v = self.bus.rd(self.db, ad)
            if not self.m8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_m(v)
        elif op == 0xB7:                     # LDA [dp],Y   (24-bit pointer!)
            ad = self.dp + self.fetch()
            base = self.bus.rd(self.db, ad) | (self.bus.rd(self.db, ad + 1) << 8)
            bk = self.bus.rd(self.db, ad + 2)
            tgt = (base + self.y) & 0xFFFF
            v = self.bus.rd(bk, tgt)
            if not self.m8:
                v |= self.bus.rd(bk, tgt + 1) << 8
            self.set_m(v)
        elif op == 0xBF:                     # LDA long,X
            lo = self.fetch()
            hi = self.fetch()
            bk = self.fetch()
            ad = (lo | (hi << 8)) + self.x
            v = self.bus.rd(bk, ad & 0xFFFF)
            if not self.m8:
                v |= self.bus.rd(bk, (ad + 1) & 0xFFFF) << 8
            self.set_m(v)
        elif op == 0xB9:                     # LDA abs,Y
            ad = (self.fetch16() + self.y) & 0xFFFF
            v = self.bus.rd(self.db, ad)
            if not self.m8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_m(v)
        elif op == 0xC9:                     # CMP #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            self.cmp(self.read_m(), v)
        elif op == 0xC0:                     # CPY #imm
            v = self.fetch() if self.x8 else self.fetch16()
            self.cmp(self.y, v)
        elif op == 0xE0:                     # CPX #imm
            v = self.fetch() if self.x8 else self.fetch16()
            self.cmp(self.x, v)
        elif op == 0x0A:                     # ASL A
            v = self.read_m()
            c = (v >> (7 if self.m8 else 15)) & 1
            v = (v << 1) & (0xFF if self.m8 else 0xFFFF)
            self.set_m(v)
            self.z = (v == 0)
            self.n = bool(v & (0x80 if self.m8 else 0x8000))
            self.c = bool(c)
        elif op == 0xAA:                     # TAX
            self.set_x(self.a)
        elif op == 0x8A:                     # TXA
            self.set_m(self.x & (0xFF if self.m8 else 0xFFFF))
        elif op == 0xA8:                     # TAY
            self.set_y(self.a)
        elif op == 0xBA:                     # TSX
            self.set_x(self.s)
        elif op == 0xC8:                     # INY
            self.set_y(self.y + 1)
        elif op == 0xE8:                     # INX
            self.set_x(self.x + 1)
        elif op == 0xE6:                     # INC dp
            ad = self.dp + self.fetch()
            v = (self.bus.rd(self.db, ad) + 1) & 0xFF
            self.bus.wr(self.db, ad, v)
            self.z = (v == 0)
            self.n = bool(v & 0x80)
        elif op == 0x1A:                     # INC A
            m = 0xFF if self.m8 else 0xFFFF
            v = (self.read_m() + 1) & m
            self.set_m(v)
            self.z = (v == 0)
            self.n = bool(v & (0x80 if self.m8 else 0x8000))
        elif op == 0x3A:                     # DEC A
            m = 0xFF if self.m8 else 0xFFFF
            v = (self.read_m() - 1) & m
            self.set_m(v)
            self.z = (v == 0)
            self.n = bool(v & (0x80 if self.m8 else 0x8000))
        elif op == 0xC6:                     # DEC dp
            ad = self.dp + self.fetch()
            v = (self.bus.rd(self.db, ad) - 1) & 0xFF
            self.bus.wr(self.db, ad, v)
            self.z = (v == 0)
        elif op == 0x38:                     # SEC
            self.c = True
        elif op == 0x18:                     # CLC
            self.c = False
        elif op == 0xE9:                     # SBC #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            m = 0xFF if self.m8 else 0xFFFF
            r = (self.read_m() - v - (0 if self.c else 1)) & m
            self.c = (self.read_m() - v - (0 if self.c else 1)) >= 0
            self.set_m(r)
            self.z = (r == 0)
            self.n = bool(r & (0x80 if self.m8 else 0x8000))
        elif op == 0x69:                     # ADC #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            m = 0xFF if self.m8 else 0xFFFF
            r = self.read_m() + v + (1 if self.c else 0)
            self.c = r > m
            self.set_m(r & m)
            self.z = ((r & m) == 0)
        elif op in self.ALU_MODES:           # ORA/AND/EOR/ADC/CMP/SBC (all modes)
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
        elif op in (0x8F, 0x9F, 0x99, 0x9D, 0x92, 0x81, 0x95, 0x83):  # STA per mode
            self._store({0x8F: 'long', 0x9F: 'long,X', 0x99: 'abs,Y', 0x9D: 'abs,X',
                         0x92: '(dp)', 0x81: '(dp,X)', 0x95: 'dp,X',
                         0x83: 'sr,S'}[op], self.read_m())
        elif op in (0x94, 0x96):             # STY dp,X / STX dp,Y
            self._reg_store_dp(0x94, 'dp,X' if op == 0x94 else 'dp,Y')
        elif op in (0xAF, 0xB2, 0xA1, 0xB5, 0xBE, 0xA3):  # LDA long/(dp)/(dp,X)/dp,X/abs,Y/sr,S
            self.set_m(self._operand({0xAF: 'long', 0xB2: '(dp)', 0xA1: '(dp,X)',
                                      0xB5: 'dp,X', 0xBE: 'abs,Y',
                                      0xA3: 'sr,S'}[op]))
            self.z = (self.read_m() == 0)
            self.n = bool(self.read_m() & (0x80 if self.m8 else 0x8000))
        elif op in (0xBC, 0xBB):             # LDY abs,X
            v = self._operand('abs,X')
            self.set_y(v)
        elif op in (0xEE, 0xEF, 0xFE, 0xE7, 0xF7, 0xCE, 0xDE, 0xC7, 0xD7):
            isinc = op in (0xEE, 0xEF, 0xFE, 0xE7, 0xF7)
            md = {0xEE: 'abs', 0xEF: 'long', 0xFE: 'abs,X', 0xE7: 'dp', 0xF7: 'dp,X',
                  0xCE: 'abs', 0xDE: 'abs,X', 0xC7: 'dp', 0xD7: 'dp,X'}[op]
            step = 1 if isinc else -1
            self._rmw(md, lambda c: c + step, self.m8)
        elif op in (0x88, 0xCA):             # DEY / DEX
            if op == 0x88:
                self.set_y(self.y - 1)
                v = self.y
            else:
                self.set_x(self.x - 1)
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
        elif op in (0xF0, 0xD0, 0x90, 0xB0, 0x10, 0x30, 0x80):
            d = self.fetch()
            if d >= 0x80:
                d -= 0x100
            take = {
                0xF0: self.z, 0xD0: not self.z, 0x90: not self.c, 0xB0: self.c,
                0x10: not self.n, 0x30: self.n, 0x80: True,
            }[op]
            if take:
                self.pc = (self.pc + d) & 0xFFFF
        elif op == 0x4C:                     # JMP abs
            self.pc = self.fetch16()
        elif op == 0x5C:                     # JML long
            lo = self.fetch()
            hi = self.fetch()
            bk = self.fetch()
            self.pc = lo | (hi << 8)
            self.pbr = bk
        elif op == 0x20:                     # JSR abs
            tgt = self.fetch16()
            ret = (self.pc - 1) & 0xFFFF
            self.push8(ret >> 8)
            self.push8(ret & 0xFF)
            self.pc = tgt
        elif op == 0x22:                     # JSL long
            lo = self.fetch()
            hi = self.fetch()
            bk = self.fetch()
            ret = (self.pc - 1) & 0xFFFF
            self.push8(self.pbr)
            self.push8(ret >> 8)
            self.push8(ret & 0xFF)
            self.pbr = bk
            self.pc = lo | (hi << 8)
        elif op == 0x60:                     # RTS
            lo = self.pop8()
            hi = self.pop8()
            self.pc = ((hi << 8) | lo) + 1
        elif op == 0x6B:                     # RTL
            lo = self.pop8()
            hi = self.pop8()
            bk = self.pop8()
            self.pc = (((hi << 8) | lo) + 1) & 0xFFFF
            self.pbr = bk
        elif op == 0x48:                     # PHA
            if self.m8:                      # 8-bit accumulator pushes one byte
                self.push8(self.a & 0xFF)
            else:
                self.push8(self.a >> 8)
                self.push8(self.a & 0xFF)
        elif op == 0x08:                     # PHP
            self.push8((0x80 if self.n else 0) | (0x40 if self.v else 0) |
                       (0x20 if self.m8 else 0) | (0x10 if self.x8 else 0) |
                       (0x08 if self.d else 0) | (0x04 if self.i else 0) |
                       (0x02 if self.z else 0) | (0x01 if self.c else 0))
        elif op == 0x28:                     # PLP
            v = self.pop8()
            self.n = bool(v & 0x80)
            self.v = bool(v & 0x40)
            self.m8 = bool(v & 0x20)
            self.x8 = bool(v & 0x10)
            self.d = bool(v & 0x08)
            self.i = bool(v & 0x04)
            self.z = bool(v & 0x02)
            self.c = bool(v & 0x01)
        elif op == 0x68:                     # PLA
            lo = self.pop8()
            hi = self.pop8() if not self.m8 else 0
            self.set_m(lo | (hi << 8))
            self.z = (self.read_m() == 0)
        elif op == 0xEB:                     # XBA: swap A's two bytes
            a = self.a & 0xFFFF
            self.a = ((a & 0xFF) << 8) | (a >> 8)
            self.z = (self.a & 0xFF) == 0
            self.n = bool(self.a & 0x80)
        elif op == 0x8B:                     # PHB
            self.push8(self.db)
        elif op == 0xAB:                     # PLB
            self.db = self.pop8()
        elif op == 0x5A:                     # PHY
            if not self.x8:                  # 8 bit index pushes one byte
                self.push8(self.y >> 8)
            self.push8(self.y & 0xFF)
        elif op == 0x7A:                     # PLY
            lo = self.pop8()
            hi = self.pop8() if not self.x8 else 0
            self.set_y(lo | (hi << 8))
        elif op == 0xDA:                     # PHX
            if not self.x8:
                self.push8(self.x >> 8)
            self.push8(self.x & 0xFF)
        elif op == 0xFA:                     # PLX
            lo = self.pop8()
            hi = self.pop8() if not self.x8 else 0
            self.set_x(lo | (hi << 8))
        elif op in (0x64, 0x74):             # STZ dp / STZ dp,X
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
        elif op == 0x1C:                     # TRB abs
            ad = self.fetch16()
            self.bus.wr(self.db, ad, self.bus.rd(self.db, ad) & ~(self.read_m() & 0xFF))
        elif op == 0x0C:                     # TSB abs
            ad = self.fetch16()
            self.bus.wr(self.db, ad, self.bus.rd(self.db, ad) | (self.read_m() & 0xFF))
        elif op == 0x6C:                     # JMP (abs)
            ad = self.fetch16()
            self.pc = self.bus.rd(self.db, ad) | (self.bus.rd(self.db, ad + 1) << 8)
        elif op in (0x7C,):                  # JMP (abs,X)
            ad = (self.fetch16() + self.x) & 0xFFFF
            self.pc = self.bus.rd(self.db, ad) | (self.bus.rd(self.db, ad + 1) << 8)
        elif op == 0xA6:                     # LDX dp
            ad = self.dp + self.fetch()
            self.set_x(self.bus.rd(self.db, ad))
        elif op == 0xA4:                     # LDY dp
            ad = self.dp + self.fetch()
            self.set_y(self.bus.rd(self.db, ad))
        elif op == 0x84:                     # STY dp
            ad = self.dp + self.fetch()
            self._reg_store(self.db, ad, self.y)
        elif op == 0x86:                     # STX dp
            ad = self.dp + self.fetch()
            self._reg_store(self.db, ad, self.x)
        elif op in (0x8C, 0x8E):             # STY abs / STX abs
            ad = self.fetch16()
            self._reg_store(self.db, ad, self.y if op == 0x8C else self.x)
        elif op == 0xAC:                     # LDY abs
            ad = self.fetch16()
            v = self.bus.rd(self.db, ad)
            if not self.x8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_y(v)
        elif op == 0xAE:                     # LDX abs
            ad = self.fetch16()
            v = self.bus.rd(self.db, ad)
            if not self.x8:
                v |= self.bus.rd(self.db, ad + 1) << 8
            self.set_x(v)
        elif op == 0x29:                     # AND #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            self.set_m(self.read_m() & v)
            self.z = (self.read_m() == 0)
        elif op == 0x09:                     # ORA #imm
            v = self.fetch()
            if not self.m8:
                v |= self.fetch() << 8
            self.set_m(self.read_m() | v)
            self.z = (self.read_m() == 0)
        elif op in (0xDB,):                  # STOP
            raise SystemExit('STP at %02X:%04X' % (self.pbr, self.pc))
        else:
            raise NotImplementedError('opcode $%02X at %02X:%04X'
                                      % (op, self.pbr, (self.pc - 1) & 0xFFFF))
        self.last_pc = pc0

    def cmp(self, a, b):
        r = (a - b) & (0xFF if self.m8 else 0xFFFF)
        self.z = (r == 0)
        self.n = bool(r & (0x80 if self.m8 else 0x8000))
        self.c = a >= b

    # flags default
    z = False
    n = False
    c = False