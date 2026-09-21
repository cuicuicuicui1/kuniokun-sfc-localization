"""SNES font packing and IPS patch generation helpers."""
import struct


# --------------------------------------------------------------- SNES 2bpp
def pack_8x8(bits):
    """bits: 8 rows of 8 ints (0..3). Returns 16 bytes, row-interleaved:
    byte[y*2]=plane0, byte[y*2+1]=plane1 for row y."""
    out = bytearray()
    for y in range(8):
        p0 = p1 = 0
        for x in range(8):
            v = bits[y][x]
            if v & 1:
                p0 |= 0x80 >> x
            if v & 2:
                p1 |= 0x80 >> x
        out.append(p0)
        out.append(p1)
    return bytes(out)


def unpack_8x8(data, off=0):
    """Inverse of pack_8x8 -> 8 rows of 8 ints."""
    rows = []
    for y in range(8):
        p0 = data[off + y * 2]
        p1 = data[off + y * 2 + 1]
        rows.append([((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                     for x in range(8)])
    return rows


def pack_16x16(bits):
    """bits: 16 rows of 16 ints. Returns 64 bytes = four 8x8 tiles in the order
    top-left, top-right, bottom-left, bottom-right (matching tilemap layout
    T, T+1, T+32, T+33)."""
    out = bytearray()
    for ty in (0, 8):
        for tx in (0, 8):
            sub = [row[tx:tx + 8] for row in bits[ty:ty + 8]]
            out += pack_8x8(sub)
    return bytes(out)


def unpack_16x16(data, off=0):
    """Inverse of pack_16x16 -> 16 rows of 16 ints."""
    grid = [[0] * 16 for _ in range(16)]
    k = off
    for ty in (0, 8):
        for tx in (0, 8):
            sub = unpack_8x8(data, k)
            k += 16
            for y in range(8):
                for x in range(8):
                    grid[ty + y][tx + x] = sub[y][x]
    return grid


def ascii_art(rows, ink='#', blank='.'):
    return '\n'.join(''.join(ink if v else blank for v in r) for r in rows)


# ------------------------------------------------------------------- IPS
def _ips_emit(f, off, data, rle_min=12):
    """Emit one logical block, splitting into <=0xFFFF chunks and using IPS
    RLE (size field 0) for long runs of one byte. Returns records written."""
    n = 0
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 0xFFFF:
            j += 1
        if j - i >= rle_min:
            f.write(bytes([(off >> 16) & 0xFF, (off >> 8) & 0xFF, off & 0xFF]))
            f.write(b'\x00\x00')
            f.write(struct.pack('>H', j - i))
            f.write(bytes([data[i]]))
            off += j - i
            n += 1
            i = j
            continue
        j = min(len(data), i + 0xFFFF)
        # shorten the literal run so an RLE run can start right after
        k = j
        while k - 1 > i and data[k - 1] == data[i]:
            k -= 1
        if k > i:
            j = k
        chunk = data[i:j]
        f.write(bytes([(off >> 16) & 0xFF, (off >> 8) & 0xFF, off & 0xFF]))
        f.write(struct.pack('>H', len(chunk)))
        f.write(chunk)
        off += len(chunk)
        n += 1
        i = j
    return n


def make_ips(original, patched, path):
    """Write an IPS patch turning `original` into `patched`.

    Handles ROM growth by emitting records past the original EOF; the ROM
    expansion tail is RLE-compressed so the patch stays small."""
    assert len(patched) >= len(original), 'IPS here only handles growth'
    recs = 0
    i = 0
    n = len(original)
    with open(path, 'wb') as f:
        f.write(b'PATCH')
        while i < n:
            if original[i] != patched[i]:
                start = i
                while i < n and original[i] != patched[i]:
                    i += 1
                recs += _ips_emit(f, start, patched[start:i])
            else:
                i += 1
        if len(patched) > n:
            # the whole expanded tail: zeros plus whatever we placed in it
            recs += _ips_emit(f, n, patched[n:])
        f.write(b'EOF')
    return recs


def apply_ips(ips_path, rom):
    d = open(ips_path, 'rb').read()
    assert d[:5] == b'PATCH'
    out = bytearray(rom)
    i = 5
    while True:
        if d[i:i + 3] == b'EOF':
            break
        off = (d[i] << 16) | (d[i + 1] << 8) | d[i + 2]
        i += 3
        ln = (d[i] << 8) | d[i + 1]
        i += 2
        if ln == 0:                       # RLE record
            rlen = (d[i] << 8) | d[i + 1]
            i += 2
            val = d[i]
            i += 1
            chunk = bytes([val]) * rlen
        else:
            chunk = d[i:i + ln]
            i += ln
        if off + len(chunk) > len(out):
            out.extend(b'\x00' * (off + len(chunk) - len(out)))
        out[off:off + len(chunk)] = chunk
    return bytes(out)
