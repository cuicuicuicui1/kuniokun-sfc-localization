"""Minimal 65816 disassembler for LoROM analysis.

Tracks M/X flag widths through REP/SEP when disassembling linearly.
Addressing-mode strings follow common (ca65-ish) notation.
"""
# opcode -> (mnemonic, mode)
OPS = {}
def _d(mn, mode, *codes):
    for c in codes:
        OPS[c] = (mn, mode)

_d('BRK','sig',0x00); _d('ORA','indx',0x01); _d('COP','imm',0x02); _d('ORA','sr',0x03)
_d('TSB','dp',0x04); _d('ORA','dp',0x05); _d('ASL','dp',0x06); _d('ORA','indl',0x07)
_d('PHP','imp',0x08); _d('ORA','immM',0x09); _d('ASL','acc',0x0A); _d('PHD','imp',0x0B)
_d('TSB','abs',0x0C); _d('ORA','abs',0x0D); _d('ASL','abs',0x0E); _d('ORA','long',0x0F)
_d('BPL','rel',0x10); _d('ORA','indy',0x11); _d('ORA','dpi',0x12); _d('ORA','sr',0x13)
_d('TRB','dp',0x14); _d('ORA','dpx',0x15); _d('ASL','dpx',0x16); _d('ORA','indly',0x17)
_d('CLC','imp',0x18); _d('ORA','absy',0x19); _d('INC','acc',0x1A); _d('TCS','imp',0x1B)
_d('TRB','abs',0x1C); _d('ORA','absx',0x1D); _d('ASL','absx',0x1E); _d('ORA','longx',0x1F)
_d('JSR','abs',0x20); _d('AND','indx',0x21); _d('JSL','long',0x22); _d('AND','sr',0x23)
_d('BIT','dp',0x24); _d('AND','dp',0x25); _d('ROL','dp',0x26); _d('AND','indl',0x27)
_d('PLP','imp',0x28); _d('AND','immM',0x29); _d('ROL','acc',0x2A); _d('PLD','imp',0x2B)
_d('BIT','abs',0x2C); _d('AND','abs',0x2D); _d('ROL','abs',0x2E); _d('AND','long',0x2F)
_d('BMI','rel',0x30); _d('AND','indy',0x31); _d('AND','dpi',0x32); _d('AND','sr',0x33)
_d('BIT','dpx',0x34); _d('AND','dpx',0x35); _d('ROL','dpx',0x36); _d('AND','indly',0x37)
_d('SEC','imp',0x38); _d('AND','absy',0x39); _d('DEC','acc',0x3A); _d('TSC','imp',0x3B)
_d('BIT','absx',0x3C); _d('AND','absx',0x3D); _d('ROL','absx',0x3E); _d('AND','longx',0x3F)
_d('RTI','imp',0x40); _d('EOR','indx',0x41); _d('WDM','imm',0x42); _d('EOR','sr',0x43)
_d('MVP','blk',0x44); _d('EOR','dp',0x45); _d('LSR','dp',0x46); _d('EOR','indl',0x47)
_d('PHA','imp',0x48); _d('EOR','immM',0x49); _d('LSR','acc',0x4A); _d('PHK','imp',0x4B)
_d('JMP','abs',0x4C); _d('EOR','abs',0x4D); _d('LSR','abs',0x4E); _d('EOR','long',0x4F)
_d('BVC','rel',0x50); _d('EOR','indy',0x51); _d('EOR','dpi',0x52); _d('EOR','sr',0x53)
_d('MVN','blk',0x54); _d('EOR','dpx',0x55); _d('LSR','dpx',0x56); _d('EOR','indly',0x57)
_d('CLI','imp',0x58); _d('EOR','absy',0x59); _d('PHY','imp',0x5A); _d('TCD','imp',0x5B)
_d('JML','long',0x5C); _d('EOR','absx',0x5D); _d('LSR','absx',0x5E); _d('EOR','longx',0x5F)
_d('RTS','imp',0x60); _d('ADC','indx',0x61); _d('PER','rel16',0x62); _d('ADC','sr',0x63)
_d('STZ','dp',0x64); _d('ADC','dp',0x65); _d('ROR','dp',0x66); _d('ADC','indl',0x67)
_d('PLA','imp',0x68); _d('ADC','immM',0x69); _d('ROR','acc',0x6A); _d('RTL','imp',0x6B)
_d('JMP','ind',0x6C); _d('ADC','abs',0x6D); _d('ROR','abs',0x6E); _d('ADC','long',0x6F)
_d('BVS','rel',0x70); _d('ADC','indy',0x71); _d('ADC','dpi',0x72); _d('ADC','sr',0x73)
_d('STZ','dpx',0x74); _d('ADC','dpx',0x75); _d('ROR','dpx',0x76); _d('ADC','indly',0x77)
_d('SEI','imp',0x78); _d('ADC','absy',0x79); _d('PLY','imp',0x7A); _d('TDC','imp',0x7B)
_d('JMP','indx',0x7C); _d('ADC','absx',0x7D); _d('ROR','absx',0x7E); _d('ADC','longx',0x7F)
_d('BRA','rel',0x80); _d('STA','indx',0x81); _d('BRL','rel16',0x82); _d('STA','sr',0x83)
_d('STY','dp',0x84); _d('STA','dp',0x85); _d('STX','dp',0x86); _d('STA','indl',0x87)
_d('DEY','imp',0x88); _d('BIT','immM',0x89); _d('TXA','imp',0x8A); _d('PHB','imp',0x8B)
_d('STY','abs',0x8C); _d('STA','abs',0x8D); _d('STX','abs',0x8E); _d('STA','long',0x8F)
_d('BCC','rel',0x90); _d('STA','indy',0x91); _d('STA','dpi',0x92); _d('STA','sr',0x93)
_d('STY','dpx',0x94); _d('STA','dpx',0x95); _d('STX','dpy',0x96); _d('STA','indly',0x97)
_d('TYA','imp',0x98); _d('STA','absy',0x99); _d('TXS','imp',0x9A); _d('TXY','imp',0x9B)
_d('STZ','abs',0x9C); _d('STA','absx',0x9D); _d('STZ','absx',0x9E); _d('STA','longx',0x9F)
_d('LDY','immX',0xA0); _d('LDA','indx',0xA1); _d('LDX','immX',0xA2); _d('LDA','sr',0xA3)
_d('LDY','dp',0xA4); _d('LDA','dp',0xA5); _d('LDX','dp',0xA6); _d('LDA','indl',0xA7)
_d('TAY','imp',0xA8); _d('LDA','immM',0xA9); _d('TAX','imp',0xAA); _d('PLB','imp',0xAB)
_d('LDY','abs',0xAC); _d('LDA','abs',0xAD); _d('LDX','abs',0xAE); _d('LDA','long',0xAF)
_d('BCS','rel',0xB0); _d('LDA','indy',0xB1); _d('LDA','dpi',0xB2); _d('LDA','sr',0xB3)
_d('LDY','dpx',0xB4); _d('LDA','dpx',0xB5); _d('LDX','dpy',0xB6); _d('LDA','indly',0xB7)
_d('CLV','imp',0xB8); _d('LDA','absy',0xB9); _d('TSX','imp',0xBA); _d('TYX','imp',0xBB)
_d('LDY','absx',0xBC); _d('LDA','absx',0xBD); _d('LDX','absy',0xBE); _d('LDA','longx',0xBF)
_d('CPY','immX',0xC0); _d('CMP','indx',0xC1); _d('REP','imm',0xC2); _d('CMP','sr',0xC3)
_d('CPY','dp',0xC4); _d('CMP','dp',0xC5); _d('DEC','dp',0xC6); _d('CMP','indl',0xC7)
_d('INY','imp',0xC8); _d('CMP','immM',0xC9); _d('DEX','imp',0xCA); _d('WAI','imp',0xCB)
_d('CPY','abs',0xCC); _d('CMP','abs',0xCD); _d('DEC','abs',0xCE); _d('CMP','long',0xCF)
_d('BNE','rel',0xD0); _d('CMP','indy',0xD1); _d('CMP','dpi',0xD2); _d('CMP','sr',0xD3)
_d('PEI','dp',0xD4); _d('CMP','dpx',0xD5); _d('DEC','dpx',0xD6); _d('CMP','indly',0xD7)
_d('CLD','imp',0xD8); _d('CMP','absy',0xD9); _d('PHX','imp',0xDA); _d('STP','imp',0xDB)
_d('JML','indl',0xDC); _d('CMP','absx',0xDD); _d('DEC','absx',0xDE); _d('CMP','longx',0xDF)
_d('CPX','immX',0xE0); _d('SBC','indx',0xE1); _d('SEP','imm',0xE2); _d('SBC','sr',0xE3)
_d('CPX','dp',0xE4); _d('SBC','dp',0xE5); _d('INC','dp',0xE6); _d('SBC','indl',0xE7)
_d('INX','imp',0xE8); _d('SBC','immM',0xE9); _d('NOP','imp',0xEA); _d('XBA','imp',0xEB)
_d('CPX','abs',0xEC); _d('SBC','abs',0xED); _d('INC','abs',0xEE); _d('SBC','long',0xEF)
_d('BEQ','rel',0xF0); _d('SBC','indy',0xF1); _d('SBC','dpi',0xF2); _d('SBC','sr',0xF3)
_d('PEA','abs',0xF4); _d('SBC','dpx',0xF5); _d('INC','dpx',0xF6); _d('SBC','indly',0xF7)
_d('SED','imp',0xF8); _d('SBC','absy',0xF9); _d('PLX','imp',0xFA); _d('XCE','imp',0xFB)
_d('JSR','indx',0xFC); _d('SBC','absx',0xFD); _d('INC','absx',0xFE); _d('SBC','longx',0xFF)

SIZE = {'imp':1,'acc':1,'sig':2,'imm':2,'immM':None,'immX':None,'dp':2,'dpx':2,'dpy':2,
        'sr':2,'indx':2,'indy':2,'dpi':2,'indl':2,'indly':2,'abs':3,'absx':3,'absy':3,
        'long':4,'longx':4,'ind':3,'indl2':3,'rel':2,'rel16':3,'blk':3}


def op_size(op, mflag, xflag):
    mn, mode = OPS[op]
    if mode == 'immM':
        return 3 if mflag == 0 else 2
    if mode == 'immX':
        return 3 if xflag == 0 else 2
    if mode == 'indl' and mn == 'JML':
        return 3
    return SIZE[mode]


def fmt(op, ops, pc, mflag, xflag):
    mn, mode = OPS[op]
    if mode in ('imp',):
        return mn
    if mode == 'acc':
        return mn + ' A'
    if mode == 'sig':
        return '%s $%02X' % (mn, ops[0])
    if mode == 'imm':
        return '%s #$%02X' % (mn, ops[0])
    if mode == 'immM':
        return ('%s #$%04X' if mflag == 0 else '%s #$%02X') % (mn, int.from_bytes(ops, 'little'))
    if mode == 'immX':
        return ('%s #$%04X' if xflag == 0 else '%s #$%02X') % (mn, int.from_bytes(ops, 'little'))
    if mode == 'dp':
        return '%s $%02X' % (mn, ops[0])
    if mode == 'dpx':
        return '%s $%02X,X' % (mn, ops[0])
    if mode == 'dpy':
        return '%s $%02X,Y' % (mn, ops[0])
    if mode == 'sr':
        return '%s $%02X,S' % (mn, ops[0])
    if mode == 'indx':
        return '%s ($%02X,X)' % (mn, ops[0])
    if mode == 'indy':
        return '%s ($%02X),Y' % (mn, ops[0])
    if mode == 'dpi':
        return '%s ($%02X)' % (mn, ops[0])
    if mode == 'indl':
        return '%s [$%02X]' % (mn, ops[0])
    if mode == 'indly':
        return '%s [$%02X],Y' % (mn, ops[0])
    if mode == 'abs':
        return '%s $%04X' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'absx':
        return '%s $%04X,X' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'absy':
        return '%s $%04X,Y' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'long':
        return '%s $%06X' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'longx':
        return '%s $%06X,X' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'ind':
        return '%s ($%04X)' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'indl2':
        return '%s [$%04X]' % (mn, int.from_bytes(ops, 'little'))
    if mode == 'rel':
        t = (pc + 2 + (ops[0] - 256 if ops[0] > 127 else ops[0])) & 0xFFFF
        return '%s $%04X' % (mn, t)
    if mode == 'rel16':
        d = int.from_bytes(ops, 'little')
        t = (pc + 3 + (d - 65536 if d > 32767 else d)) & 0xFFFF
        return '%s $%04X' % (mn, t)
    if mode == 'blk':
        return '%s $%02X,$%02X' % (mn, ops[0], ops[1])
    return mn


def rom_to_cpu(off):
    bank = off // 0x8000
    return (bank << 16) | (0x8000 + (off % 0x8000))


def disasm(data, off, count=40, mflag=1, xflag=1):
    """Linear disassembly. Returns list of (rom_off, raw_bytes, text, mflag, xflag)."""
    out = []
    o = off
    for _ in range(count):
        if o >= len(data):
            break
        op = data[o]
        mn, mode = OPS[op]
        n = op_size(op, mflag, xflag)
        raw = data[o:o + n]
        if len(raw) < n:
            break
        txt = fmt(op, raw[1:], rom_to_cpu(o) & 0xFFFF, mflag, xflag)
        out.append((o, raw, txt, mflag, xflag))
        if op == 0xC2:
            mflag = 0 if (raw[1] & 0x20) else mflag
            xflag = 0 if (raw[1] & 0x10) else xflag
        elif op == 0xE2:
            mflag = 1 if (raw[1] & 0x20) else mflag
            xflag = 1 if (raw[1] & 0x10) else xflag
        o += n
    return out


def show(data, off, count=40, mflag=1, xflag=1, label=''):
    if label:
        print('==== %s ====' % label)
    for o, raw, txt, mf, xf in disasm(data, off, count, mflag, xflag):
        print('%06X  %-10s %s   [%d%d]' % (o, ' '.join('%02X' % b for b in raw), txt, mf, xf))


if __name__ == '__main__':
    import sys
    d = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 0)
    n = int(sys.argv[3], 0) if len(sys.argv) > 3 else 40
    show(d, off, n)
