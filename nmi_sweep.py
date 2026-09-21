"""nmi_sweep.py - find who consumes the $0B00 VRAM script buffer, and what the NMI handler does.
Checks whether the game uses DMA channel 1 / $2116 / $2115 while my patched drawer might be running.
"""
import re
import mos65xx

BASE = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon'
rom = open(BASE + '/kuniokun_cn.smc', 'rb').read()
orig = open(BASE + '/dl/roms/kuniokun__SF8127.smc', 'rb').read()


def dis(off, n, m=True, x=True):
    buf = rom[off:off + n]
    ins = mos65xx.disassemble(buf, address=0x8000 + (off % 0x8000), m=m, x=x)
    for i in ins:
        print('  %06X  %s' % (off + (i.address & 0x7FFF), i.text))


print('=== NMI vector ===')
iv = 0x7FEA
for name, a in (('NMI', 0x7FEA), ('RESET', 0x7FFC), ('IRQ', 0x7FEE)):
    print('  %s = $%02X:%04X' % (name, orig[a + 2], orig[a] | (orig[a + 1] << 8)))
print('=== NMI handler @ROM 0x00B88C ===')
dis(0x00B88C, 0x90)
print('=== IRQ handler ===')
irq = orig[0x7FEE] | (orig[0x7FEF] << 8)
ira = orig[0x7FF0]
print('  $%02X:%04X -> ROM 0x%06X' % (ira, irq, (ira & 0x7F) * 0x8000 + (irq & 0x7FFF)))
dis((ira & 0x7F) * 0x8000 + (irq & 0x7FFF), 0x60)

print('=== search for reads/writes of $0B00-$0BFF (abs/long/abs,X) ===')
# patterns: LDA $0B00 (AD 00 0B), STA $0B00 (8D 00 0B), STA $0B00,X (9D 00 0B), LDA $0B00,X (BD 00 0B)
pats = {'AD': 'LDA', '8D': 'STA', '9D': 'STA,X', 'BD': 'LDA,X'}
hits = []
for op, nm in pats.items():
    for m in re.finditer(bytes([int(op, 16), 0x00, 0x0B]), orig):
        hits.append((m.start(), nm))
hits.sort()
for off, nm in hits:
    print('  ROM 0x%06X  %s $0B00   (bank $%02X addr $%04X)' % (
        off, nm, off // 0x8000, 0x8000 + (off % 0x8000)))

print('=== DMA usage around each hit (disassemble 48 bytes before) ===')
for off, nm in hits:
    print('--- context for hit at ROM 0x%06X ---' % off)
    dis(max(0, off - 0x60), 0xA0)

print('=== who writes VMAIN $2115 / VMADD $2116 (long+abs) ===')
for op, nm in (('8D', 'abs'), ('9D', 'abs,X'), ('9F', 'long,X'), ('8F', 'long')):
    for pat in (bytes([int(op, 16), 0x15, 0x21]), bytes([int(op, 16), 0x16, 0x21]),
                bytes([int(op, 16), 0x15, 0x21, 0x00]), bytes([int(op, 16), 0x16, 0x21, 0x00])):
        pass
for reg, name in ((0x15, 'VMAIN'), (0x16, 'VMADDL'), (0x17, 'VMADDH'),
                  (0x10, 'DMA0'), (0x0B, 'MDMAEN')):
    for op, nm in (('8D', 'STA abs'), ('9D', 'STA abs,X')):
        for m in re.finditer(bytes([int(op, 16), reg, 0x21]), orig):
            print('  ROM 0x%06X %s $21%02X (%s)' % (m.start(), nm, reg, name))