"""Build a TEST rom (kwinv.smc) that draws the command window once, by itself.

The window is normally only drawn when the Start menu opens - a state this
machine cannot reach (the probe always lands in the story cutscene, whose scene
script never enters the field main loop's menu branch).  So the drawer entry
is redirected at
a test stub that draws the window itself and then falls through to the real
drawer.  Everything except "the menu script calls this" is the shipped code
path, so a screenshot of the result is real evidence for the static glyph
design.

The stub runs on every drawer call and advances one step per call, so a full
upload queue cannot make it give up:

    state 0  copy the 52 byte label table from ROM 0x01F743 to $040A
    state 1  $036E = 2, $039E = 0, JSL $03F95D  (the window's first text row)
    state 2  $036E = 3, $039E = 1, JSL $03F95D  (the second text row)
    state 3  done, `plp` + `jml $3E:8200`

$036E is saved and restored around the draws because the real drawer needs it.

    python patch_inv.py
"""
import cnbuild5 as cb

SRC = 'kuniokun_cn.smc'
OUT = 'kwinv.smc'
STUB = 0x1F0760                  # $3E:8760: free (drawer ends ~$3E:8690, the
                                 # high byte table is $3E:8700..8754)
HOOK = 0x01FA7A                  # $03:FA7A  the drawer's tail: INC $036F / RTS

code = bytearray()
fix = []


def emit(*bs):
    code.extend(bs)


def here():
    return len(code)


def branch(op, name):
    fix.append((len(code) + 1, name))
    emit(op, 0x00)


# ---------------------------------------------------------------- the stub
# Hooked at the drawer's TAIL ($03:FA7A = INC $036F / RTS), so it runs after the
# drawer has staged its own cells and the row wipe: whatever the box had on the
# window's two rows can no longer overwrite the labels.  It only acts when the
# drawer has just drawn column 0 (a line start: $036F == 1 at that point), which
# is rare enough that the text still gets its queue space, and it re-draws at
# every following line start, so the window stays visible.
emit(0x08)                              # php
emit(0xE2, 0x30)                        # sep #$30
emit(0x48)                              # pha
emit(0xDA)                              # phx
emit(0xAD, 0x6F, 0x03)                  # lda $036f
emit(0xC9, 0x01)                        # cmp #$01
branch(0xD0, 'out')                     # bne out (not the first cell of a line)
emit(0xAD, 0x6E, 0x03, 0x48)            # lda $036e / pha (the drawer's row)
emit(0xA2, 0x00)                        # ldx #$00
loop = here()
emit(0xBF, 0x43, 0xF7, 0x03)            # lda $03f743,x (the window's cell table)
emit(0x9D, 0x0A, 0x04)                  # sta $040a,x
emit(0xE8)                              # inx
emit(0xE0, 0x34)                        # cpx #$34 = 52 cells
branch(0x90, 'loop')                    # bcc loop
emit(0xA9, 0x02, 0x8D, 0x6E, 0x03)      # lda #$02 / sta $036e (text row 2)
emit(0x9C, 0x9E, 0x03)                  # stz $039e (pass 0: the first row)
emit(0x22, 0x5D, 0xF9, 0x03)            # jsl $03f95d (the engine's own builder)
emit(0xA9, 0x01, 0x8D, 0x9E, 0x03)      # lda #$01 / sta $039e (pass 1)
emit(0x22, 0x5D, 0xF9, 0x03)            # jsl $03f95d (advances $036e itself)
emit(0x68, 0x8D, 0x6E, 0x03)            # pla / sta $036e
out = here()
emit(0xEE, 0x6F, 0x03)                  # inc $036f (what the tail used to do)
emit(0xFA, 0x68, 0x28)                  # plx / pla / plp
emit(0x60)                              # rts

for idx, name in fix:
    off = {'loop': loop, 'out': out}[name] - (idx + 1)
    assert -128 <= off <= 127, (name, off)
    code[idx] = off & 0xFF


def main():
    rom = bytearray(open(SRC, 'rb').read())
    want = bytes([0xEE, 0x6F, 0x03, 0x60])   # the drawer tail: INC $036F / RTS
    assert bytes(rom[HOOK:HOOK + 4]) == want, rom[HOOK:HOOK + 5].hex(" ").strip()
    assert len(code) < 0xA0, len(code)
    rom[STUB:STUB + len(code)] = code
    snes = 0x8000 + (STUB - cb.CODE_ROM)
    rom[HOOK:HOOK + 4] = bytes([0x5C, snes & 0xFF, snes >> 8, 0x3E])
    open(OUT, 'wb').write(bytes(rom))
    print('wrote %s: %d byte stub at $3E:%04X, hook $03:FA7A -> $3E:%04X'
          % (OUT, len(code), snes, snes))
    print('stub: %s' % code.hex(' '))


if __name__ == '__main__':
    main()
