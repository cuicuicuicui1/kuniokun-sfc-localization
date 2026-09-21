"""Dump the message loader / macro handler region of bank $03 with a
SEP/REP tracking disassembler, to find where the speaker-name macro ($E2)
takes its text from."""
import sys
import mos65xx

ROM = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/work_kuniokun_2mb.smc'
data = open(ROM, 'rb').read()


def snes_to_rom(bank, addr):
    return bank * 0x8000 + (addr - 0x8000)


def dis(bank, start, length, m=True, x=True):
    base = snes_to_rom(bank, start)
    buf = data[base:base + length]
    i = 0
    addr = start
    out = []
    while i < len(buf):
        try:
            ins = mos65xx.decode(buf, offset=i, address=addr, m=m, x=x)
        except Exception as e:
            out.append('%04X  ?? truncated (%s)' % (addr, e))
            break
        raw = buf[i:i + ins.size].hex(' ')
        out.append('%04X  %-14s %s' % (addr, raw, ins.text))
        if ins.opcode == 0xE2 and ins.operand is not None:
            m = bool(ins.operand & 0x20)
            x = bool(ins.operand & 0x10)
        elif ins.opcode == 0xC2 and ins.operand is not None:
            m = not (ins.operand & 0x20)
            x = not (ins.operand & 0x10)
        i += ins.size
        addr += ins.size
    return out


if __name__ == '__main__':
    args = sys.argv[1:]
    start = int(args[0], 16) if args else 0xED00
    length = int(args[1], 16) if len(args) > 1 else 0x1C0
    m = args[2] != '0' if len(args) > 2 else True
    x = args[3] != '0' if len(args) > 3 else True
    for line in dis(0x03, start, length, m, x):
        print(line)