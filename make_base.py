#!/usr/bin/env python3
"""从原版做出构建基线 work_kuniokun_2mb.smc。

基线 = 原版（1MB）+ 1MB 零填充 + 档头三处改动：
  0x7FD7  romsize 0x0A → 0x0B（8 Mbit → 16 Mbit）
  0x7FDC/0x7FDE  校验和与补码（LoROM 标准算法）

之后的每一次构建都从这个基线出发（cnbuild5.py 会在写盘前重算校验和），
所以基线本身只要字节固定即可。

    python make_base.py
"""
import os
import sys
import zlib

ORIG = 'dl/roms/kuniokun__SF8127.smc'
OUT = 'work_kuniokun_2mb.smc'
ORIG_SIZE = 0x100000
ORIG_CRC = 0x56C05339
BASE_CRC = 0xDE95E688

if not os.path.exists(ORIG):
    raise SystemExit('把原版放在 %s（1MB，CRC32 %08X）' % (ORIG, ORIG_CRC))

data = open(ORIG, 'rb').read()
if len(data) != ORIG_SIZE:
    raise SystemExit('原版大小 %d，期望 %d' % (len(data), ORIG_SIZE))
crc = zlib.crc32(data)
if crc != ORIG_CRC:
    raise SystemExit('原版 CRC32 %08X，期望 %08X —— 版本不对' % (crc, ORIG_CRC))

rom = bytearray(data) + bytes(ORIG_SIZE)          # 补到 2MB
rom[0x7FD7] = 0x0B                                # 16 Mbit

# 校验和：除自身四个字节外全部求和，低 16 位取反存 0x7FDC
rom[0x7FDC] = rom[0x7FDD] = rom[0x7FDE] = rom[0x7FDF] = 0
total = (sum(rom) + 0x1FE) & 0xFFFF
rom[0x7FDC] = (total ^ 0xFFFF) & 0xFF
rom[0x7FDD] = (total ^ 0xFFFF) >> 8
rom[0x7FDE] = total & 0xFF
rom[0x7FDF] = total >> 8

open(OUT, 'wb').write(rom)
crc = zlib.crc32(rom)
print('%s: %d 字节，校验和 0x%04X，CRC32 %08X' % (OUT, len(rom), total, crc))
if crc != BASE_CRC:
    print('提示：与记录的基线 CRC32 %08X 不一致，核对一下原版是不是同一个 dump' % BASE_CRC)
    sys.exit(1)
print('与记录的基线一致。')
