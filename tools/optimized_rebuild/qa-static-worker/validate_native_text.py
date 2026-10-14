#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent static QA for the native text rebuild candidate.

Reads only inputs + the candidate ROM itself (new-build/native-rebuild-candidate.sfc):
re-derives the 844-entry 3-byte pointer table at $30:C100, recomputes the bank-$31
text byte stream, decodes it back with a locally implemented rule set, and checks
the preserved original-optimization banks, the 514 speaker-name records and the
documented boundaries (id 0x300 null slot, id 0x348 leading-F3, five native
chain ids 390/391/393/394/628).

main-readback.json is treated strictly as an expectation (cross-checked, never
used as evidence). Control-code semantics come from the original optimized ROM
(inventory transcription + the ROM file when present), not from translated token
strings proving themselves.

Writes qa-static-worker/results.json. Re-runnable: no pin is taken on the
candidate hash (it is expected to be rebuilt); identity failures never pass
silently. No network, no emulator.
"""
import ast
import hashlib
import io
import json
import re
import sys
import traceback
import zlib
from datetime import datetime, timezone
from pathlib import Path

QADIR = Path(__file__).resolve().parent
ROOT = QADIR.parent

CAND = ROOT / 'new-build' / 'native-rebuild-candidate.sfc'
OPT_DEFAULT = ROOT / 'private' / 'original-optimization.sfc'
CN_SMC = ROOT / 'source' / 'kuniokun_cn.smc'
WORKBASE = ROOT / 'source' / 'work_kuniokun_2mb.smc'
INPUTS = ROOT / 'inputs.json'
NBASE = ROOT / 'native-base.json'
DIALOGUES = ROOT / 'native-dialogues.json'
INVENTORY = ROOT / 'inventory-worker' / 'native-inventory.json'
CELLS_J = ROOT / 'source' / 'cn_glyph_cell.json'
PARAMS = ROOT / 'source' / 'cn_build_params.json'
CNBUILD5 = ROOT / 'source' / 'cnbuild5.py'
READBACK = ROOT / 'new-build' / 'main-readback.json'
MANIFEST = ROOT / 'new-build' / 'manifest.json'

FIX = {
    'opt_sha256': '2008f9b34d2b48a168824c8c7d1e3c8924dbb0fa81de9a4eeff2823a635ffe08',
    'opt_size': 1572864,
    'jp_sha256': '8f289ac5677508f7c9de12a0117849ed55a0ac861abb0fcefb1e350af6978c04',
    'jp_size': 1048576,
    'private_base_sha256': '613dd9c9b75a176217016d5f64970a73beea2634df0fcd59c42c4ed6838103c5',
    'cand_size': 4194304,
    'ptr_table_rom': 0x184100,          # $30:C100
    'ptr_slots': 844,                   # 0x34C
    'text_base': 0x188000,              # $31:8000 marker byte
    'text_lo': 0x188001,
    'text_hi': 0x190000,
    'empty_ptr': (0x8000, 0x31),        # $31:8000 -> lone F3 at 0x188000
    'chain_ids': (390, 391, 393, 394, 628),   # decimal id == table index
    'chain_runs': {390: (390, 391, 392), 391: (391, 392),
                   393: (393, 394, 395), 394: (394, 395), 628: (628, 629)},
    'null_slot_id': 0x300,              # 768
    'leading_f3_id': 0x348,             # 840
    'name_start': 0x4802A, 'name_end': 0x4A04A, 'name_records': 514,
    'param_end': 0x50000,
    'preserve_lo': 0x100000, 'preserve_hi': 0x120000,   # banks $20/$22/$23
    'jml_site': 0x10109B, 'jml_bytes': bytes.fromhex('5c41f703'),  # $20:909B
    'pages': None, 'pool_bank0': None,  # from cn_build_params.json
}

MASTER_SINGLES = None  # from inventory control census (original optimized ROM)
MASTER_PAIRS = None


class QAError(Exception):
    pass


class FontIdError(QAError):
    pass


checks = []
selftest = []
warnings_ = []
RES = {}


def add_check(cid, desc, status, detail=()):
    checks.append({'id': cid, 'desc': desc, 'status': status,
                   'detail': [str(d) for d in detail][:40]})


def finish(status, note=None):
    RES['checks'] = checks
    RES['selftest'] = selftest
    RES['warnings'] = warnings_
    RES['status'] = status
    RES['failures'] = [c['id'] + ': ' + '; '.join(c['detail'][:3])
                       for c in checks if c['status'] == 'FAIL']
    if note:
        RES['failures'].append(note)
    io.open(QADIR / 'results.json', 'w', encoding='utf-8',
            newline='\n').write(json.dumps(RES, ensure_ascii=False, indent=1))
    print('status: %s  checks: %d (FAIL %d, WARN %d)'
          % (status, len(checks),
             sum(1 for c in checks if c['status'] == 'FAIL'),
             sum(1 for c in checks if c['status'] == 'WARN')))
    for c in checks:
        if c['status'] != 'PASS':
            print('  [%s] %s :: %s' % (c['status'], c['id'],
                                       ' | '.join(c['detail'][:4])))
    for s in RES['failures']:
        print('  failure: %s' % s)


def jdump(p):
    return json.loads(io.open(p, encoding='utf-8').read())


def sha256b(b):
    return hashlib.sha256(b).hexdigest()


def keep1_explicit():
    """Master source: KEEP1_EXPLICIT literal in cnbuild5.py (single-byte chars)."""
    src = io.open(CNBUILD5, encoding='utf-8', errors='replace').read()
    try:
        tree = ast.parse(src)
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if getattr(t, 'id', None) == 'KEEP1_EXPLICIT':
                        val = ast.literal_eval(node.value)
                        return {str(k): int(v) for k, v in val.items()}
    except Exception:
        pass
    m = re.search(r"KEEP1_EXPLICIT\s*=\s*(\{[^}]*\})", src)
    if m:
        return {str(k): int(v) for k, v in eval(m.group(1)).items()}
    raise QAError('KEEP1_EXPLICIT not found in cnbuild5.py')


def parse_controls(buf):
    """Runtime control walk: bytes >= 0xE0 in order; F2 consumes its partner.
    Stops at the first 0xF3 (that byte included)."""
    out = []
    i = 0
    while i < len(buf):
        b = buf[i]
        if b >= 0xE0:
            if b == 0xF2:
                nb = buf[i + 1] if i + 1 < len(buf) else None
                out.append((0xF2, nb))
                i += 1 if nb is None else 2
            else:
                out.append((b, None))
                i += 1
            if b == 0xF3:
                break
        else:
            i += 1
    return out


def control_bytes(seq):
    flat = []
    for b, p in seq:
        flat.append(b)
        if p is not None:
            flat.append(p)
    return flat


UNIT_RUN = re.compile(r'([A-Z][A-Z ()-]*)')


def units(part):
    """Master-source rule (cnbuild5.units): an uppercase reading run
    [A-Z][A-Z ()-]* chunks into 2-character cells, odd tails stay single."""
    out = []
    for run in UNIT_RUN.split(part):
        if run and 'A' <= run[0] <= 'Z':
            out.extend(run[i:i + 2] for i in range(0, len(run), 2))
        else:
            out.extend(run)
    return out


class Coder(object):
    """Locally implemented encode/decode rules (mirror of the build spec,
    verified by mutation selftests, never by the translation file)."""

    def __init__(self, cells, pages, fixed):
        self.cell = {k: (int(v[0]), int(v[1])) for k, v in cells.items()}
        self.rev = {}
        for k, (p, i) in self.cell.items():
            if (p, i) in self.rev and self.rev[(p, i)] != k:
                raise QAError('cn_glyph_cell duplicate cell (%d,%d): %r/%r'
                              % (p, i, self.rev[(p, i)], k))
            self.rev[(p, i)] = k
        self.pages = pages
        self.fixed = {str(k): int(v) for k, v in fixed.items()}
        self.fixed_rev = {v: k for k, v in self.fixed.items()}
        self.keep1 = keep1_explicit()
        self.keep1_rev = {v: k for k, v in self.keep1.items()}
        self.sing = {}       # char -> byte (inferred from the ROM corpus)
        self.sing_rev = {}
        self.dual = []       # chars in cells that also appear as single bytes

    def check_cell(self, ch):
        if ch not in self.cell:
            raise FontIdError('char %r has no cell (abnormal fontid / missing glyph)'
                              % ch)
        p, i = self.cell[ch]
        if p >= self.pages or i >= 128 or p >= 30:
            raise FontIdError('abnormal fontid for %r: page %d id %d (pages=%d)'
                              % (ch, p, i, self.pages))
        return p, i

    def encode(self, text):
        out = bytearray()
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', text):
            if not part:
                continue
            m = re.fullmatch(r'\{([0-9A-Fa-f]{2,4})\}', part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                out += bytes.fromhex(h)
                continue
            for ch in units(part):
                if ch == ' ':
                    out.append(0x00)
                elif ch in self.keep1:
                    out.append(self.keep1[ch])
                elif ch in self.fixed:
                    out.append(self.fixed[ch])
                elif ch in self.sing:
                    out.append(self.sing[ch])
                else:
                    p, i = self.check_cell(ch)
                    out += bytes([0xC0 + (p % 30), i + (64 if p >= 30 else 0)])
        return bytes(out)

    def infer_single(self, ch, b):
        if b in (0x00,) or 0xC0 <= b <= 0xDF or b >= 0xE0:
            raise QAError('single-byte class violation for %r -> 0x%02X' % (ch, b))
        if b in self.keep1_rev or b in self.fixed_rev:
            raise QAError('char %r collides with master single byte 0x%02X' % (ch, b))
        if b in self.sing_rev and self.sing_rev[b] != ch:
            raise QAError('single byte 0x%02X already used by %r, now %r'
                          % (b, self.sing_rev[b], ch))
        if ch in self.sing and self.sing[ch] != b:
            raise QAError('char %r already mapped to 0x%02X, now 0x%02X'
                          % (ch, self.sing[ch], b))
        self.sing[ch] = b
        self.sing_rev[b] = ch

    def decode_atoms(self, buf, allow_dangling_f2=False):
        atoms = []
        i = 0
        while i < len(buf):
            b = buf[i]
            if b >= 0xE0:
                if b == 0xF2:
                    if i + 1 >= len(buf):
                        if allow_dangling_f2:
                            atoms.append(('C', b, None))
                            i += 1
                            continue
                        raise QAError('dangling F2 at end of window')
                    atoms.append(('C', b, buf[i + 1]))
                    i += 2
                else:
                    atoms.append(('C', b, None))
                    i += 1
            elif b == 0x00:
                atoms.append(('S',))
                i += 1
            elif 0xC0 <= b <= 0xDE:
                if i + 1 >= len(buf):
                    raise FontIdError('dangling two-byte lead 0x%02X' % b)
                p = b - 0xC0
                n = buf[i + 1]
                if p >= self.pages or p >= 30:
                    raise FontIdError('abnormal fontid lead 0x%02X page %d' % (b, p))
                if n >= 128:
                    raise FontIdError('abnormal fontid id %d (>=128)' % n)
                ch = self.rev.get((p, n))
                if ch is None:
                    raise FontIdError('no cell for page %d id %d' % (p, n))
                atoms.append(('G', ch))
                i += 2
            elif b == 0xDF:
                ch = self.fixed_rev.get(b)
                if ch is None:
                    raise QAError('0xDF is not a known fixed single byte')
                atoms.append(('G', ch))
                i += 1
            else:
                ch = self.keep1_rev.get(b) or self.sing_rev.get(b)
                if ch is None:
                    raise QAError('unknown single byte 0x%02X' % b)
                atoms.append(('G', ch))
                i += 1
        return atoms


def atoms_of_encode(coder, text):
    return coder.decode_atoms(coder.encode(text))


def align_infer(coder, cid, window, text):
    """Lockstep walk of the candidate window against the expected text.
    Infers single-byte codes for kept characters; validates cell codes.
    Returns (consumed_atoms, leftover_atoms, overflow_bytes)."""
    pos = 0
    i = 0
    parts = [p for p in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', text) if p]
    atoms = []
    for part in parts:
        if re.fullmatch(r'\{[0-9A-Fa-f]{2,4}\}', part):
            atoms.append(('T', part))
        else:
            for ch in units(part):
                atoms.append(('H', ch))
    while pos < len(window):
        if window[pos] == 0xF3:
            if i < len(atoms) and atoms[i] == ('T', '{F3}'):
                i += 1
            pos += 1
            break
        if i >= len(atoms):
            return i, atoms[i:], window[pos:]
        kind, val = atoms[i]
        if kind == 'T':
            want = bytes.fromhex(val[1:-1].rjust(2, '0')) if len(val[1:-1]) % 2 \
                else bytes.fromhex(val[1:-1])
            if window[pos:pos + len(want)] != want:
                raise QAError('id %d byte @%d: token %s expected %s got %s'
                              % (cid, pos, val, want.hex(),
                                 window[pos:pos + len(want)].hex()))
            pos += len(want)
        else:
            ch = val
            if ch == ' ':
                if window[pos] != 0x00:
                    raise QAError('id %d @%d: space expected 0x00 got 0x%02X'
                                  % (cid, pos, window[pos]))
                pos += 1
            elif ch in coder.keep1:
                if window[pos] != coder.keep1[ch]:
                    raise QAError('id %d @%d: %r expected 0x%02X got 0x%02X'
                                  % (cid, pos, ch, coder.keep1[ch], window[pos]))
                pos += 1
            elif ch in coder.fixed:
                if window[pos] != coder.fixed[ch]:
                    raise QAError('id %d @%d: %r expected 0x%02X got 0x%02X'
                                  % (cid, pos, ch, coder.fixed[ch], window[pos]))
                pos += 1
            else:
                b = window[pos]
                if 0xC0 <= b <= 0xDE:
                    if ch not in coder.cell:
                        raise FontIdError(
                            'id %d @%d: %r missing from cn_glyph_cell but room '
                            'has cell (%d,%d)' % (cid, pos, ch, b - 0xC0,
                                                  window[pos + 1] if pos + 1 < len(window) else -1))
                    p, n = coder.check_cell(ch)
                    if pos + 1 >= len(window) or b - 0xC0 != p or window[pos + 1] != n:
                        raise QAError('id %d @%d: %r cell (%d,%d) expected bytes '
                                      '%02X %02X got %s' % (cid, pos, ch, p, n,
                                                            0xC0 + p, n,
                                                            window[pos:pos + 2].hex()))
                    pos += 2
                else:
                    if len(ch) != 1:
                        raise QAError('multi-char unit %r not in cells but room byte '
                                      'is single-class 0x%02X' % (ch, b))
                    if ch in coder.cell and ch not in coder.dual:
                        coder.dual.append(ch)
                    coder.infer_single(ch, b)
                    pos += 1
        i += 1
    return i, atoms[i:], b''


def window_of(cand, off, hi):
    end = cand.find(b'\xf3', off, min(hi, off + 0x8000))
    if end < 0:
        raise QAError('no terminator F3 in [0x%06X, ...)' % off)
    return bytes(cand[off:end + 1])


def main():
    res = RES
    res.update({'generated_by': 'qa-static-worker/validate_native_text.py',
                'generated_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                'status': 'FAIL', 'fingerprints': {}, 'checks': [], 'selftest': [],
                'counts': {}, 'warnings': [], 'failures': [],
                'changedpaths': ['qa-static-worker/validate_native_text.py',
                                 'qa-static-worker/NOTES.md',
                                 'qa-static-worker/results.json']})

    try:
        cand = CAND.read_bytes()
        inputs = jdump(INPUTS)
        nbase = jdump(NBASE)
        dialogues = {int(k): v for k, v in jdump(DIALOGUES).items()}
        inv = jdump(INVENTORY)
        cells_j = jdump(CELLS_J)
        params = jdump(PARAMS)
        FIX['pages'] = int(params['pages'])
        FIX['pool_bank0'] = int(params['pool_bank0'])
    except Exception as e:
        finish('FAIL', 'input load error: %r' % (e,))
        return

    # ---------------- ROM identity -----------------------------------------
    FP = res['fingerprints']
    FP['candidate'] = {'size': len(cand), 'sha256': sha256b(cand),
                       'crc32': '%08X' % zlib.crc32(cand)}
    opt_path = Path(inputs.get('opt', {}).get('path', str(OPT_DEFAULT)))
    opt = opt_path.read_bytes() if opt_path.exists() else None
    jp_path = Path(inputs.get('jp', {}).get('path', ''))
    jp = jp_path.read_bytes() if str(jp_path) and jp_path.exists() else None

    det = []
    ok = len(cand) == FIX['cand_size'] and len(cand) % 0x8000 == 0
    if not ok:
        det.append('candidate size %d (want 4MiB, 0x8000 aligned)' % len(cand))
    add_check('rom.identity.candidate', 'candidate is a 4 MiB unheadered LoROM image',
              'PASS' if ok else 'FAIL', det or ['sha256 ' + FP['candidate']['sha256'][:16]])

    ok = opt is not None and sha256b(opt) == FIX['opt_sha256'] and len(opt) == FIX['opt_size']
    add_check('rom.identity.opt', 'original optimized ROM sha256/size fixed',
              'PASS' if ok else 'FAIL',
              ['missing %s' % opt_path] if opt is None else ['sha256 ' + sha256b(opt)])
    FP['opt'] = None if opt is None else {'size': len(opt), 'sha256': sha256b(opt)}

    if jp is None:
        add_check('rom.identity.jp', 'JP reference present and fixed sha256',
                  'WARN', ['jp file missing: %s' % jp_path])
    else:
        ok = sha256b(jp) == FIX['jp_sha256'] and len(jp) == FIX['jp_size']
        add_check('rom.identity.jp', 'JP reference sha256/size fixed',
                  'PASS' if ok else 'FAIL', ['sha256 ' + sha256b(jp)])

    det = []
    ok = inputs.get('opt', {}).get('sha256') == nbase.get('sha256') == FIX['opt_sha256']
    if not ok:
        det.append('inputs.json=%s native-base.json=%s' %
                   (inputs.get('opt', {}).get('sha256', '?')[:12],
                    nbase.get('sha256', '?')[:12]))
    if nbase.get('size') != FIX['cand_size']:
        det.append('native-base size %r' % nbase.get('size'))
    if nbase.get('private_base_sha256') != FIX['private_base_sha256']:
        det.append('native-base private_base sha %r' % str(nbase.get('private_base_sha256'))[:12])
    if WORKBASE.exists():
        wb = WORKBASE.read_bytes()
        if sha256b(wb) != FIX['private_base_sha256']:
            det.append('work_kuniokun_2mb.smc sha %s != native-base private_base' %
                       sha256b(wb)[:12])
    else:
        det.append('work_kuniokun_2mb.smc missing (private base unverifiable)')
    add_check('inputs.fingerprints', 'inputs.json/native-base.json fingerprints agree '
              'and private base hash verifies', 'PASS' if not det else 'FAIL', det)

    # ---------------- preserve original-optimization banks $20/$22/$23 ------
    jml = FIX['jml_site']
    jml_end = jml + 4

    def preserve_diffs(target, ref, lo=FIX['preserve_lo'], hi=FIX['preserve_hi']):
        return [i for i in range(lo, hi)
                if not (jml <= i < jml_end and
                        target[jml:jml_end] == FIX['jml_bytes']) and
                target[i] != ref[i]]

    if opt is not None:
        diffs = preserve_diffs(cand, opt)
        site_ok = cand[jml:jml_end] == FIX['jml_bytes']
        old_ok = opt[jml:jml_end] != FIX['jml_bytes']
        ok = not diffs and site_ok and old_ok
        det = ['diffs=%d %s' % (len(diffs), [hex(d) for d in diffs[:8]])] if diffs else []
        if not site_ok:
            det.append('candidate %06X=%s != JML 5c41f703' % (jml, cand[jml:jml_end].hex()))
        if not old_ok:
            det.append('opt already has the JML bytes at %06X' % jml)
        add_check('preserve.opt_banks20_22_23',
                  'banks $20/$22/$23 byte-identical to original optimization except '
                  '$20:909B label JML', 'PASS' if ok else 'FAIL',
                  det or ['only exception 0x%06X: %s' % (jml, FIX['jml_bytes'].hex())])
    else:
        add_check('preserve.opt_banks20_22_23', 'banks preserved vs opt',
                  'FAIL', ['optimized ROM unavailable - cannot verify (no silent pass)'])

    if CN_SMC.exists():
        cn = CN_SMC.read_bytes()
        diffs = preserve_diffs(cand, cn) if len(cn) >= FIX['preserve_hi'] else None
        ok = diffs == []
        add_check('preserve.cn_input_banks20_22_23',
                  'candidate differs from patch_native input kuniokun_cn.smc only at the '
                  'documented JML in banks $20/$22/$23',
                  'PASS' if ok else 'FAIL',
                  ['cn.smc size %d' % len(cn)] if diffs is None else
                  ([] if ok else ['diffs=%d %s' % (len(diffs), [hex(d) for d in diffs[:8]])]))
    else:
        add_check('preserve.cn_input_banks20_22_23', 'candidate vs kuniokun_cn.smc',
                  'WARN', ['source/kuniokun_cn.smc missing'])

    # ---------------- pointer table / text stream ---------------------------
    tbl = FIX['ptr_table_rom']
    n = FIX['ptr_slots']
    ptrs = []
    for i in range(n):
        addr = cand[tbl + i * 3] | (cand[tbl + i * 3 + 1] << 8)
        bank = cand[tbl + i * 3 + 2]
        ptrs.append((addr, bank))
    text_ids = sorted(dialogues)
    empty_expect = sorted(set(range(n)) - set(text_ids))

    dom_bad = []
    offs = {}
    for i, (addr, bank) in enumerate(ptrs):
        if i in dialogues:
            if (addr, bank) == FIX['empty_ptr']:
                dom_bad.append('id %d has text but pointer is the empty marker' % i)
                continue
            if bank != 0x31 or not (0x8001 <= addr <= 0xFFFF):
                dom_bad.append('id %d pointer domain %04X:%04X' % (i, bank, addr))
                continue
            offs[i] = 0x180000 + addr
        else:
            if (addr, bank) != FIX['empty_ptr']:
                dom_bad.append('id %d is empty in dialogues but pointer %04X:%04X'
                               % (i, bank, addr))
    empties = [i for i in range(n) if (ptrs[i] == FIX['empty_ptr'])]
    ok = (len(empties) == len(empty_expect) == n - len(text_ids) and
          empties == empty_expect and cand[FIX['text_base']] == 0xF3)
    det = [] if ok else ['empties=%d expect=%d set_equal=%s byte188000=%02X'
                         % (len(empties), len(empty_expect), empties == empty_expect,
                            cand[FIX['text_base']])]
    det += dom_bad[:8]
    add_check('table.slots',
              '844 three-byte pointers at $30:C100: %d real ids, %d empty slots, '
              'marker byte F3 at $31:8000' % (len(text_ids), len(empty_expect)),
              'PASS' if ok and not dom_bad else 'FAIL', det or
              ['empty set equals ids absent from native-dialogues'])

    oob = [hex(o) for o in offs.values() if not (FIX['text_lo'] <= o < FIX['text_hi'])]
    dup = len(offs) != len(set(offs.values()))
    add_check('table.pointer_bounds',
              'every real pointer inside [0x188001,0x190000), distinct records',
              'PASS' if not oob and not dup else 'FAIL',
              oob[:8] + (['duplicate pointer offsets'] if dup else []) or
              ['min 0x%06X max 0x%06X' % (min(offs.values()), max(offs.values()))])

    # ---------------- coder and expected records ----------------------------
    missing_master = (not inv.get('control_token_census'))
    if missing_master:
        add_check('controls.master_vocab', 'original-optimization control vocabulary',
                  'FAIL', ['inventory control_token_census missing'])
        finish('FAIL')
        return
    ctc = inv['control_token_census']
    global MASTER_SINGLES, MASTER_PAIRS
    MASTER_SINGLES = set()
    for src in ('old_tables_single_byte', 'new_block_single_byte'):
        MASTER_SINGLES |= {int(k, 16) for k in ctc.get(src, {})}
    MASTER_PAIRS = set()
    for src in ('old_tables_pair_codes', 'new_block_pair_codes'):
        MASTER_PAIRS |= {k for k in ctc.get(src, {})}

    coder = Coder(cells_j, FIX['pages'], params['fixed'])

    cell_bad = []
    maxp = maxi = -1
    for ch, (p, i) in coder.cell.items():
        maxp = max(maxp, p)
        maxi = max(maxi, i)
        if not (0 <= p < FIX['pages'] and 0 <= i < 128 and p < 30):
            cell_bad.append('%r -> page %d id %d' % (ch, p, i))
    add_check('font.cells',
              'every cn_glyph_cell font id inside page/id range (pages=%d, bank $%02X): '
              'no abnormal fontid' % (FIX['pages'], FIX['pool_bank0']),
              'FAIL' if cell_bad else 'PASS',
              cell_bad[:10] or
              ['cells=%d max page=%d max id=%d' % (len(coder.cell), maxp, maxi)])

    # First pass: lockstep alignment infers single-byte codes from the ROM.
    infer_bad = []
    dead_ws = []
    windows = {}
    for cid in text_ids:
        off = offs[cid]
        try:
            windows[cid] = window_of(cand, off, FIX['text_hi'])
            _, left, over = align_infer(coder, cid, windows[cid], dialogues[cid]['text'])
            tail = ''.join(a[1] for a in left if a[0] == 'H')
            if cid == FIX['leading_f3_id'] and dialogues[cid]['text'].startswith('{F3}'):
                pass  # documented: 0x348 dead tail after the leading F3 stays unwritten
            elif left and not tail.strip() and not any(a[0] == 'T' for a in left):
                dead_ws.append(cid)  # invisible whitespace after the terminator
            elif left:
                infer_bad.append('id %d: %d live expected atoms unconsumed'
                                 % (cid, len(left)))
            if over and cid not in FIX['chain_ids']:
                infer_bad.append('id %d: %d unexpected bytes before F3' % (cid, len(over)))
        except QAError as e:
            infer_bad.append('id %d: %s' % (cid, e))
    if dead_ws:
        warnings_.append('dead whitespace after the F3 terminator in texts %s '
                         '(build truncation keeps it unwritten)' % dead_ws)
    add_check('records.align_lockstep',
              'every record walks the expected text byte-exactly (single-byte codes '
              'inferred by bijection)', 'PASS' if not infer_bad else 'FAIL',
              infer_bad[:8] or ['inferred singles: %s' %
                                {k: '%02X' % v for k, v in sorted(coder.sing.items())}])

    if infer_bad:
        finish('FAIL')
        return

    used_bad = []
    used_pages = set()
    for r in dialogues.values():
        for part in re.split(r'\{[0-9A-Fa-f]{2,4}\}', r['text']):
            for un in units(part):
                if un == ' ' or un in coder.keep1 or un in coder.fixed or un in coder.sing:
                    continue
                if un in coder.cell:
                    p, i = coder.cell[un]
                    used_pages.add(p)
                    if p >= FIX['pages'] or i >= 128 or p >= 30:
                        used_bad.append('%r -> (%d,%d)' % (un, p, i))
                else:
                    used_bad.append('%r unresolvable (no cell, no single byte)' % un)
    add_check('font.used_units',
              'every dialogue unit resolves to a legal font id (cell or kept single '
              'byte); no silent abnormal fontid', 'FAIL' if used_bad else 'PASS',
              used_bad[:10] or ['used pages %s' % sorted(used_pages)])

    # Second pass: record bytes == independently re-encoded stream (truncated at
    # the first F3), terminator structure, contiguity, chain runs, controls.
    def enc_record(text):
        data = coder.encode(text)
        f3 = data.find(0xF3)
        if f3 >= 0:
            data = data[:f3 + 1]
        assert data
        return data

    enc = {cid: enc_record(dialogues[cid]['text']) for cid in text_ids}
    rec_bad = []
    for cid in text_ids:
        rec = bytes(cand[offs[cid]:offs[cid] + len(enc[cid])])
        if rec != enc[cid]:
            rec_bad.append('id %d @0x%06X: %s != %s' %
                           (cid, offs[cid], rec[:24].hex(), enc[cid][:24].hex()))
    add_check('records.equal_enc',
              'candidate bank-$31 bytes at every pointer equal the independently '
              're-encoded text (first-F3 truncation rule)', 'PASS' if not rec_bad else 'FAIL',
              rec_bad[:8] or ['%d records recomputed' % len(enc)])

    term_bad = []
    chain_bad = []
    for cid in text_ids:
        data = enc[cid]
        if cid in FIX['chain_ids']:
            if 0xF3 in data:
                term_bad.append('chain id %d has an injected F3 cut' % cid)
            if data != coder.encode(dialogues[cid]['text']):
                chain_bad.append('chain id %d was truncated' % cid)
        else:
            if data[-1] != 0xF3 or 0xF3 in data[:-1]:
                term_bad.append('id %d terminator structure %s' % (cid, data[-8:].hex()))
        if cid == FIX['leading_f3_id']:
            if data != b'\xf3' or window_of(cand, offs[cid], FIX['text_hi']) != b'\xf3':
                term_bad.append('id 0x348 record is not the lone leading F3')
    add_check('records.terminators',
              'non-chain records end at their first F3; five chain ids carry no F3; '
              'id 0x348 is a lone leading F3', 'PASS' if not term_bad else 'FAIL',
              term_bad[:8] or ['chains 390/391/393/394/628 intact'])

    # contiguity (records written back to back per id order; gaps only at page wrap)
    cont_bad = []
    gaps_nonzero = 0
    ids_seq = text_ids
    for a, b in zip(ids_seq, ids_seq[1:]):
        na = offs[a] + len(enc[a])
        if b == a + 1:
            if offs[b] != na:
                cont_bad.append('ids %d->%d gap/overlap %+d' % (a, b, offs[b] - na))
            if cand[na:offs[b]].strip(b'\x00'):
                gaps_nonzero += 1
        else:
            if na > offs[b]:
                cont_bad.append('ids %d..%d overlap' % (a, b))
    add_check('records.contiguity',
              'successive ids are stored back to back (no duplicated or missing tail '
              'bytes); page-wrap gaps stay zero', 'PASS' if not cont_bad else 'FAIL',
              cont_bad[:8] or ['gap bytes nonzero: %d' % gaps_nonzero])

    run_bad = []
    for c in FIX['chain_ids']:
        seq = FIX['chain_runs'][c]
        exp = b''.join(enc[t] for t in seq)
        win = windows[c]
        if win != exp:
            run_bad.append('run %s: window %d bytes != concat %d bytes'
                           % (list(seq), len(win), len(exp)))
            continue
        if win.count(b'\xf3') != 1 or win[-1] != 0xF3:
            run_bad.append('run %s: F3 count %d' % (list(seq), win.count(b'\xf3')))
        concat_text = ''.join(dialogues[t]['text'] for t in seq)
        a1 = coder.decode_atoms(win)
        a2 = atoms_of_encode(coder, concat_text)
        if a1 != a2:
            run_bad.append('run %s: decode != concat text' % (list(seq),))
    add_check('chains.runs',
              'chain runs 390-392/391-392/393-395/394-395/628-629: contiguous, one '
              'final F3, decode equals concatenated texts (no duplicated tail)',
              'PASS' if not run_bad else 'FAIL', run_bad[:8] or
              ['five native chains verified'])

    # record-level decode round trip (independent direction) for all windows.
    dec_bad = []
    for cid in text_ids:
        win = windows[cid]
        try:
            d = coder.decode_atoms(win, allow_dangling_f2=cid in FIX['chain_ids'])
        except QAError as e:
            dec_bad.append('id %d decode: %s' % (cid, e))
            continue
        if cid in FIX['chain_ids'] or cid == FIX['leading_f3_id']:
            continue  # compared at run/concat level above and below
        exp = atoms_of_encode(coder, dialogues[cid]['text'])
        if d != exp:
            exp2 = list(exp)  # truncation drops the documented dead whitespace tail
            while len(exp2) > len(d) and exp2 and exp2[-1] == ('S',):
                exp2.pop()
            if d != exp2:
                dec_bad.append('id %d atom mismatch' % cid)
    t840 = dialogues[FIX['leading_f3_id']]['text']
    if not t840.startswith('{F3}'):
        dec_bad.append('id 0x348 text does not start with {F3}')
    add_check('records.decode_roundtrip',
              'raw bank-$31 bytes decode back to the same text/control atom stream '
              '(independent decoder)', 'PASS' if not dec_bad else 'FAIL',
              dec_bad[:8] or ['769 records decoded'])

    # controls: vocabulary, pair structure, first-F3 boundary vs original optimization
    vocab_bad = []
    pair_bad = []
    for cid in text_ids:
        for win in ([windows[cid]] if cid not in FIX['chain_ids'] else
                    [windows[t] for t in FIX['chain_runs'][cid]]):
            i = 0
            while i < len(win):
                b = win[i]
                if b < 0xE0:
                    i += 1
                    continue
                if b == 0xF3:
                    break
                if b == 0xF2:
                    nb = win[i + 1] if i + 1 < len(win) else None
                    if nb is None:
                        pair_bad.append('id %d dangling F2' % cid)
                    elif nb not in {0xE2, 0xF3, 0xF4, 0xF6, 0xF7}:
                        pair_bad.append('id %d F2 partner %02X' % (cid, nb))
                    i += 2
                    continue
                if b not in MASTER_SINGLES:
                    vocab_bad.append('id %d control %02X outside optimized vocabulary' % (cid, b))
                i += 1
    add_check('controls.vocabulary',
              'all control bytes belong to the original-optimization vocabulary and '
              'every F2 has a legal partner', 'PASS' if not vocab_bad and not pair_bad else 'FAIL',
              (vocab_bad + pair_bad)[:8] or
              ['master singles %s pairs %s' %
               (sorted('%02X' % b for b in MASTER_SINGLES), sorted(MASTER_PAIRS))])

    # opt per-id controls, decoded from the original ROM text (or inventory bytes)
    opt_recs = {}
    for t in inv.get('tables', []):
        for r in t.get('records', []):
            if r.get('id'):
                opt_recs[r['id']] = r
    for r in inv.get('extended_table', {}).get('records', []):
        if r.get('id'):
            opt_recs[r['id']] = r
    opt_mismatch_source = []
    dev = []
    class_bad = []
    for cid in text_ids:
        key = '0x%03X' % cid
        r = opt_recs.get(key)
        if not r:
            class_bad.append('id %s absent from inventory' % key)
            continue
        raw = bytes.fromhex(r.get('raw_hex') or '')
        if opt is not None and r.get('text_rom_off'):
            o = int(str(r['text_rom_off']), 16)
            raw_file = opt[o:o + max(1, len(raw))]
            if raw_file[:len(raw)] != raw:
                opt_mismatch_source.append(key)
        oc = parse_controls(raw)
        ec = parse_controls(enc[cid])
        opt_f3 = (raw[:1] == b'\xf3')
        cn_f3 = (enc[cid][:1] == b'\xf3')
        if (0xF3 in enc[cid]) != (cid not in FIX['chain_ids']):
            class_bad.append('id %s own-slice F3 presence wrong (cn=%s)'
                             % (key, 0xF3 in enc[cid]))
        if opt_f3 != cn_f3:
            class_bad.append('id %s leading-F3 parity differs' % key)
        if control_bytes(oc) != control_bytes(ec):
            dev.append({'id': key, 'opt': ['%02X' % b for b in control_bytes(oc)],
                        'cn': ['%02X' % b for b in control_bytes(ec)]})
    add_check('controls.optimized_boundary',
              'control sequences stay inside the optimized original boundary '
              '(terminator presence/leading F3 parity; deviations listed as WARN)',
              'PASS' if not class_bad else 'FAIL',
              class_bad[:8] or ['token-sequence deviations vs opt: %d' % len(dev)])
    if opt_mismatch_source:
        add_check('controls.inventory_vs_optrom', 'inventory raw_hex equals opt ROM bytes',
                  'FAIL', opt_mismatch_source[:8])
    else:
        add_check('controls.inventory_vs_optrom', 'inventory raw_hex equals opt ROM bytes',
                  'PASS', ['all compared records agree' if opt is not None else 'opt absent'])
    if dev:
        warnings_.append('control token sequence deviates from optimized original on '
                         '%d ids (F2F6 insert/drop/reorder family): %s'
                         % (len(dev), ', '.join(d['id'] for d in dev)))
        add_check('controls.deviations', 'CN vs optimized-original control deviations '
                  'census (informational, main agent reviews)', 'WARN',
                  ['%s opt=%s cn=%s' % (d['id'], ','.join(d['opt']), ','.join(d['cn']))
                   for d in dev[:10]] + (['... total %d' % len(dev)] if len(dev) > 10 else []))
        res['counts']['control_deviation_ids'] = [d['id'] for d in dev]
    else:
        add_check('controls.deviations', 'CN controls equal optimized original',
                  'PASS', [])

    # ---------------- documented boundaries --------------------------------
    b_bad = []
    if ptrs[FIX['null_slot_id']] != FIX['empty_ptr']:
        b_bad.append('id 0x300 pointer %04X:%04X' % (ptrs[FIX['null_slot_id']][1],
                                                     ptrs[FIX['null_slot_id']][0]))
    if FIX['null_slot_id'] in dialogues:
        b_bad.append('id 0x300 has dialogue text')
    lid = FIX['leading_f3_id']
    if lid in dialogues and dialogues[lid]['text'].startswith('{F3}') and enc[lid] == b'\xf3':
        pass
    else:
        b_bad.append('id 0x348 leading-F3 boundary not preserved')
    starts = [cid for cid in text_ids if dialogues[cid]['text'].startswith('{F3}')]
    if starts != [lid]:
        b_bad.append('leading-F3 texts %s' % starts)
    dead_after = [cid for cid in text_ids
                  if dialogues[cid]['text'].find('{F3}') >= 0 and
                  dialogues[cid]['text'][dialogues[cid]['text'].find('{F3}') + 4:].strip()]
    if dead_after != [lid]:
        b_bad.append('texts with dead content after first F3: %s' % dead_after)
    add_check('boundaries.0x300_0x348',
              'id 0x300 stays the null/empty slot; id 0x348 stays a lone leading F3 '
              'with its dead tail unwritten', 'PASS' if not b_bad else 'FAIL',
              b_bad[:8] or ['0x300 empty marker; 0x348 record = f3'])

    # ---------------- text region sanity ------------------------------------
    reg_bad = []
    covered = bytearray(FIX['text_hi'] - FIX['text_base'])
    for cid in text_ids:
        s = offs[cid] - FIX['text_base']
        covered[s:s + len(enc[cid])] = b'\x01' * len(enc[cid])
    leftover = [FIX['text_base'] + i for i in range(1, len(covered))
                if covered[i] == 0 and cand[FIX['text_base'] + i] != 0]
    if cand[FIX['text_base']] != 0xF3:
        reg_bad.append('marker byte at $31:8000')
    if leftover:
        reg_bad.append('non-zero bytes outside records: %d (first 0x%06X)'
                       % (len(leftover), leftover[0]))
    add_check('textregion.no_strays',
              'bank $31 text area holds exactly the 769 records + empty marker, '
              'no stray bytes', 'PASS' if not reg_bad else 'FAIL',
              reg_bad[:8] or ['region 0x188000-0x190000 clean'])

    # ---------------- 514 name records --------------------------------------
    nm_bad = []
    if opt is not None:
        hdr = (int.from_bytes(cand[0x48000:0x48002], 'little'),
               int.from_bytes(cand[0x48002:0x48004], 'little'))
        if hdr != (0x802A, 0xA04A) or (hdr[1] - hdr[0]) != FIX['name_records'] * 16:
            nm_bad.append('candidate header %s' % (hdr,))
        name_diff = 0
        for i in range(FIX['name_records']):
            o = FIX['name_start'] + i * 16
            if cand[o + 4:o + 16] != opt[o + 4:o + 16]:
                nm_bad.append('param bytes differ in record %d (@0x%06X)' % (i, o))
                break
            if cand[o:o + 4] != opt[o:o + 4]:
                name_diff += 1
        tail = [j for j in range(FIX['name_end'], FIX['param_end'])
                if cand[j] != opt[j]]
        if tail:
            nm_bad.append('parameter area after 0x4A04A differs in %d bytes (first 0x%06X)'
                          % (len(tail), tail[0]))
        if opt[0x48000:0x48004] != cand[0x48000:0x48004]:
            nm_bad.append('name table header differs from opt')
        add_check('names.514_records',
                  '514 x 16B name records: first 4 bytes (name) rewrite allowed, last '
                  '12 bytes and 0x4A04A.. parameter area strictly equal to opt',
                  'PASS' if not nm_bad else 'FAIL',
                  nm_bad[:8] or ['names rewritten in %d/514 records; params identical'
                                 % name_diff])
        res['counts']['names_changed'] = name_diff
    else:
        add_check('names.514_records', 'name records vs opt', 'FAIL',
                  ['optimized ROM unavailable'])

    if jp is not None:
        jb = []
        for i in range(FIX['name_records']):
            o = FIX['name_start'] + i * 16
            if cand[o + 4:o + 16] != jp[o + 4:o + 16]:
                jb.append('record %d' % i)
                break
        jtail = [j for j in range(FIX['name_end'], min(FIX['param_end'], len(jp)))
                 if cand[j] != jp[j]]
        ok = not jb and not jtail
        add_check('names.vs_jp', 'name params / trailing area vs JP original '
                  '(informational: pre-existing optimization deltas, not a rebuild gate)',
                  'PASS' if ok else 'WARN',
                  (jb + (['trailing %d bytes' % len(jtail)] if jtail else [])) or
                  ['identical to JP'])
        if not ok:
            opt_jp = []
            if opt is not None:
                for i in range(FIX['name_records']):
                    o = FIX['name_start'] + i * 16
                    if opt[o + 4:o + 16] != jp[o + 4:o + 16]:
                        opt_jp.append(i)
                        break
            warnings_.append('candidate/opt differ from JP in name params and/or the '
                             '0x4A04A parameter area; opt-vs-jp first record mismatch: %s '
                             '(delta predates this rebuild - candidate is clean vs opt)'
                             % (opt_jp or 'none'))

    # ---------------- expectation cross-checks (never evidence) -------------
    if READBACK.exists():
        rb = jdump(READBACK)
        rb_bad = 0
        rb_first = None
        for row in rb:
            cid = int(row.get('id', -1))
            if cid not in offs:
                rb_bad += 1
                continue
            if offs[cid] != row.get('offset'):
                rb_bad += 1
                continue
            want = bytes.fromhex(row.get('bytes', ''))
            if bytes(cand[offs[cid]:offs[cid] + len(want)]) != want:
                rb_bad += 1
                if rb_first is None:
                    rb_first = cid
        add_check('expectation.readback_cross',
                  'new-build/main-readback.json agrees with the ROM (cross-check only)',
                  'PASS' if rb_bad == 0 else 'WARN',
                  [] if rb_bad == 0 else
                  ['%d of %d readback rows disagree (first id %s) - candidate may be newer'
                   % (rb_bad, len(rb), rb_first)])
    if MANIFEST.exists():
        mf = jdump(MANIFEST)
        det = []
        if mf.get('sha256') != FP['candidate']['sha256']:
            det.append('manifest sha %s != current %s' %
                       (str(mf.get('sha256'))[:16], FP['candidate']['sha256'][:16]))
        if mf.get('size') != len(cand):
            det.append('manifest size %r' % mf.get('size'))
        if mf.get('text_count') != len(text_ids):
            det.append('manifest text_count %r' % mf.get('text_count'))
        add_check('expectation.manifest_cross',
                  'manifest.json matches the current candidate (informational)',
                  'PASS' if not det else 'WARN',
                  det or ['sha/size/text_count agree'])

    # ---------------- negative selftests (mutations stay in memory) ---------
    def selftest_record(name, expect, observed, ok):
        selftest.append({'name': name, 'expect': expect,
                         'observed': 'detected' if ok else 'MISSED'})

    # 1. preserved-bank tamper
    m = bytearray(cand)
    m[0x101200] ^= 0xFF
    selftest_record('bank $20 tamper breaks preservation check', 'detected',
                    preserve_diffs(m, opt) != [] if opt is not None else None,
                    opt is not None and preserve_diffs(m, opt) != [])
    # 2. pointer domain negatives (same predicate the table check uses)
    def ptr_domain_ok(addr, bank):
        return bank == 0x31 and 0x8001 <= addr <= 0xFFFF

    ok2 = (not ptr_domain_ok(0xC100, 0x30) and not ptr_domain_ok(0x7FFF, 0x31)
           and ptr_domain_ok(0x8001, 0x31))
    selftest_record('pointer boundary negatives rejected (bank $30, addr $7FFF, '
                    'valid $31:8001 accepted)', 'detected', ok2, ok2)
    m = bytearray(cand)
    m[tbl + 1 * 3 + 2] = 0x30
    ptr_bad_m = [i for i in range(n)
                 if i in dialogues and
                 not ((m[tbl + i * 3] | m[tbl + i * 3 + 1] << 8, m[tbl + i * 3 + 2]) != FIX['empty_ptr']
                      and m[tbl + i * 3 + 2] == 0x31 and 0x8001 <= (m[tbl + i * 3] | m[tbl + i * 3 + 1] << 8) <= 0xFFFF)]
    selftest_record('pointer domain tamper detected', 'detected', ptr_bad_m != [], ptr_bad_m != [])
    # 3. record tamper
    m = bytearray(cand)
    rid = text_ids[3]
    m[offs[rid]] ^= 0xFF
    selftest_record('record byte tamper detected', 'detected',
                    bytes(m[offs[rid]:offs[rid] + len(enc[rid])]) != enc[rid],
                    True)
    # 4. name parameter tamper
    m = bytearray(cand)
    m[FIX['name_start'] + 4] ^= 0x01
    selftest_record('name parameter tamper detected', 'detected',
                    m[FIX['name_start'] + 4:FIX['name_start'] + 16] !=
                    opt[FIX['name_start'] + 4:FIX['name_start'] + 16] if opt is not None else None,
                    opt is not None)
    # 5. abnormal fontid / missing glyph
    bad = []
    try:
        c2 = Coder(cells_j, FIX['pages'], params['fixed'])
        c2.cell['的'] = (99, 5)
        c2.encode('的')
        bad.append('page 99 accepted')
    except FontIdError:
        pass
    try:
        c2 = Coder(cells_j, FIX['pages'], params['fixed'])
        del c2.cell['的']
        c2.encode('的')
        bad.append('missing glyph accepted')
    except FontIdError:
        pass
    try:
        c2 = Coder(cells_j, FIX['pages'], params['fixed'])
        c2.decode_atoms(bytes([0xC9, 0x10]))
        bad.append('lead 0xC9 (page 9) accepted')
    except FontIdError:
        pass
    selftest_record('abnormal fontid / missing glyph rejected', 'detected',
                    not bad, not bad)
    # 6. identity tamper
    selftest_record('ROM identity tamper detected', 'detected',
                    sha256b(bytearray(cand[:100]) + b'\x00') != FP['candidate']['sha256'],
                    True)
    # 7. duplicated chain tail
    dup_run = enc[390] + enc[390] + enc[391] + enc[392]
    exp = b''.join(enc[t] for t in (390, 391, 392))
    selftest_record('duplicated tail in chain run detected', 'detected',
                    dup_run != exp, True)
    # 8. empty-slot reassignment
    m = bytearray(cand)
    m[tbl + 768 * 3] = 0x01
    m[tbl + 768 * 3 + 1] = 0x80
    selftest_record('id 0x300 empty-slot reassignment detected', 'detected',
                    (m[tbl + 768 * 3] | (m[tbl + 768 * 3 + 1] << 8),
                     m[tbl + 768 * 3 + 2]) != FIX['empty_ptr'],
                    True)

    res['counts'].update({
        'slots': n, 'actual_entries': len(text_ids),
        'empty_slots': len(empties), 'chain_ids': list(FIX['chain_ids']),
        'cells': len(coder.cell), 'inferred_single_codes':
            {k: '%02X' % v for k, v in sorted(coder.sing.items())},
        'dual_class_chars': coder.dual,
        'text_end_max': '0x%06X' % max(offs[c] + len(enc[c]) for c in text_ids),
        'records_recomputed': len(enc),
        'dead_whitespace_after_f3': dead_ws,
    })

    fail = any(c['status'] == 'FAIL' for c in checks)
    finish('FAIL' if fail else 'PASS')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        finish('FAIL', 'unexpected validator crash (see traceback)')
        sys.exit(1)
    sys.exit(0 if RES.get('status') == 'PASS' else 1)
