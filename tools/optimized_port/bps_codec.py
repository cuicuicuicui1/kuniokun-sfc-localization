# -*- coding: utf-8 -*-
"""Minimal BPS patch writer (linear encoding) + a decoder used to verify the round trip.

Actions used:
  SourceCopy  for runs where source[i] == target[i]   (with a signed offset to keep the
              source-relative pointer in sync)
  TargetRead  for runs that differ
"""
import zlib, struct


def _num(out, n):
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x); break
        out.append(x); n -= 1


def _snum(out, n):
    _num(out, (abs(n) << 1) | (1 if n < 0 else 0))


def encode(source, target, metadata=b''):
    out = bytearray(b'BPS1')
    _num(out, len(source)); _num(out, len(target))
    _num(out, len(metadata)); out += metadata
    i = 0; n = len(target); srel = 0
    while i < n:
        same = i < len(source) and source[i] == target[i]
        j = i
        while j < n and ((j < len(source) and source[j] == target[j]) == same):
            j += 1
        if same:
            _num(out, ((j - i - 1) << 2) | 2)      # SourceCopy
            _snum(out, i - srel)
            srel = i + (j - i)
        else:
            _num(out, ((j - i - 1) << 2) | 1)      # TargetRead
            out += target[i:j]
        i = j
    out += struct.pack('<I', zlib.crc32(source) & 0xffffffff)
    out += struct.pack('<I', zlib.crc32(target) & 0xffffffff)
    out += struct.pack('<I', zlib.crc32(out) & 0xffffffff)
    return bytes(out)


def decode(patch, source):
    """Validate all three BPS CRCs and implement all four action types."""
    if len(patch) < 19 or patch[:4] != b'BPS1':
        raise ValueError('Not a BPS patch')
    crc_src, crc_tgt, crc_patch = struct.unpack('<III', patch[-12:])
    if zlib.crc32(patch[:-4]) & 0xffffffff != crc_patch:
        raise ValueError('BPS patch CRC mismatch')
    if zlib.crc32(source) & 0xffffffff != crc_src:
        raise ValueError('BPS source CRC mismatch: wrong base ROM')
    p, end = 4, len(patch) - 12
    def rnum():
        nonlocal p
        shift, data = 1, 0
        for _ in range(10):
            if p >= end:
                raise ValueError('Truncated BPS number')
            x = patch[p]; p += 1
            data += (x & 0x7f) * shift
            if x & 0x80:
                return data
            shift <<= 7; data += shift
        raise ValueError('Oversized BPS number')
    def rsnum():
        data = rnum()
        return -(data >> 1) if data & 1 else data >> 1
    src_size, tgt_size, meta_size = rnum(), rnum(), rnum()
    if src_size != len(source):
        raise ValueError('BPS source size mismatch')
    if p + meta_size > end:
        raise ValueError('Truncated BPS metadata')
    p += meta_size
    out = bytearray(); srel = trel = 0
    while len(out) < tgt_size:
        data = rnum(); act = data & 3; length = (data >> 2) + 1
        if len(out) + length > tgt_size:
            raise ValueError('BPS action exceeds target size')
        if act == 0:  # SourceRead uses the OUTPUT position, not SourceCopy's cursor.
            start = len(out)
            if start + length > len(source):
                raise ValueError('SourceRead outside source')
            out += source[start:start + length]
        elif act == 1:
            if p + length > end:
                raise ValueError('Truncated TargetRead')
            out += patch[p:p + length]; p += length
        elif act == 2:
            srel += rsnum()
            if srel < 0 or srel + length > len(source):
                raise ValueError('SourceCopy outside source')
            out += source[srel:srel + length]; srel += length
        else:  # TargetCopy has its own signed relative cursor; overlap is legal.
            trel += rsnum()
            for _ in range(length):
                if not 0 <= trel < len(out):
                    raise ValueError('TargetCopy outside written target')
                out.append(out[trel]); trel += 1
    if p != end:
        raise ValueError('Unexpected data after BPS actions')
    if zlib.crc32(out) & 0xffffffff != crc_tgt:
        raise ValueError('BPS target CRC mismatch')
    return bytes(out)
