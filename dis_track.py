"""dis_track.py -- mode-tracking disassembler for the patched code blocks.

mos65xx.disassemble() assumes one M/X width for the whole buffer, which misaligns
everything after the first SEP/REP.  This walks instruction by instruction,
updating M and X whenever SEP/REP with an immediate mask is seen, so the operand
sizes match what the console will actually decode.

Usage:
    python dis_track.py                 # dump every patched block
    python dis_track.py 0x1F0200 0x140  # dump one ROM range
"""
import sys
import mos65xx

ROM = r"C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
rom = open(ROM, "rb").read()

BLOCKS = [
    ("bank$03 sanitize   $03:E970", 0x01E970, 0x14),
    ("bank$03 slot pairs $03:E900", 0x01E900, 0x60),
    ("preload  $3E:8000", 0x1F0000, 0x28),
    ("dispatch $3E:8080", 0x1F0080, 0x120),
    ("drawer   $3E:8200", 0x1F0200, 0x150),
]

LONG_JUMPS = {0x5C, 0x22, 0x6B}     # JML, JSL, RTL -- follow-through is unknown


def dump(off, size, m, x, header):
    if header:
        print("=" * 76)
        print("%s  (ROM %06X, $%02X:%04X, m=%d x=%d)"
              % (header, off, (off // 0x8000), 0x8000 + (off % 0x8000), m, x))
        print("=" * 76)
    pos = 0
    stops = set()
    while pos < size:
        raw = rom[off + pos:off + pos + 12]
        try:
            ins = mos65xx.decode(raw, offset=0, address=(off + pos), m=m, x=x)
        except Exception as exc:                      # Truncated / unknown opcode
            print("  %06X  %-14s  <stop: %s>"
                  % (off + pos, " ".join("%02X" % b for b in raw[:4]), exc))
            break
        print("  %06X  %-14s m%d x%d  %s"
              % (off + pos, " ".join("%02X" % b for b in raw[:ins.size]),
                 m, x, ins.text))
        pos += ins.size
        if ins.mnemonic == "sep":
            mask = ins.operand
            if mask & 0x20:
                m = True
            if mask & 0x10:
                x = True
        elif ins.mnemonic == "rep":
            mask = ins.operand
            if mask & 0x20:
                m = False
            if mask & 0x10:
                x = False
        elif ins.opcode in LONG_JUMPS:
            print("  %06X  %-14s <control transfer -- decoding continues linearly>"
                  % (off + pos, ""))
            stops.add(off + pos)
        elif ins.mnemonic in ("rts", "rtl", "jmp", "jml", "bra", "bcc", "bcs",
                              "beq", "bne", "bpl", "bmi"):
            # keep decoding linearly so we see the fall-through path as well
            continue


if len(sys.argv) >= 3:
    off = int(sys.argv[1], 0)
    size = int(sys.argv[2], 0)
    dump(off, size, True, True, "custom range")
else:
    for hdr, off, size in BLOCKS:
        dump(off, size, True, True, hdr)
        print()