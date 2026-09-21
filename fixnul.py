"""Repair the literal NUL bytes that the heredoc mangling introduced."""
BS = chr(92)
p = 'sfc_tools.py'
d = open(p, 'rb').read()
bad = b"b'" + b'\x00\x00' + b"'"
good = ("b'" + BS + "x00" + BS + "x00'").encode()
n = d.count(bad)
d = d.replace(bad, good)
open(p, 'wb').write(d)
print('replaced', n, 'occurrences; remaining NULs =', d.count(b'\x00'))