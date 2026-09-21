"""Find every reference to the upload-queue pointers $09DD / $09DF and print the
flusher's disassembly.  The queue at $0B00 holds 8-byte entries
[addr_lo, addr_hi, vmain, count, data...] that the game turns into VRAM DMAs;
my drawer already appends tilemap entries there and they reach VRAM, so routing
glyph bitmaps through the same queue is the fix candidate."""
import sys
from mos65xx import decode

ROMF = "kuniokun_cn.smc"
ROM = open(ROMF, "rb").read()

def rom2snes(off):
    return off // 0x8000, 0x8000 + (off % 0x8000)

def dis(off, n, label=""):
    bk, ad = rom2snes(off)
    print("--- %s ROM %06X = $%02X:%04X (%d bytes) ---" % (label, off, bk, ad, n))
    m = x = True
    i = 0
    while i < n:
        try:
            ins = decode(ROM, offset=off + i, address=ad + i, m=m, x=x)
        except Exception as e:
            print("  (stop at +%d: %s)" % (i, e))
            break
        print("  %04X  %-10s m%d x%d  %s" % (ad + i, ins.text, m, x, ""))
        b = ROM[off + i]
        if b == 0xE2:
            v = ROM[off + i + 1]
            if v & 0x20: m = True
            if v & 0x10: x = True
        elif b == 0xC2:
            v = ROM[off + i + 1]
            if v & 0x20: m = False
            if v & 0x10: x = False
        i += ins.size

# --- every absolute reference to $09DD / $09DF -------------------------------
pats = {
    "LDA $09DD": bytes([0xAD, 0xDD, 0x09]),
    "STA $09DD": bytes([0x8D, 0xDD, 0x09]),
    "LDX $09DD": bytes([0xAE, 0xDD, 0x09]),
    "STX $09DD": bytes([0x8E, 0xDD, 0x09]),
    "LDA $09DF": bytes([0xAD, 0xDF, 0x09]),
    "STA $09DF": bytes([0x8D, 0xDF, 0x09]),
    "LDX $09DF": bytes([0xAE, 0xDF, 0x09]),
    "STX $09DF": bytes([0x8E, 0xDF, 0x09]),
    "DEC $09DD": bytes([0xCE, 0xDD, 0x09]),
    "INC $09DD": bytes([0xEE, 0xDD, 0x09]),
    "DEC $09DF": bytes([0xCE, 0xDF, 0x09]),
    "INC $09DF": bytes([0xEE, 0xDF, 0x09]),
}
print("=== references to $09DD / $09DF ===")
sites = []
for name, pat in pats.items():
    i = 0
    while True:
        j = ROM.find(pat, i)
        if j < 0:
            break
        bk, ad = rom2snes(j)
        sites.append((j, name, bk, ad))
        print("  %-12s at ROM %06X = $%02X:%04X" % (name, j, bk, ad))
        i = j + 1
print()

# --- references to the queue base $0B00 --------------------------------------
print("=== references to $0B00 / $0B01 (queue base) ===")
for pat, nm in ((bytes([0x00, 0x0B]), "abs $0B00"), (bytes([0x9D, 0x00, 0x0B]), "STA $0B00,X"),
                (bytes([0xBD, 0x00, 0x0B]), "LDA $0B00,X"), (bytes([0xB9, 0x00, 0x0B]), "LDA $0B00,Y")):
    i = 0
    cnt = 0
    while True:
        j = ROM.find(pat, i)
        if j < 0:
            break
        bk, ad = rom2snes(j)
        print("  %-14s at ROM %06X = $%02X:%04X" % (nm, j, bk, ad))
        cnt += 1
        i = j + 1
        if cnt > 12:
            print("    ... (more)")
            break
print()

# --- disassemble around each $09DF site to expose the flusher ----------------
for off, name, bk, ad in sites:
    if name in ("LDA $09DD", "STA $09DD", "LDA $09DF", "STA $09DF"):
        start = max(0, off - 0x30)
        dis(start, 0x80, "%s (around $%02X:%04X)" % (name, bk, ad))
        print()