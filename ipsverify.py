"""Strict IPS round-trip verifier. Defaults to this checkout, NOT an old release.

python ipsverify.py --rom candidate.smc --ips candidate.ips [--original original.smc]
"""
from pathlib import Path
import argparse
import zlib

ROOT=Path(__file__).resolve().parent

def apply_ips(base,path):
    data=Path(path).read_bytes()
    if data[:5]!=b'PATCH':raise ValueError('missing IPS PATCH signature')
    out=bytearray(base);i=5;records=0
    def take(n):
        nonlocal i
        if i+n>len(data):raise ValueError(f'truncated IPS record at byte {i}')
        chunk=data[i:i+n];i+=n;return chunk
    while True:
        offset=take(3)
        if offset==b'EOF':
            tail=data[i:]
            if len(tail)==3:
                size=int.from_bytes(tail,'big')
                if size<len(out):del out[size:]
                elif size>len(out):out.extend(bytes(size-len(out)))
            elif tail:raise ValueError('invalid trailing data after IPS EOF')
            return bytes(out),records
        offset=int.from_bytes(offset,'big');size=int.from_bytes(take(2),'big')
        if size:
            chunk=take(size)
        else:
            size=int.from_bytes(take(2),'big')
            if not size:raise ValueError('zero-length IPS RLE record')
            chunk=take(1)*size
        if offset+size>len(out):out.extend(bytes(offset+size-len(out)))
        out[offset:offset+size]=chunk;records+=1

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,default=ROOT/'kuniokun_cn.smc')
    p.add_argument('--ips',type=Path,default=ROOT/'kuniokun_cn.ips')
    p.add_argument('--original',type=Path,default=ROOT/'dl/roms/kuniokun__SF8127.smc')
    a=p.parse_args(argv)
    try:
        got,n=apply_ips(a.original.read_bytes(),a.ips);want=a.rom.read_bytes()
    except (OSError,ValueError) as exc:
        print('FAIL:',exc);return 1
    print(f'ips records: {n}; patched bytes: {len(got)}; target bytes: {len(want)}')
    print(f'patched CRC32: {zlib.crc32(got):08X}; target CRC32: {zlib.crc32(want):08X}')
    print('identical:',got==want)
    if got!=want:
        print('FAIL: IPS does not reproduce the selected ROM');return 1
    return 0

if __name__=='__main__':raise SystemExit(main())
