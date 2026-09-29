"""Minimal message-tick fixture; no unknown opcode or step timeout counts as success.

This is a model, not emulator acceptance. Queue application models the two
VMAIN modes emitted by the drawer; it does not model PPU timing.
"""
import sim65816 as S

RETURN = (0x3E, 0xDF00)


def make_cpu(rom, codes=None):
    cpu = S.CPU(rom)
    w = cpu.bus.wram
    w[0x373] = 0xC0
    codes = [0x41] * 200 if codes is None else list(codes)
    w[0x3E8] = len(codes)
    w[0x3EA:0x3EA+len(codes)] = bytes(codes)
    return cpu


def tick(cpu):
    cpu.pbr, cpu.db, cpu.pc, cpu.s = 3, 3, 0xEE70, 0x1FF
    cpu.m8 = cpu.x8 = True
    cpu.push8(RETURN[0]); cpu.push8((RETURN[1]-1)>>8); cpu.push8((RETURN[1]-1)&255)
    for _ in range(200000):
        if (cpu.pbr, cpu.pc) == RETURN:
            assert cpu.s == 0x1FF, 'message tick stack imbalance'
            return
        cpu.step()
    raise AssertionError('message tick did not return')


def flush(cpu):
    w = cpu.bus.wram
    start = w[0x9DD] | w[0x9DE]<<8
    end = w[0x9DF] | w[0x9E0]<<8
    assert 0 <= start <= end <= 0x100, (start,end)
    entries = []
    while start < end:
        p = 0xB00 + start
        addr = w[p] | w[p+1]<<8
        mode, n = w[p+2:p+4]
        assert mode in (0x80,0x81) and n>0 and n%2==0 and start+4+n <= end, (start,mode,n,end)
        step = 32 if mode==0x81 else 1
        entries.append((addr,mode,n))
        for j in range(0,n,2):
            cpu.vram[(addr+j//2*step)&0x7FFF] = w[p+4+j] | w[p+5+j]<<8
        start += 4+n
    w[0x9DD:0x9E1] = bytes(4)
    return entries
