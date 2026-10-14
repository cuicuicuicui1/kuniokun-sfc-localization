"""Table-driven 65816 disassembler (subset sufficient for hand-verification).

python dis65.py <rom> <bank> <addr> <n>       -- linear disasm from CPU addr
python dis65.py <rom> --file <off> <n>        -- linear disasm from file offset
Immediate width tracks SEP/REP seen earlier in the linear sweep. Unknown bytes
print as their documented/undocumented name from the table (subset covers the
common opcodes; anything missing degrades gracefully).
"""
import sys

MODES = {
 0x00:('BRK','imp'),0x01:('ORA','dpIX'),0x02:('COP','imp'),0x03:('ORA','srIY'),
 0x04:('TSB','dp'),0x05:('ORA','dp'),0x06:('ASL','dp'),0x07:('ORA','dpIL'),
 0x08:('PHP','imp'),0x09:('ORA','imm'),0x0A:('ASL','acc'),0x0B:('PHD','imp'),
 0x0C:('TSB','abs'),0x0D:('ORA','abs'),0x0E:('ASL','abs'),0x0F:('ORA','absL'),
 0x10:('BPL','rel'),0x11:('ORA','dpIY'),0x12:('ORA','dpI'),0x13:('ORA','srI'),
 0x14:('TRB','dp'),0x15:('ORA','dpX'),0x16:('ASL','dpX'),0x17:('ORA','dpILX'),
 0x18:('CLC','imp'),0x19:('ORA','absY'),0x1A:('INC','acc'),0x1B:('TCS','imp'),
 0x1C:('TRB','abs'),0x1D:('ORA','absX'),0x1E:('ASL','absX'),0x1F:('ORA','absLX'),
 0x20:('JSR','abs'),0x21:('AND','dpIX'),0x22:('JSL','absL'),0x23:('AND','srIY'),
 0x24:('BIT','dp'),0x25:('AND','dp'),0x26:('ROL','dp'),0x27:('AND','dpIL'),
 0x28:('PLP','imp'),0x29:('AND','imm'),0x2A:('ROL','acc'),0x2B:('PLD','imp'),
 0x2C:('BIT','abs'),0x2D:('AND','abs'),0x2E:('ROL','abs'),0x2F:('AND','absL'),
 0x30:('BMI','rel'),0x31:('AND','dpIY'),0x32:('AND','dpI'),0x33:('AND','srI'),
 0x34:('BIT','dpX'),0x35:('AND','dpX'),0x36:('ROL','dpX'),0x37:('AND','dpILX'),
 0x38:('SEC','imp'),0x39:('AND','absY'),0x3A:('DEC','acc'),0x3B:('TSC','imp'),
 0x3C:('BIT','absX'),0x3D:('AND','absX'),0x3E:('ROL','absX'),0x3F:('AND','absLX'),
 0x40:('RTI','imp'),0x41:('EOR','dpIX'),0x42:('WDM','imp'),0x43:('EOR','srIY'),
 0x44:('MVP','blk'),0x45:('EOR','dp'),0x46:('LSR','dp'),0x47:('EOR','dpIL'),
 0x48:('PHA','imp'),0x49:('EOR','imm'),0x4A:('LSR','acc'),0x4B:('PHK','imp'),
 0x4C:('JMP','abs'),0x4D:('EOR','abs'),0x4E:('LSR','abs'),0x4F:('EOR','absL'),
 0x50:('BVC','rel'),0x51:('EOR','dpIY'),0x52:('EOR','dpI'),0x53:('EOR','srI'),
 0x54:('MVN','blk'),0x55:('EOR','dpX'),0x56:('LSR','dpX'),0x57:('EOR','dpILX'),
 0x58:('CLI','imp'),0x59:('EOR','absY'),0x5A:('PHY','imp'),0x5B:('TCD','imp'),
 0x5C:('JMP','absL'),0x5D:('EOR','absX'),0x5E:('LSR','absX'),0x5F:('EOR','absLX'),
 0x60:('RTS','imp'),0x61:('ADC','dpIX'),0x62:('PER','abs'),0x63:('ADC','srIY'),
 0x64:('STZ','dp'),0x65:('ADC','dp'),0x66:('ROR','dp'),0x67:('ADC','dpIL'),
 0x68:('PLA','imp'),0x69:('ADC','imm'),0x6A:('ROR','acc'),0x6B:('RTL','imp'),
 0x6C:('JMP','ind'),0x6D:('ADC','abs'),0x6E:('ROR','abs'),0x6F:('ADC','absL'),
 0x70:('BVS','rel'),0x71:('ADC','dpIY'),0x72:('ADC','dpI'),0x73:('ADC','srI'),
 0x74:('STZ','dpX'),0x75:('ADC','dpX'),0x76:('ROR','dpX'),0x77:('ADC','dpILX'),
 0x78:('SEI','imp'),0x79:('ADC','absY'),0x7A:('PLY','imp'),0x7B:('TDC','imp'),
 0x7C:('JMP','indX'),0x7D:('ADC','absX'),0x7E:('ROR','absX'),0x7F:('ADC','absLX'),
 0x80:('BRA','rel'),0x81:('STA','dpIX'),0x82:('BRL','relL'),0x83:('STA','srIY'),
 0x84:('STY','dp'),0x85:('STA','dp'),0x86:('STX','dp'),0x87:('STA','dpIL'),
 0x88:('DEY','imp'),0x89:('BIT','imm'),0x8A:('TXA','imp'),0x8B:('PHB','imp'),
 0x8C:('STY','abs'),0x8D:('STA','abs'),0x8E:('STX','abs'),0x8F:('STA','absL'),
 0x90:('BCC','rel'),0x91:('STA','dpIY'),0x92:('STA','dpI'),0x93:('STA','srI'),
 0x94:('STY','dpX'),0x95:('STA','dpX'),0x96:('STX','dpY'),0x97:('STA','dpILX'),
 0x98:('TYA','imp'),0x99:('STA','absY'),0x9A:('TXS','imp'),0x9B:('TXY','imp'),
 0x9C:('STZ','abs'),0x9D:('STA','absX'),0x9E:('STZ','absX'),0x9F:('STA','absLX'),
 0xA0:('LDY','imm'),0xA1:('LDA','dpIX'),0xA2:('LDX','imm'),0xA3:('LDA','srIY'),
 0xA4:('LDY','dp'),0xA5:('LDA','dp'),0xA6:('LDX','dp'),0xA7:('LDA','dpIL'),
 0xA8:('TAY','imp'),0xA9:('LDA','imm'),0xAA:('TAX','imp'),0xAB:('PLB','imp'),
 0xAC:('LDY','abs'),0xAD:('LDA','abs'),0xAE:('LDX','abs'),0xAF:('LDA','absL'),
 0xB0:('BCS','rel'),0xB1:('LDA','dpIY'),0xB2:('LDA','dpI'),0xB3:('LDA','srI'),
 0xB4:('LDY','dpX'),0xB5:('LDA','dpX'),0xB6:('LDX','dpY'),0xB7:('LDA','dpILX'),
 0xB8:('CLV','imp'),0xB9:('LDA','absY'),0xBA:('TSX','imp'),0xBB:('TYX','imp'),
 0xBC:('LDY','absX'),0xBD:('LDA','absX'),0xBE:('LDX','absY'),0xBF:('LDA','absLX'),
 0xC0:('CPY','imm'),0xC1:('CMP','dpIX'),0xC2:('REP','imm'),0xC3:('CMP','srIY'),
 0xC4:('CPY','dp'),0xC5:('CMP','dp'),0xC6:('DEC','dp'),0xC7:('CMP','dpIL'),
 0xC8:('INY','imp'),0xC9:('CMP','imm'),0xCA:('DEX','imp'),0xCB:('WAI','imp'),
 0xCC:('CPY','abs'),0xCD:('CMP','abs'),0xCE:('DEC','abs'),0xCF:('CMP','absL'),
 0xD0:('BNE','rel'),0xD1:('CMP','dpIY'),0xD2:('CMP','dpI'),0xD3:('CMP','srI'),
 0xD4:('PEI','dp'),0xD5:('CMP','dpX'),0xD6:('DEC','dpX'),0xD7:('CMP','dpILX'),
 0xD8:('CLD','imp'),0xD9:('CMP','absY'),0xDA:('PHX','imp'),0xDB:('STP','imp'),
 0xDC:('JML','indL'),0xDD:('CMP','absX'),0xDE:('DEC','absX'),0xDF:('CMP','absLX'),
 0xE0:('CPX','imm'),0xE1:('SBC','dpIX'),0xE2:('SEP','imm'),0xE3:('SBC','srIY'),
 0xE4:('CPX','dp'),0xE5:('SBC','dp'),0xE6:('INC','dp'),0xE7:('SBC','dpIL'),
 0xE8:('INX','imp'),0xE9:('SBC','imm'),0xEA:('NOP','imp'),0xEB:('XBA','imp'),
 0xEC:('CPX','abs'),0xED:('SBC','abs'),0xEE:('INC','abs'),0xEF:('SBC','absL'),
 0xF0:('BEQ','rel'),0xF1:('SBC','dpIY'),0xF2:('SBC','dpI'),0xF3:('SBC','srI'),
 0xF4:('PEA','abs'),0xF5:('SBC','dpX'),0xF6:('INC','dpX'),0xF7:('SBC','dpILX'),
 0xF8:('SED','imp'),0xF9:('SBC','absY'),0xFA:('PLX','imp'),0xFB:('XCE','imp'),
 0xFC:('JSR','indX'),0xFD:('SBC','absX'),0xFE:('INC','absX'),0xFF:('SBC','absLX'),
}

SZ = {'imp':1,'acc':1,'imm':2,'dp':2,'dpX':2,'dpY':2,'abs':3,'absX':3,'absY':3,
      'absL':4,'absLX':4,'dpIX':2,'dpIY':2,'dpI':2,'dpIL':2,'dpILX':2,'rel':2,
      'relL':3,'ind':3,'indX':3,'indL':4,'blk':3,'srIY':2,'srI':2}

A_IMM = {'ORA','AND','EOR','ADC','SBC','CMP','BIT','LDA'}


def disasm(rom, bank, addr, n, m8=True, x8=True):
    out = []
    pc = addr
    end = addr + n
    while pc < end:
        off = bank * 0x8000 + (pc - 0x8000)
        if off < 0 or off >= len(rom):
            break
        op = rom[off]
        mn, md = MODES[op]
        size = SZ[md]
        if md == 'imm' and mn in A_IMM:
            size = 2 if m8 else 3
        elif md == 'imm' and mn in ('LDX', 'LDY', 'CPX', 'CPY'):
            size = 2 if x8 else 3
        raw = rom[off:off + size]
        out.append((pc, size, render(mn, md, raw, pc, size)))
        if mn == 'SEP' and len(raw) > 1:
            if raw[1] & 0x20: m8 = True
            if raw[1] & 0x10: x8 = True
        elif mn == 'REP' and len(raw) > 1:
            if raw[1] & 0x20: m8 = False
            if raw[1] & 0x10: x8 = False
        pc += size
    return out


def render(mn, md, raw, pc, size):
    if md == 'imp':
        return mn
    if md == 'acc':
        return mn + ' A'
    if md == 'imm':
        return '%s #$%02X' % (mn, raw[1]) if size == 2 else '%s #$%04X' % (mn, raw[1] | raw[2] << 8)
    if md == 'dp':
        return '%s $%02X' % (mn, raw[1])
    if md == 'dpX':
        return '%s $%02X,X' % (mn, raw[1])
    if md == 'dpY':
        return '%s $%02X,Y' % (mn, raw[1])
    if md == 'dpIX':
        return '%s ($%02X,X)' % (mn, raw[1])
    if md == 'dpIY':
        return '%s ($%02X),Y' % (mn, raw[1])
    if md == 'dpI':
        return '%s ($%02X)' % (mn, raw[1])
    if md == 'dpIL':
        return '%s [$%02X]' % (mn, raw[1])
    if md == 'dpILX':
        return '%s [$%02X],X' % (mn, raw[1])
    if md == 'srIY':
        return '%s ($%02X,S),Y' % (mn, raw[1])
    if md == 'srI':
        return '%s ($%02X,S)' % (mn, raw[1])
    if md == 'abs':
        return '%s $%04X' % (mn, raw[1] | raw[2] << 8)
    if md == 'absX':
        return '%s $%04X,X' % (mn, raw[1] | raw[2] << 8)
    if md == 'absY':
        return '%s $%04X,Y' % (mn, raw[1] | raw[2] << 8)
    if md == 'absL':
        return '%s $%02X%04X' % (mn, raw[3], raw[1] | raw[2] << 8)
    if md == 'absLX':
        return '%s $%02X%04X,X' % (mn, raw[3], raw[1] | raw[2] << 8)
    if md == 'rel':
        d = raw[1] - 256 if raw[1] > 127 else raw[1]
        return '%s $%04X' % (mn, (pc + 2 + d) & 0xFFFF)
    if md == 'relL':
        d = raw[1] | raw[2] << 8
        if d > 0x7FFF: d -= 0x10000
        return '%s $%04X' % (mn, (pc + 3 + d) & 0xFFFF)
    if md == 'ind':
        return '%s ($%04X)' % (mn, raw[1] | raw[2] << 8)
    if md == 'indX':
        return '%s ($%04X,X)' % (mn, raw[1] | raw[2] << 8)
    if md == 'indL':
        return '%s [$%04X]' % (mn, raw[1] | raw[2] << 8)
    if md == 'blk':
        return '%s #$%02X,#$%02X' % (mn, raw[1], raw[2])
    return mn


def cpu_to_file(bank, addr):
    if addr < 0x8000 or addr >= 0x10000:
        return None
    return bank * 0x8000 + (addr - 0x8000)


def main():
    rom = open(sys.argv[1], 'rb').read()
    if sys.argv[2] == '--file':
        off = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0)
        bank = off // 0x8000
        addr = 0x8000 + off % 0x8000
    else:
        bank = int(sys.argv[2], 0)
        addr = int(sys.argv[3], 0)
        n = int(sys.argv[4], 0)
    for pc, size, txt in disasm(rom, bank, addr, n):
        fo = cpu_to_file(bank, pc)
        print('%02X:%04X  %05X  %s' % (bank, pc, fo, txt))


if __name__ == '__main__':
    main()
