"""Independent check: apply the delivered IPS to the ORIGINAL ROM and require the
result to equal the delivered ROM byte for byte."""
import struct, zlib

ORIG = 'dl/roms/kuniokun__SF8127.smc'
WORK = 'kuniokun_cn.smc'
IPS = r'F:\BaiduNetdiskDownload\SFC deepseek\初代热血硬派-汉化\kuniokun_cn.ips'
SMC = r'F:\BaiduNetdiskDownload\SFC deepseek\初代热血硬派-汉化\kuniokun_cn.smc'


def apply_ips(base, path):
    d = open(path, 'rb').read()
    assert d[:5] == b'PATCH', d[:8]
    out = bytearray(base)
    i, n = 5, 0
    while i < len(d):
        if d[i:i + 3] == b'EOF':
            break
        off = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]
        i += 3
        sz = (d[i] << 8) | d[i + 1]
        i += 2
        if sz == 0:
            rl = (d[i] << 8) | d[i + 1]
            i += 2
            val = d[i]
            i += 1
            data = bytes([val]) * rl
        else:
            data = d[i:i + sz]
            i += sz
        if off + len(data) > len(out):
            out.extend(b'\x00' * (off + len(data) - len(out)))
        out[off:off + len(data)] = data
        n += 1
    return bytes(out), n


base = open(ORIG, 'rb').read()
got, nrec = apply_ips(base, IPS)
want = open(SMC, 'rb').read()
print('ips records      :', nrec)
print('patched size     :', len(got))
print('delivered size   :', len(want))
print('identical        :', got == want)
print('patched  crc32   : %08X' % zlib.crc32(got))
print('delivered crc32  : %08X' % zlib.crc32(want))
if got != want:
    diff = [i for i in range(min(len(got), len(want))) if got[i] != want[i]]
    print('first differences:', ['%06X' % o for o in diff[:20]], 'total', len(diff))
