"""Negative controls for the verification tools and CPU-model loop flags."""
from pathlib import Path
import subprocess
import sys
import tempfile
from ipsverify import apply_ips
from sim65816 import CPU

with tempfile.TemporaryDirectory(prefix='ips-negative-') as tmp:
    root=Path(tmp);patch=root/'test.ips'
    for malformed in (b'',b'PATCH',b'PATCH\0\0\1\0\2X',b'PATCHEOFjunk',b'PATCH\0\0\0\0\0\0\0XEOF'):
        patch.write_bytes(malformed)
        try:apply_ips(b'abc',patch)
        except ValueError:pass
        else:raise AssertionError(f'malformed IPS was accepted: {malformed!r}')
    patch.write_bytes(b'PATCH\0\0\1\0\1ZEOF')
    assert apply_ips(b'abc',patch)==(b'aZc',1)
    patch.write_bytes(b'PATCHEOF\0\0\2')
    assert apply_ips(b'abc',patch)==(b'ab',0)
    patch.write_bytes(b'PATCHEOF');(root/'base.smc').write_bytes(b'abc');(root/'target.smc').write_bytes(b'abd')
    args=[sys.executable,str(Path(__file__).with_name('ipsverify.py')),'--original',str(root/'base.smc'),'--rom',str(root/'target.smc'),'--ips',str(patch)]
    assert subprocess.run(args,capture_output=True).returncode==1,'mismatch must exit nonzero'
    (root/'target.smc').write_bytes(b'abc')
    assert subprocess.run(args,capture_output=True).returncode==0
for m8,initial,want,n,z in ((True,0,255,True,False),(True,1,0,False,True),(False,0,65535,True,False),(False,256,255,False,False)):
    image=bytearray(0x8000);image[:2]=b'\xC6\x17'
    c=CPU(image);c.pc=0x8000;c.m8=m8;c.c=True
    c.bus.wr(0,0x17,initial);c.bus.wr(0,0x18,initial>>8);c.step()
    got=c.bus.rd(0,0x17)+(0 if m8 else c.bus.rd(0,0x18)<<8)
    assert (got,c.n,c.z,c.c)==(want,n,z,True)
print('PASS: malformed/truncated IPS rejected, mismatched target exits 1, matching target exits 0, DEC updates N/Z at both widths')
