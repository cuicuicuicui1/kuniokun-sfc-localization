"""Build the Chinese-patched 初代熱血硬派くにおくん ROM  (design v5).

Two independent text pipelines exist in the engine and both are patched:

  (1) dialogue / list box - bank $03
      loader (ROM 0x01ED25) copies message bytes into the RAM buffer $03EA,
      the consumer (ROM 0x01EEF5) feeds each byte to the drawer at ROM 0x01FA30,
      which appends 8-byte VRAM-script entries to RAM $0B00 for a 16-row x 26-col
      box whose cell address is $7C00 + row*0x40 + 3 + col.
  (2) three HUD name widgets - renderer at ROM 0x00FC77, called from
      ROM 0x00FC2F / 0x00FC40 / 0x00FC51, which writes tilemap entries directly
      to $2118/$2119 at cursor $79C6 / $7A06 / $7A46.

Encoding: [0xC5 + page][id], page 0..10, id 0..113
  * $C5-$CF is dead space in the original code map, and stays below $E0 so the
    macro expander copies it verbatim.
  * the id byte doubles as the VRAM slot.  A build-time graph colouring makes
    sure glyphs that can be on screen together never share a slot, which holds
    for the dialog box and for list screens of any height.
  * slot -> tile pair comes from SLOTPAIR[], skipping the pairs that surviving
    original codes still draw (space, punctuation, digits, frame, decor).
  * glyph bitmap at bank (POOL_BANK0 + page) : ($8000 + id*32) is DMA'd into its slot
    on every draw, so no glyph cache and no extra RAM are needed.

Patches (all verified byte-for-byte against the original ROM):
  0x01FA30 (3) -> JMP drawer_copy   ; Chinese check + verbatim copy of the drawer
  0x01ECA7 (3) -> JSR sanitize      ; macro copier 1: keep $C5-$CF out of records
  0x01ECC5 (3) -> JSR sanitize      ; macro copier 2
  0x00FC79 (4) -> JML $3E:8000      ; widget preload (pointer table -> $22/$23/$24)
  0x00FC85 (2) -> EA EA
  0x00FC92 (4) -> JML $3E:8080      ; widget dispatcher
"""
from pathlib import Path
import json
import os
import re

import kuniokun_map as km
import cnglyph
from cnfont8 import render8x16
from sfc_tools import pack_8x8, make_ips

GLYPH_THRESH = 140
GLYPH_WIDEN = 1.12
# The 8x16 renderer (cnfont8.render8x16) scales the 16 px face down to
# eight columns with LANCZOS before thresholding, and that averaging pulls
# the strokes well below 140: at GLYPH_THRESH the glyphs came out as
# scattered dashes, unreadable even for a character as simple as 力.
# Measured over 等验器鞋攻御运力最敏: 100 is clean, 70 is bold but still
# legible, 45 merges strokes.  The 16x16 path is a different function
# (cnglyph.render16x16) and keeps GLYPH_THRESH.
GLYPH8_THRESH = 100

BASE = str(Path(__file__).resolve().parent)
SRC_ROM = BASE + '/work_kuniokun_2mb.smc'
OUT_ROM = BASE + '/kuniokun_cn.smc'
OUT_IPS = BASE + '/kuniokun_cn.ips'
ORIG_ROM = BASE + '/dl/roms/kuniokun__SF8127.smc'
FONT_PATH = 'C:/Windows/Fonts/msyh.ttc'
FONT_ROM = 0x0F8000                 # the engine's own font block, 256
FONT_BANK = 0x1F                    # tiles, copied to VRAM $C000 at boot

CODE_ROM = 0x1F0000                    # bank $3E scratch
PRELOAD_ROM = CODE_ROM                 # $3E:8000
DISPATCH_ROM = 0x1F6000                 # $3E:E000: room for the dispatch
                                        # routine to grow; at $3E:8080 it had
                                        # only 256 bytes before the slot table
E3_SLOTPAIR = CODE_ROM + 0x180         # $3E:8180  slot -> two tile pairs
E3_ROWSET = None                        # $3E: row -> label pair set (set in main)
E3_SLOTHI = CODE_ROM + 0x700            # $3E:8700  slot -> tile high byte: the
                                        # moved label pairs live outside the font
                                        # window, so their tile numbers need bits
                                        # 8-9 (0 for every other entry, which keeps
                                        # the drawer's output identical there)
B3_SLOTPAIR = 0x01E900                 # $03:E900  spare text space now:
B3_SLOTPAIR_LIMIT = 0x01E970           # the slot table moved to bank $3E

# ------------------------------------------------------------- item names
# The status screen's three equipment values (buki / uraji / kutsu) are drawn
# by $01:FC75, which reads a name out of the pointer table at $03:DBC3 and
# names tiles through FA/FB.  It uploads no glyphs, so it only works while the
# font block still holds those kana -- and the glyph pool overwrites 45 of
# those tiles during ordinary play (measured with hw/clashwatch.lua; the font
# block is loaded once, at boot, and never reloaded).
#
# So the names get their own code and their own glyph table.  A code is
# [ITEM_PREFIX][id], id indexing an 8x16 table at $3f:8000 + id*32 which the
# renderer uploads before naming the tiles.  8x16 rather than the dialogue's
# 16x16 because a value is drawn one character per column and the label column
# beside it leaves only 12: a 16x16 glyph would halve that.
#
# The slot a glyph is uploaded to comes from the VRAM cursor, not from the
# build time colouring.  The three values are on screen together, so they must
# not share slots, and only the cursor tells them apart: $79C6 / $7A06 / $7A46
# (rows 14 / 16 / 18, column 6) give the slot bases 0 / 13 / 26, and inside one
# value the slot advances one per column.  That keeps the names out of the
# colouring entirely -- they need no pool slots and no protected tiles.
ITEM_TABLE = 0x01DBC5
ITEM_PREFIX = 0xDE                     # $db..$de are unused: the drawer's
                                       # Chinese range stops at $da and the one
                                       # byte codes start at $df
ITEM_GLYPH_BANK = 0x3F
ITEM_MENU_GLYPH_ROM = 0x1FA000       # $3F:A000: legible 16x16 list-only glyphs
ITEM_GLYPH_ROM = 0x1F8000
ITEM_GLYPH_MAX = 256
ITEMDRAW_ROM = 0x1F4800                # $3e:c800
ITEMBASE_ROM = 0x1F4A00                # $3e:ca00  three bytes: 0, 13, 26
ITEM_HOOK = 0x00FCA5                   # cpu $01:fca5, the FB[code] lookup
# ------------------------------------------------------- the battle HUD plate
# $00:8C83 names the battle HUD's name plate tiles through FA/FB, one BYTE of
# the name record per cell.  A four byte record is four cells, which is right
# when the record holds four single byte codes -- but a translated name is two
# two byte codes ([page][id]), so the plate drew FA[page] and FA[id] and came
# out as four wrong glyphs (user screenshot: "=○Θ" beside the HP bar).
#
# HUDNAME_HOOK replaces the six instructions that do that lookup
# ($00:8C91..$00:8CA2, 18 bytes).  For a code below $C0 it falls back to the
# engine's own FA/FB.  For a two byte code it takes glyph  (cell >> 1) of the
# record, uploads it into the name pair slots and sets $22/$23 for the caller.
#
# The plate is drawn during ACTIVE DISPLAY, so there is no VRAM DMA here (the
# two existing glyph hooks could use one only because the status screen runs in
# forced blank).  The glyph goes through the engine's own $0B00 queue instead,
# which $00:8385 flushes in vblank: two 32 byte tile entries, no tile map cells
# (the caller writes those from $22/$23).
HUDNAME_ROM = 0x1F5000                 # $3E:D000, free up to DISPATCH_ROM
HUDNAME_HOOK = 0x000C91                # cpu $00:8C91, 18 bytes, M/X 8 bit
# The item name a battle message pastes in is [$DE][8x16 id] per hanzi, a code
# only the status screen's renderer knows.  The message drawer's dispatch sends
# $DE to the fixed-glyph path, where FIXED0 = $DF leaves $DC..$DE unused, so
# $DE can be claimed here: the drawer branches to this routine, which uploads
# the glyph through the $0B00 queue (the message box is drawn during active
# display, so no VRAM DMA) and rejoins the drawer's own exit.
ITEMMSG_ROM = 0x1F5400                 # $3E:D400, free up to DISPATCH_ROM
PACE_ROM = 0x1F5800                    # $3E:D800, the drawer's pacing gate
PACE_HOOK = 0x01EEE5                   # cpu $03:EEE5, 6 bytes, M/X 8 bit, DBR=$03
# $03C4 is NOT scratch: it is the low horizontal-scroll byte in the last
# five-byte record of the live BG3 HDMA table at $03AA-$03C8. HDMA reads it at
# scanline 216 without any CPU opcode referencing $03C4. The old countdown
# therefore shifted the bottom eight scanlines by 0..5 pixels while typing.
# $03E7 is the original loader's otherwise-unused per-message byte, reset by
# STZ $03E7 at $03:EBAC. It is beyond the HDMA terminator (and the loader's
# overlapping 16-bit table-copy store at $03C9), before length/index $03E8/9.
# Its ownership is checked by model tests and a physical-WRAM access trace,
# not merely by absence of absolute CPU references. Do not use queue-tail
# bytes here: existing 256-byte glyph/HUD batches can reach them.
PACE_FRAMES = 0x03E7                   # per-message attempts until next glyph
LABELDRAW_ROM = 0x1F4C00               # $3e:cc00
LABEL_HOOK = 0x00F9BC                  # cpu $01:f9bc, the same lookup
                                       # inside the label interpreter
ITEM_CHARS = {}                        # char -> 8x16 id, filled in main()

E3_DRAWER = CODE_ROM + 0x200           # $3E:8200  drawer: Chinese branch
E3_MSG = CODE_ROM + 0x800              # $3E:8800  new entry: blank the box,
                                       #           then replay the eaten op
# the macro-copier hook is a 3-byte JSR, so the sanitizer must live in bank $03;
# it goes into the tail of the status-verb region, which is only reached through
# pointers (never walked byte by byte) and keeps 200+ spare bytes.
B3_SANITIZE = 0x01E970
B3_SANITIZE_LIMIT = 0x01E982
B3_SANITIZE_END = 0x01E982        # text may use everything up to the $EA macro table
POOL_ROM = 0x100000                    # bank $20 + page
POOL_STRIDE = 64                       # one Chinese glyph = 16x16 px = four tiles
GLYPH_TILES = 4                        # tiles per glyph: TL, BL, TR, BR
# Tables whose text is deliberately left in Japanese.  Empty now: the item
# window was the last one, and it turned out to be live (the status screen's
# buki/uraji/kutsu rows -- see the item-name block below).  Kept because the
# packer, the region list and the colouring all consult it.
NO_TRANSLATE = set()

# speaker-name records (user-approved: every name is translated).
# Each record is 4 code bytes, so a name is at most two hanzi; name_hanzi.json
# (built by name_table.py) holds one rendering per kana reading.  The label
# glyphs live in their own banks and are drawn with their own tile pairs, so
# they never take part in the body colouring (see LABEL_* below).
NAME_HANZI_FILE = '/name_hanzi.json'
NAME_RECORD_BASE = 0x4802A
NAME_RECORDS = 560

TABLES = [(0x0193B5, 694), (0x01DBC5, 110), (0x01E098, 35),
          (0x01E1D5, 50), (0x01E4CE, 124)]
REGIONS = [(0x019921, 0x01DBC3), (0x01DCA1, 0x01E096), (0x01E0DE, 0x01E1D3),
           (0x01E239, 0x01E4CC), (0x01E5C6, 0x01E982)]

PREFIX0 = 0xC0                       # first codepoint of the two byte codes
FIXED_N = int(os.environ.get('FIXED_N', '1'))   # one byte codes (slots 0..N-1, page 0)
FIXED0 = 0xE0 - FIXED_N                 # they sit at the top: $DC..$DF
# codepoints the engine never draws: FA/FB are the box glyph, no text uses them
NEVER_KEEP = {0xC0, 0xC1, 0xC2, 0xC3, 0xC4}
FIXED_CODES = {}                        # filled in main(): char -> code byte
CODE_BUDGET = FIXED0 - PREFIX0         # room for the two byte codes                         # $C5..$D1 -> pages
PAGES = 13
INSTRUMENT = False
SLOTS = 53                             # two independent tile pairs per glyph
SLOTS_DEFAULT = SLOTS                  # what clamp_slots() clamps down from
# --- speaker name labels ------------------------------------------------------
# A label can sit beside any message, so its glyphs cannot take part in the
# body colouring: 450 names would need 280 glyphs and blow the pool.  Labels
# get their own code pages, their own storage banks and their own two tile
# pairs, exactly like the engine's kana names had their own font tiles.
# v39 candidate: enabled by default, matching the configured release build.
# HUDFIX's call ABI, per-glyph source and in-flight queue insertion are covered
# by the complete caller test plus Mesen CPU regression, not isolated cells.
HUDFIX = os.environ.get('HUDFIX', '1') == '1'    # $00:8C91 name plate hook
ITEMSG = os.environ.get('ITEMSG', '1') == '1'    # drawer $DE item name hook
# Drawer attempts between two drawn message characters (v37).  The engine types
# at about one cell per frame on its own, which dumps a whole three line message
# in about a second and a half - unreadable (user report, 2026-09-25).  While
# the gate holds a character back the tick makes exactly one attempt per frame,
# so PACE attempts come out as PACE message ticks (not video frames).  Holding A or B bypasses the gate
# and fast-forwards at the drawer's own 3 chars per tick.
PACE = int(os.environ.get('PACE', '6'))
LABEL_GLYPHS = 2                        # a four byte record holds two glyphs
LABEL_NAME_GLYPHS = 4 if ITEMSG else 2                   # same, for a name a {E3}-{F7} slot
LABEL_NAME_SETS = 1                     # pastes into the middle of a message
LABEL_ID0 = 128                         # body ids stop at SLOTS; label ids
                                        # start here, in the same pages
# The dialogue box keeps the last rows of the previous messages on screen, so
# two labels can be visible at once.  Each label takes a pair set of its own,
# picked by the label's row (mod LABEL_SETS): rows that are close enough to be
# visible together differ by one or two, so they always land in different sets
# and an old label is never overwritten by a new one.
LABEL_SETS = 2 if ITEMSG else 3                           # the box shows two text rows, so
                                        # three sets already guarantee that
                                        # rows on screen together differ
POOL_BANK0 = 0x20
MAX_COL = 26                           # box width in cells
MAX_ROWS = 16                          # box rows before the row counter wraps
WRAP_COL = 25                          # first column that cannot hold a 2-cell glyph

# --- VRAM upload queue -------------------------------------------------------
# The engine's own flusher at $00:8385 turns variable length entries in WRAM
# $0B00 into channel 0 VRAM DMAs; its cursors are $09DD (flushed) / $09DF
# (appended) and every caller clears both afterwards, so the buffer is a 256
# byte page per flush cycle.  A CPU write to $2118 outside VBlank (which is what
# the old 8x16 build used) is silently dropped by the PPU, the queue is not.
QUEUE = 0x0B00
QUEUE_APPEND = 0x09DF
QUEUE_FLUSHED = 0x09DD
QUEUE_ROOM = 0x9AB6
GLYPH_ENTRY = 2 * (4 + 32)             # queue bytes per glyph: two tile pairs
CELL_ENTRY = 8                         # queue bytes per tile map cell
GLYPH_COST = GLYPH_ENTRY + 2 * CELL_ENTRY
ROW_WIPE = 2 * (4 + 52)                # one text row: 26 upper + 26 lower cells
ROW_WIPE_CHECK = ROW_WIPE + GLYPH_COST  # what one draw may stage in one flush
# box rows are blanked by $3E:8800, so ROW_WIPE and every wipe
# scratch byte are gone: nothing in this patch keeps state in WRAM.

# --- text state bookkeeping (WRAM $0D40-$0D4F: unchanged in a 2600 frame probe)

HOOK_DRAWER = 0x01FA30
HOOK_COPY1 = 0x01ECA7
HOOK_COPY2 = 0x01ECC5
HOOK_LOAD = 0x01EB9E                   # entry to the engine's per-line text loader
HOOK_DRIVER = 0x01EE70                 # entry to the per-frame text state machine
HOOK_A = 0x00FC79
HOOK_KEEP_BANK = 0x00FC85
HOOK_B = 0x00FC92

# colouring windows: glyphs of messages that can be on screen at the same time.
# The largest window that can still be coloured wins (see choose_windows()).
# The box is wiped at every message entry (see build_wipe()), so only one main
# script message is ever visible; list screens show several entries at once.
WIN_MAIN_MAX = 3                       # main script: message i .. i+win-1
WIN_LIST_MAX = 10                      # list tables: entry i .. i+win-1

KEEP1_EXPLICIT = {'!': 0x01, ':': 0x09, '?': 0x0C}
KEEP1 = dict(KEEP1_EXPLICIT)


def derive_keep1(texts=None, need_pairs=None):
    """Keep every character whose original font tiles are protected anyway.

    A kept character costs one byte instead of two and is drawn by the original
    font, so it also removes a Chinese glyph from the slot demand.  Characters
    that would need extra protected tiles are not worth it: two tiles are half a
    glyph slot.  The untranslated item window, the speaker names and the status
    script already protect all the kana, digits and punctuation.
    """
    by_char = {}
    for code, ch in km.CODE.items():
        if code >= 0xE0 or len(ch) != 1 or ch == ' ':
            continue
        by_char.setdefault(ch, code)
    prot = protected_tiles()
    keep = dict(KEEP1_EXPLICIT)
    added = {}
    for ch in sorted(by_char):
        if ch in keep:
            continue
        code = by_char[ch]
        if code in NEVER_KEEP:              # $C0..$C4 are prefixes now
            continue
        if km.FA[code] in prot and km.FB[code] in prot:
            added[ch] = code
    keep.update(added)
    KEEP1.clear()
    KEEP1.update(keep)
    return added


DECOR_TILES = (0x20, 0x72, 0x85, 0x86, 0x93)
# Tiles the engine re-uploads while the dialogue box is on screen: a frame
# probe showed a label's glyphs landing in 0xe6-0xed / 0xf7-0xfe and being
# erased by the next box redraw, so a label pair must not sit there.  Body
# slots may: a body glyph is re-uploaded whenever it is drawn.
#
# v39-rc3 correction: protecting more glyph tiles cannot fix bottom-edge
# drift. The cause was PACE_FRAMES aliasing the live HDMA scroll byte $03C4;
# it was masked by held A/B tests, which reset the old countdown to zero.
# Keep this glyph exclusion separate from the HDMA/pacing regression.
BOX_GFX_TILES = (0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xEB, 0xEC, 0xED,
                 0xF7, 0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE)
PROTECT_TILES = (set([0x00, 0x01]) | set(range(0x10, 0x20))
                 | set([0x1A, 0x1E]) | set(DECOR_TILES)
                 | set([0x47, 0x4A, 0x4B, 0x4D, 0x4E, 0x4F]))
# 0x47 and 0x4a-0x4f: the yes/no choice box's arrow and its two 16x16 cells
# (CHOICE_* below).  None of them is reachable through FA/FB (checked over the
# whole table) and none of them is a literal tile in the status script, so the
# only drawing code that touches them is the choice box itself.

# Tiles inside the font window that the engine draws as graphics, not as text:
# the scene background and the dialogue box frame.  Seen in the tile maps of
# every VRAM dump ($E0/$E1 in the scene rows, $F0 as the frame).
# $00:8B13..8B9C draws HP bars using E7..EF (P1/P2), F7..FF (NPCs)
# and cap F2. These are live graphics, NOT disposable dialogue glyph slots.
# The original nine NPC bitmaps are byte-identical to the player set. When
# HUDFIX is enabled, both sets use E7..EF, with their original palette bits.
HUD_BAR_TILES = frozenset(range(0xE7, 0xF0)) | {0xF2}
GFX_TILES = set((0xE0, 0xE1, 0xF0)) | HUD_BAR_TILES

# katakana code -> hiragana code with the same reading (Unicode -0x60 pairs)
_inv = {}
for _c, _ch in km.CODE.items():
    if len(_ch) == 1:
        _inv.setdefault(_ch, _c)
KANA_MAP = {}
for _ch, _c in _inv.items():
    _o = ord(_ch)
    if 0x30A1 <= _o <= 0x30F6 and chr(_o - 0x60) in _inv:
        KANA_MAP[_c] = _inv[chr(_o - 0x60)]


# v14: the HUD and the status screen keep the original katakana.  Rewriting
# them to hiragana was only ever a way to free tiles; the item window and the
# status script are drawn by the engine with the original font, so leaving them
# alone costs nothing extra -- the katakana tiles are protected instead of the
# hiragana ones, a straight swap.
#
# v19: default ON.  The old "costs 22 tile pairs" measurement was taken while
# the item window (dead code, no reference anywhere in the ROM) still had its
# katakana protected as well; with PROTECT_GROUPS=stat it is free -- measured:
# HUD_ORIG=1 gives the same 68 protected tiles, 89 free pairs, 36 slots and the
# same colouring window (main=1 list=9) as HUD_ORIG=0, and the status script is
# left byte-identical to the original, which is what the user asked for.
HUD_ORIG = os.environ.get('HUD_ORIG', '1') == '1'


def rewrite_kana(b):
    """Katakana -> hiragana for text the engine still draws with the original
    font.  Same language, same byte count, same pointer table, but 38 fewer font
    tiles have to stay reserved."""
    return bytes(KANA_MAP.get(x, x) for x in b)


def status_script_code_runs():
    """(start, end) of every code run in the status screen drawing script.

    The interpreter at $00:F971 walks blocks of [addr_lo][addr_hi][count]: with
    count < $80 the bytes are literal tile numbers, with count >= $80 they are
    font codes -- only the latter may be rewritten."""
    data = open(ORIG_ROM, 'rb').read()
    base = 0x00F9DB
    blob = data[base:base + 0x125]
    runs, y = [], 0
    while y < len(blob) and blob[y] != 0xFF:
        y += 2
        cnt = blob[y]
        y += 1
        if cnt == 0:
            continue
        n = cnt & 0x7F
        if cnt & 0x80:
            runs.append((base + y, base + y + n))
        y += n
    return runs


# Which groups of still-Japanese text keep their original font tiles reserved.
# Each group is only worth its tiles if the engine really draws it:
#   item  - the 110 item names: pointer table $03DBC3 -> strings $03DCA1, drawn
#           by $01:FC75.  An earlier build dropped this group, reasoning that
#           $01:F7CC was the drawer and that nothing references it.  Both halves
#           of that were wrong.  $01:F7CC is the status screen's own handler
#           (it pushes state, sets $212C, then calls $F8C3/$F971/$FA8B/$FBBB/
#           $FCF5); it is reached through the state dispatcher, which a search
#           for direct JSR/JMP/JSL cannot see.  The real drawer is $01:FC75,
#           called from $01:FC20..$FC54 with the three VRAM cursors $79C6/$7A06/
#           $7A46 -- the buki/uraji/kutsu rows of the status screen.  The user's
#           own screenshot shows あかのうらじ and せった, both in that table.
#           The group is left OFF for now, and that is a known defect, not a
#           decision: turning it on is measured to drop the free pair count from
#           94 to 78, which clamps SLOTS to 20 (31 with HUD_ORIG=0) while the
#           colouring needs 32.  Two independent EmuHawk probes of the built
#           v22 ROM (hw/clashwatch.lua) show the pool overwriting 18 of the 45
#           item-name tiles during ordinary play and never restoring them --
#           there is no font reload when the status screen opens; CPU $00:8775
#           is the only font-block DMA in the ROM and it runs at boot.
#           Fixing this properly needs ~2 more free tiles, or a dedicated
#           renderer path for the item names; see notes/current-state.md.
#   names - the 560 speaker-name records.  The build rewrites every one of them
#           to two byte hanzi codes, so nothing draws their kana any more and
#           reserving those tiles is pure waste.  Verified on the built ROM:
#           985 two byte codes, zero font codes left.
#   stat  - historical metadata name; labels now use a dedicated renderer.
#           Live name/condition raw tiles are protected unconditionally.
PROTECT_GROUPS = set(
    g for g in os.environ.get('PROTECT_GROUPS', 'stat').split(',') if g)


def untranslated_codes():
    """Original-font codes the engine still renders itself."""
    data = open(ORIG_ROM, 'rb').read()
    codes = set(KEEP1_EXPLICIT.values()) | set(range(0x10, 0x1A))
    if 'item' in PROTECT_GROUPS:
        for s, e in ((0x01DCA1, 0x01E096),):        # item window text
            codes |= set(b for b in (data[s:e] if HUD_ORIG else rewrite_kana(data[s:e]))
                         if 0 < b < 0xE0)
    if 'names' in PROTECT_GROUPS:
        for i in range(560):                        # speaker name records
            rec = rewrite_kana(data[0x4802A + i * 16:0x4802A + i * 16 + 4])
            for b in rec:
                if b == 0:
                    break
                if b < 0xE0:
                    codes.add(b)
    # These static status labels are now rendered by build_labeldrawer().
    # Protecting their obsolete kana wastes the HP bar's tile budget. The
    # still-live literal name/condition fields are protected below instead.
    return codes


SLOT_STRIDE = None       # entries per half of the slot table
PROTECT_CODES = None

TOKEN = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')

# cells a macro expands to (see cells_of_token)
MACRO_CELLS = {'E0': 1, 'E1': 1, 'E2': 4, 'E3': 4, 'E4': 4, 'E5': 4, 'E6': 4,
               'E7': 4, 'E8': 4, 'E9': 4, 'EA': 8, 'EB': 12, 'EC': 12,
               'ED': 12, 'EE': 12, 'EF': 5}


def snes_of_rom(off):
    return (off // 0x8000, 0x8000 + (off % 0x8000))


# ============================================================== text utilities
def units(part):
    """The rendering units of a plain text run: one entry per character."""
    return list(part)


def pieces(s):
    """Split a string into rendering units (each exactly one screen cell)."""
    out = []
    for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', s):
        if not part:
            continue
        m = TOKEN.fullmatch(part)
        if m:
            h = m.group(1)
            if len(h) & 1:
                h = '0' + h
            b = bytes.fromhex(h)
            if len(b) == 2 and b[0] == 0xF2:
                continue
            out.append(part)
        else:
            out.extend(units(part))
    return out


def ncells(s):
    """Width of a string in box cells (a Chinese glyph is two cells wide)."""
    n = 0
    for p in pieces(s):
        if TOKEN.fullmatch(p):
            n += cells_of_token(p)
        else:
            n += 2 if (p != ' ' and p not in KEEP1) else 1
    return n


def cells_of_token(tok):
    """How many cells a control token expands to.

    Measured from the engine's macro dispatch ($03:EBFC): $E0/$E1 stand for one
    character, the speaker name $E2 and the string macros $E3-$E9 copy up to four
    characters, $EA eight, the list macros $EB-$EE copy the first line of an
    entry (reserved at twelve), $EF prints a number of up to five digits.
    Newlines and page breaks are zero width.
    """
    h = TOKEN.fullmatch(tok).group(1)
    if len(h) & 1:
        h = '0' + h
    b = bytes.fromhex(h)
    if b[0] == 0xF2:                   # newline + its argument
        return 0
    return MACRO_CELLS.get('%02X' % b[0], 0)


def wrap_segments(s, max_col=MAX_COL):
    """Insert in-box line breaks so that no line is wider than the box.

    This has to run *after* align_tokens(), which re-imposes the original
    control sequence and drops tokens the translator added; the breaks added
    here are the ones that end up in the ROM.  A line is filled greedily and a
    break is never left in front of closing punctuation.
    """
    tail = '，。！？、：；）」』】'
    atoms = []
    for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', s):
        if not part:
            continue
        if TOKEN.fullmatch(part):
            atoms.append((part, cells_of_token(part)))
        else:
            for ch in units(part):
                atoms.append((ch, 1 if (ch == ' ' or ch in KEEP1) else 2))
    lines = [[]]
    breaks = ['']              # breaks[i] separates line i-1 from line i
    col = 0
    for a, w in atoms:
        if w == 0 and a.startswith('{F2'):         # existing newline / page break
            lines.append([])
            breaks.append(a)                       # keep the original break code
            col = 0
            continue
        if w and col + w > max_col:
            if a in tail and len(lines[-1]) >= 2:  # keep punctuation off the margin
                prev = lines[-1].pop()
                lines.append([prev, (a, w)])
                breaks.append('{F2F6}')
                col = prev[1] + w
            else:
                lines.append([(a, w)])
                breaks.append('{F2F6}')
                col = w
            continue
        lines[-1].append((a, w))
        col += w
    out = ''.join(a for a, _ in lines[0])
    for i in range(1, len(lines)):
        out += breaks[i] + ''.join(a for a, _ in lines[i])
    return out


def glyphs_of(s):
    """Every character of a string that will be encoded as a 2-byte Chinese code."""
    return set(ch for ch in pieces_str(s) if ch != ' ' and ch not in KEEP1)


def pieces_str(s):
    """The same split as pieces(), but tokens that carry text are dropped and
    plain characters are returned individually (tokens are never Chinese)."""
    out = []
    for p in pieces(s):
        if TOKEN.fullmatch(p):
            continue
        out.append(p)
    return out


def reflow(s):
    """Break over-long lines and merge pages that need too many rows.

    A line may not exceed the box width, and a page may not need more rows than
    the box shows at once (the box scrolls, and rows that are visible together
    must not share slots).  Line breaks are added as {F2F6}, which is exactly
    what the engine uses for an in-box newline.
    """
    lines = []
    for line in s.split('{F2F6}'):
        while ncells(line) > MAX_COL:
            ps = pieces(line)
            total = len(ps)
            best, bestcost = None, None
            for cut in range(2, total - 1):
                left, right = ps[cut - 1], ps[cut]
                cost = abs(cut - total / 2.0)
                if left in '，。！？、：；）」』】':
                    cost -= 3.0
                if right in '，。！？、：；':
                    cost -= 3.0
                if left == ' ' or right == ' ':
                    cost -= 2.0
                if bestcost is None or cost < bestcost:
                    best, bestcost = cut, cost
            assert best, (line, total)
            lines.append(''.join(ps[:best]).rstrip())
            line = ''.join(ps[best:]).lstrip()
        lines.append(line)

    pages, page = [], []
    for line in lines:
        if '{F2F4}' in line:
            parts = line.split('{F2F4}')
            for i, p in enumerate(parts):
                page.append(p)
                if i < len(parts) - 1:
                    pages.append(page)
                    page = []
        else:
            page.append(line)
    pages.append(page)

    merged = []
    for p in pages:
        while len(p) > MAX_ROWS:
            cand, bestn = None, None
            for i in range(len(p) - 1):
                n = ncells(p[i]) + ncells(p[i + 1])
                if n <= MAX_COL and (bestn is None or n > bestn):
                    cand, bestn = i, n
            if cand is None:
                break
            p = p[:cand] + [p[cand] + p[cand + 1]] + p[cand + 2:]
        merged.append(p)

    out = []
    for p in merged:
        for i, line in enumerate(p):
            out.append(line + '{F2F6}' if i < len(p) - 1 else line)
    return ''.join(out)


def choose_windows(per_table):
    """Largest colouring windows that still fit in SLOTS colours.

    The main script shows one message at a time (its rows scroll), the list
    tables show several consecutive entries at once.  Windows model "can be on
    screen together"; bigger is safer, so try the biggest that colours.
    """
    for win_main in range(WIN_MAIN_MAX, 0, -1):
        for win_list in range(WIN_LIST_MAX, 0, -1):
            windows = []
            for ti, gs in per_table.items():
                win = win_main if ti == 0 else win_list
                for i in range(len(gs)):
                    u = set()
                    for j in range(i, min(i + win, len(gs))):
                        u |= gs[j]
                    # Speaker name labels are not part of this colouring: they
                    # are drawn with their own tile pairs from their own banks
                    # (see LABEL_*), so they never share a slot with a body
                    # glyph no matter which name labels which message.
                    windows.append(u)
            if CMDWIN == 2:
                # The command window shows all five labels at once, so their
                # glyphs must not share a slot with each other.  They may share
                # with body glyphs: the game is paused while the menu is open,
                # so nothing else uploads to those slots before the menu closes.
                windows.append(set(''.join(t for _r, _c, t in MENU_LABELS)))
            widest = max(len(w) for w in windows)
            if widest > SLOTS:
                print('  skip win_main=%d win_list=%d widest=%d (SLOTS=%d)'
                      % (win_main, win_list, widest, SLOTS))
                continue
            enc = Encoder()
            try:
                enc.colour(windows)
            except ValueError as e:
                print('  colouring failed at win_main=%d win_list=%d: %s' % (win_main, win_list, e))
                continue
            return enc, windows, win_main, win_list
    raise SystemExit('no feasible colouring window')


TOKEN = re.compile(r'\{([0-9A-Fa-f]{2,4})\}')


def tokens(s):
    return [m.group(1).upper() for m in TOKEN.finditer(s)]


def align_tokens(orig_text, mine):
    """Force `mine` to carry exactly the control tokens of the original entry.

    The engine walks messages by counting $F2 bytes, and each loader copies into
    its RAM buffer until the first $F2, so the control-token sequence of every
    entry must stay byte-for-byte what the original had.  My translations
    sometimes dropped the trailing {F2F3} (or a name/number slot), so the
    original sequence wins and my prose segments are re-distributed between it.
    """
    orig_tok = tokens(orig_text)
    my_seg = re.split(r'\{[0-9A-Fa-f]{2,4}\}', mine)
    if len(my_seg) < len(orig_tok) + 1:
        my_seg = my_seg + [''] * (len(orig_tok) + 1 - len(my_seg))
    out = my_seg[0]
    for i, t in enumerate(orig_tok):
        out += '{%s}' % t + my_seg[i + 1]
    for extra in my_seg[len(orig_tok) + 1:]:
        out += extra
    return out


# ==================================================================== encoding
class Encoder:
    def __init__(self):
        self.slot = {}          # char -> slot id
        self.cell = {}          # char -> (page, id)
        self.order = []         # chars in storage order
        self.load = [0] * SLOTS

    def colour(self, windows):
        """DSATUR colouring (dynamic saturation degree first).

        Balanced slots matter because a slot is also a storage column: chars that
        share a slot must live in different pool banks, so no slot may collect
        more than PAGES glyphs.  The one byte codes own slots 0..FIXED_N-1 for
        good (their code byte says which slot), so the rest uses the others.

        Speaker-name glyphs ride in every window, so DSATUR assigns them first
        (they saturate fastest) and each keeps a private slot.
        """
        freq = {}
        wcount = {}
        wsets = list(windows)
        cw = {}                                 # char -> window indices
        for wi, w in enumerate(wsets):
            for ch in w:
                freq[ch] = freq.get(ch, 0) + 1
                wcount[ch] = wcount.get(ch, 0) + 1
                cw.setdefault(ch, []).append(wi)
        satb = {ch: set() for ch in freq}       # char -> slots banned around it
        for ch in FIXED_CODES:                  # one byte codes: private slots
            self.slot[ch] = FIXED_CODES[ch] - FIXED0
            self.load[self.slot[ch]] += 1
        # A pre-assigned slot must ban every character it can share a window
        # with, or the pool hands out that slot again and one of the two draws
        # the other's glyph.
        for w in wsets:
            pre = {self.slot[c] for c in w if c in self.slot}
            if not pre:
                continue
            for c2 in w:
                if c2 in satb and c2 not in self.slot:
                    satb[c2] |= pre
        remaining = set(freq) - set(self.slot)
        while remaining:
            ch = max(remaining,
                     key=lambda c: (len(satb[c]), wcount.get(c, 0), freq.get(c, 0)))
            banned = satb[ch]
            free = [s for s in range(SLOTS) if s not in banned
                    and self.load[s] < (CODE_ROM - POOL_ROM) // 0x8000]
            if not free:
                raise ValueError('cannot colour %r: %d blockers' % (ch, len(banned)))
            s = min(free, key=lambda x: (self.load[x], x))
            self.slot[ch] = s
            self.load[s] += 1
            remaining.discard(ch)
            for wi in cw[ch]:
                for c2 in wsets[wi]:
                    if c2 in remaining:
                        satb[c2].add(s)

    def pack_pool(self):
        """(page, id) cells: id is the slot, page spreads chars that share a slot."""
        used = [set() for _ in range(PAGES)]
        for ch in sorted(FIXED_CODES, key=lambda c: FIXED_CODES[c]):
            s = FIXED_CODES[ch] - FIXED0            # one byte codes live in page 0
            self.cell[ch] = (0, s)
            used[0].add(s)
            self.order.append(ch)
        for ch in sorted(self.slot, key=lambda c: (self.slot[c], c)):
            if ch in FIXED_CODES:
                continue
            s = self.slot[ch]
            for p in range(PAGES):
                if s not in used[p]:
                    used[p].add(s)
                    self.cell[ch] = (p, s)
                    self.order.append(ch)
                    break
            else:
                raise SystemExit('pool too small for glyph %r (slot %d)' % (ch, s))

    def encode(self, s):
        out = bytearray()
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', s):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                out += bytes.fromhex(h)
                continue
            for ch in units(part):
                if ch == ' ':
                    out.append(0x00)
                elif ch in KEEP1:
                    out.append(KEEP1[ch])
                elif ch in FIXED_CODES:
                    out.append(FIXED_CODES[ch])
                else:
                    p, i = self.cell[ch]
                    out += bytes([PREFIX0 + p, i])
        return bytes(out)

    def encode_item(self, s):
        """Item names: [ITEM_PREFIX][8x16 id] instead of the pool's two byte
        code.  They are drawn by their own renderer out of their own glyph
        table, so they take no pool slot and join no colouring window."""
        out = bytearray()
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', s):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                out += bytes.fromhex(h)
                continue
            for ch in units(part):
                if ch == ' ':
                    out.append(0x00)
                elif ch in KEEP1:
                    out.append(KEEP1[ch])
                elif ch in FIXED_CODES:
                    out.append(FIXED_CODES[ch])
                else:
                    out += bytes([ITEM_PREFIX, ITEM_CHARS[ch]])
        return bytes(out)


# ---------------------------------------------------------- command window
# The Start menu is not part of the text system.  The engine copies a fixed
# 52 byte table (26 cells x 2 rows) from ROM $01F743 to WRAM $040A, and its own
# routine at $01F95D turns each byte into a tilemap word through the FA/FB font
# tables -- FB[code] is the upper half of the cell, FA[code] the lower one.  A
# The window's labels are drawn by the routine at $03:F95D, which walks the 52
# byte table at ROM 0x01F743 (copied to WRAM $040A by script step $F718) and
# writes, for each of the 26 cells: the upper tile of cell c from FB[code], and
# the lower tile from FA[code] one tile map row below.  Both are 8 bit, so the
# glyphs have to sit inside the font window (tiles 0-255), and they have to be
# there *statically* - nothing re-uploads them while the menu is open, and the
# engine redraws the box background for the tiles it owns.  The font window is
# full, so the space comes from the speaker name labels: their tile pairs move
# outside the window (the drawer writes tile map words, so 10 bit tiles are no
# problem for it) and the freed font tiles take twelve 8x16 hanzi, written into
# the ROM font block at 0x0F8000 (VRAM $C000 is a straight 4 KB copy of it).
# v13: the command window's static hanzi need ten tile pairs inside the font
# window, and the budget is exactly full without them (68 body pairs for the 34
# colours DSATUR needs, plus 16 for the label and name sets = all 84 free
# pairs).  Putting the labels outside the font window to pay for the window is
# what caused the coloured band, so the window waits until the text is short
# enough for DSATUR to fit in fewer slots.  CMDWIN=1 builds it again for a
# future session, but only after the pair budget has room.
CMDWIN = int(os.environ.get('CMDWIN', '2'))    # 2 = the labels are drawn out of
                                               # the glyph pool (two characters
                                               # each, no resident tile pairs);
                                               # 1 = static font glyphs (single
                                               # characters); 0 = Japanese (the
                                               # old 10 resident
                                        # pairs it needs do not fit
                                        # beside the choice-box tiles
# The window's cells stay in the box's tile map after the menu is put away, and
# the map rows that end up outside the box (the strip just above it) show them:
# that is the coloured band.  Two hooks push blanking entries through the
# engine's own upload queue -- one on the menu's close step ($03:F85B), one on
# the end of a drawing sequence ($03:F700) as a fallback.  Which rows to clear
# is decided when the menu *opens*, in cmdwin_hook: the window is drawn at the
# two text rows $0391 and $0391+1, and text row k lives at map rows
# f(k) = (k & 1) ? 2k-2 : 2k+2 (from the address tables $FA8E/$FA7E), so the
# pair (2j, 2j+1) covers exactly the four map rows 4j..4j+3 -- one clean run,
# and the value 2*$0391 = 4j is stored in a byte of the queue page tail.
MENUCLOSE_SITE = 0x01F85B              # $03:F85B  the menu's close step
MENUCLOSE_SITE2 = 0x01F706             # $03:F706  end of a drawing sequence
ARM_SITE = 0x01F72E                    # $03:F72E  the menu's setup step
MENUCLOSE_STUB = 0x1F4000              # $3E:C000  blank the window's rows there
MENUCLOSE_STUB2 = 0x1F4100             # $3E:C100  the second entry point
MENUCLOSE_STUB3 = 0x1F4200             # $3E:C200  the arming stub
MENUCLOSE_STUB4 = 0x1F4300             # $3E:C300  the every-draw band wipe
BAND_SITE = 0x01FCC8                   # $03:FCC8  start of a drawing sequence
MENUPEND = 0x0BFB                      # queue page tail, past the $F9 limit
CMDWIN_ROM = 0x01F743
CMDWIN_ROW = 26
# One glyph per item, and the cells are the ones the engine's own cursor points
# at -- moving a label would move it out from under the marker.  Why one glyph
# and not two: every static glyph the window draws costs the tile pool, and the
# pool's slot count is what the colouring window is bought with.  Measured: with
# two-glyph labels the pool drops from 36 slots to 34 and the window collapses
# from main=1 list=9 to list=4 -- the same "smaller window = weaker no-two-
# glyphs-on-screen-together guarantee" trap the compressed dialogue fell into.
# At five single glyphs the window stays list=9.  Full two-glyph labels are
# possible only by drawing them out of the pool at run time (see the handoff).
# v21: the same five labels drawn out of the glyph pool instead of the font, so
# each one can be two characters.  A label glyph is a normal 16x16 pool glyph:
# its left half is the pair t/t+1 (upper/lower tile of the left cell) and its
# right half u/u+1, so two 1-byte codes per glyph put it in the window.  The
# codes' FA/FB are pointed at the slot's tiles at build time; what is missing at
# run time is the tile *data*, which a stub stages into the upload queue over
# the first few frames the menu is open (see build_menuload).  That costs no
# resident tile pair at all, which is the only way two-character labels fit.
MENU_LABELS = [                 # (row, first cell, text) - two cells per hanzi
    (0, 1, '气力'),             # きりょくをつかう
    (0, 12, '道具'),            # どうぐをつかう
    (1, 0, '装备'),             # そうびする
    (1, 11, '状态'),            # すてーたすをみる
    (1, 22, '扔掉'),            # すてる
]
# NOTE: $3E:C400 is the stale-row stub's address and the drawer JSLs it for every
# glyph it draws; putting the uploader there made the drawer jump into the menu's
# code and the game froze at the first message.  Keep clear of it.
MENU_STUB = 0x1F4600            # $3E:C600  the label uploader
MENU_TAB = 0x1F4700             # $3E:C700  its per-glyph records
MENU_LOAD = 0x0BF9              # queue page tail: 1-based glyph index, 0 = done
# The hook has to sit in bank $03 and be reached only while the menu is open:
# a stub in bank $3E that replays a JSR would call it in *its own* bank, and the
# prompt's dispatcher at $F0F8 is shared with the choice box (hooking it froze
# the game at the first prompt).  $03:F841 is called from the command window's
# own states, every frame it is open, and is 16 bytes of straight line code.
MENU_HOOK = 0x01F841            # $03:F841  called from the menu's input state

CMDWIN_LABELS = [               # (row, first cell, text) - one cell per hanzi
    (0, 1, '气'),               # きりょくをつかう
    (0, 12, '物'),              # どうぐをつかう
    (1, 0, '装'),               # そうびする
    (1, 11, '态'),              # すてーたすをみる
    (1, 22, '扔'),              # すてる
]
# Codes whose FA/FB entries we repoint at the window's static glyphs.  They
# must be codes that nothing else *draws*: the text engine treats $F0-$FF as
# control codes (the dispatch table at $03:FCA8), so a message never renders
# one as a glyph, and the window tables the engine ships never contain one
# either.  That matters: the option window copies its labels straight into the
# same 52 byte table ($03:F913) and draws them through the same FA/FB tables,
# so a code that is also a real character (the first attempt used $E4/$E6/$E8/
# $E9, which are kanji) made every choice prompt come out as our window glyphs.
# $F2 is left out: it is the terminator the option copy loop stops at.
CMDWIN_CODES = [0xF0, 0xF1, 0xF3, 0xF4, 0xF5, 0xF6, 0xF8, 0xF9, 0xFA, 0xFB,
                0xFC, 0xFD, 0xFE, 0xFF, 0xE4, 0xE6, 0xE8, 0xE9, 0xDD, 0xDE,
                0x85, 0x86, 0x88, 0x8F, 0x95, 0x9C]
# v13: the label pair sets used to live outside the font window, in the tile
# pairs 460..510.  That is where the coloured band came from: those bytes are
# read as *tile map cells* by the layers whose character base is $C000, so every
# label we drew rewrote a scene row and the row came out as coloured glyph
# fragments.  Reproduced in EmuHawk (band at frame 2592, one tile row above the
# box), pinned by zeroing VRAM $D800-$DFFF (the band vanished, the scene stayed)
# and by the fact that zeroing the map at byte $4000..$5800 also changes that
# row.  The labels are back inside the font window now and SLOTS is five lower
# to pay for it (see clamp_slots).
OUTSIDE_PAIRS = []


def cmdwin_static(rom, win_pairs):
    """Draw the command window's labels as static 8x16 glyphs.

    win_pairs are the tile pairs the label sets gave up, one per unique hanzi
    (two tiles each: the upper and lower half of the 8x16 cell).  Their bitmaps
    go into the ROM font block, twelve unused codes are pointed at them, and the
    window's cell table is rewritten.  Nothing uploads these tiles at run time --
    the font block is copied into VRAM $C000 wholesale, exactly like the glyphs
    the engine still draws itself, and these are tiles the engine never redraws.
    """
    chars = cmdwin_chars()
    if len(chars) > len(CMDWIN_CODES):
        raise SystemExit('command window needs %d codes, have %d'
                         % (len(chars), len(CMDWIN_CODES)))
    tiles = cmdwin_tiles(win_pairs)
    if len(chars) > len(tiles):
        raise SystemExit('command window needs %d glyphs, have %d tile slots'
                         % (len(chars), len(tiles)))

    code_of = {}
    for i, ch in enumerate(chars):
        up, dn = tiles[i]
        g = cnglyph.render16(ch)          # 8x16 grid of 0/1, top row first
        rom[km.FONT + up * 16:km.FONT + up * 16 + 16] = pack_8x8(g[:8])
        rom[km.FONT + dn * 16:km.FONT + dn * 16 + 16] = pack_8x8(g[8:])
        code_of[ch] = CMDWIN_CODES[i]

    fa = bytearray(rom[km.FA_OFF:km.FA_OFF + 256])
    fb = bytearray(rom[km.FB_OFF:km.FB_OFF + 256])
    for i, ch in enumerate(chars):
        up, dn = tiles[i]
        c = code_of[ch]
        fb[c] = up                        # the cell's upper tile (row R)
        fa[c] = dn                        # the cell's lower tile (row R+1)
    rom[km.FA_OFF:km.FA_OFF + 256] = bytes(fa)
    rom[km.FB_OFF:km.FB_OFF + 256] = bytes(fb)

    tbl = bytearray(CMDWIN_ROW * 2)
    for row, cell, txt in CMDWIN_LABELS:
        q = row * CMDWIN_ROW + cell
        for ch in txt:
            tbl[q] = code_of[ch]
            q += 1
    rom[CMDWIN_ROM:CMDWIN_ROM + len(tbl)] = bytes(tbl)
    print('command window: %d labels, %d hanzi in pairs %s, codes %s'
          % (len(CMDWIN_LABELS), len(chars), win_pairs[:len(chars)],
             ' '.join('%02X' % code_of[ch] for ch in chars)))
    return chars, code_of


_glyph_cache = {}


def glyph64(ch):
    """One Chinese glyph: 16x16 pixels = four 8x8 tiles, in the order the drawer
    writes them: top-left, bottom-left, top-right, bottom-right.  A "quad" slot
    t holds the whole glyph in the four consecutive tiles t..t+3, so the left
    screen cell (upper word at column c, lower word at c+32) shows TL/BL and the
    right cell (c+1, c+33) shows TR/BR."""
    if ch not in _glyph_cache:
        g = cnglyph.render16x16(ch)
        tl = [row[:8] for row in g[:8]]
        bl = [row[:8] for row in g[8:]]
        tr = [row[8:] for row in g[:8]]
        br = [row[8:] for row in g[8:]]
        _glyph_cache[ch] = pack_8x8(tl) + pack_8x8(bl) + pack_8x8(tr) + pack_8x8(br)
    return _glyph_cache[ch]


# ================================================================= code blobs
# The command window, the choice prompt and a few other prompts are not drawn
# from strings: the engine copies a fixed table of codes into $040A and renders
# it with the same font tables the text uses ($03:F95D).  Those tables sit at
# $03:F450..$03:F4F6 and their codes draw font tiles that the string scan never
# saw -- three of them (7, 175, 212) even ended up in our free tile pool, which
# is why the choice prompt came out as coloured glyph fragments.
PROMPT_TABLE = (0x01F464, 0x01F4E0)

# ---- the yes/no choice box -------------------------------------------------
# It is drawn by three script blocks, one per map row: the tables at $03:F455
# (high byte of the VRAM word address) and $03:F458 (low byte) are indexed by
# $0395, and $03:F45F/$03:F4A7 hold the block pointers for the two prompt sets
# ($0363).  Each block is [byte index into $040A][byte count][(tile, attr) ...]
# and the whole 64 byte buffer is then uploaded to its row: set 0 fills $7BA0
# (top border), $7BC0 (text) and $7BE0 (bottom).  See prev_choice.py, which
# renders the same data out of a ROM.
#
# The text row is only eight pixels tall in the original -- the kana are the
# single tiles $44/$45/$46 -- which is too small for a hanzi (8x8 是/否 is an
# unreadable blob, 16x8 is still squashed).  So the box keeps its three rows and
# the two options are drawn as 16x16 cells across the text row and the bottom
# row: upper row = (TL, TR), lower row = (BL, BR), exactly the arrangement the
# drawer uses.  The layout of the text row, left to right, is
#     cell 17  18    19 20   21  22    23 24   25  26
#          43  cursor  是      gap  cursor  否    gap  43
# cells 18 and 22 are the two cursor positions ($03:F3C3 = $7BD2/$7BD6) and the
# arrow is $03:F3C7[0] = $47, blank = $03:F3C7[1] = $49.
CHOICE_YES_TILES = (0x44, 0x45, 0x46, 0x4F)     # TL, BL, TR, BR
CHOICE_NO_TILES = (0x4A, 0x4B, 0x4D, 0x4E)
CHOICE_BLOCK_UP = 0x01F47B                      # $03:F47B: text row $7BC0
CHOICE_BLOCK_DN = 0x01F491                      # $03:F491: bottom row $7BE0
CHOICE_ROW_UP_TILES = (0x43, 0x49, 0x44, 0x46, 0x49, 0x49, 0x4A, 0x4D, 0x49, 0x43)
CHOICE_ROW_DN_TILES = (0x43, 0x49, 0x45, 0x4F, 0x49, 0x49, 0x4B, 0x4E, 0x49, 0x43)

# Tiles the (kana rewritten) prompt tables draw that our tile pool would take.
# Measured with the pool as it stands: with the kana rewrite in place only this
# one is left, so protecting it costs a single tile pair.
PROMPT_CLOBBERED = frozenset(
    int(t, 0) for t in os.environ.get('PROMPT_CLOBBERED', '209').replace(' ', '').split(',')
    if t)                        # tile 209 is the one the pool would still take.
                                 # Protecting it costs one tile pair and the
                                 # colouring needs all 34 slots (68 pairs) plus
                                 # 16 for the label/name sets: 84 = 84 exactly,
                                 # so there is nothing to pay with.  Shorten the
                                 # widest messages until DSATUR fits in 33 slots
                                 # and this comes back.


def prompt_table_tiles():
    """The font tiles the fixed prompt tables draw.

    These tables are not text.  Each entry is a tiny drawing script -
    [VRAM word address 2][byte count 1][data] - and the data is a run of
    (tile number, attribute $24) pairs, because the choice window copies those
    cells straight into its own map instead of re-rendering anything.  So the
    *tile numbers* are what has to stay intact, and they are plain bytes here,
    not codes: reading the region through FA/FB (which is what this did) pro-
    tects the wrong tiles and leaves the choice window drawing fragments of our
    hanzi.  The freeze hw/kunio_cn_v16.001_vram.bin is the evidence - it shows
    tiles 65..70, 73, 76, 83 and 244 overwritten while the build believed it had
    paid for the window.

    Which bytes are tile numbers and which are not is settled by the freeze
    hw/kunio_cn_v16.001_vram.bin, taken with the choice window on screen: the
    tiles it shows overwritten are 65,66,67,68,69,70,73,76,83 - all of them the
    table's bytes in 0x40..0x5f.  The remaining bytes are the run addresses
    (e.g. $22F4, $1422, $F4AD) and the attribute words ($24, $64, $20, $2c,
    $12, $14), none of which are drawn as glyphs.  Protecting the whole region
    instead costs 19 tiles rather than 9, and that is the difference between the
    command window fitting in the tile budget and not.
    """
    data = open(ORIG_ROM, 'rb').read()
    return set(b for b in data[PROMPT_TABLE[0]:PROMPT_TABLE[1]]
               if 0x40 <= b <= 0x5F)


def prompt_tiles():
    """Prompt tiles our tile pool would take, i.e. the ones that must be kept."""
    return set(t for t in prompt_table_tiles() if t in PROMPT_CLOBBERED)


def protected_tiles():
    global PROTECT_CODES
    if PROTECT_CODES is None:
        PROTECT_CODES = untranslated_codes()
    res = set(PROTECT_TILES) | set(GFX_TILES) | prompt_tiles()
    if not HUDFIX:  # also works after load_build_params changes the switch
        res.update(range(0xF7, 0x100))
    # $01:FBBB reads these fields as tile IDs, not dialogue character codes.
    res |= set(open(ORIG_ROM, 'rb').read()[0xFC55:0xFC75])
    for c in PROTECT_CODES:
        res.add(km.FA[c])
        res.add(km.FB[c])
    for c in KEEP1.values():
        res.add(km.FA[c])
        res.add(km.FB[c])
    return res


# --------------------------------------------------------- status screen labels
# The 16 label blocks in the script at $01:F9DB are drawn by the interpreter at
# $01:F971, which names tiles through FA/FB and uploads nothing -- so they only
# render while the font block still holds their kana, and the glyph pool
# overwrites those tiles during ordinary play (the same defect the item names
# had; see hw/clashwatch.lua).  They are static text, so the fix is the command
# window's: bake 8x16 hanzi into font tiles the engine never redraws, point the
# script's own codes at them, and rewrite the blocks.  The script's 33 codes are
# drawn by nothing else -- that is exactly what the `stat` group protected -- so
# repointing them is safe, and the group can go.
#
# Chinese is shorter than the kana, so every block shrinks and the script still
# fits its 175 bytes with room to spare.  The map is refilled by $01:F8C3 before
# the script runs, so the cells a shorter label no longer reaches are blank, not
# stale.
STATUS_LABELS = {
    0x7889: None,               # the name field: ー plus blanks, then $FBBB
    0x78C9: '等级:',
    0x7902: '最大体力:',
    0x7942: '最大气力 :',
    0x7982: '经验:',
    0x79C2: '武器 :',
    0x7A02: '衬里:',
    0x7A42: '鞋  :',
    0x7892: '状态  :',
    0x78D2: '体力  :',
    0x7912: '气力  :',
    0x7952: '力    :',
    0x7992: '敏捷  :',
    0x79D2: '攻击力:',
    0x7A12: '防御力 :',
    0x7A52: '运气  :',
}
STATUS_SCRIPT = 0x00F9DB
STATUS_SCRIPT_END = 0x00FA8A      # sub $FA8B starts here: the script is 175 B
STATUS_LABEL_HANZI = {}           # hanzi -> script code, filled in main()
STATUS_LABEL_SLOT = {}            # script code -> pool slot
STATUS_LITERAL_TILES = set()      # tiles the script's literal blocks draw
LITERAL_TILES_RESTORE = []        # of those, the ones a pool slot sits on
LITERAL_TILE_MOVE = {}            # old literal tile -> the idle tile it moved to
STATUS_FIRST_TEXT = 0             # the script's first text block's address
STATUS_SLOT_BASE = 0              # labels take slots 0..n-1
ITEM_SLOT_BASE0 = 24              # the item values start above them
ITEM_SLOT_SPAN = 4                # slots per value (longest name: 4)
                                  # 23 label slots + 3 * 4 = 35 <= SLOTS
STATUS_SLOT_TABLE = 0x1F4B00      # $3E:CB00  code -> slot, $FF = not a label
# The label's 8x16 glyph id lives here, NOT in FA.  Every code the status script
# names is also a KEEP1 code, and KEEP1 exists precisely so those codes keep
# pointing at the original kana tiles through FA -- writing the glyph id into FA
# left the kana (く/に/り/き in the speaker names) pointing at tiles 0..22, which
# the glyph pool then overwrote: the battle HUD's name plate came out blank or
# as hanzi fragments.  A table of its own keeps the two uses apart.
STATUS_LABEL_ID_TABLE = 0x1F4F00  # $3E:CF00  code -> 8x16 glyph id
LITERALFIX_ROM = 0x1F4E00          # $3e:ce00
LITERAL_HOOK = 0x00F976            # cpu $01:f976, SEP #$30 / LDY #$00
# The status screen needs STATUS_SLOT_COUNT + 3 * ITEM_SLOT_SPAN slots on
# screen at once -- 23 + 15 = 38 -- and the text needs its own window
# (list=9).  Both come out of the same pool because they never share a
# screen, so SLOTS must clear 38.
STATUS_SLOT_COUNT = 0


def status_label_hanzi():
    """The labels' distinct hanzi, in the order the blocks draw them."""
    blocks, _used = status_script_blocks()
    out = []
    for vmadd, _c, _kind, _vals, _o in blocks:
        cn = STATUS_LABELS.get(vmadd)
        if cn is None:
            continue
        for ch in cn:
            if ch not in (' ', ':') and ch not in out:
                out.append(ch)
    return out


def status_literal_tiles():
    """Tiles the script's literal-tile blocks name.

    Those blocks are not font codes -- the interpreter writes the byte straight
    into the tile map -- so the label hook never sees them, and nothing else
    keeps the pool off them.  Two of them (the -- STATUS -- row's glyphs) were
    slot 8's tiles, so a hanzi uploaded into slot 8 landed on top of them and the
    row came out as gibberish.  Protect them like any other drawn tile.
    """
    blocks, _used = status_script_blocks()
    out = set()
    for _vm, _c, kind, vals, _o in blocks:
        if kind == 'tiles':
            out.update(vals)
    out.discard(0x00)                  # the blank tile is protected anyway
    return out


def status_script_blocks():
    """(vram addr, count byte, kind, values, offset) per block, in order."""
    data = open(ORIG_ROM, 'rb').read()
    blob = data[STATUS_SCRIPT:STATUS_SCRIPT_END]
    out, y = [], 0
    while y < len(blob) and blob[y] != 0xFF:
        vmadd = blob[y] | (blob[y + 1] << 8)
        cnt = blob[y + 2]
        y += 3
        if cnt == 0:
            out.append((vmadd, 0, 'empty', [], y))
            continue
        n = cnt & 0x7F
        vals = list(blob[y:y + n])
        y += n
        out.append((vmadd, cnt, 'text' if cnt & 0x80 else 'tiles', vals, y))
    return out, y


def status_label_slot_list(n):
    """n pool slots whose tiles the script's literal blocks do not draw.

    The -- STATUS -- row is written as raw tile numbers, so the label hook never
    sees it and nothing keeps the pool off its tiles: slot 8's tiles were two of
    that row's glyphs, and a hanzi uploaded into slot 8 landed on top of them --
    the row came out as gibberish.  Protecting those tiles instead costs five
    tiles and drops the colouring window from list=9 to list=4, which is not
    worth it: the status screen needs 23 label slots plus 12 for the item values
    and the pool has 36, so simply skipping the colliding slots is free.
    """
    lo, hi, _np, _win = build_slotpairs()
    bad = set()
    for s_ in range(len(lo)):
        t = lo[s_] | (hi[s_] << 8)
        if t in STATUS_LITERAL_TILES or t + 1 in STATUS_LITERAL_TILES:
            bad.add(s_)
    out = [s_ for s_ in range(len(lo)) if s_ not in bad]
    if len(out) < n + 3 * ITEM_SLOT_SPAN:
        raise SystemExit('only %d usable slots for %d labels + %d item values'
                         % (len(out), n, 3 * ITEM_SLOT_SPAN))
    if out[n - 1] >= ITEM_SLOT_BASE0:
        raise SystemExit('label slot %d reaches the item base %d'
                         % (out[n - 1], ITEM_SLOT_BASE0))
    return out[:n]


def status_labels(rom, glyph_of):
    """Point the labels' codes at 8x16 glyphs and rewrite the script's blocks.

    glyph_of gives each hanzi its id in the shared 8x16 table.  The labels take
    no font tile: the hook at $01:F9BC uploads the glyph into a pool slot the
    code names, exactly as the item names do, and the status screen has no
    dialogue text on it, so those slots are free to be the pool's own.  That
    keeps the whole change off the tile budget -- baking the glyphs into the
    font instead costs 23 tile pairs, which collapses the colouring window from
    list=9 to list=4 and would let list screens corrupt each other.
    """
    blocks, used = status_script_blocks()
    # The -- STATUS -- row is the script's only literal tile block: the
    # interpreter writes those tile numbers straight into the map, so no font
    # code names them and the pool has no idea they are on screen.  Four of the
    # row's glyphs sit on tiles the pool can reach, and the hanzi a dialogue
    # left in them is what made the row read as gibberish -- the defect that
    # survived v28.  Protecting those tiles is not worth its price: free_pairs()
    # pairs greedily, so pulling four tiles out of an unbroken run of pairs
    # costs far more than four pairs and collapses the colouring window from
    # list=9 to list=4.  The row moves instead.  Each colliding glyph is copied
    # into a free tile the pool can never pair up -- both its neighbours are
    # protected, so the 32 byte half-glyph DMA can never start there; these are
    # the same idle tiles the single-character command labels used -- and the
    # script is rewritten to name them.  Nothing is uploaded at run time, so
    # there is no timing left to get wrong.
    pool_reach = set()
    for _t in free_pairs():
        pool_reach.add(_t)
        pool_reach.add(_t + 1)
    idle = cmdwin_singles()
    for _t in sorted(STATUS_LITERAL_TILES):
        if _t not in pool_reach or _t in LITERAL_TILE_MOVE:
            continue
        if not idle:
            raise SystemExit('no idle tile left to move the -- STATUS -- row to')
        LITERAL_TILE_MOVE[_t] = idle.pop(0)
    for _src, _dst in LITERAL_TILE_MOVE.items():
        rom[km.FONT + _dst * 16:km.FONT + _dst * 16 + 16] = \
            bytes(rom[km.FONT + _src * 16:km.FONT + _src * 16 + 16])
    codes = sorted(set(c for _v, _c, k, vals, _o in blocks if k == 'text'
                       for c in vals) - {0x00, 0x09, 0x1D})
    hanzi = status_label_hanzi()
    if len(hanzi) > len(codes):
        raise SystemExit('status labels need %d codes, the script has %d'
                         % (len(hanzi), len(codes)))
    global STATUS_SLOT_COUNT
    slots = status_label_slot_list(len(hanzi))
    for i, ch in enumerate(hanzi):
        STATUS_LABEL_HANZI[ch] = codes[i]
        STATUS_LABEL_SLOT[codes[i]] = slots[i]
    STATUS_SLOT_COUNT = len(hanzi)
    # The 8x16 glyph id goes in its own table, and FA/FB are left alone: these
    # codes are all KEEP1 codes too, so FA has to keep naming the original kana
    # tiles (see STATUS_LABEL_ID_TABLE).
    ids = bytearray([0xFF]) * 256
    for ch, c in STATUS_LABEL_HANZI.items():
        ids[c] = glyph_of[ch]
    rom[STATUS_LABEL_ID_TABLE:STATUS_LABEL_ID_TABLE + 256] = bytes(ids)
    tab = bytearray([0xFF]) * 256
    for c, sl in STATUS_LABEL_SLOT.items():
        tab[c] = sl
    rom[STATUS_SLOT_TABLE:STATUS_SLOT_TABLE + 256] = bytes(tab)
    out = bytearray()
    for vmadd, cnt, kind, vals, _o in blocks:
        cn = STATUS_LABELS.get(vmadd)
        if kind != 'text' or cn is None:
            if kind == 'tiles':
                vals = [LITERAL_TILE_MOVE.get(v, v) for v in vals]
            out += bytes([vmadd & 0xFF, vmadd >> 8, cnt])
            out += bytes(vals)
            continue
        enc = []
        for ch in cn:
            if ch == ' ':
                enc.append(0x00)
            elif ch == ':':
                enc.append(0x09)
            else:
                enc.append(STATUS_LABEL_HANZI[ch])
        assert len(enc) < 0x80, (hex(vmadd), len(enc))
        out += bytes([vmadd & 0xFF, vmadd >> 8, 0x80 | len(enc)])
        out += bytes(enc)
    if len(out) + 1 > STATUS_SCRIPT_END - STATUS_SCRIPT:
        raise SystemExit('status script grew to %d bytes, the region is %d'
                         % (len(out) + 1, STATUS_SCRIPT_END - STATUS_SCRIPT))
    rom[STATUS_SCRIPT:STATUS_SCRIPT + len(out)] = bytes(out)
    # The interpreter stops on a block whose ADDR_HI is $FF ($F97A reads
    # $F9DC,Y, one past the block's first byte), so the sentinel has to sit
    # at offset len(out)+1, not len(out).
    rom[STATUS_SCRIPT + len(out)] = 0x00
    rom[STATUS_SCRIPT + len(out) + 1] = 0xFF
    for i in range(STATUS_SCRIPT + len(out) + 2, STATUS_SCRIPT_END):
        rom[i] = 0x00
    print('status labels: %d hanzi in slots %s, script %d -> %d bytes'
          % (len(hanzi), sorted(STATUS_LABEL_SLOT.values()), used, len(out) + 1))
    print('  literal tiles to restore: %s (first text block $%04X)'
          % (sorted('%02X' % t for t in LITERAL_TILES_RESTORE), STATUS_FIRST_TEXT))
    if LITERAL_TILE_MOVE:
        print('  -- STATUS -- row moved off the pool: %s'
              % ' '.join('%02X->%02X' % (a, b)
                         for a, b in sorted(LITERAL_TILE_MOVE.items())))
    else:
        print('  -- STATUS -- row already clear of the pool')
    return len(hanzi)


def choice_box(rom):
    """Draw 是 / 否 into the yes/no choice box.

    The box draws the font block's tiles, not our pool's, so the glyphs are
    baked into the font (the way cmdwin_static does for the command window) and
    the two drawing scripts are rewritten to name them.  Ink is colour 1 on a
    colour 2 background -- the convention the kana they replace used -- so a
    glyph sits on the box's fill tile ($49, solid colour 2) without a seam.
    """
    for tiles, ch in ((CHOICE_YES_TILES, '是'), (CHOICE_NO_TILES, '否')):
        g = [[1 if v else 2 for v in row] for row in cnglyph.render16x16(ch)]
        quads = ([row[:8] for row in g[:8]], [row[:8] for row in g[8:]],
                 [row[8:] for row in g[:8]], [row[8:] for row in g[8:]])
        for t, q in zip(tiles, quads):
            rom[km.FONT + t * 16:km.FONT + t * 16 + 16] = pack_8x8(q)
    for off, tiles in ((CHOICE_BLOCK_UP, CHOICE_ROW_UP_TILES),
                       (CHOICE_BLOCK_DN, CHOICE_ROW_DN_TILES)):
        data = bytearray(rom[off:off + 22])
        assert data[0] == 0x22 and data[1] == 0x14, data[:2].hex()
        assert data[2 + 2 * len(tiles) - 1] == 0x64, data[2 + 2 * len(tiles) - 1]
        for i, t in enumerate(tiles):
            data[2 + 2 * i] = t            # attributes (the corner flips) stay
        rom[off:off + 22] = bytes(data)
    print('choice box: 是 in tiles %s, 否 in %s'
          % (' '.join('%02X' % t for t in CHOICE_YES_TILES),
             ' '.join('%02X' % t for t in CHOICE_NO_TILES)))


def cmdwin_chars():
    """The command window's label glyphs, in the order they are assigned."""
    out = []
    for _r, _c, txt in CMDWIN_LABELS:
        for ch in txt:
            if ch not in out:
                out.append(ch)
    return out


def cmdwin_singles():
    """Free tiles that can never join a pair, for the window's static glyphs.

    The glyph pool uploads a glyph half as one 32 byte DMA, so it can only use
    consecutive tiles; a free tile whose two neighbours are both protected is
    unusable to it and sits idle.  The command window's static glyphs are not
    uploaded at run time at all (the font block is copied into VRAM wholesale)
    and the window names each half cell's tile independently, so those singles
    cost nothing.  The fixed prompts' tiles are skipped -- the choice box names
    them directly -- as are the top codes, which the engine's own tables use.
    """
    res = protected_tiles()
    box = set(range(0x41, 0x50)) | {0x53}
    used = set()
    for t in free_pairs():                # free_pairs() pairs greedily, so this
        used.add(t)                       # is exactly what the pool can reach
        used.add(t + 1)
    return [t for t in range(0x20, 0x100)
            if t not in res and t not in used and t not in box]


def cmdwin_pairs():
    """Tile pairs the command window's static glyphs still need (one per hanzi).

    Glyphs that fit in an unpaired tile need no pair at all, which is what keeps
    the pool's slot count high enough for the colouring to close: at ten pairs
    the pool is left with 31 slots and one glyph needs 32.
    """
    if CMDWIN == 1:
        # static font glyphs: one tile pair per glyph the unpaired tiles cannot
        # hold
        return max(0, len(cmdwin_chars()) - len(cmdwin_singles()) // 2)
    return 0                           # off, or the pool route (takes no pairs)


def cmdwin_tiles(win_pairs):
    """(upper, lower) font tile per label glyph: singles first, then the pairs."""
    singles = cmdwin_singles()
    n_single = min(len(cmdwin_chars()), len(singles) // 2)
    out = [(singles[2 * i], singles[2 * i + 1]) for i in range(n_single)]
    for j in range(len(cmdwin_chars()) - n_single):
        out.append((win_pairs[j], win_pairs[j] + 1))
    return out


def cmdwin_pool(rom, enc, entries):
    """Point the window's label cells at glyph-pool slots.

    Two 1-byte codes per glyph: the left cell shows the slot's t/t+1 pair (upper
    and lower half of the 8x16 cell) and the right cell its u/u+1 pair, exactly
    how the drawer lays a 16x16 glyph out.  The window's own draw loop reads
    FA/FB as always, so nothing about the drawing changes -- only the tiles it
    names, and those tiles are loaded at run time by build_menuload().

    Returns (chars, table) where table is the uploader's per-glyph record:
    [vram word addr of t][vram word addr of u][pool address][pool bank].
    """
    chars = []
    for _r, _c, txt in MENU_LABELS:
        for ch in txt:
            if ch not in chars:
                chars.append(ch)
    if len(chars) * 2 > len(CMDWIN_CODES):
        raise SystemExit('menu needs %d codes, have %d'
                         % (len(chars) * 2, len(CMDWIN_CODES)))
    fa = bytearray(rom[km.FA_OFF:km.FA_OFF + 256])
    fb = bytearray(rom[km.FB_OFF:km.FB_OFF + 256])
    table = bytearray()
    for i, ch in enumerate(chars):
        if ch not in enc.slot:
            raise SystemExit('menu glyph %r never made it into the pool' % ch)
        s = enc.slot[ch]
        t = entries[s]
        u = entries[SLOTS + s]
        x, y = CMDWIN_CODES[2 * i], CMDWIN_CODES[2 * i + 1]
        fb[x], fa[x] = t, t + 1
        fb[y], fa[y] = u, u + 1
        page = enc.cell[ch][0]
        src = POOL_ROM + page * 0x8000 + s * POOL_STRIDE
        addr = 0x8000 + (src & 0x7FFF)          # the pool never straddles a bank
        table += bytes([(0x6000 + t * 8) & 0xFF, (0x6000 + t * 8) >> 8,
                        (0x6000 + u * 8) & 0xFF, (0x6000 + u * 8) >> 8,
                        addr & 0xFF, addr >> 8, src >> 15])
    rom[km.FA_OFF:km.FA_OFF + 256] = bytes(fa)
    rom[km.FB_OFF:km.FB_OFF + 256] = bytes(fb)
    tbl = bytearray(CMDWIN_ROW * 2)
    for row, cell, txt in MENU_LABELS:
        q = row * CMDWIN_ROW + cell
        for ch in txt:
            i = chars.index(ch)
            tbl[q] = CMDWIN_CODES[2 * i]
            tbl[q + 1] = CMDWIN_CODES[2 * i + 1]
            q += 2
    rom[CMDWIN_ROM:CMDWIN_ROM + len(tbl)] = bytes(tbl)
    print('command window: %d labels, %d glyphs from the pool, codes %s'
          % (len(MENU_LABELS), len(chars),
             ' '.join('%02X' % c for c in CMDWIN_CODES[:2 * len(chars)])))
    return chars, table


def load_build_params(path=None):
    """Re-apply the settings a built ROM was made with.

    The verifiers recompute the slot table and the protected set from this
    module, so they must run with the same switches the ROM was built with.
    Two of them are not literals in the source any more: PROMPT_CLOBBERED is a
    fixed point the build searches for, and SLOTS is whatever the tile budget
    allowed.  Both are recorded in cn_build_params.json next to the ROM.
    """
    global PROMPT_CLOBBERED, PROTECT_GROUPS, PROTECT_CODES, SLOTS
    global STALEROW_ON, CMDWIN, HUD_ORIG, HUDFIX, ITEMSG, PACE, PACE_FRAMES
    global LABEL_SETS, LABEL_NAME_GLYPHS, POOL_ROM, POOL_BANK0
    par = json.load(open(path or (BASE + '/cn_build_params.json'), encoding='utf-8'))
    POOL_ROM = par.get('pool_rom', 0x108000)
    POOL_BANK0 = par.get('pool_bank0', 0x21)
    HUDFIX = par.get('hudfix', HUDFIX)
    ITEMSG = par.get('itemsg', ITEMSG)
    PACE = par.get('pace', PACE)
    PACE_FRAMES = par.get('pace_counter', 0x03C4)  # legacy metadata only
    LABEL_SETS = par.get('label_sets', 2 if ITEMSG else 3)
    LABEL_NAME_GLYPHS = par.get('label_name_glyphs', 4 if ITEMSG else 2)
    if 'stalerow' in par:
        STALEROW_ON = par['stalerow']
    if 'cmdwin' in par:
        CMDWIN = int(par['cmdwin'])
    if 'hud_orig' in par:
        HUD_ORIG = par['hud_orig']
    if 'prompt_clobbered' in par:
        PROMPT_CLOBBERED = frozenset(par['prompt_clobbered'])
    if 'protect_groups' in par:
        PROTECT_GROUPS = set(par['protect_groups'])
    if 'slots' in par:
        SLOTS = par['slots']
    PROTECT_CODES = None
    return par


def fix_prompt_tiles(max_iter=12):
    """Reserve every prompt-table tile the drawer's pool would otherwise take.

    The choice window and the other fixed prompts are drawn by the engine from
    the font block, not by our drawer, so any tile the drawer uploads a hanzi
    into loses the glyph the prompt needs - that is the one garbled cell that
    survived v13.  Which tiles the pool takes depends on the protected set
    (protecting one tile shrinks the pool and can move another prompt tile out
    of it), so iterate to a fixed point.  Free pairs are not enough to decide
    this: the pool only uses as many pairs as the slots and label sets need, so
    the test has to be run against the real slot table.
    """
    global PROMPT_CLOBBERED, PROTECT_CODES, SLOTS
    need = prompt_table_tiles()
    prot = set(PROMPT_CLOBBERED)
    for _ in range(max_iter):
        PROMPT_CLOBBERED = frozenset(prot)
        PROTECT_CODES = None
        SLOTS = SLOTS_DEFAULT
        clamp_slots()
        lo, hi, _npairs, _win = build_slotpairs()
        pool = set()
        for i in range(len(lo)):
            base = lo[i] | (hi[i] << 8)
            pool.add(base)
            pool.add(base + 1)
        for base in hud_pairs():
            pool.update((base, base + 1))
        bad = need & pool
        if not bad:
            return sorted(prot)
        prot |= bad
    raise SystemExit('the prompt tiles never settle: %s' % sorted(prot))


def clamp_slots():
    """How many body slots the free tile pairs can actually hold.

    The label pair sets and the command window's static glyphs take the top of
    the free list; the box background tiles are protected now, so every free
    pair left is one the engine never redraws and a label keeps its glyphs for
    as long as its row is visible.
    """
    global SLOTS
    SLOTS = min(SLOTS, (len(free_pairs())
                        - 2 * (LABEL_GLYPHS * LABEL_SETS
                               + LABEL_NAME_GLYPHS * LABEL_NAME_SETS)
                        - cmdwin_pairs()) // 2)
    if os.environ.get('SLOTS_FORCE'):          # measurement only
        SLOTS = int(os.environ['SLOTS_FORCE'])
    return SLOTS


HUDPAIR_ROM = 0x1F0780  # private tables, outside both message slot tables

def hud_pairs():
    """Reserve combat glyphs permanently, separate from all message writers.

    Original kana player names use protected static tiles. Only the two enemy
    plates need Chinese: four 16x16 glyphs. Translating player HUD names must
    instead budget eight glyphs. Upper/lower plates share column indices ONLY
    in the original-player-name build, never between the two enemy plates.
    """
    if not HUDFIX:
        return []
    count = 4 if HUD_ORIG else 8
    safe = [t for t in _available_pairs()
            if t not in BOX_GFX_TILES and t + 1 not in BOX_GFX_TILES]
    assert len(safe) >= count * 2, 'not enough reserved HUD pairs'
    tail = safe[-count * 2:]
    return tail[::2] + tail[1::2]

def free_pairs():
    held = set(hud_pairs())
    return [t for t in _available_pairs() if t not in held]


def build_slotpairs():
    """Slot table: two bytes per slot = two free tile pairs.

    Each slot stores two base tiles: the glyph's left half is the pair t/t+1 and
    its right half u/u+1, where t and u come from free_pairs().  Two independent
    pairs instead of one four-aligned quad is what makes the slot count
    comfortable (a quad would need four consecutive free tiles).

    The last LABEL_GLYPHS * LABEL_SETS entries are the speaker-name label pairs
    and the last LABEL_NAME_GLYPHS * LABEL_NAME_SETS ones the runtime name pairs,
    so the drawer finds a label's right half at the same offset it uses for a
    slot's.

    The label sets give up their font tiles: those tiles hold the command
    window's static glyphs (cmdwin_static) and the labels themselves move to
    OUTSIDE_PAIRS, outside the font window.  A label is resident, so it must sit
    where the engine never redraws - which is exactly what the tiles out there
    are (measured byte by byte: never written in 16000 frames), while inside the
    window every tile is either drawn as text or redrawn as box background.
    Returns (low bytes of every entry, their high bytes, pair count, the freed
    pairs that now hold the window glyphs).
    """
    pairs = free_pairs()
    global SLOT_STRIDE
    n = (SLOTS + LABEL_GLYPHS * LABEL_SETS
         + LABEL_NAME_GLYPHS * LABEL_NAME_SETS)
    SLOT_STRIDE = n
    if len(pairs) < 2 * n:
        raise SystemExit('only %d free tile pairs, need %d for %d slots + %d '
                         'label pair sets + %d name pair sets'
                         % (len(pairs), 2 * n, SLOTS, LABEL_SETS, LABEL_NAME_SETS))
    # The label pair sets take the safest pairs - the tail of the free list once
    # the box background tiles are left out - and the body slots take the rest.
    # A body glyph is re-uploaded every time it is drawn, so it can live on a
    # pair the engine redraws; a label is drawn once and must not.
    need = 2 * (LABEL_GLYPHS * LABEL_SETS + LABEL_NAME_GLYPHS * LABEL_NAME_SETS)
    n_win = cmdwin_pairs()
    safe = [t for t in pairs if t not in BOX_GFX_TILES and t + 1 not in BOX_GFX_TILES]
    if len(safe) < need + n_win:
        raise SystemExit('only %d pairs free of the box graphics, need %d + %d'
                         % (len(safe), need, n_win))
    # Everything stays inside the font window.  Tiles out there are read as tile
    # map cells by the layers whose character base is $C000, so a resident glyph
    # written to them turns a scene row into coloured glyph fragments - that was
    # the band (see the notes in OUTSIDE_PAIRS' place above).
    lab = safe[-(need + n_win):]
    win = lab[:n_win]                    # -> the command window's static glyphs
    lab = lab[n_win:]                    # -> the label and name pair sets
    body = [t for t in pairs if t not in lab and t not in win]
    if len(body) < 2 * SLOTS:
        raise SystemExit('only %d body pairs, need %d' % (len(body), 2 * SLOTS))
    left = bytes(t & 0xFF for t in body[0:2 * SLOTS:2] + lab[0:need:2])
    right = bytes(t & 0xFF for t in body[1:2 * SLOTS:2] + lab[1:need:2])
    entries = left + right
    # High byte of every entry's tile.  The label entries are the only tiles
    # above 255 (the drawer ORs this into the tile map word); every other entry
    # stays 0, so those cells come out exactly as the old 8 bit table made them.
    hi = bytearray(len(entries))
    n_ent = SLOTS + LABEL_GLYPHS * LABEL_SETS + LABEL_NAME_GLYPHS * LABEL_NAME_SETS
    for k, t in enumerate(lab[0:need:2]):
        hi[SLOTS + k] = t >> 8
    for k, t in enumerate(lab[1:need:2]):
        hi[n_ent + SLOTS + k] = t >> 8
    assert all(v in (0, 1) for v in hi), sorted(set(hi))
    assert (not CMDWIN) or len(win) == cmdwin_pairs()
    return entries, bytes(hi), len(pairs), win


def free_quads():
    """4-aligned groups of four consecutive tiles, none of them protected."""
    res = protected_tiles()
    return [t for t in range(0, 256, 4) if not any((t + i) in res for i in range(4))]


def status_label_tiles(n):
    """n tile pairs for the baked status labels.

    They are static -- nothing re-uploads them -- so they have to sit where the
    engine never redraws: the tail of the free list, the same pool the speaker
    name label sets take from, and clear of the box graphics the engine
    repaints.  Reserving them here (rather than in PROTECT_TILES) keeps the
    choice inside the build, where free_pairs() can see it.
    """
    pairs = free_pairs()
    paired = set()
    for t in pairs:
        paired.add(t)
        paired.add(t + 1)
    prot = protected_tiles()
    # singles first: a tile no pair can reach costs the pool nothing
    singles = [t for t in range(0x20, 0x100)
               if t not in prot and t not in STATUS_LABEL_PROTECT
               and t not in paired and t not in BOX_GFX_TILES]
    safe = [t for t in pairs
            if t not in BOX_GFX_TILES and t + 1 not in BOX_GFX_TILES]
    tiles, si = [], 0
    for t in singles:
        if len(tiles) >= 2 * n:
            break
        tiles.append(t)
    for t in safe:
        if len(tiles) >= 2 * n:
            break
        if t in STATUS_LABEL_PROTECT or t + 1 in STATUS_LABEL_PROTECT:
            continue
        if t in tiles or t + 1 in tiles:
            continue
        tiles += [t, t + 1]
    if len(tiles) < 2 * n:
        raise SystemExit('status labels need %d tiles, only %d are free'
                         % (2 * n, len(tiles)))
    tiles = tiles[:2 * n]
    STATUS_LABEL_PROTECT.update(tiles)
    return [(tiles[2 * i], tiles[2 * i + 1]) for i in range(n)]


def _available_pairs():
    """Base tiles t whose successor t+1 is free too.

    A glyph half is uploaded by one 32 byte DMA, so its two tiles have to be
    consecutive; they no longer have to be even aligned, which recovers a good
    part of the tiles the untranslated Japanese needs.  Pairs never overlap."""
    res = protected_tiles()
    fs = set(t for t in range(256) if t not in res)
    used, out = set(), []
    for t in range(256):
        if t in fs and (t + 1) in fs and t not in used and (t + 1) not in used:
            out.append(t)
            used.add(t)
            used.add(t + 1)
    return out


def build_preload():
    b = bytearray([
        0xBF, 0xC3, 0xDB, 0x03,      # LDA $03DBC3,X
        0x85, 0x22,                  # STA $22
        0xBF, 0xC4, 0xDB, 0x03,      # LDA $03DBC4,X
        0x85, 0x23,                  # STA $23
        0xE2, 0x30,                  # SEP #$30
        0xA9, 0x03,                  # LDA #$03
        0x85, 0x24,                  # STA $24
    ])
    bk, ad = snes_of_rom(0x00FC89)
    b += bytes([0x5C, ad & 0xFF, ad >> 8, bk])
    return bytes(b)


def scratch_hits(code):
    """Absolute accesses inside the game's live workspace $0d40-$0d5f."""
    absops = {0xAD: 'lda', 0x8D: 'sta', 0x9C: 'stz', 0xBD: 'lda,x', 0x9D: 'sta,x',
              0xB9: 'lda,y', 0x99: 'sta,y', 0xCD: 'cmp', 0xEE: 'inc', 0xCE: 'dec',
              0xCC: 'cpy', 0xEC: 'cpx', 0x2C: 'bit', 0x2E: 'rol', 0x4E: 'lsr',
              0x0C: 'tsb', 0x1C: 'trb', 0x0E: 'asl', 0x6E: 'ror'}
    hits = []
    for i in range(len(code) - 2):
        op = code[i]
        if op in absops:
            addr = code[i + 1] | (code[i + 2] << 8)
            if 0x0D40 <= addr <= 0x0D5F:
                hits.append((i, absops[op], '$%04X' % addr))
    return hits


class Asm:
    """Tiny helper: emit bytes, collect labels, resolve branches/jumps at the end."""

    def __init__(self, base):
        self.base = base
        self.b = bytearray()
        self.lab = {}
        self.fix = []       # (kind, pos, label)

    def op(self, *bs):
        self.b += bytes(bs)

    def hexs(self, s):
        self.b += bytes.fromhex(s.replace(' ', ''))

    def label(self, name):
        assert name not in self.lab
        self.lab[name] = len(self.b)

    def rel(self, opcode, name):
        self.fix.append(('rel', len(self.b) + 1, name))
        self.op(opcode, 0x00)

    def jmp_to(self, name):
        self.fix.append(('abs', len(self.b) + 1, name))
        self.op(0x4C, 0x00, 0x00)

    def far_rel(self, opcode, name, tag):
        """Branch to a label a relative branch cannot reach.

        Invert the branch so it skips a three byte JMP; the branch and the JMP
        together are the same test, and the JMP reaches anywhere in the bank.
        """
        inv = {0xB0: 0x90, 0x90: 0xB0, 0xD0: 0xF0, 0xF0: 0xD0}[opcode]
        self.rel(inv, 'far_' + tag)
        self.jmp_to(name)
        self.label('far_' + tag)

    def long_to(self, rom_off):
        bk, ad = snes_of_rom(rom_off)
        self.op(0x5C, ad & 0xFF, ad >> 8, bk)

    def done(self):
        for kind, pos, name in self.fix:
            tgt = self.lab[name]
            if kind == 'rel':
                off = tgt - (pos + 1)
                assert -128 <= off <= 127, (name, off)
                self.b[pos] = off & 0xFF
            else:
                addr = 0x8000 + (self.base + tgt) % 0x8000
                self.b[pos] = addr & 0xFF
                self.b[pos + 1] = addr >> 8
        return bytes(self.b)


def build_dispatch():
    """Widget renderer hook at 0x00FC92 (A = code, Y = index, M/X 8 bit)."""
    a = Asm(DISPATCH_ROM)
    a.op(0xB7, 0x22)                     # LDA [$22],Y
    a.op(0xC9, 0xF2)                     # CMP #$F2
    a.rel(0xD0, 'nd')
    a.long_to(0x00FCC6)                  # F2 -> original RTS
    a.label('nd')
    a.op(0xC9, PREFIX0)                  # CMP #$C5
    a.rel(0x90, 'nor')                   # below the prefix range: original path
    a.op(0xC9, PREFIX0 + PAGES)          # CMP #$D1
    a.rel(0x90, 'ok2')                   # inside the range: Chinese
    a.long_to(0x00FC98)                  # far: original path (A and Y intact)
    a.label('nor')
    a.long_to(0x00FC98)
    a.label('ok2')
    a.op(0x8B)                           # PHB (keep the caller's DBR)
    a.op(0x38, 0xE9, PREFIX0)            # SEC / SBC #$C5 -> page
    a.op(0x18, 0x69, POOL_BANK0)         # CLC / ADC #$21 -> glyph bank
    a.op(0x48)                           # PHA (M = 8 on entry)
    a.op(0xC8)                           # INY
    a.op(0xB7, 0x22)                     # LDA [$22],Y -> id
    a.op(0xC9, SLOTS)                    # CMP #SLOTS
    a.rel(0x90, 'ok3')
    a.op(0x68)                           # PLA
    a.op(0x88)                           # DEY (back to the code byte)
    a.op(0xB7, 0x22)                     # LDA [$22],Y -> the code again
    a.op(0xAB)                           # PLB
    a.long_to(0x00FC98)                  # far: original path, A and Y restored
    a.label('ok3')
    a.op(0xAA)                           # TAX      (id)
    a.op(0xAB)                           # PLB -> DBR = glyph bank
    a.op(0x98, 0x48)                     # TYA / PHA: keep the string index
    a.op(0x8A)                           # TXA      (A = id again)
    a.op(0xC2, 0x30, 0x29, 0xFF, 0x00)   # REP #$30 / AND #$00FF
    a.op(0x0A, 0x0A, 0x0A, 0x0A, 0x0A)   # ASL x5 -> id*32
    a.op(0xA8)                           # TAY (16 bit)
    a.op(0xE2, 0x20)                     # SEP #$20 (X/Y stay 16 bit)
    _b, _a = snes_of_rom(B3_SLOTPAIR)
    lo, hi = _a & 0xFF, (_a >> 8) & 0xFF
    a.op(0xBF, lo, hi, _b)               # LDA $03:SLOTPAIR,X -> tile pair
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)
    a.op(0x0A, 0x0A, 0x0A)               # tile*8 words -> VRAM destination
    a.op(0x09, 0x00, 0x60, 0x8D, 0x16, 0x21)
    a.op(0xE2, 0x20)
    a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)   # $2115 = $80: one word per write
    _dma_glyph(a)
    a.op(0xE2, 0x30)                     # SEP #$30
    a.op(0x68, 0xA8)                     # PLA / TAY: the string index back
    a.op(0xAB)                           # PLB -> the caller's DBR
    a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)
    a.op(0xA5, 0x20, 0x8D, 0x16, 0x21)   # tilemap address = cursor
    a.op(0xA5, 0x21, 0x8D, 0x17, 0x21)
    a.op(0xBF, lo, hi, _b)               # LDA $03:SLOTPAIR,X -> top tile
    a.op(0x8D, 0x18, 0x21)               # the table holds tile numbers
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)
    a.op(0x1A, 0x8D, 0x18, 0x21)         # bottom tile
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)
    a.op(0xC8, 0xE6, 0x20)               # INY / INC $20
    a.rel(0xF0, 'row')
    a.long_to(DISPATCH_ROM)
    a.label('row')
    a.op(0xE6, 0x21)
    a.long_to(DISPATCH_ROM)
    return a.done()


def _dma_glyph(a, chan=2, bank=None):
    """Stage the 32 byte glyph at bank:$8000+Y into VRAM with DMA.

    Replaces the sixteen word CPU loop, which costs four instructions per word
    and made the status screen's draw long enough that the engine never got to
    unblank the screen -- the symptom was a black status screen with the game
    still running.  A DMA is about a tenth of the work.  Channel 2: the engine's
    own flusher and the drawer's glyph upload both use lower channels.

    Entered with A 8 bit, Y = the glyph's byte offset, $2116/$2117 and $2115
    already pointing at the destination.
    """
    if bank is None:
        bank = ITEM_GLYPH_BANK
    b = chan * 0x10
    a.op(0xC2, 0x20)                       # REP #$20
    a.op(0x98)                             # TYA
    a.op(0x18, 0x69, 0x00, 0x80)           # CLC / ADC #$8000
    a.op(0x8D, 0x02 + b, 0x43)             # STA $43x2 -> A1T low and high
    a.op(0xA9, 0x20, 0x00)                 # LDA #$0020
    a.op(0x8D, 0x05 + b, 0x43)             # STA $43x5 -> DAS low and high
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0xA9, 0x01, 0x8D, 0x00 + b, 0x43)  # LDA #$01 / STA $43x0 (DMAP)
    a.op(0xA9, 0x18, 0x8D, 0x01 + b, 0x43)  # LDA #$18 / STA $43x1 (VMDATAL)
    a.op(0xA9, bank, 0x8D, 0x04 + b, 0x43)  # LDA #bank / STA $43x4 (A1B)
    a.op(0xA9, 1 << chan, 0x8D, 0x0B, 0x42)  # LDA #bit / STA $420B (start)



def literal_tiles_to_restore():
    """The script's literal tiles that a pool slot actually sits on.

    Only those can have been overwritten: a tile no slot uses still holds the
    font's own glyph, because nothing else writes the font window.  Two of the
    -- STATUS -- row's tiles were slot 8's, which is why the row came out as
    gibberish after a dialogue draw.
    """
    lo, hi, _np, _win = build_slotpairs()
    used = set()
    for s_ in range(len(lo)):
        t = lo[s_] | (hi[s_] << 8)
        used.update((t, t + 1))
    return sorted(t for t in STATUS_LITERAL_TILES if t in used)


def build_literalfix():
    """Put the script's clobbered literal tiles back before the script runs.

    The -- STATUS -- row is the script's one literal-tile block: the interpreter
    writes its tile numbers straight into the tile map, so the label hook never
    sees them and the pool is free to use those tiles as slots.  A dialogue draw
    leaves a hanzi in them and the row comes out as gibberish -- and skipping the
    colliding slots does not help, because the dialogue uses every slot.

    Restoring the whole 4096 byte font block would work but is far too much to
    add to the status screen's blanked draw.  Only the literal tiles a slot
    really sits on need it, and that is two tiles here: one 32 byte DMA.

    Entered at the interpreter's $F976, whose two instructions (SEP #$30 and
    LDY #$00) this hook eats and replays.
    """
    tiles = literal_tiles_to_restore()
    a = Asm(LITERALFIX_ROM)
    a.op(0xE2, 0x30)                       # SEP #$30 (the eaten op)
    a.op(0xA0, 0x00)                       # LDY #$00 (the eaten op)
    if tiles:
        a.op(0x8B)                         # PHB
        a.op(0xDA)                         # PHX
        # channel 2: the engine's flusher and the drawer's glyph DMA use lower
        a.op(0xA9, 0x01, 0x8D, 0x20, 0x43)  # DMAP
        a.op(0xA9, 0x18, 0x8D, 0x21, 0x43)  # BBAD = VMDATAL
        # (each tile's DMA is started after its own registers are set: starting
        # one here would fire with DAS still zero, which means 65536 bytes)
        for t in tiles:
            a.op(0xC2, 0x30)               # REP #$30
            a.op(0xA9, (0x6000 + t * 8) & 0xFF, (0x6000 + t * 8) >> 8,
                     0x8D, 0x16, 0x21)     # LDA #vram / STA $2116
            a.op(0xE2, 0x20)               # SEP #$20: the rest is 8 bit
            a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)   # LDA #$80 / STA $2115
            _fb, _fa = snes_of_rom(FONT_ROM + t * 16)
            a.op(0xC2, 0x20)               # REP #$20: a 16 bit immediate, so
                                           # the store writes A1T low and high
            a.op(0xA9, _fa & 0xFF, _fa >> 8, 0x8D, 0x22, 0x43)   # A1T
            a.op(0xE2, 0x20)               # SEP #$20
            a.op(0xA9, _fb, 0x8D, 0x24, 0x43)                    # A1B
            a.op(0xA9, 16, 0x8D, 0x25, 0x43)     # DAS low = 16
            a.op(0xA9, 0x00, 0x8D, 0x26, 0x43)   # DAS high
            a.op(0xA9, 0x04, 0x8D, 0x0B, 0x42)   # start channel 2
        a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)  # LDA #$81 / STA $2115: the block
                                           # loop relies on the +32 increment
        a.op(0xFA)                         # PLX
        a.op(0xAB)                         # PLB
    a.op(0xE2, 0x30)                       # SEP #$30
    a.long_to(0x00F97A)                    # -> the interpreter's block loop
    return a.done(), tiles


def build_pace():
    """The message drawer's pacing gate, hooked over $03:EEE5's first bytes.

    $03:EEE5 runs once per drawn character (up to three attempts per tick) and
    used to read `LDA #$08 / JSL $009AB6`.  That JSL is NOT a frame wait: it is
    the $0B00 queue-space allocator ($00:9AB6: if the queue drained, reset both
    cursors, else return the requested size plus the write cursor).  Its argument
    is discarded by this call path, so the byte v31 changed paced nothing - the
    engine types at about one cell per frame with or without it, on the original
    ROM too (hw/_fld_orig.log vs hw/_fld_v36b.log, same message segments to the
    frame).  The real gate lives here.

    Entry: M/X 8 bit, DBR=$03 (the tick does PHK/PLB), A = don't care.  The gate
    counts DRAWER ATTEMPTS in $03E7 and lets one through every PACE of them.
    While it holds a character back the tick makes exactly one attempt per message tick
    (the SEC return stops the three-attempt loop), so PACE attempts are PACE
    ticks (the intro ticks every other video frame); on a fire tick the second attempt spends one more count, which is
    exactly what reload = PACE accounts for (fire, PACE-1 holds, fire...).
    P1 A/B held ($031A/$031C bit7) fast-forwards at three attempts per tick.
    $00:BBF7 stores rising edges in $0316/$0318, and held bytes in $031A/$031C.
    X/Y (bit6) are NOT A/B. Reset the countdown during bypass so releasing
    mid-count resumes immediately rather than inheriting the old delay.  On "not yet" the gate returns
    SEC, exactly like the engine's own busy exit at $03:EF2B, so the tick skips
    the remaining attempts; on "go" it replays the original
    `LDA #$08 / JSL $009AB6` (the queue reservation side effect stays) and
    returns CLC into $03:EEEB.  No engine counter is consulted: a first cut
    keyed on $0322 never counted on real hardware (that byte only moves in some
    main loop paths), so the count lives entirely in this gate.

    Blank cells draw through the SAME entry ($03:EF12, taken once $03E9 has
    reached $03E8), so the gate checks for an exhausted buffer and lets those
    through unpaced - they overwrite empty cells and a paced filler would hang
    a 2-4 s invisible pause after every line before the next one starts.  The
    control-code erasers ($03:FA1C) do not use this pacing gate.
    The line-hold beat ($03:EF2D, the E0 phase in a trace) returns SEC before
    the typewriter, so beats simply freeze the count.
    """
    a = Asm(PACE_ROM)
    a.op(0x08)                             # php
    a.op(0xE2, 0x30)                       # sep #$30
    a.op(0x48)                             # pha
    a.op(0xAD, 0x1A, 0x03)                 # lda $031A   (P1 held A/X byte)
    a.op(0x0D, 0x1C, 0x03)                 # ora $031C   (P1 held B/Y byte)
    a.op(0x29, 0x80)                       # and #$80    (A/B, not X/Y)
    a.rel(0xD0, 'bypass')                  # bne bypass: held fast-forward
    a.op(0xAC, 0xE9, 0x03)                 # ldy $03e9   (buffer index)
    a.op(0xCC, 0xE8, 0x03)                 # cpy $03e8   (vs length)
    a.rel(0xB0, 'bypass')                  # bcs bypass: exhausted, unpaced filler
    a.op(0xAD, PACE_FRAMES & 0xFF, PACE_FRAMES >> 8) # lda pacing counter
    a.rel(0xF0, 'fire')                    # beq fire: due now
    a.op(0xCE, PACE_FRAMES & 0xFF, PACE_FRAMES >> 8) # dec pacing counter
    a.label('hold')
    a.op(0x68)                             # pla
    a.op(0x28)                             # plp
    a.op(0x38)                             # sec
    a.op(0x6B)                             # rtl -> $03:EEEB, carry set
    a.label('fire')
    a.op(0xA9, PACE & 0xFF)                # lda #PACE
    a.op(0x8D, PACE_FRAMES & 0xFF, PACE_FRAMES >> 8) # sta pacing counter
    a.rel(0x80, 'go')
    a.label('bypass')
    a.op(0x9C, PACE_FRAMES & 0xFF, PACE_FRAMES >> 8) # stz pacing counter
    a.label('go')
    a.op(0x68)                             # pla
    a.op(0x28)                             # plp
    a.op(0xA9, 0x08)                       # lda #$08   (replay: 8 queue bytes)
    a.op(0x22, 0xB6, 0x9A, 0x00)           # jsl $009ab6 (the queue allocator)
    a.op(0x18)                             # clc
    a.op(0x6B)                             # rtl -> $03:EEEB, carry clear
    return a.done()


def build_hudname():
    """Battle HUD name plate: see HUDNAME_HOOK.

    Entered with $18 = the byte index into the name record (char slot * 4 +
    cell) and M/X 8 bit.  Cell k takes glyph  (k >> 1)  of the record, its left
    half when k is even and its right half when k is odd, and leaves that cell's
    two tiles in $22 (upper) / $23 (lower) for the caller to write.

    Only the upload happens on even cells: the odd cell shares the glyph, and
    when the queue is too full to stage it the tiles are simply left as they
    are -- they still hold the same glyph from the previous frame, because the
    private HUD reservation is not shared with any message-name/item pairs.
    Both enemy plates get two distinct glyphs. Queue pressure may defer a new
    glyph, so the complete ABI and real timing are still tested separately.
    """
    TABLE_N = len(hud_pairs()) // 2
    SLOT0 = 0
    lo, loh = snes_of_rom(HUDPAIR_ROM), snes_of_rom(HUDPAIR_ROM + 16)
    ro, roh = snes_of_rom(HUDPAIR_ROM + TABLE_N), snes_of_rom(HUDPAIR_ROM + 16 + TABLE_N)
    a = Asm(HUDNAME_ROM)

    def ld_pair(low_t, hi_t):
        """A = the 16 bit tile of pair entry X (low table + high table)."""
        a.hexs('E2 20')                                  # sep #$20
        a.hexs('BF %02X %02X %02X' % (hi_t[1] & 0xFF, hi_t[1] >> 8, hi_t[0]))
        a.hexs('EB')                                     # xba
        a.hexs('BF %02X %02X %02X' % (low_t[1] & 0xFF, low_t[1] >> 8, low_t[0]))
        a.hexs('C2 20 48')                               # rep #$20 / pha

    a.hexs('08 E2 30 8B')                # php / sep #$30 / phb
    # Test the current two-byte PAIR, not the entire four-byte record.
    # The second hanzi can be on another page, or this pair can be blank/kana.
    a.hexs('A5 18 29 FE A8')             # lda $18 / and #$fe / tay
    a.hexs('B9 46 1B C9 C0')             # lda $1b46,y / cmp #$c0
    a.rel(0xB0, 'two')                   # bcs two: two two byte codes
    a.hexs('A4 18 B9 46 1B')             # ldy $18 / lda $1b46,y
    a.hexs('AA')                         # tax
    a.hexs('BF 9E FA 03 85 22')          # lda $03fa9e,x / sta $22
    a.hexs('BF 9E FB 03 85 23')          # lda $03fb9e,x / sta $23
    a.hexs('AB 28 6B')                   # plb / plp / rtl -- this path pushed
                                         # nothing, so it must NOT fall into fin
    a.label('fin')
    a.hexs('E2 30')                      # sep #$30 (X may be 16 bit by now)
    for _ in range(5):                   # bank + right tile + left tile
        a.hexs('68')                     # pla
    a.hexs('C2 20 68 85 1E')             # rep / pla / sta $1e: the engine's value
    a.hexs('E2 20')                      # sep: back to the 8 bit M of the entry
    a.hexs('AB 28 6B')                   # plb / plp / rtl

    a.label('two')
    a.hexs('C2 20 A5 1E 48 E2 20')       # rep #$20 / lda $1e / pha / sep #$20:
                                         # park the engine's $1e/$1f before
                                         # borrowing them -- and M must go back
                                         # to 8 bit, or the LDA $18 below reads
                                         # two bytes and the slot comes out wrong
    # Plate-specific slot: two glyphs per live enemy, four glyphs total.
    a.hexs('A5 18 29 %02X 4A' % (7 if HUD_ORIG else 15))             # lda $18 / and #$03 / lsr a
    a.hexs('18 69 %02X' % SLOT0)         # clc / adc #SLOT0
    a.hexs('C2 20 29 FF 00 AA')          # rep #$20 / and #$00ff / tax
    ld_pair(lo, loh)                     # push the left half tile
    ld_pair(ro, roh)                     # push the right half tile
    # pool offset = the id byte * 64  (id byte = LABEL_ID0 + idx, and the glyph
    # lives at (LABEL_ID0 + idx) * POOL_STRIDE inside its page).  It goes in the
    # zero page rather than on the stack: the bank sits on top of the stack, so
    # a PLA would fetch the bank and not the offset.
    a.hexs('E2 20 A5 18 29 FE A8')       # sep / lda $18 / and #$fe / tay
    a.hexs('B9 47 1B')                   # lda $1b47,y   (the id byte)
    a.hexs('C2 20 29 FF 00')             # rep / and #$00ff
    for _ in range(6):
        a.hexs('0A')                     # asl x6 -> id * 64
    a.hexs('85 1E')                      # sta $1e (the pool offset, 16 bit)
                                         # $1e is borrowed: the plate is drawn
                                         # during ACTIVE DISPLAY, so an NMI can
                                         # fire and the engine's own value has to
                                         # come back -- it is pushed at the top
                                         # of the two path and popped at fin
    # pool bank = POOL_BANK0 + page - $c0
    a.hexs('E2 20 B9 46 1B')             # sep / lda $1b46,y  (the page byte)
    a.hexs('38 E9 %02X 18 69 %02X 48' % (PREFIX0, POOL_BANK0))       # sec / sbc #$c0 / clc / adc #$21 / pha
    # stack: [01,s]=bank [02,s]=right tile [04,s]=left tile
    #
    # Only even cells stage the glyph; the odd cell reuses what the even one
    # put there.  Also skip when the queue is close to full -- the tiles keep
    # the previous frame's glyph, which for the same record is the same glyph.
    a.hexs('A5 18 29 01')                # lda $18 / and #$01
    a.far_rel(0xD0, 'pick', 'hudodd')     # odd cell: nothing to stage
    # Reserve 72 glyph bytes plus up to 48 bytes for the four-cell caller.
    # Check the full cursor, not just its low byte. A busy queue defers glyphs.
    a.hexs('C2 20 AD DF 09 C9 88 00 E2 20')
    a.far_rel(0xB0, 'pick', 'hudq')       # insufficient headroom: no insertion

    # $8C45 has already written a four-byte cell header at QUEUE_APPEND,
    # but has NOT committed it. Insert the glyphs BEFORE that pending header.
    # Moving only $09DF loses the append when $8C57 stores the saved X back.
    a.hexs('C2 30 AE DF 09')             # rep #$30 / ldx $09df
    a.hexs('BD 00 0B 9D 48 0B')          # move header word 0 forward 72 bytes
    a.hexs('BD 02 0B 9D 4A 0B')          # move header word 1 forward 72 bytes
    # At this point: bank(1), pairs(4), saved DP(2), DB(1), P(1),
    # JSL return(3), caller's PHX(1). Update the X that PLX will restore.
    a.hexs('E2 20 A3 0D 18 69 48 83 0D') # saved X += 72
    a.hexs('A3 01 48 AB')                # lda $01,s / pha / plb: glyph bank
    a.hexs('AE DF 09')                   # ldx $09df
    for slot_off, off_extra in ((4, 0), (2, 32)):
        # VRAM word address = $6000 + tile * 8
        a.hexs('E2 20')                  # sep #$20: the round before left M 16
        a.hexs('A3 %02X' % slot_off)     # lda $06,s / $04,s (the tile's low byte)
        a.hexs('C2 30 29 FF 00 0A 0A 0A')  # rep #$30 / and / asl x3.  X *and* Y
        # have to be 16 bit here: the pool offset is up to 32704, and a TAY with
        # an 8 bit Y would drop its high byte and read the wrong page.
        a.hexs('09 00 60')               # ora #$6000
        a.hexs('9D 00 0B E8 E8')         # sta $0b00,x / inx inx
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep / lda #$80 / sta / inx ($2115)
        a.hexs('A9 20 9D 00 0B E8')      # lda #$20 / sta / inx (32 bytes)
        a.hexs('C2 30 A5 1E')            # rep / lda $1e: the pool offset
        if off_extra:
            a.hexs('18 69 %02X 00' % off_extra)        # clc / adc #32
        a.hexs('A8')                     # tay
        for _ in range(16):              # 16 words: the pair, from DBR:$8000+Y
            a.hexs('B9 00 80 9D 00 0B E8 E8 C8 C8')
    a.hexs('8E DF 09')                   # stx $09df
    a.hexs('E2 20 A9 03 48 AB')          # sep / lda #$03 / pha / plb (DBR back)
    a.label('pick')
    # The ORIGINAL caller puts $22 on the lower row (base) and $23 on the
    # upper row (base-32). Pool pairs are top-first, unlike FA/FB kana.
    # Therefore return lower=tile+1 in $22, upper=tile in $23.
    # Half 0 is the left pair, half 1 is the right pair.
    a.hexs('A5 18 29 01')                # lda $18 / and #$01
    a.hexs('D0 0A')                      # bne useright
    a.hexs('A3 04 85 23 1A 85 22')       # top -> $23, bottom -> $22
    a.jmp_to('fin')
    a.label('useright')
    a.hexs('A3 02 85 23 1A 85 22')       # top -> $23, bottom -> $22
    a.jmp_to('fin')
    return a.done()


def build_itemmsg():
    """The item name a battle message pastes in: the drawer's $DE branch.

    v23 gave the item names their own code -- [$DE][8x16 id], glyphs in the
    table at $3F:8000 -- because the status screen's three values cannot share
    the pool.  The message drawer only knows the Chinese page codes, so a name
    pasted into a battle message came out as FA[$de] and FA[id]: two wrong
    glyphs per hanzi, the four fragments in the user's screenshot.

    Entered by JML from the drawer's dispatch with A = $12 = $DE, so PBR is $3E
    and an RTS would return into the wrong bank: every exit is a JML into bank
    $03, and the stack must be left exactly as the drawer's own paths leave it
    because those exits RTS straight to the consumer.

    The glyph is 8x16 (one column, tiles t/t+1), so the column advances once --
    $03:FA7A does that -- and the id byte is eaten with INC $03E9, exactly like
    the drawer's own two byte codes.  The slot is SLOT0 + (column & 3): the
    glyphs of one name sit in four consecutive columns, so their low bits are
    always distinct and four name pairs are enough.
    """
    SLOT0 = SLOTS + LABEL_GLYPHS * LABEL_SETS
    lo, loh = snes_of_rom(E3_SLOTPAIR), snes_of_rom(E3_SLOTHI)
    a = Asm(ITEMMSG_ROM)

    a.hexs('08 E2 30 8B')                # php / sep #$30 / phb
    # room for the 36 byte tile entry and the two 8 byte cells?
    a.hexs('C2 20 AD DF 09 C9 %02X 00 E2 20' % (0x100 - 44))
    a.far_rel(0xB0, 'deter', 'ies')      # bcs deter: retry next frame
    # A DE name can be the first visible entry of a message/list row. It
    # bypasses the body drawer now, so it owns the same row-start blanking.
    a.hexs('AD 6F 03')
    a.far_rel(0xD0, 'rowready', 'ieskiprow')
    a.hexs('C2 20 AD DF 09 C9 %02X 00 E2 20' % (0x101 - ROW_WIPE - 44))
    a.far_rel(0xB0, 'deter', 'ierow')
    a.hexs('C2 30 AE DF 09')
    _rowwipe(a, 0, 'item')
    _rowwipe(a, 0x20, 'item')
    a.hexs('8E DF 09 E2 30')
    a.label('rowready')
    # slot = SLOT0 + ($036f & 3)
    a.hexs('AD 6F 03 29 03')             # lda $036f / and #$03
    a.hexs('18 69 %02X' % SLOT0)         # clc / adc #SLOT0
    a.hexs('C2 20 29 FF 00 AA')          # rep #$20 / and #$00ff / tax
    a.hexs('E2 20')                      # sep #$20
    a.hexs('BF %02X %02X %02X' % (loh[1] & 0xFF, loh[1] >> 8, loh[0]))
    a.hexs('EB')                         # xba
    a.hexs('BF %02X %02X %02X' % (lo[1] & 0xFF, lo[1] >> 8, lo[0]))
    a.hexs('C2 20 48')                   # rep #$20 / pha: the pair's upper tile
    a.hexs('AE DF 09')                   # ldx $09df (the queue cursor)
    # 32 bytes to VRAM word $6000 + tile * 8, from $3F:8000 + id * 32
    a.hexs('E2 20 A3 01')                # sep / lda $01,s (the tile low byte)
    a.hexs('C2 30 29 FF 00 0A 0A 0A')    # rep #$30 / and / asl x3 -> tile * 8
    a.hexs('09 00 60')                   # ora #$6000
    a.hexs('9D 00 0B E8 E8')             # sta $0b00,x / inx inx
    a.hexs('E2 20 A9 80 9D 00 0B E8')    # sep / lda #$80 / sta / inx ($2115)
    a.hexs('A9 20 9D 00 0B E8')          # lda #$20 / sta / inx (32 bytes)
    a.hexs('AD E9 03 1A')                # byte index of the following ID
    # X/Y are 16-bit here; TAY transfers hidden B even when M=8. The previous
    # VRAM address left B=$60..$67, which selected an unrelated WRAM byte.
    a.hexs('C2 30 29 FF 00 A8 E2 20')    # explicitly zero-extend before TAY
    a.hexs('B9 EA 03')                   # lda $03ea,y (the glyph id)
    a.hexs('C2 30 29 FF 00')             # rep #$30 / and #$00ff
    for _ in range(5):
        a.hexs('0A')                     # asl x5 -> id * 32
    a.hexs('A8')                         # tay
    a.hexs('E2 20 A9 3F 48 AB')          # sep / lda #$3f / pha / plb
    a.hexs('C2 20')                      # WORD copies: do not leave plane-1 queue garbage
    for _ in range(16):                  # 16 words: the glyph, from DBR:$8000+Y
        a.hexs('B9 00 80 9D 00 0B E8 E8 C8 C8')
    a.hexs('E2 20 A9 03 48 AB')          # sep / lda #$03 / pha / plb
    # the two cells at (row $036e, column $036f), like the drawer's own writer
    a.hexs('E2 30 AC 6E 03')             # sep #$30 / ldy $036e
    a.hexs('B9 8E FA 18 6D 6F 03')       # lda $fa8e,y / clc / adc $036f
    a.hexs('9D 00 0B E8')                # sta $0b00,x / inx
    a.hexs('B9 7E FA 69 00 9D 00 0B E8')  # lda $fa7e,y / adc #0 / sta / inx
    a.hexs('A9 81 9D 00 0B E8')          # lda #$81 / sta / inx (VMAIN $81)
    a.hexs('A9 04 9D 00 0B E8')          # lda #$04 / sta / inx (two words)
    a.hexs('C2 20 A3 01')                # rep #$20 / lda $01,s (the tile)
    a.hexs('09 00 24 9D 00 0B E8 E8')    # ora #$2400 / sta / inx inx
    a.hexs('1A 9D 00 0B E8 E8')          # inc a (tile + 1) / sta / inx inx
    a.hexs('8E DF 09')                   # stx $09df
    a.hexs('EE E9 03')                   # inc $03e9 (consume the id byte)
    a.hexs('E2 20 68 68')                # sep #$20 / pla x2 (the tile)
    a.hexs('AB 28')                      # plb / plp
    a.long_to(0x01FA7A)                  # jml $03:fa7a (inc $036f / rts)
    # ---- not enough queue room: give the frame back -------------------------
    a.label('deter')
    a.hexs('AD E9 03 3A 8D E9 03')       # lda $03e9 / dec a / sta $03e9
    a.hexs('AB 28')                      # plb / plp
    a.long_to(0x01FA7D)                  # jml $03:fa7d (plain rts)
    return a.done()


def build_itemdrawer():
    """Item names on the status screen: the hook at CPU $01:FCA5.

    Entered with X = the code byte, Y = the index into the name, $2116/$2117
    already pointing at the value's next cell and the cursor in $20/$21.  A
    code below ITEM_PREFIX is the engine's own kana or a digit: replay the eaten
    FB[code] lookup and carry on.  An item code carries an 8x16 glyph id: upload
    that glyph into the slot the cursor names, then write the two tile map cells
    the original wrote.

    The slot comes from the cursor so the three values cannot collide: they are
    on screen together and only the cursor tells them apart.  Bases 0 / 12 / 24
    keep every slot below SLOTS, so no item glyph ever lands on a label pair.
    """
    a = Asm(ITEMDRAW_ROM)
    a.op(0xE0, ITEM_PREFIX)                # CPX #$DE
    a.rel(0xF0, 'item')                    # equal -> our glyph, else the engine's
    a.op(0xBF, 0x9E, 0xFB, 0x03)           # LDA $03FB9E,X  (the eaten lookup)
    a.long_to(0x00FCA9)                    # -> the original STA $2118
    a.label('item')
    a.op(0x5A)                             # PHY (the upload's TAY clobbers it)
    # slot = base(cursor) + (column - 6), clamped to 11
    a.op(0xA5, 0x20)                       # LDA $20
    a.op(0x38, 0xE9, 0xC6)                 # SEC / SBC #$C6
    for _ in range(6):
        a.op(0x4A)                         # LSR x6 -> 0 / 1 / 2
    a.op(0xAA)                             # TAX
    _b, _a = snes_of_rom(ITEMBASE_ROM)
    a.op(0xBF, _a & 0xFF, _a >> 8, _b)     # LDA $3E:ITEMBASE,X -> 0 / 12 / 24
    a.op(0x85, 0x1E)                       # STA $1E
    a.op(0xA5, 0x20)                       # LDA $20
    a.op(0x29, 0x1F)                       # AND #$1F
    a.op(0x38, 0xE9, 0x06)                 # SEC / SBC #$06
    a.rel(0xB0, 'cok')
    a.op(0xA9, 0x00)                       # LDA #$00: left of column 6
    a.label('cok')
    a.op(0xC9, ITEM_SLOT_SPAN)             # CMP #ITEM_SLOT_SPAN
    a.rel(0x90, 'ccl')
    a.op(0xA9, ITEM_SLOT_SPAN - 1)         # clamp an overlong value
    a.label('ccl')
    a.op(0x18, 0x65, 0x1E)                 # CLC / ADC $1E  -> the slot
    a.op(0x85, 0x1E)                       # STA $1E
    # glyph source: bank $3f, offset id*32
    a.op(0xC8)                             # INY
    a.op(0xB7, 0x22)                       # LDA [$22],Y
    a.op(0xC2, 0x30, 0x29, 0xFF, 0x00)     # REP #$30 / AND #$00FF
    for _ in range(5):
        a.op(0x0A)                         # ASL x5 -> id*32
    a.op(0xA8)                             # TAY
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0x8B)                             # PHB
    a.op(0xA9, ITEM_GLYPH_BANK)            # LDA #$3F
    a.op(0x48)                             # PHA
    a.op(0xAB)                             # PLB -> DBR = $3F
    # tile pair base -> $1F, upload 32 bytes there
    a.op(0xA5, 0x1E)                       # LDA $1E
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)     # REP #$20 / AND #$00FF
    a.op(0xAA)                             # TAX
    a.op(0xE2, 0x20)                       # SEP #$20
    _b2, _a2 = snes_of_rom(E3_SLOTPAIR)
    a.op(0xBF, _a2 & 0xFF, _a2 >> 8, _b2)  # LDA $3E:SLOTPAIR,X
    a.op(0x85, 0x1F)                       # STA $1F        (the upper tile)
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)     # REP #$20 / AND #$00FF
    for _ in range(3):
        a.op(0x0A)                         # ASL x3 -> tile*8 words
    a.op(0x09, 0x00, 0x60)                 # ORA #$6000
    a.op(0x8D, 0x16, 0x21)                 # STA $2116
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)     # LDA #$80 / STA $2115
    _dma_glyph(a)
    a.op(0xE2, 0x30)                       # SEP #$30
    a.op(0xAB)                             # PLB (back to $01)
    # the two tile map cells: upper at the cursor, lower one map row down
    a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)     # LDA #$81 / STA $2115
    a.op(0xA5, 0x20, 0x8D, 0x16, 0x21)     # LDA $20 / STA $2116
    a.op(0xA5, 0x21, 0x8D, 0x17, 0x21)     # LDA $21 / STA $2117
    a.op(0xA5, 0x1F, 0x8D, 0x18, 0x21)     # LDA $1F / STA $2118
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)     # LDA #$24 / STA $2119
    a.op(0xA5, 0x1F, 0x1A, 0x8D, 0x18, 0x21)   # LDA $1F / INC A / STA $2118
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)     # LDA #$24 / STA $2119
    a.op(0x7A)                             # PLY (undo the TAY in the upload)
    a.op(0xC8, 0xC8)                       # INY / INY: past the code and the id
    a.op(0xE6, 0x20)                       # INC $20
    a.rel(0xF0, 'row')
    a.long_to(0x00FC92)                    # back to the character loop
    a.label('row')
    a.op(0xE6, 0x21)                       # INC $21
    a.long_to(0x00FC92)
    return a.done()



def _emit_tile_restore(a, tiles):
    """DMA each of these font tiles from ROM back into VRAM.

    Used to undo what the glyph pool did to tiles the engine draws itself but
    the drawer never stages -- the -- STATUS -- row's glyphs above all.  One
    16 byte transfer per tile on channel 2; the engine's flusher and the
    drawer's own glyph DMA use lower channels.
    """
    a.op(0xA9, 0x01, 0x8D, 0x20, 0x43)     # DMAP
    a.op(0xA9, 0x18, 0x8D, 0x21, 0x43)     # BBAD = VMDATAL
    for t in tiles:
        _fb, _fa = snes_of_rom(FONT_ROM + t * 16)
        a.op(0xC2, 0x30)                   # REP #$30
        a.op(0xA9, (0x6000 + t * 8) & 0xFF, (0x6000 + t * 8) >> 8,
                 0x8D, 0x16, 0x21)         # LDA #vram / STA $2116
        a.op(0xE2, 0x20)                   # SEP #$20
        a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)  # LDA #$80 / STA $2115
        a.op(0xC2, 0x20)                   # REP #$20: 16 bit immediate
        a.op(0xA9, _fa & 0xFF, _fa >> 8, 0x8D, 0x22, 0x43)   # A1T
        a.op(0xE2, 0x20)                   # SEP #$20
        a.op(0xA9, _fb, 0x8D, 0x24, 0x43)  # A1B
        a.op(0xA9, 16, 0x8D, 0x25, 0x43)   # DAS low = 16
        a.op(0xA9, 0x00, 0x8D, 0x26, 0x43)  # DAS high
        a.op(0xA9, 0x04, 0x8D, 0x0B, 0x42)  # start channel 2


def build_labeldrawer():
    """Status screen labels: the hook at CPU $01:F9BC.

    The interpreter at $01:F971 walks [addr][count][codes] blocks and names each
    cell's tiles through FB[code] (upper) and FA[code] (lower).  For a label
    code the eaten lookup is replaced by: upload the glyph FA[code] names, out
    of the shared 8x16 table, into the pool slot the code's entry in the slot
    table names, then write the same two cells.  A code the table does not know
    falls through to the engine's own FA/FB path, so the name field and the
    colon keep working.

    Entered with X = the code, Y = the script index, DBR = $01, M = 8, and the
    interpreter's VRAM cursor already in $2116/$2117.
    """
    a = Asm(LABELDRAW_ROM)
    if LITERAL_TILES_RESTORE and os.environ.get('LITFIX', '0') == '1':
        # The first call happens with the cursor on the script's first TEXT
        # block, right after the literal -- STATUS -- row was written.  Put
        # that row's tiles back here: the pool had a hanzi in them from the
        # last dialogue draw, and the row's tile map cells already point at
        # them, so restoring the content is enough.
        # STATUS_FIRST_TEXT is a VRAM address: compare $39/$3A with it as it
        # stands (snes_of_rom would treat it as a ROM offset and give $F889).
        _a4 = STATUS_FIRST_TEXT
        a.op(0xAD, 0x39, 0x00, 0xC9, _a4 & 0xFF)
                                           # LDA $0039 / CMP #lo
        a.far_rel(0xD0, 'nores', 'nrl')
        a.op(0xAD, 0x3A, 0x00, 0xC9, _a4 >> 8)
                                           # LDA $003A / CMP #hi
        a.far_rel(0xD0, 'nores', 'nrh')
        a.op(0x8B)                         # PHB
        a.op(0xDA)                         # PHX
        _emit_tile_restore(a, LITERAL_TILES_RESTORE)
        a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)  # LDA #$81 / STA $2115 (the loop
                                           # relies on the +32 increment)
        a.op(0xA5, 0x39, 0x8D, 0x16, 0x21)  # LDA $39 / STA $2116: the DMA left
        a.op(0xA5, 0x3A, 0x8D, 0x17, 0x21)  # the cursor on the last tile it
                                           # wrote, and the cell's tile map
                                           # words go to $39/$3A
        a.op(0xFA)                         # PLX
        a.op(0xAB)                         # PLB
        a.label('nores')
    _b, _a = snes_of_rom(STATUS_SLOT_TABLE)
    a.op(0xBF, _a & 0xFF, _a >> 8, _b)     # LDA $3E:SLOTTAB,X
    a.op(0xC9, 0xFF)                       # CMP #$FF
    a.rel(0xD0, 'lab')
    a.op(0xBF, 0x9E, 0xFB, 0x03)           # LDA $03FB9E,X (the eaten lookup)
    a.long_to(0x00F9C0)                    # -> the original STA $2118
    a.label('lab')
    a.op(0x85, 0x1F)                       # STA $1F        (the slot)
    a.op(0x5A)                             # PHY
    _b3, _a3 = snes_of_rom(STATUS_LABEL_ID_TABLE)
    a.op(0xBF, _a3 & 0xFF, _a3 >> 8, _b3)  # LDA $3E:LABELID,X (the 8x16 glyph id)
    a.op(0xC2, 0x30, 0x29, 0xFF, 0x00)     # REP #$30 / AND #$00FF
    for _ in range(5):
        a.op(0x0A)                         # ASL x5 -> id*32
    a.op(0xA8)                             # TAY
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0x8B)                             # PHB
    a.op(0xA9, ITEM_GLYPH_BANK)            # LDA #$3F
    a.op(0x48)                             # PHA
    a.op(0xAB)                             # PLB -> DBR = $3F
    a.op(0xA5, 0x1F)                       # LDA $1F
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)     # REP #$20 / AND #$00FF
    a.op(0xAA)                             # TAX            (the slot)
    a.op(0xE2, 0x20)                       # SEP #$20
    _b2, _a2 = snes_of_rom(E3_SLOTPAIR)
    a.op(0xBF, _a2 & 0xFF, _a2 >> 8, _b2)  # LDA $3E:SLOTPAIR,X
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)     # REP #$20 / AND #$00FF
    for _ in range(3):
        a.op(0x0A)                         # ASL x3 -> tile*8 words
    a.op(0x09, 0x00, 0x60)                 # ORA #$6000
    a.op(0x8D, 0x16, 0x21)                 # STA $2116
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0xA9, 0x80, 0x8D, 0x15, 0x21)     # LDA #$80 / STA $2115
    _dma_glyph(a)
    a.op(0xE2, 0x30)                       # SEP #$30: M AND X back to 8 bit.
                                           # The REP #$30 above left X 16 bit,
                                           # and the interpreter's caller reads
                                           # the character index with LDX
                                           # $1BA6 -- a 16 bit X there loads two
                                           # bytes and shifts every index after
                                           # it, which left the status screen
                                           # black.
    a.op(0xAB)                             # PLB (DBR back to $01)
    a.op(0xA9, 0x81, 0x8D, 0x15, 0x21)     # LDA #$81 / STA $2115
    a.op(0xA5, 0x39, 0x8D, 0x16, 0x21)     # LDA $39 / STA $2116
    a.op(0xA5, 0x3A, 0x8D, 0x17, 0x21)     # LDA $3A / STA $2117
    a.op(0xA5, 0x1F)                       # LDA $1F
    a.op(0xC2, 0x20, 0x29, 0xFF, 0x00)     # REP #$20 / AND #$00FF
    a.op(0xAA)                             # TAX
    a.op(0xE2, 0x20)                       # SEP #$20
    a.op(0xBF, _a2 & 0xFF, _a2 >> 8, _b2)  # LDA $3E:SLOTPAIR,X
    a.op(0x8D, 0x18, 0x21)                 # STA $2118
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)     # LDA #$24 / STA $2119
    a.op(0xBF, _a2 & 0xFF, _a2 >> 8, _b2)  # LDA $3E:SLOTPAIR,X
    a.op(0x1A)                             # INC A: the cell below
    a.op(0x8D, 0x18, 0x21)                 # STA $2118
    a.op(0xA9, 0x24, 0x8D, 0x19, 0x21)     # LDA #$24 / STA $2119
    a.op(0x7A)                             # PLY
    a.long_to(0x00F9D4)                    # -> INC $39 / DEC $1E / loop
    return a.done()


def _rowwipe(a, extra, tag):
    """Stage one 52 byte queue entry blanking the 26 text cells of the row in
    $036e: columns 3..28 of the upper cell row (the lower half of each cell is
    another 26 words at +$20).  X is the queue cursor and is left past the entry,
    so a second call continues the same entry run; A and Y are scratch."""
    a.hexs('08 E2 30')                 # php / sep #$30: the caller's M and X
                                       # widths are restored by plp
    a.hexs('AD 6E 03')                 # lda $036e (the text row)
    a.hexs('C2 20 29 FF 00')           # rep #$20 / and #$00ff
    for _ in range(6):
        a.hexs('0A')                   # asl x6: 64 words per text row
    a.hexs('18 69 %02X %02X' % ((0x7C00 + 3 + extra) & 0xFF,
                                (0x7C00 + 3 + extra) >> 8))   # adc #$7c03
    a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx (VRAM address)
    a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep / lda #$80 / sta / inx ($2115)
    a.hexs('A9 34 9D 00 0B E8')        # lda #$34 / sta / inx (52 bytes)
    a.hexs('C2 20 E2 10 A9 00 2C')     # rep #$20 / sep #$10 / lda #$2c00 (blank)
    a.hexs('A0 1A')                    # ldy #26: words per cell row
    a.label('rw%s%02X' % (tag, extra))
    a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx
    a.hexs('88')                       # dey
    a.rel(0xD0, 'rw%s%02X' % (tag, extra))      # bne rw (loop)
    a.hexs('28')                       # plp


def build_drawer_copy():
    """Draw one 16x16 Chinese glyph as two tile pairs in two screen cells.

    Entered through a JML planted at ROM 0x01FA30, so PBR is $3E inside this code
    and an RTS would return into the wrong bank: every exit is an explicit JML
    into bank $03.  The character code is read from RAM $12 exactly like the
    original drawer does, because the row eraser ($FA0B, sub 6) calls the drawer
    with a leftover A that has nothing to do with the character.

    Nothing here keeps state in WRAM.  The glyph bank, the id and the two tile
    pairs ride on the stack, the pool offset is in Y and the upload queue cursor
    in X.  The area the old build used ($0d40-$0d5f, with WIPE_PEND at $0d43) is
    the game's own workspace:

        $01:88C0 STA $0D43   $01:81B9/$01:81FB/$01:8DAF STZ $0D43
        $0C:C793/$0C:C913 STZ $0D42         $01:831F STA $0D44
        $01:889C/$01:8DB2 STA/STZ $0D53     $01:8DAC STZ $0D54
        $01:8E71/$01:8EE0 STA $0D54         $01:8DA9 STA $0D55
        $05:BCC1/$05:BCDE STA $0D40         $09:FF36 STA $0D51
        $02:8029/$02:8180/$02:824E/$02:82FC STZ $0D5F   (see scratch_hits)

    so the engine zeroed the wipe flags between arming and staging and the box
    was never blanked.  Blanking now happens once per message at $3E:8800.

    A glyph occupies four tiles that need not be adjacent: the slot table gives
    two consecutive free tile pairs, the left screen cell shows tiles a/a+1 and
    the right one b/b+1.  The left pair is the pool's first 32 bytes, the right
    pair its second 32 bytes, uploaded through the engine's own queue ($0B00,
    flushed by $00:8385) as entries

        [+0/+1] VRAM word address, [+2] $2115, [+3] byte count, [+4...] data

    One glyph costs two 36 byte tile entries plus two 8 byte tile map cells.
    """
    a = Asm(E3_DRAWER)

    def rowwipe(extra, tag):
        return _rowwipe(a, extra, tag)

        a.hexs('08 E2 30')                 # php / sep #$30: the caller's M and X
                                           # widths are restored by plp, and the
                                           # wipe body works in 8 bit mode
        a.hexs('AD 6E 03')                 # lda $036e (the text row)
        a.hexs('C2 20 29 FF 00')           # rep #$20 / and #$00ff
        for _ in range(6):
            a.hexs('0A')                   # asl x6: 64 words per tile map row
        a.hexs('18 69 %02X %02X' % ((0x7C00 + 3 + extra) & 0xFF,
                                    (0x7C00 + 3 + extra) >> 8))   # adc #$7c03
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx (VRAM address)
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep / lda #$80 / sta / inx ($2115)
        a.hexs('A9 34 9D 00 0B E8')        # lda #$34 / sta / inx (52 bytes)
        a.hexs('C2 20 E2 10 A9 00 2C')     # rep #$20 / sep #$10: 16 bit words but
                                           # an 8 bit index, so ldy below stays a
                                           # one byte immediate
        a.hexs('A0 1A')                    # ldy #26: words per cell row
        a.label('rw%s%02X' % (tag, extra))
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx
        a.hexs('88')                       # dey
        a.rel(0xD0, 'rw%s%02X' % (tag, extra))      # bne rw (loop)
        a.hexs('28')                       # plp: back to the caller's widths

    def sload(off):
        """A = the 16 bit tile at $off,s, leaving M=0 (the stack is never grown
        here, so the offsets stay valid across calls).  The tile number needs 10
        bits: the label pairs moved outside the font window (see
        build_slotpairs), and the tile map word the drawer builds below carries
        the extra bits through $2400 anyway."""
        a.hexs('C2 20')                    # rep #$20: a 16 bit load
        a.hexs('A3 %02X' % off)            # lda $off,s (the whole tile)

    # ---- dispatch on the code in $12 -----------------------------------------
    #   $c0..$c0+pages-1  two byte Chinese code (prefix + id)
    #   $dc..$dc+FIXED_N  one byte code of a frequent character
    #   everything else   the original drawer, whose first instructions the
    #                     4 byte hook ate and which are replayed here
    if STALEROW_ON:
        a.hexs('22 00 C4 3E')              # jsl $3e:c400: at a row start this
                                           # wipes the stale row above (see
                                           # build_stalerow); it does nothing on
                                           # the other cells
    a.hexs('A5 12')                        # lda $12
    a.hexs('C9 %02X' % PREFIX0)            # cmp #$c0
    a.rel(0x90, 'occ')                     # bcc occ
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #$c0+pages
    a.far_rel(0x90, 'setc', 'setc')        # bcc setc (too far for rel now)
    if ITEMSG:
        # BEQ on the PREVIOUS cmp would test $12 == FIXED0, and with FIXED_N=1
        # that is the dash code $DF - every dash would land in the item-name
        # branch (verify16: 2688 failures, all on $DF entries, the drawer
        # drawing the name slot pair).  The item code needs its own compare.
        a.hexs('C9 %02X' % ITEM_PREFIX)    # cmp #$de: the item name code
        a.far_rel(0xF0, 'itemmsg', 'im')       # beq itemmsg: a pasted item name
    a.hexs('C9 %02X' % FIXED0)             # DE must be tested BEFORE this lower bound
    a.rel(0x90, 'occ')                     # unused code space
    a.hexs('C9 %02X' % (FIXED0 + FIXED_N))  # cmp #$e0
    a.far_rel(0x90, 'setf', 'setf')        # bcc setf (too far for rel now)
    a.label('occ')
    # A row starts here if the column is zero.  The engine's own font glyphs (the
    # speaker name, the colon) come through this path, so the wipe has to happen
    # here as well or the row would only be wiped once a Chinese glyph joined it.
    a.hexs('AD DF 09')                     # lda $09df (first free queue byte)
    a.hexs('C9 %02X' % (0x101 - 8))        # cmp #$f9: the original drawer stages 8
    a.far_rel(0xB0, 'defer0', 'occr')      # bcs defer0: no room, retry next frame
    a.hexs('AD 6F 03')                     # lda $036f
    a.far_rel(0xD0, 'occ0', 'occ0')        # bne occ0: not the row's first cell
    a.hexs('AD DF 09 C9 %02X' % (0x101 - ROW_WIPE - 8))
                                           # lda $09df / cmp #$89: the row wipe
                                           # plus that 8 byte entry must fit
    a.far_rel(0xB0, 'defer0', 'occw')      # bcs defer0: retry next frame
    a.hexs('AE DF 09')                     # ldx $09df (queue cursor)
    a.hexs('5A')                           # phy (Y is the original drawer's)
    rowwipe(0, 'o')
    rowwipe(0x20, 'o')
    a.hexs('7A')                           # ply
    a.hexs('8E DF 09')                     # stx $09df
    a.label('occ0')
    a.hexs('AD 6F 03 C9 1A')               # lda $036f / cmp #$1a (hook food)
    a.rel(0x90, 'oc1')                     # bcc oc1
    a.long_to(0x01FA7A)                    # jml $03:fa7a: past column 26 is lost,
                                           # exactly like the original drawer
    a.label('oc1')
    a.long_to(0x01FA35)                    # jml $03:fa35 (the original drawer)

    # ---- the code byte: glyph bank and id ------------------------------------
    # A code is [page prefix][id].  Body glyphs have id < SLOTS and take the
    # slot's tile pair; speaker name labels have id >= LABEL_ID0 and take the
    # label's own pair (chosen by the glyph's column), because a label can sit
    # beside any message and must never share tiles with a body glyph.  Both
    # kinds share the same pages: a label's storage cell is id * 64, far above
    # the SLOTS cells a page uses for body glyphs.
    a.label('setc')
    a.hexs('A5 12 38 E9 %02X 18 69 %02X 48'
           % (PREFIX0, POOL_BANK0))        # bank = code - $c0 + $21 -> stack
    a.hexs('AD E9 03 1A A8')               # lda $03e9 / inc a / tay
    a.hexs('B9 EA 03')                     # lda $03ea,y (the glyph id)
    a.hexs('C9 %02X' % SLOTS)              # cmp #SLOTS
    a.rel(0x90, 'gotid')                   # bcc gotid: a body glyph
    a.hexs('C9 %02X' % LABEL_ID0)          # cmp #LABEL_ID0
    a.far_rel(0x90, 'cnbad', 'id')         # bcc cnbad: unused code space
    a.hexs('48')                           # pha: the label glyph id -> stack
    # The pair set follows the label's row: rows close enough to be on screen
    # together differ by one or two, so their sets (row mod LABEL_SETS) differ
    # and a new label never overwrites an old one that is still visible.
    a.hexs('AD 6E 03 AA')                  # lda $036e / tax (the row)
    _tb, _ta = snes_of_rom(E3_ROWSET)
    a.hexs('BF %02X %02X %02X' % (_ta & 0xFF, _ta >> 8, _tb))
                                           # lda $3e:rowset,x -> the set
    a.hexs('0A')                           # asl a: set * LABEL_GLYPHS
    a.hexs('48')                           # pha: the set offset -> stack
    # The speaker's record is always the buffer's first four bytes (measured
    # over a full run: label draws happen at index 0 and 2 only).  Inside that
    # prefix the position comes from the code in front of this one - the two
    # glyphs of a name are two label codes in a row.  A label code past the
    # prefix is a runtime name slot ({E3}-{E9}) holding someone else's record
    # and must not touch a label pair.
    a.hexs('AD E9 03')                     # lda $03e9
    a.hexs('C9 04')                        # cmp #4: the record's own four bytes
    a.rel(0xB0, 'lscr')                    # bcs lscr: past the label's prefix
    a.hexs('38 E9 02')                     # sec / sbc #2 (the previous code)
    a.rel(0x90, 'lpos0')                   # bcc lpos0: nothing in front of it
    a.hexs('A8')                           # tay
    a.hexs('B9 EA 03 C9 %02X' % PREFIX0)   # lda $03ea,y / cmp #PREFIX0
    a.rel(0x90, 'lpos0')                   # bcc lpos0
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #PREFIX0+PAGES
    a.rel(0xB0, 'lpos0')                   # bcs lpos0
    a.hexs('B9 EB 03 C9 %02X' % LABEL_ID0)  # lda $03eb,y / cmp #LABEL_ID0
    a.rel(0x90, 'lpos0')                   # bcc lpos0
    a.hexs('A9 %02X' % (LABEL_GLYPHS - 1))  # lda #LABEL_GLYPHS-1 (the second)
    a.rel(0x80, 'lset')                    # bra lset
    a.label('lpos0')
    a.hexs('A9 00')                        # lda #0 (the name's first glyph)
    a.label('lset')
    a.hexs('18 63 01')                     # clc / adc $01,s (the set offset)
    a.hexs('18 69 %02X AA' % SLOTS)        # clc / adc #SLOTS / tax
    a.hexs('68')                           # pla: drop the set offset again
    a.rel(0x80, 'pairs')                   # bra pairs
    # Another record (a macro copied a name that is not this speaker's) must
    # not land on a label pair: it would overwrite the label's own glyph.  The
    # last body slot's pair takes it - a body glyph is re-uploaded when drawn.
    a.label('lscr')
    # A macro pasted someone else's name here (a {E3}-{F7} slot), so this is not
    # the speaker's label and must not land on a label pair.  It still needs one
    # pair PER GLYPH: sending both glyphs to a single scratch pair made every
    # two-character name come out doubled ("国夫" -> "夫夫"), because the second
    # upload overwrote the first.  The glyph in front of this one says which of
    # the name's two glyphs this is, exactly as in the label path above.
    a.hexs('AD E9 03')                     # lda $03e9
    a.hexs('38 E9 02')                     # sec / sbc #2 (the previous code)
    a.rel(0x90, 'lscr0')                   # bcc lscr0: nothing in front of it
    a.hexs('A8')                           # tay
    a.hexs('B9 EA 03 C9 %02X' % PREFIX0)   # lda $03ea,y / cmp #PREFIX0
    a.rel(0x90, 'lscr0')                   # bcc lscr0
    a.hexs('C9 %02X' % (PREFIX0 + PAGES))  # cmp #PREFIX0+PAGES
    a.rel(0xB0, 'lscr0')                   # bcs lscr0
    a.hexs('B9 EB 03 C9 %02X' % LABEL_ID0)  # lda $03eb,y / cmp #LABEL_ID0
    a.rel(0x90, 'lscr0')                   # bcc lscr0
    a.hexs('A9 %02X' % (LABEL_NAME_GLYPHS - 1))
                                           # lda #1: the name's second glyph
    a.rel(0x80, 'lscr1')                   # bra lscr1
    a.label('lscr0')
    a.hexs('A9 00')                        # lda #0: the name's first glyph
    a.label('lscr1')
    a.hexs('18 69 %02X' % (SLOTS + LABEL_GLYPHS * LABEL_SETS))
                                           # clc / adc #SLOTS + label sets
    a.hexs('AA')                           # tax
    a.hexs('68')                           # pla: drop the set offset (unused:
                                           # a pasted name has no row history)
    a.rel(0x80, 'pairs')                   # bra pairs
    a.label('gotid')
    a.hexs('48')                           # pha: id -> stack
    a.hexs('AA')                           # tax: X = id for the slot table
    a.rel(0x80, 'pairs')                   # bra pairs
    a.label('setf')
    a.hexs('A9 %02X 48' % POOL_BANK0)      # lda #$21 / pha (one byte codes: page 0)
    a.hexs('A5 12 38 E9 %02X' % FIXED0)    # lda $12 / sec / sbc #$dc = id
    a.rel(0x80, 'gotid')                   # bra gotid (push the id, X = id)
    def pushpair(lo_rom, hi_rom):
        """Push the 16 bit tile of pair entry X (low byte table + high byte
        table, both in bank $3e).  Every glyph half takes this path; only the
        label sets live above tile 255, and there the high byte is 1."""
        a.hexs('E2 20')                    # sep #$20: byte loads
        b_, a_ = snes_of_rom(hi_rom)
        a.hexs('BF %02X %02X %02X' % (a_ & 0xFF, a_ >> 8, b_))   # lda $3e:hi,x
        a.hexs('EB')                       # xba: into the high byte of A
        b_, a_ = snes_of_rom(lo_rom)
        a.hexs('BF %02X %02X %02X' % (a_ & 0xFF, a_ >> 8, b_))   # lda $3e:lo,x
        a.hexs('C2 20 48 E2 20')           # rep #$20 / pha: the tile (16 bit),
                                           # then back to the 8 bit M the rest of
                                           # the drawer works in

    a.label('pairs')
    # the right half of a pair sits TABLE_N entries after the left half, and the
    # table carries every label pair set after the body slots
    TABLE_N = (SLOTS + LABEL_GLYPHS * LABEL_SETS
               + LABEL_NAME_GLYPHS * LABEL_NAME_SETS)
    pushpair(E3_SLOTPAIR, E3_SLOTHI)
    pushpair(E3_SLOTPAIR + TABLE_N, E3_SLOTHI + TABLE_N)
    # stack now [bank][id][PA][PA+1][PB][PB+1] with PB on top
    a.label('guard')
    # If this glyph starts a row it carries the row wipe too, so the guard must
    # reserve both.  Column zero and a column at or past the wrap point both mean
    # a row starts (the wrap below turns the second case into column zero).
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xF0, 'gwide')                   # beq gwide: column zero, row wipe too
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'g88')                     # bcc g88: only the glyph is staged
    a.label('gwide')
    a.hexs('AD DF 09 C9 %02X' % (0x101 - ROW_WIPE_CHECK))
                                           # lda $09df / cmp #$39: row wipe plus
                                           # glyph must fit in the queue page
    a.rel(0x80, 'gdone')                   # bra gdone
    a.label('g88')
    a.hexs('AD DF 09 C9 %02X' % (0x101 - GLYPH_COST))
                                           # lda $09df / cmp #$a9
    a.label('gdone')
    a.far_rel(0xB0, 'defer', 'guard')      # bcs defer: no room, retry next frame

    # ---- wrap like the engine's own $F2 handler -----------------------------
    a.label('room')
    a.hexs('AD 6F 03')                     # lda $036f
    a.hexs('C9 %02X' % WRAP_COL)           # cmp #WRAP_COL
    a.rel(0x90, 'nowrap')                  # bcc nowrap (two cells still fit)
    a.hexs('EE 6E 03')                     # inc $036e
    a.hexs('AD 6E 03 C9 10')               # lda $036e / cmp #$10
    a.rel(0x90, 'w1')                      # bcc w1
    a.hexs('9C 6E 03')                     # stz $036e (16 rows wrap)
    a.label('w1')
    a.hexs('9C 6F 03')                     # stz $036f (column 0)
    a.hexs('EE 6D 03 AD 6D 03 C9 03')      # inc $036d / lda $036d / cmp #$03
    a.rel(0x90, 'nowrap')                  # bcc nowrap
    a.hexs('A9 03 8D 6D 03')               # lda #$03 / sta $036d
    a.hexs('AD 73 03 09 20 8D 73 03')      # lda $0373 / ora #$20 / sta $0373
    a.hexs('9C 71 03')                     # stz $0371 (box scroll request)
    a.label('nowrap')

    # ---- the storage offset: id * 64 inside the glyph's bank -----------------
    a.hexs('A3 05')                        # lda $05,s (the glyph id)
    a.hexs('C2 30 29 FF 00')               # rep #$30 / and #$00ff
    for _ in range(6):
        a.hexs('0A')                       # asl x6: id * 64 = the pool offset
    a.hexs('A8')                           # tay
    # Only M is cut to 8 bits here: sep #$30 would clear the high byte of Y and
    # Y = id * 64 (up to 32704 for a label), so every glyph except the first few
    # would be read from bank:$8002.  X is loaded through A instead of ldx.
    a.hexs('E2 20')                        # sep #$20 (M = 8 only)
    a.hexs('A3 06 48 AB')                  # lda $06,s (the glyph bank) / pha / plb
    a.hexs('AD DF 09 C2 20 29 FF 00 AA')   # lda $09df / rep #$20 / and #$00ff / tax
    # X is the queue cursor and Y is id * 64 for the pool reads below, so Y is
    # parked around the wipe.
    a.hexs('AD 6F 03')                     # lda $036f
    a.rel(0xD0, 'norow')                   # bne norow: not the row's first glyph
    a.hexs('5A')                           # phy
    rowwipe(0, 'c')
    rowwipe(0x20, 'c')
    a.hexs('7A')                           # ply
    a.label('norow')

    # ---- left and right half: two 32 byte tile entries ----------------------
    for off in (3, 1):                     # PA then PB (16 bit tiles)
        sload(off)
        a.hexs('0A 0A 0A')                 # asl x3 (base tile * 8 words)
        a.hexs('09 00 60')                 # ora #$6000
        a.hexs('9D 00 0B E8 E8')           # sta $0b00,x (VRAM address), inx inx
        a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep #$20 / lda #$80 / sta / inx
        a.hexs('A9 20 9D 00 0B E8')        # lda #$20 / sta / inx (32 bytes)
        a.hexs('C2 20')                    # rep #$20
        for _ in range(16):                # 16 words = the pair, DBR = pool bank
            a.hexs('B9 00 80 9D 00 0B E8 E8 C8 C8')
    a.hexs('E2 20 A9 03 48 AB')            # sep #$20 / lda #$03 / pha / plb (DBR back)

    # ---- two tile map cells (the original drawer's tail, twice) -------------
    # sep #$30 here: ldy $036e needs an 8 bit index to read a single byte, and Y
    # is not needed any more (id * 64 was only for the pool reads above).  X is
    # the queue cursor, always below 256, so the truncation loses nothing.
    for off, plus in ((3, 0), (1, 1)):     # PA at column c, PB at c+1
        a.hexs('E2 30')                    # sep #$30
        a.hexs('AC 6E 03')                 # ldy $036e (row)
        a.hexs('B9 8E FA 18 6D 6F 03')     # cell address low byte
        if plus:
            a.hexs('1A')                   # inc a: the next column
        a.hexs('9D 00 0B E8')              # sta $0b00,x / inx
        a.hexs('B9 7E FA 69 00 9D 00 0B E8')   # cell address high (carry)
        a.hexs('A9 81 9D 00 0B E8')        # VMAIN $81: the upper and lower cell
        a.hexs('A9 04 9D 00 0B E8')        # count = 4 bytes = two words
        sload(off)                         # M=0
        a.hexs('09 00 24 9D 00 0B E8 E8')  # ora #$2400 / sta / inx inx
        a.hexs('1A 9D 00 0B E8 E8')        # inc a (the pair's second tile) / sta
    a.hexs('8E DF 09')                     # stx $09df

    # ---- bookkeeping --------------------------------------------------------
    a.hexs('E2 20 A5 12 C9 %02X' % FIXED0)   # sep #$20 / lda $12 / cmp #$dc
    a.rel(0xB0, 'noid')                    # bcs noid (one byte code: nothing to eat)
    a.hexs('EE E9 03')                     # inc $03e9 (consume the id byte)
    a.label('noid')
    a.hexs('EE 6F 03')                     # inc $036f ($FA7A adds the second cell)
    a.hexs('C2 20 68 68')                  # rep #$20 / pla x2: PB and PA are
                                           # 16 bit tiles (2 bytes each)
    a.hexs('E2 30 68 68')                  # sep #$30 / pla x2: the id, the bank
    a.long_to(0x01FA7A)                    # jml $03:fa7a (inc $036f / rts)

    # ---- not yet drawable: give the frame back ------------------------------
    # The consumer at $03:eeea calls the drawer and then increments $03e9
    # unconditionally, so the drawer compensates with a decrement: the index
    # comes out unchanged and the code is tried again next frame.  At index 0
    # the decrement must still happen - it wraps to $ff and the consumer's
    # increment brings it back to 0 - because index 0 is the speaker name's
    # first glyph and skipping it would leave the previous name's tiles in
    # place (a stale label).
    a.label('defer')
    a.hexs('AD E9 03')                     # lda $03e9
    a.hexs('3A 8D E9 03')                  # dec a / sta $03e9
    a.hexs('C2 20 68 68')                  # rep #$20 / pla x2 (PB, PA: 16 bit)
    a.hexs('E2 30 68 68')                  # sep #$30 / pla x2 (id, bank)
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)

    # the same retry, for the original drawer's path: nothing was pushed there, so
    # the return address must stay on the stack
    a.label('defer0')
    a.hexs('AD E9 03')                     # lda $03e9
    a.hexs('3A 8D E9 03')                  # dec a / sta $03e9 (wraps at index 0)
    a.hexs('E2 30')                        # sep #$30
    a.long_to(0x01FA7D)                    # jml $03:fa7d (plain rts)

    # ---- id out of range: eat the byte, leave the cells blank ---------------
    a.label('cnbad')
    a.hexs('E2 30 68 68')                  # sep #$30 / pla pla
    a.hexs('EE E9 03')                     # inc $03e9
    a.long_to(0x01FA7A)                    # jml $03:fa7a

    if ITEMSG:
        # the $DE dispatch lands here and never comes back (see build_itemmsg)
        a.label('itemmsg')
        a.long_to(ITEMMSG_ROM)                 # jml $3e:d400
    return a.done()


BAND_DEBUG = os.environ.get('BAND_DEBUG', '0') == '1'


def _band_stub(rom_at):
    """Blank the four map rows above the box (28..31) at the start of every
    drawing sequence.

    The band the user keeps seeing is not only the command window: the engine
    never redraws those rows for a message, so whatever was written there once
    (the window's cells, an option window, anything) stays on screen forever.
    This runs before the text is drawn, so the message and any option window
    that follows simply overwrite the blanked cells again.
    """
    a = Asm(rom_at)
    a.hexs('08 E2 30')                     # php / sep #$30
    if BAND_DEBUG:
        a.hexs('EE F9 0B')                 # inc $0bf9: count the firings
    a.hexs('A9 1C 85 14')                  # lda #28 / sta $14 (first row)
    a.hexs('64 15')                        # stz $15 (rows done)
    a.label('row')
    a.hexs('A9 38')                        # lda #56 (one whole entry)
    a.hexs('22 B6 9A 00')                  # jsl $009ab6 (cursor reset side effect)
    a.hexs('AD DF 09 C9 C1')               # lda $09df / cmp #$f9 - 56
    a.rel(0xB0, 'flush')                   # bcs flush: page full
    a.hexs('C2 20 A5 14 29 FF 00')         # rep #$20 / lda $14 / and #$00ff
    for _ in range(5):
        a.hexs('0A')                       # asl x5: 32 words per map row
    a.hexs('18 69 03 7C')                  # clc / adc #$7c03
    a.hexs('85 16')                        # sta $16
    a.hexs('E2 20 AE DF 09')               # sep #$20 / ldx $09df
    a.hexs('C2 20 A5 16 9D 00 0B E8 E8')   # rep / lda $16 / sta $0b00,x / inx inx
    a.hexs('E2 20 A9 80 9D 00 0B E8')      # sep / lda #$80 / sta / inx
    a.hexs('A9 34 9D 00 0B E8')            # lda #$34 / sta / inx
    a.hexs('C2 20 E2 10 A9 00 2C')         # rep / sep #$10 / lda #$2c00
    a.hexs('A0 1A')                        # ldy #26
    a.label('w')
    a.hexs('9D 00 0B E8 E8')               # sta $0b00,x / inx inx
    a.hexs('88')                           # dey
    a.rel(0xD0, 'w')                       # bne w
    a.hexs('8E DF 09')                     # stx $09df
    a.hexs('E2 20 E6 14 A5 14 29 1F 85 14')   # sep / inc $14 / and #$1f / sta $14
    a.hexs('E6 15 A5 15 C9 04')            # inc $15 / lda $15 / cmp #4
    a.rel(0x90, 'row')                     # bcc row
    a.hexs('28')                           # plp
    a.hexs('AD 74 03 09 80')               # lda $0374 / ora #$80 (the eaten bytes)
    a.long_to(0x01FCCD)                    # jml $03:fccd
    a.label('flush')
    a.hexs('AD 12 42 29 80')               # lda $4212 / and #$80
    a.rel(0xF0, 'flush')                   # beq flush
    a.hexs('22 85 83 00')                  # jsl $008385
    a.jmp_to('row')                        # retry
    return a


STALEROW_STUB = 0x1F4400               # $3E:C400  wipe the stale rows above
# The old delta-row heuristic also erases fresh dialogue after F2 + blank fill.
# Keep it opt-in for A/B diagnostics only; actual row-start/explicit clears remain.
STALEROW_ON = os.environ.get('STALEROW', '0') != '0'


def _stalerow_body(a, extra, tag):
    """Stage one 52 byte queue entry for one map row, address already in A.

    Same shape as _rowwipe, but the row comes from the caller instead of $036e
    and A is reloaded from the stack for the second call."""
    a.hexs('18 69 %02X %02X' % ((0x7C00 + 3 + extra) & 0xFF, (0x7C00 + 3 + extra) >> 8))
    a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx (VRAM address)
    a.hexs('E2 20 A9 80 9D 00 0B E8')  # sep / lda #$80 / sta / inx ($2115)
    a.hexs('A9 34 9D 00 0B E8')        # lda #$34 / sta / inx (52 bytes)
    a.hexs('C2 20 E2 10 A9 00 2C')     # rep / sep #$10 / lda #$2c00
    a.hexs('A0 1A')                    # ldy #26
    a.label('sw%s%02X' % (tag, extra))
    a.hexs('9D 00 0B E8 E8')           # sta $0b00,x / inx inx
    a.hexs('88')                       # dey
    a.rel(0xD0, 'sw%s%02X' % (tag, extra))
    a.hexs('8E DF 09')                 # stx $09df (commit this entry)


def build_stalerow(rom, count_only=False):
    """Wipe the text row above the message's first row, once per message.

    The box keeps the last rows of earlier messages on screen and those cells
    point at pool slots the next message re-uploads, so an old row comes out as
    coloured glyph fragments.  The drawer calls this (JSL) at every row start:
    when the row being drawn is the message's first ($036e == $0391) the row
    above it is stale, one row later ($0391+1) the one above that.  The row is
    only wiped in those two cases, so a message never erases its own text.
    """
    a = Asm(STALEROW_STUB)
    a.hexs('08 DA 5A')                     # php / phx / phy (the drawer's state)
    a.hexs('E2 30')                        # sep #$30
    if count_only:
        a.hexs('EE F9 0B')                 # inc $0bf9
        a.hexs('28 FA 7A')                 # plp / plx / ply
        a.hexs('AD 74 03 09 80')
        a.long_to(0x01FCCD)
        code = a.done()
        rom[STALEROW_STUB:STALEROW_STUB + len(code)] = code
        bk, ad = snes_of_rom(STALEROW_STUB)
        print('stale-row counter: %d bytes at $%02X:%04X' % (len(code), bk, ad))
        return bk, ad
    # Gate: the message's *second* row, and only its first few cells.
    #
    # Measured (hw/seq1.log, 901 frames): while the stale row is on screen the
    # drawer is at $036E = $0391 + 1, and $0391 is the row to blank - at f2592
    # the box held the previous message's line on text row 4 ($0391) and the
    # message being typed on row 5 ($036E).  $0391 is *not* "the message's
    # first row": it changed once in 901 frames (f2711, 04 -> 05), not once per
    # message.  The old delta-0 gate therefore never fired while the stale row
    # was visible, and when it did fire it wiped a row still in use.
    #
    # The columns are the first few of that row.  At column 0 the drawer has
    # just staged its own row wipe (112 bytes) and its glyph, so nothing fits
    # beside it; from column 1 on it stages only its glyph (88 bytes).  Four
    # columns give four chances, because whether the page has room depends on
    # where in the frame the row happens to be drawn.
    a.hexs('AD 6E 03 38 ED 91 03 29 0F')   # lda $036e / sec / sbc $0391 / and #$0f
    a.hexs('C9 01')                        # cmp #$01
    a.far_rel(0xD0, 'out', 'sra')          # bne out: not the message's second row
    a.hexs('AD 6F 03 C9 01')               # lda $036f / cmp #$01
    a.far_rel(0x90, 'out', 'srb')          # bcc out: column 0
    a.hexs('C9 05')                        # cmp #$05
    a.far_rel(0xB0, 'out', 'src')          # bcs out: column 5 or beyond
    # Room for our 112 bytes *and* the glyph the drawer is about to stage, or it
    # would spend the next frame deferring and the wipe would fire again on the
    # retry.  v14 drove the engine's flusher from here when the page was full and
    # the machine came up with the whole screen garbled - the drawer does not run
    # in VBlank, so that is not the flusher's contract.  Skipping only costs the
    # wipe.  The room test runs before the row is pushed, so the skip leaves the
    # stack balanced.
    # the stub stages ROW_WIPE bytes (two 56 byte entries), not twice that:
    # the old check reserved 2 * ROW_WIPE and so skipped far more often
    # than it had to
    a.hexs('AD DF 09 C9 %02X' % (0x101 - ROW_WIPE - GLYPH_COST))
    a.far_rel(0xB0, 'out', 'srr')          # bcs out: no room, leave the row stale
    # Two rows, one per column pair: columns 1 and 2 blank $0391, columns 3 and
    # 4 blank $0391-1.  The previous message can be two lines long (the user's
    # screenshot shows two rows of fragments above a one-line box), and the
    # current message lives at $0391+1 and below, so both rows are safe to
    # blank.  One row per call keeps the entry inside the queue page.
    a.hexs('AD 91 03 38 E9 01 29 0F')      # lda $0391 / sec / sbc #$01 / and #$0f
    a.hexs('85 14')                        # sta $14: the row for columns 3, 4
    a.hexs('AD 6F 03 C9 03')               # lda $036f / cmp #$03
    a.rel(0x90, 'r1')                      # bcc r1: columns 1, 2 -> $0391
    a.hexs('A5 14')                        # lda $14: columns 3, 4 -> $0391-1
    a.rel(0x80, 'r2')
    a.label('r1')
    a.hexs('AD 91 03 29 0F')               # lda $0391 / and #$0f
    a.label('r2')
    a.hexs('48')                           # pha: keep the row for the second half
    a.hexs('AE DF 09')                     # ldx $09df
    a.hexs('E2 20 68 48 C2 20')            # sep #$20 / pla / pha / rep: the row
                                           # back into A, one byte at a time
    a.hexs('29 FF 00')                     # and #$00ff
    for _ in range(6):
        a.hexs('0A')                       # asl x6: 64 words per text row
    _stalerow_body(a, 0, 'o')
    a.hexs('E2 20 68 48 C2 20')            # sep / pla / pha / rep: the row again
    a.hexs('29 FF 00')
    for _ in range(6):
        a.hexs('0A')
    _stalerow_body(a, 0x20, 'o')
    a.hexs('E2 20 68')                     # sep #$20 / pla (8 bit!)
    a.label('out')
    a.hexs('FA 7A 28')                     # plx / ply / plp
    a.hexs('6B')                           # rtl
    code = a.done()
    rom[STALEROW_STUB:STALEROW_STUB + len(code)] = code
    bk, ad = snes_of_rom(STALEROW_STUB)
    print('stale-row stub: %d bytes at $%02X:%04X' % (len(code), bk, ad))
    return bk, ad



def _menuclose_stub(rom_at, replay, ret, tag):
    """One copy of the row blanking stub: wipe the four map rows the command
    window wrote, then replay the instructions its hook ate and jump back.

    The rows come from $0BFB (base | $80, written when the menu opened), so the
    stub never has to guess them from the registers.  Each row is one 56 byte
    queue entry -- 52 blank cells at columns 3..28 -- and if the page is full
    the stub waits for VBlank and drives the engine's own flusher, exactly like
    the menu open hook does.
    """
    a = Asm(rom_at)
    a.hexs('08 E2 30')                     # php / sep #$30
    a.hexs('AD %02X %02X' % (MENUPEND & 0xFF, MENUPEND >> 8))
    a.rel(0xF0, 'out' + tag)               # beq out: nothing pending
    a.hexs('29 1F 85 14')                  # and #$1f / sta $14 (first row)
    a.hexs('64 15')                        # stz $15 (rows done)
    a.label('row' + tag)
    a.hexs('A9 38')                        # lda #56: one whole entry, header
    a.hexs('22 B6 9A 00')                  # jsl $009ab6 -- only for its side
                                           # effect (it clears both cursors once
                                           # the page has drained); its result is
                                           # an 8 bit sum that wraps, and it
                                           # always clears carry, so the room
                                           # check below is ours
    a.hexs('AD DF 09 C9 C1')               # lda $09df / cmp #$f9 - 56
    a.rel(0xB0, 'flush' + tag)             # bcs flush: no room, empty it first
    a.hexs('C2 20 A5 14 29 FF 00')         # rep #$20 / lda $14 / and #$00ff
    for _ in range(5):
        a.hexs('0A')                       # asl x5: 32 words per map row
    a.hexs('18 69 03 7C')                  # clc / adc #$7c03 (map base + col 3)
    a.hexs('85 16')                        # sta $16
    a.hexs('E2 20 AE DF 09')               # sep #$20 / ldx $09df
    a.hexs('C2 20 A5 16 9D 00 0B E8 E8')   # rep #$20 / lda $16 / sta $0b00,x / inx inx
    a.hexs('E2 20 A9 80 9D 00 0B E8')      # sep #$20 / lda #$80 ($2115) / sta / inx
    a.hexs('A9 34 9D 00 0B E8')            # lda #$34 (52 bytes) / sta / inx
    a.hexs('C2 20 E2 10 A9 00 2C')         # rep #$20 / sep #$10 / lda #$2c00
    a.hexs('A0 1A')                        # ldy #26 cells
    a.label('w' + tag)
    a.hexs('9D 00 0B E8 E8')               # sta $0b00,x / inx inx
    a.hexs('88')                           # dey
    a.rel(0xD0, 'w' + tag)                 # bne w
    a.hexs('8E DF 09')                     # stx $09df (commit)
    a.hexs('E2 20 E6 14 A5 14 29 1F 85 14')   # sep / inc $14 / and #$1f / sta $14
    a.hexs('E6 15 A5 15 C9 04')            # inc $15 / lda $15 / cmp #$04
    a.rel(0x90, 'row' + tag)               # bcc row
    a.hexs('9C %02X %02X' % (MENUPEND & 0xFF, MENUPEND >> 8))   # stz $0bfb
    a.label('out' + tag)
    a.hexs('28')                           # plp: back to the caller's widths
    a.hexs(replay)                         # the instructions the hook ate
    a.long_to(ret)                         # jml back into bank $03
    a.label('flush' + tag)
    a.hexs('AD 12 42 29 80')               # lda $4212 / and #$80 (in VBlank?)
    a.rel(0xF0, 'flush' + tag)             # beq flush: not yet
    a.hexs('22 85 83 00')                  # jsl $008385: empty the queue
    a.jmp_to('row' + tag)                  # retry the same row
    return a


def _menuclose_arm(rom_at):
    """Arm the pending row wipe when the menu opens.

    Hooked on the menu script's setup step ($03:F72E), right after it has put
    ($0391 - 2) & $0f into $036E: the window is drawn at the two text rows
    $036E and $036E + 1, and text row k lives at map rows (k & 1) ? 2k-2 : 2k+2,
    so the pair starts at map row 2*$036E and covers four consecutive rows.  The
    byte is base | $80 -- bit 7 says a wipe is pending, 0 says there is none.
    """
    a = Asm(rom_at)
    a.hexs('08 E2 20')                     # php / sep #$20 (A is a byte here)
    a.hexs('AD 6E 03 0A 29 1F 09 80 8D %02X %02X'
           % (MENUPEND & 0xFF, MENUPEND >> 8))   # lda $036e / asl / and #$1f
                                                 # / ora #$80 / sta $0bfb
    if CMDWIN == 2:
        # and arm the label uploader: 1 means "start from the first glyph"
        a.hexs('A9 01 8D %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.hexs('28')                           # plp
    a.hexs('9C 9E 03 EE 92 03')            # stz $039e / inc $0392 (the eaten bytes)
    a.long_to(0x01F734)                    # jml $03:f734
    return a


def build_menuload(rom, table):
    """Stage the command window's label glyphs into the upload queue.

    Armed by the menu's own open step (build_menuclose's arming stub) and driven
    from the state dispatcher at $03:F0F8, which runs every frame the menu is
    open.  Each call copies up to three glyphs from the pool to the slot tiles
    the label codes name; the queue's VBlank flusher does the VRAM writes, so
    nothing here touches the VRAM ports.  Ten glyphs therefore land in four
    frames, which the player cannot see.

    The per-glyph record is [vram addr of t][vram addr of u][pool addr][pool
    bank]; the second 32 bytes of the glyph come from pool addr + 32.
    """
    nglyph = len(table) // 7
    a = Asm(MENU_STUB)
    a.hexs('08 E2 30')                     # php / sep #$30
    a.hexs('AD %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.far_rel(0xF0, 'out', 'none')         # beq out: nothing pending
    a.hexs('64 14')                        # stz $14: glyphs staged this call
    a.label('next')
    a.hexs('AD %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.hexs('3A')                           # dec a -> 0 based glyph index
    a.hexs('C9 %02X' % nglyph)
    a.far_rel(0xB0, 'done', 'all')         # bcs done: all of them staged
    a.hexs('85 15')                        # sta $15
    # room for both entries (2 x 36 bytes) or leave it to the next frame
    a.hexs('AD DF 09 C9 %02X' % (0x101 - 72))
    a.far_rel(0xB0, 'out', 'room')         # bcs out: no room, retry next frame
    # the table offset = index * 7
    a.hexs('A5 15 0A 0A 0A 38 E5 15')      # lda $15 / asl x3 / sec / sbc $15
    a.hexs('AA')                           # tax
    # the table lives in the stub's own bank: the operand is the CPU address,
    # $8000 + the low half of the ROM offset (not the offset's own bytes)
    tab_cpu = 0x8000 + (MENU_TAB & 0x7FFF)
    for k, dst in enumerate(('1A', '1B', '1C', '1D', '16', '17', '18')):
        ad = tab_cpu + k
        a.hexs('BF %02X %02X %02X' % (ad & 0xFF, ad >> 8, MENU_TAB >> 15))
        a.hexs('85 %s' % dst)
    for half, (lo, hi) in enumerate((('1a', '1b'), ('1c', '1d'))):
        a.hexs('A5 %s 85 1E' % lo)         # lda addr lo / sta $1e (the header word)
        a.hexs('A5 %s 85 1F' % hi)         # lda addr hi / sta $1f
        a.hexs('AE DF 09')                 # ldx $09df
        a.hexs('A5 1E 9D 00 0B E8')        # lda $1e / sta $0b00,x / inx
        a.hexs('A5 1F 9D 00 0B E8')        # lda $1f / sta / inx
        a.hexs('A9 80 9D 00 0B E8')        # lda #$80 ($2115) / sta / inx
        a.hexs('A9 20 9D 00 0B E8')        # lda #32 (bytes) / sta / inx
        # 16 words per entry (32 bytes, what the header says): the first half
        # from the glyph's offset 0, the second from offset 32
        a.hexs('C2 30 A0 %02X 00' % (0 if half == 0 else 32))   # rep #$30: M and
                                           # X both 16 bit, or the 16 bit Y
                                           # immediates desync the program counter
        a.label('w%d' % half)
        a.hexs('B7 16 9D 00 0B E8 E8 C8 C8')
        a.hexs('C0 %02X 00' % (32 if half == 0 else 64))
        a.rel(0x90, 'w%d' % half)          # bcc w
        a.hexs('E2 30 8E DF 09')           # sep #$30 / stx $09df: X must be 8
                                           # bit or this writes $09e0 too
    a.hexs('E6 14')                        # inc $14
    a.hexs('EE %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.hexs('A5 14 C9 03')                  # lda $14 / cmp #3
    a.far_rel(0x90, 'next', 'three')       # bcc next: three per frame is enough
    a.jmp_to('out')
    a.label('done')
    a.hexs('9C %02X %02X' % (MENU_LOAD & 0xFF, MENU_LOAD >> 8))
    a.label('out')
    a.hexs('28')                           # plp
    a.hexs('AC 9A 03 B9 51 F8')            # the two instructions the hook ate:
                                           # ldy $039a / lda $f851,y
    a.long_to(0x01F847)                    # jml back into that routine
    code = a.done()
    for lo, hi, what in ((STALEROW_STUB, STALEROW_STUB + 0x100, 'stale-row stub'),
                         (MENUCLOSE_STUB, MENUCLOSE_STUB + 0x400, 'menu close stubs'),
                         (CODE_ROM, CODE_ROM + 0x200, 'the drawer'),
                         (DISPATCH_ROM, DISPATCH_ROM + 0x400, 'the dispatch')):
        assert MENU_STUB >= hi or MENU_STUB + len(code) <= lo,             'the uploader overlaps %s' % what
        assert MENU_TAB >= hi or MENU_TAB + len(table) <= lo,             'the uploader table overlaps %s' % what
    rom[MENU_STUB:MENU_STUB + len(code)] = code
    rom[MENU_TAB:MENU_TAB + len(table)] = table
    bk, ad = snes_of_rom(MENU_STUB)
    print('menu label uploader: %d bytes at $%02X:%04X, %d glyphs, table %d bytes'
          % (len(code), bk, ad, nglyph, len(table)))
    return bk, ad


def build_menuclose(rom):
    """Blank the four text rows the command window wrote, when it closes.

    The window's cells stay in the box's tile map after the menu is put away,
    and the map rows that end up outside the box (the strip just above it) keep
    showing them -- the coloured band.  Two hooks push blanking entries through
    the engine's own upload queue: the menu's close step ($03:F85B) and, as a
    fallback, the end of a drawing sequence ($03:F700).  Which rows to clear is
    decided when the menu opens (see _menuclose_arm).
    """
    # The $F700 site is deliberately *after* its `jsr $f8b2`: that call is
    # bank relative, and this stub runs with PBR = $3E, so replaying it there
    # would call into the wrong bank.  $F706 is all absolute addressing.
    sites = ((MENUCLOSE_STUB, 'EE C1 03 EE C1 03 EE 9E 03', 0x01F864, 'a'),
             (MENUCLOSE_STUB2, '29 EF 8D 74 03', 0x01F70B, 'b'))
    for rom_at, replay, ret, tag in sites:
        a = _menuclose_stub(rom_at, replay, ret, tag)
        code = a.done()
        rom[rom_at:rom_at + len(code)] = code
        assert a.lab['out' + tag] - 2 <= 127, (tag, a.lab)
        assert a.lab['flush' + tag] - 2 <= 127, (tag, a.lab)
        assert a.lab['row' + tag] < a.lab['flush' + tag]
        bk, ad = snes_of_rom(rom_at)
        site = MENUCLOSE_SITE if tag == 'a' else MENUCLOSE_SITE2
        want = (bytes([0xEE, 0xC1, 0x03, 0xEE, 0xC1]) if tag == 'a'
                else bytes([0x29, 0xEF, 0x8D, 0x74, 0x03]))
        assert rom[site:site + 5] == want, rom[site:site + 6].hex(' ')
        rom[site:site + 5] = bytes([0x5C, ad & 0xFF, ad >> 8, bk, 0xEA])
        print('menu close: %d byte stub at $%02X:%04X for $%04X' % (len(code), bk, ad, site))

    a = _band_stub(MENUCLOSE_STUB4)
    code = a.done()
    rom[MENUCLOSE_STUB4:MENUCLOSE_STUB4 + len(code)] = code
    bk, ad = snes_of_rom(MENUCLOSE_STUB4)
    assert rom[BAND_SITE:BAND_SITE + 5] == bytes([0xAD, 0x74, 0x03, 0x09, 0x80]),         rom[BAND_SITE:BAND_SITE + 6].hex(' ')
    rom[BAND_SITE:BAND_SITE + 5] = bytes([0x5C, ad & 0xFF, ad >> 8, bk, 0xEA])
    print('band wipe: %d byte stub at $%02X:%04X for $%04X' % (len(code), bk, ad, BAND_SITE))

    a = _menuclose_arm(MENUCLOSE_STUB3)
    code = a.done()
    rom[MENUCLOSE_STUB3:MENUCLOSE_STUB3 + len(code)] = code
    bk, ad = snes_of_rom(MENUCLOSE_STUB3)
    assert rom[ARM_SITE:ARM_SITE + 5] == bytes([0x9C, 0x9E, 0x03, 0xEE, 0x92]), \
        rom[ARM_SITE:ARM_SITE + 6].hex(' ')
    rom[ARM_SITE:ARM_SITE + 5] = bytes([0x5C, ad & 0xFF, ad >> 8, bk, 0xEA])
    print('menu close: %d byte arm stub at $%02X:%04X for $%04X' % (len(code), bk, ad, ARM_SITE))


def build_sanitize():
    """A macro may copy a raw byte out of the record table; $C5-$CF inside a
    record would be decoded as a Chinese prefix and swallow the next byte."""
    a = Asm(B3_SANITIZE)
    a.op(0xC9, PREFIX0)                  # CMP #$C5
    a.rel(0x90, 'store')
    a.op(0xC9, PREFIX0 + PAGES)          # CMP #$D0
    a.rel(0xB0, 'store')
    a.op(0xA9, 0xF1)                     # LDA #$F1 (harmless control code)
    a.label('store')
    a.op(0x9D, 0xEA, 0x03)               # STA $03EA,X
    a.op(0x60)                           # RTS
    return a.done()


# ====================================================================== build
def main():
    tr = json.load(open(BASE + '/cn_translation.json', encoding='utf-8'))
    textrecs = json.load(open(BASE + '/kuniokun_text.json', encoding='utf-8'))

    # ---- 1. reflow translations, then force the original control structure
    # The engine walks messages by counting $F2 bytes and every loader copies
    # until the first $F2, so the control-token sequence per entry must be
    # exactly the original's.  align_tokens() restores any token my translation
    # dropped (mainly the trailing {F2F3}) and re-distributes my prose between
    # the original tokens.
    orig_text = {'%06X' % r['text_rom_off']: r['text'] for r in textrecs}
    tbl_of = {'%06X' % r['text_rom_off']: r['table_rom_off'] for r in textrecs}
    fixed = {}
    stats = {'max_col': 0, 'max_row': 0, 'changed': 0, 'aligned': 0, 'wrapped': 0,
             'skipped': 0}
    for k, v in tr.items():
        if tbl_of.get(k) in NO_TRANSLATE:
            stats['skipped'] += 1
            continue
        # No line splitting before align_tokens(): a break inserted here is a
        # segment boundary for align_tokens(), which then drops the original's
        # trailing {F2F3} into the middle of the sentence -- and the loader stops
        # at the first $F3, so everything behind it is never read.  wrap_segments()
        # adds the in-box breaks after alignment instead ({F2F6} continues the).
        w = v
        if reflow(v) != v:
            stats['changed'] += 1
        a = align_tokens(orig_text[k], w)
        if a != w:
            stats['aligned'] += 1
        # Chinese glyphs are two cells wide, so lines that were fine with kana are
        # now too wide.  Storing a {F2F6} for each of them costs two bytes and we do
        # not have the room, so the drawer wraps those lines at run time instead (it
        # replays the F2 handler when a Chinese glyph would land past column 25).
        # wrap_segments() is still applied to count how many entries rely on that.
        b = wrap_segments(a)
        if b != a:
            stats['wrapped'] += 1
        fixed[k] = a
    for k, v in fixed.items():
        assert (tokens(v) == tokens(orig_text[k])
                or [t for t in tokens(v) if t != 'F2F6']
                == [t for t in tokens(orig_text[k]) if t != 'F2F6']), \
            (k, tokens(v), tokens(orig_text[k]))
        for p in v.split('{F2F4}'):
            lines = p.split('{F2F6}')
            stats['max_row'] = max(stats['max_row'], len(lines))
            for l in lines:
                stats['max_col'] = max(stats['max_col'], ncells(l))
    # Every byte behind the first $F3 of an entry is dead: the line loader stops
    # there and the message driver moves on.  Prose must never sit there.
    lost = []
    for k, v in fixed.items():
        img = bytearray()
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', v):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                img += bytes.fromhex(h)
            else:
                img += b'\x01' * len(part)      # one marker byte per prose char
        i = img.find(b'\xf3')
        if i >= 0 and img[i + 1:].count(1):
            lost.append((k, bytes(img[i + 1:]).count(1)))
    assert not lost, ('text behind the entry terminator would never be read', lost[:10])

    # The run-time wrapper only triggers on Chinese codes: for every entry check
    # that each line's overflow happens on a Chinese glyph, otherwise the original
    # drawer would drop the rest of that line.
    at_risk = []
    for k, v in fixed.items():
        col = 0
        for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', v):
            if not part:
                continue
            m = TOKEN.fullmatch(part)
            if m:
                h = m.group(1)
                if len(h) & 1:
                    h = '0' + h
                bb = bytes.fromhex(h)
                if bb[0] == 0xF2:
                    col = 0                # newline / page break
                else:
                    col += cells_of_token(part)
                continue
            for ch in part:
                w = 1 if (ch == ' ' or ch in KEEP1) else 2
                if col + w > WRAP_COL + 1 and w == 1:
                    at_risk.append((k, ch, col))
                    break
                col += w
    if at_risk:
        print('   lines that overflow on a single-byte code: %d %s'
              % (len(at_risk), at_risk[:6]))

    # width measured per prose run (between control tokens), which is what the
    # box actually shows on one line
    over = []
    for k, v in fixed.items():
        for seg in re.split(r'\{[0-9A-Fa-f]{2,4}\}', v):
            if ncells(seg) > MAX_COL:
                over.append((k, ncells(seg)))
    print('text: %d strings reflowed; %d aligned to the original control codes; '
          '%d needed extra line breaks; widest prose run %d cells, tallest page %d lines, '
          '%d runs wider than the box; %d left in Japanese (item window)'
          % (stats['changed'], stats['aligned'], stats['wrapped'], stats['max_col'],
             stats['max_row'], len(over), stats['skipped']))
    if over:
        print('   too wide: %s' % over[:10])

    # ---- 1b. characters that still have a single-byte code keep it: they cost
    #          one byte instead of two and their tiles get protected, which is
    #          what makes the text fit the original regions
    _res = NEVER_KEEP & untranslated_codes()
    assert not _res, ('reserved codepoints appear in untranslated text: %s'
                      % sorted(_res))
    added = derive_keep1(fixed.values())

    # the dead codes $d2..$d2+n-1 become one byte codes for the most frequent
    # Chinese characters: 2 bytes per occurrence is what outgrows bank $03
    cnt = {}
    for t in fixed.values():
        for part in re.split(r'\{[0-9A-Fa-f]{2,4}\}', t):
            for ch in part:
                if ch != ' ' and ch not in KEEP1:
                    cnt[ch] = cnt.get(ch, 0) + 1
    top = [c for c, n in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:FIXED_N]]
    FIXED_CODES.clear()
    FIXED_CODES.update({ch: FIXED0 + i for i, ch in enumerate(top)})
    print('one byte codes: %s (%d occurrences)'
          % (' '.join('%s=%02X' % (c, FIXED_CODES[c]) for c in top),
             sum(cnt[c] for c in top)))

    def _len_with(keepset):
        n = 0
        for t in fixed.values():
            for part in re.split(r'(\{[0-9A-Fa-f]{2,4}\})', t):
                m = TOKEN.fullmatch(part)
                if m:
                    h = m.group(1)
                    if len(h) & 1:
                        h = '0' + h
                    n += len(bytes.fromhex(h))
                else:
                    for ch in part:
                        n += 1 if (ch == ' ' or ch in keepset) else 2
        return n

    if os.environ.get('CHARSTAT'):
        cnt = {}
        for t in fixed.values():
            for part in re.split(r'\{[0-9A-Fa-f]{2,4}\}', t):
                for ch in part:
                    if ch != ' ' and ch not in KEEP1:
                        cnt[ch] = cnt.get(ch, 0) + 1
        top = sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))
        print('CN chars: %d distinct, %d occurrences total'
              % (len(cnt), sum(cnt.values())))
        print('  top 20: %s' % ' '.join('%s%d' % (c, n) for c, n in top[:20]))
        cum = 0
        for k in (8, 14, 20, 30, 40, 53):
            cum = sum(n for _, n in top[:k])
            print('  saving if the %d most frequent get a one byte code: %d bytes'
                  % (k, cum))
    if os.environ.get('KEEP1_OLD'):
        _old = {ch: c for ch, c in json.load(open(BASE + '/params_old53.json'))['keep1'].items()}
        print('byte length with old keep1 (%d chars): %d ; with new (%d chars): %d'
              % (len(_old), _len_with(_old), len(KEEP1), _len_with(KEEP1)))
    save = sum(sum(t.count(ch) for t in fixed.values()) for ch in added)
    global SLOTS, PAGES

    global STATUS_LITERAL_TILES
    STATUS_LITERAL_TILES = status_literal_tiles()
    print('status script literal tiles reserved: %s'
          % sorted('%02X' % t for t in STATUS_LITERAL_TILES))
    # Resolve these here, before the code blobs are built: build_labeldrawer()
    # emits the restore from them, and status_labels() only runs later.
    global LITERAL_TILES_RESTORE, STATUS_FIRST_TEXT
    _blk, _u = status_script_blocks()
    STATUS_FIRST_TEXT = next(vm for vm, _c, k, _v, _o in _blk if k == 'text')
    print('prompt tiles reserved: %s' % fix_prompt_tiles())
    LITERAL_TILES_RESTORE = literal_tiles_to_restore()
    print('keep1: %d characters reuse original codes (%d bytes saved); '
          '%d glyph slots available' % (len(added), save, SLOTS))
    print('   %s' % ''.join(sorted(added)))

    # ---- 1c. the item names' own 8x16 glyph table
    # One id per distinct hanzi, in the order the names are stored, so the ids
    # are stable across builds as long as the translations do not change.
    for ch in status_label_hanzi():
        if ch not in ITEM_CHARS:
            ITEM_CHARS[ch] = len(ITEM_CHARS)
    for r in sorted([r for r in textrecs if r['table_rom_off'] == ITEM_TABLE],
                    key=lambda r: r['index']):
        for ch in re.sub(r'\{[0-9A-Fa-f]{2,4}\}', '',
                         fixed['%06X' % r['text_rom_off']]):
            if ch == ' ' or ch.isdigit() or ch in KEEP1 or ch in FIXED_CODES:
                continue
            if ch not in ITEM_CHARS:
                ITEM_CHARS[ch] = len(ITEM_CHARS)
    assert len(ITEM_CHARS) <= ITEM_GLYPH_MAX, len(ITEM_CHARS)
    print('item names: %d distinct hanzi -> 8x16 table at $%02X:8000'
          % (len(ITEM_CHARS), ITEM_GLYPH_BANK))

    assert open(SRC_ROM, 'rb').read()[0x100000:0x108000] == bytes(0x8000), 'new pool bank is occupied in baseline'

    # ---- 2. colouring windows
    per_table = {}
    for ti, (table_off, count) in enumerate(TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        assert len(recs) == count, (hex(table_off), len(recs), count)
        if table_off in NO_TRANSLATE or table_off == ITEM_TABLE:
            per_table[ti] = []          # the item names take no pool slot:
            continue                    # their renderer picks one at run time
        per_table[ti] = [glyphs_of(fixed['%06X' % r['text_rom_off']]) for r in recs]
    windows = []
    enc, windows, win_main, win_list = choose_windows(per_table)
    print('colouring: windows main=%d list=%d, %d windows, widest %d glyphs, '
          '%d distinct glyphs'
          % (win_main, win_list, len(windows), max(len(w) for w in windows),
             len(set().union(*windows))))
    PAGES = max(1, -(-(len(enc.slot) - FIXED_N) // max(1, SLOTS - FIXED_N)))
    while True:
        if POOL_ROM + PAGES * 0x8000 > CODE_ROM or PREFIX0 + PAGES > ITEM_PREFIX:
            raise SystemExit('glyph pool overlaps code bank or item prefix')
        try:
            enc.pack_pool()
            break
        except SystemExit:
            PAGES += 1
            if PAGES > CODE_BUDGET:
                raise SystemExit(
                    'not enough codepoints: %d pages > %d '
                    '($%02X..$%02X); %d glyphs, %d slots'
                    % (PAGES, CODE_BUDGET, PREFIX0, FIXED0 - 1,
                       len(enc.slot), SLOTS))
            enc.cell, enc.order = {}, []
    assert PREFIX0 + PAGES <= FIXED0, (hex(PREFIX0 + PAGES), hex(FIXED0))
    print('glyph slots: %d distinct, %d stored in %d pages of %d slots '
          '(codes $%02X..$%02X, one byte $%02X..$DF)'
          % (len(enc.slot), len(enc.order), PAGES, SLOTS,
             PREFIX0, PREFIX0 + PAGES - 1, FIXED0))

    # ---- 3. encode + pack into the free space of bank $03
    # Every entry has its own pointer, so the text may live anywhere in bank $03;
    # the five pointer tables only sit interleaved between the five text regions,
    # and the packer simply skips them.  Entries whose bytes are identical share
    # one copy (the engine always walks from the pointer to the first $F2, so the
    # stored length is not part of the format).
    addr_of = {}
    _tot = [0]
    missing = []
    shared = {}
    # regions of tables that keep their original text are not ours to fill
    active = [(s_, min(e_, B3_SANITIZE_END))
              for s_, e_ in REGIONS
              if dict(zip([r[0] for r in REGIONS], [t for t, c in TABLES]))[s_]
              not in NO_TRANSLATE]
    chunks = {s: bytearray() for s, e in active}
    fit = {s_: s_ for s_, e_ in active}      # next free offset per region
    si, cur = 0, active[0][0]
    per_table = {}
    for ti, (table_off, count) in enumerate(TABLES):
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        if table_off in NO_TRANSLATE:
            per_table[table_off] = (0, count)
            continue
        used = 0
        for r in recs:
            key = '%06X' % r['text_rom_off']
            if key not in fixed:
                missing.append(key)
                addr_of[key] = None
                continue
            b = bytes(enc.encode_item(fixed[key]) if table_off == ITEM_TABLE
                      else enc.encode(fixed[key]))
            if os.environ.get('ENC_TOTAL'):
                _tot[0] += len(b)
            if b in shared:
                addr_of[key] = shared[b]
                continue
            # first fit over every active region: entries only need *some*
            # address in bank $03 (each has its own pointer), so a region whose
            # tail is too small for this entry must not block it
            target = None
            for s_, e_ in active:
                if fit[s_] + len(b) <= e_:
                    target = s_
                    break
            if target is None:
                print('capacity report: active=%s' % [(hex(s_), hex(e_), e_ - s_)
                                                      for s_, e_ in active])
                print('  packed so far: %s total=%d'
                      % ([(hex(k), len(v)) for k, v in chunks.items()],
                         sum(len(v) for v in chunks.values())))
                print('  per table: %s' % {hex(k): v for k, v in per_table.items()})
                raise SystemExit('text does not fit the bank $03 text space '
                                 '(entry %s, %d bytes)' % (key, len(b)))
            addr_of[key] = fit[target]
            shared[b] = fit[target]
            chunks[target] += b
            fit[target] += len(b)
            used += len(b)
        per_table[table_off] = (used, count)
    if os.environ.get('ENC_TOTAL'):
        print('encoded text (each entry, before sharing): %d bytes' % _tot[0])
    if missing:
        raise SystemExit('%d untranslated strings, e.g. %s' % (len(missing), missing[:5]))
    for (start, end), (table_off, count) in zip(REGIONS, TABLES):
        if table_off in NO_TRANSLATE:
            print('  table 0x%06X: left in Japanese (%d entries, %d bytes)'
                  % (table_off, count, end - start))
            continue
        print('  table 0x%06X: %5d bytes packed, %4d bytes used of %5d (%d entries)'
              % (table_off, per_table[table_off][0], len(chunks[start]), end - start,
                 count))
    total = sum(len(c) for c in chunks.values())
    cap = sum(e - s for s, e in active)
    print('encoded text: %d bytes (capacity %d, %d free)'
          % (total, cap, cap - total))
    if active[-1][0] + len(chunks[active[-1][0]]) > B3_SANITIZE:
        raise SystemExit('status text would run into the sanitizer')
    json.dump({k: v for k, v in addr_of.items() if v is not None},
              open(BASE + '/cn_addr_map.json', 'w'), indent=0)
    json.dump({'%s' % k: v for k, v in enc.cell.items()},
              open(BASE + '/cn_glyph_cell.json', 'w'), indent=0)
    # final build parameters, so that verify5.py reproduces the exact same
    # encoder state (KEEP1 / SLOTS / PAGES are decided inside this function)
    json.dump({'keep1': {'%s' % ch: c for ch, c in KEEP1.items()},
               'slots': SLOTS, 'pages': PAGES, 'prefix0': PREFIX0,
               'pool_rom': POOL_ROM, 'pool_bank0': POOL_BANK0,
               'menu_list': True, 'menu_list_rom': 0x1F6000, 'menu_item_glyph_rom': ITEM_MENU_GLYPH_ROM, 'menu_item_width': 2,
               'glyphs': len(enc.order),
               'stride': POOL_STRIDE,
               'wrap_col': WRAP_COL,
               'no_translate': sorted(NO_TRANSLATE),
               'protect_groups': sorted(PROTECT_GROUPS),
               'prompt_clobbered': sorted(PROMPT_CLOBBERED),
               'stalerow': bool(STALEROW_ON),
               'cmdwin': int(CMDWIN),
               'hud_orig': bool(HUD_ORIG),
               'hudfix': bool(HUDFIX), 'hud_bar_shared': bool(HUDFIX),
               'hud_pairs': hud_pairs(), 'hud_top_first': True, 'hud_pair_rom': HUDPAIR_ROM,
               'itemsg': bool(ITEMSG), 'pace': PACE, 'pace_counter': PACE_FRAMES,
               'label_sets': LABEL_SETS, 'label_name_glyphs': LABEL_NAME_GLYPHS,
               'fixed': {k: v for k, v in FIXED_CODES.items()},
               'fixed0': FIXED0,
               'fixed_n': FIXED_N,
               'cell': {'%s' % k: v for k, v in enc.cell.items()},
               'item_chars': {'%s' % k: v for k, v in ITEM_CHARS.items()}},
              open(BASE + '/cn_build_params.json', 'w'), indent=0)

    # ---- 4. write the ROM
    rom = bytearray(open(SRC_ROM, 'rb').read())
    assert len(rom) == 0x200000

    if os.environ.get('BASE_ONLY') == '1':
        # Layer-coverage build: skip every layer and land back on the baseline -
        # which is the original ROM plus the 2 MB padding and the header, so the
        # checksum path below reproduces it byte for byte.  check_layers.py
        # diffs this against the original to prove the layer switches are
        # complete (a layer not gated on BASE_ONLY would show up here).
        rom[0x7FDC:0x7FE0] = b'\x00\x00\x00\x00'
        t = sum(rom) & 0xFFFF
        chk = (t + 0x1FE) & 0xFFFF
        rom[0x7FDC] = (chk ^ 0xFFFF) & 0xFF
        rom[0x7FDD] = (chk ^ 0xFFFF) >> 8
        rom[0x7FDE] = chk & 0xFF
        rom[0x7FDF] = chk >> 8
        rom[0x7FD7] = 0x0B
        ver = sum(rom) & 0xFFFF
        assert ver == chk, (hex(ver), hex(chk))
        out = os.environ.get('OUT_ROM', OUT_ROM)
        open(out, 'wb').write(rom)
        print('BASE_ONLY build: %s written (baseline == original + header, '
              'all layers skipped)' % out)
        return

    pool = bytearray(PAGES * 0x8000)
    for ch in enc.order:
        p, i = enc.cell[ch]
        off = p * 0x8000 + i * POOL_STRIDE
        pool[off:off + POOL_STRIDE] = glyph64(ch)
    rom[POOL_ROM:POOL_ROM + len(pool)] = pool
    print('glyph pool: %d bytes at ROM 0x%06X (banks $%02X-$%02X)'
          % (len(pool), POOL_ROM, POOL_BANK0, POOL_BANK0 + PAGES - 1))

    # ---- 4b. the item names: their 8x16 glyphs, the slot base table, the hook
    itbl = bytearray(ITEM_GLYPH_MAX * 32)
    for ch, i in ITEM_CHARS.items():
        g = render8x16(ch, FONT_PATH, thresh=GLYPH8_THRESH, widen=GLYPH_WIDEN)
        itbl[i * 32:i * 32 + 16] = pack_8x8(g[:8])
        itbl[i * 32 + 16:i * 32 + 32] = pack_8x8(g[8:])
    rom[ITEM_GLYPH_ROM:ITEM_GLYPH_ROM + len(itbl)] = itbl
    # The status widget still needs condensed 8x16 names. The list has room
    # for six full 16x16 glyphs per field, so do not squash readable item names.
    menu_glyphs=bytearray(ITEM_GLYPH_MAX*64)
    for ch,i in ITEM_CHARS.items():
        g=cnglyph.render16x16(ch)
        menu_glyphs[i*64:i*64+64]=(pack_8x8([r[:8] for r in g[:8]])+
                                 pack_8x8([r[:8] for r in g[8:]])+
                                 pack_8x8([r[8:] for r in g[:8]])+
                                 pack_8x8([r[8:] for r in g[8:]]))
    assert rom[ITEM_MENU_GLYPH_ROM:ITEM_MENU_GLYPH_ROM+len(menu_glyphs)]==bytes(len(menu_glyphs)), 'menu item glyph destination occupied'
    rom[ITEM_MENU_GLYPH_ROM:ITEM_MENU_GLYPH_ROM+len(menu_glyphs)]=menu_glyphs

    rom[ITEMBASE_ROM:ITEMBASE_ROM + 3] = bytes(
        [ITEM_SLOT_BASE0, ITEM_SLOT_BASE0 + ITEM_SLOT_SPAN,
         ITEM_SLOT_BASE0 + 2 * ITEM_SLOT_SPAN])
    icode = build_itemdrawer()
    for lo, hi, what in ((CODE_ROM, CODE_ROM + 0x200, 'the drawer'),
                         (E3_SLOTPAIR, E3_SLOTPAIR + 0x200, 'the slot table'),
                         (E3_SLOTHI, E3_SLOTHI + 0x100, 'the slot high bytes'),
                         (E3_MSG, E3_MSG + 0x100, 'the message entry'),
                         (STALEROW_STUB, STALEROW_STUB + 0x100, 'stale-row stub'),
                         (MENUCLOSE_STUB, MENUCLOSE_STUB + 0x400, 'menu close stubs'),
                         (MENU_STUB, MENU_STUB + 0x100, 'the menu uploader'),
                         (MENU_TAB, MENU_TAB + 0x100, 'the menu table'),
                         (DISPATCH_ROM, DISPATCH_ROM + 0x400, 'the dispatch')):
        assert ITEMDRAW_ROM >= hi or ITEMDRAW_ROM + len(icode) <= lo, \
            'the item drawer overlaps %s' % what
        assert ITEMBASE_ROM >= hi or ITEMBASE_ROM + 3 <= lo, \
            'the item base table overlaps %s' % what
    rom[ITEMDRAW_ROM:ITEMDRAW_ROM + len(icode)] = icode
    assert rom[ITEM_HOOK:ITEM_HOOK + 4] == bytes([0xBF, 0x9E, 0xFB, 0x03]), \
        rom[ITEM_HOOK:ITEM_HOOK + 4].hex(' ')
    _bk, _ad = snes_of_rom(ITEMDRAW_ROM)
    rom[ITEM_HOOK:ITEM_HOOK + 4] = bytes([0x5C, _ad & 0xFF, _ad >> 8, _bk])
    print('item names: %d bytes at $%02X:%04X, hooked at $%04X'
          % (len(icode), _bk, _ad, ITEM_HOOK))

    # ---- the battle HUD's name plate (see HUDNAME_HOOK) ---------------------
    # Reserve the 144 additional glyph bytes before the full HUD caller.
    if HUDFIX:
        assert rom[0xAE5:0xAEB]==bytes.fromhex('A9 52 22 B6 9A 00'), 'HUD allocator caller changed'
        rom[0xAE6]=0xE2
    hcode = build_hudname() if HUDFIX else b''
    if HUDFIX:
        # Same bar pixels, same palettes, one shared set of nine font tiles.
        # $14 only selects +$10 for NPC bar tiles; $19 still selects palette.
        for tile in range(0xE7, 0xF0):
            a0, b0 = FONT_ROM + tile * 16, FONT_ROM + (tile + 0x10) * 16
            assert rom[a0:a0+16] == rom[b0:b0+16], 'HP bitmap dedup precondition'
        assert rom[0xAD9:0xADB] == bytes.fromhex('A9 10')
        assert rom[0xB77:0xB79] == bytes.fromhex('A9 F7')
        rom[0xADA] = 0x00  # both player/NPC bars use E7..EF, not F7..FF
        rom[0xB78] = 0xE7  # NPC empty segment also uses shared set
        assert HUDNAME_ROM + len(hcode) <= DISPATCH_ROM, \
            'the HUD name hook overruns the dispatch routine'
        _p = bytes.fromhex('A418B9461B AABF9EFA03 8522 BF9EFB03 8523')
        assert rom[HUDNAME_HOOK:HUDNAME_HOOK + 18] == _p, \
            'the HUD name hook site: ' + rom[HUDNAME_HOOK:HUDNAME_HOOK + 18].hex(' ')
        rom[HUDNAME_ROM:HUDNAME_ROM + len(hcode)] = hcode
        _bk, _ad = snes_of_rom(HUDNAME_ROM)
        rom[HUDNAME_HOOK:HUDNAME_HOOK + 4] = bytes([0x22, _ad & 0xFF, _ad >> 8, _bk])
        for _i in range(4, 18):                # the JSL returns here, then slides
            rom[HUDNAME_HOOK + _i] = 0xEA      # through the NOPs into the PLX
        print('HUD name plate: %d bytes at $%02X:%04X, hooked at $%04X'
              % (len(hcode), _bk, _ad, HUDNAME_HOOK))
    else:
        print('HUD name plate: OFF (HUDFIX=1 to enable)')

    # ---- the item name a battle message pastes in (see ITEMMSG_ROM) ---------
    if ITEMSG:
        mcode = build_itemmsg()
        assert ITEMMSG_ROM >= HUDNAME_ROM + len(hcode),         'the item message hook overlaps the HUD name hook'
        assert ITEMMSG_ROM + len(mcode) <= DISPATCH_ROM,         'the item message hook overruns the dispatch routine'
        rom[ITEMMSG_ROM:ITEMMSG_ROM + len(mcode)] = mcode
        _bk, _ad = snes_of_rom(ITEMMSG_ROM)
        print('item name in messages: %d bytes at $%02X:%04X, drawer branches at $DE'
              % (len(mcode), _bk, _ad))
    else:
        print('item name in messages: OFF (ITEMSG=1 to enable)')
    if os.environ.get('LITERALFIX', '0') == '1':
        lfix, lfix_tiles = build_literalfix()
    else:
        lfix, lfix_tiles = b'', []

    for lo, hi, what in ((CODE_ROM, CODE_ROM + 0x200, 'the drawer'),
                         (E3_SLOTPAIR, E3_SLOTPAIR + 0x200, 'the slot table'),
                         (E3_SLOTHI, E3_SLOTHI + 0x100, 'the slot high bytes'),
                         (E3_MSG, E3_MSG + 0x100, 'the message entry'),
                         (STALEROW_STUB, STALEROW_STUB + 0x100, 'stale-row stub'),
                         (MENUCLOSE_STUB, MENUCLOSE_STUB + 0x400, 'menu close stubs'),
                         (MENU_STUB, MENU_STUB + 0x100, 'the menu uploader'),
                         (MENU_TAB, MENU_TAB + 0x100, 'the menu table'),
                         (ITEMDRAW_ROM, ITEMDRAW_ROM + 0x100, 'the item drawer'),
                         (ITEMBASE_ROM, ITEMBASE_ROM + 0x100, 'the item base table'),
                         (STATUS_SLOT_TABLE, STATUS_SLOT_TABLE + 0x100, 'the label slots'),
                         (LABELDRAW_ROM, LABELDRAW_ROM + 0x100, 'the label drawer'),
                         (DISPATCH_ROM, DISPATCH_ROM + 0x400, 'the dispatch')):
        assert LITERALFIX_ROM >= hi or LITERALFIX_ROM + len(lfix) <= lo,             'the font restore overlaps %s' % what
    if lfix:
        rom[LITERALFIX_ROM:LITERALFIX_ROM + len(lfix)] = lfix
        assert rom[LITERAL_HOOK:LITERAL_HOOK + 4] == bytes([0xE2, 0x30, 0xA0, 0x00]),             rom[LITERAL_HOOK:LITERAL_HOOK + 4].hex(' ')
        _bk3, _ad3 = snes_of_rom(LITERALFIX_ROM)
        rom[LITERAL_HOOK:LITERAL_HOOK + 4] = bytes([0x5C, _ad3 & 0xFF, _ad3 >> 8, _bk3])
        print('literal tile restore: %d bytes at $%02X:%04X, hooked at $%04X, '
              'tiles %s'
              % (len(lfix), _bk3, _ad3, LITERAL_HOOK,
                 sorted('%02X' % t for t in lfix_tiles)))
    lcode = build_labeldrawer()
    for lo, hi, what in ((CODE_ROM, CODE_ROM + 0x200, 'the drawer'),
                         (E3_SLOTPAIR, E3_SLOTPAIR + 0x200, 'the slot table'),
                         (E3_SLOTHI, E3_SLOTHI + 0x100, 'the slot high bytes'),
                         (E3_MSG, E3_MSG + 0x100, 'the message entry'),
                         (STALEROW_STUB, STALEROW_STUB + 0x100, 'stale-row stub'),
                         (MENUCLOSE_STUB, MENUCLOSE_STUB + 0x400, 'menu close stubs'),
                         (MENU_STUB, MENU_STUB + 0x100, 'the menu uploader'),
                         (MENU_TAB, MENU_TAB + 0x100, 'the menu table'),
                         (ITEMDRAW_ROM, ITEMDRAW_ROM + 0x100, 'the item drawer'),
                         (ITEMBASE_ROM, ITEMBASE_ROM + 0x100, 'the item base table'),
                         (DISPATCH_ROM, DISPATCH_ROM + 0x400, 'the dispatch')):
        assert LABELDRAW_ROM >= hi or LABELDRAW_ROM + len(lcode) <= lo,             'the label drawer overlaps %s' % what
        assert STATUS_SLOT_TABLE >= hi or STATUS_SLOT_TABLE + 256 <= lo,             'the label slot table overlaps %s' % what
    rom[LABELDRAW_ROM:LABELDRAW_ROM + len(lcode)] = lcode
    assert rom[LABEL_HOOK:LABEL_HOOK + 4] == bytes([0xBF, 0x9E, 0xFB, 0x03]),         rom[LABEL_HOOK:LABEL_HOOK + 4].hex(' ')
    _bk2, _ad2 = snes_of_rom(LABELDRAW_ROM)
    rom[LABEL_HOOK:LABEL_HOOK + 4] = bytes([0x5C, _ad2 & 0xFF, _ad2 >> 8, _bk2])
    print('status labels: %d bytes at $%02X:%04X, hooked at $%04X'
          % (len(lcode), _bk2, _ad2, LABEL_HOOK))

    # ---- the drawer's pacing gate (v37) --------------------------------------
    # The engine types at about one cell per frame on its own, so a three line
    # message flashed past in roughly a second and a half and the box pushed its
    # oldest row out the moment a new one began - nothing stayed readable (user
    # report, 2026-09-25: "第二行会显示被跳过的很快").  Two earlier patches here
    # were measured on real traces to have changed nothing (see build_pace for
    # why: $00:9AB6 is the queue allocator, and $00:FFBE is a ROM constant), so
    # both are gone and the real gate is in: one character every PACE frames,
    # A/B held fast-forwards.  The gate paces the box-full scroll too, because a
    # row is only pushed when the next one starts typing - a slow typewriter
    # keeps every line on screen for seconds before it moves.
    pcode = build_pace()
    for lo, hi, what in ((ITEMMSG_ROM, ITEMMSG_ROM + 0x400, 'the item message hook'),
                         (DISPATCH_ROM, DISPATCH_ROM + 0x400, 'the dispatch')):
        assert PACE_ROM >= hi or PACE_ROM + len(pcode) <= lo,             'the pace gate overlaps %s' % what
    rom[PACE_ROM:PACE_ROM + len(pcode)] = pcode
    _bkp, _adp = snes_of_rom(PACE_ROM)
    assert rom[PACE_HOOK:PACE_HOOK + 6] == bytes([0xA9, 0x08, 0x22, 0xB6, 0x9A, 0x00]),         'pace hook site: ' + rom[PACE_HOOK:PACE_HOOK + 6].hex(' ')
    rom[PACE_HOOK:PACE_HOOK + 6] = bytes([0x22, _adp & 0xFF, _adp >> 8, _bkp, 0xEA, 0xEA])
    print('typewriter pace: %d bytes at $%02X:%04X, hooked at $03:EEE5, '
          'one char per %d message ticks, held A/B fast-forwards'
          % (len(pcode), _bkp, _adp, PACE))

    # ---- idle auto-continue knob (EXPERIMENTAL, default = original) ----------
    # When a message block ends the engine waits for A; if none comes within
    # #$F0 = 240 engine passes it wipes the box and continues on its own.  The
    # logic loop runs at 30 Hz, so that is 480 real frames = 8 s of dead air,
    # and the field-trace gaps between message blocks are 570-720 real frames.
    # Shortening it to 120 passes was BUILT AND MEASURED to make things WORSE:
    # the early wipe lands inside the scene driver's own wait, and the pauses
    # grew from 570-720 to 900+ real frames (hw/_chain_v38.log, three ~900 frame
    # stalls, none in the v37 chain over the same input).  The default below
    # leaves the engine byte untouched; IDLEPASS=120 replays the failed
    # experiment for forensics.
    IDLEPASS = int(os.environ.get('IDLEPASS', '240'))
    if IDLEPASS != 240:
        _idlec = 0x01EED7
        assert rom[_idlec:_idlec + 2] == bytes([0xC9, 0xF0]),             'idle auto-continue site: ' + rom[_idlec:_idlec + 2].hex(' ')
        rom[_idlec + 1] = IDLEPASS & 0xFF
        print('idle auto-continue: $03:EED8 waits 240 -> %d passes (EXPERIMENTAL)'             % IDLEPASS)

    for (start, end), (table_off, count) in zip(REGIONS, TABLES):
        if table_off in NO_TRANSLATE:
            continue                    # keep the original Japanese items
        body = bytes(chunks[start])
        rom[start:end] = body + b'\x00' * (end - start - len(body))
    for table_off, count in TABLES:
        if table_off in NO_TRANSLATE:
            continue
        recs = sorted([r for r in textrecs if r['table_rom_off'] == table_off],
                      key=lambda r: r['index'])
        for i, r in enumerate(recs):
            a_ = addr_of['%06X' % r['text_rom_off']]
            if a_ >= 0x018000:               # keep the SNES address in bank $03
                sa = 0x8000 + (a_ & 0x7FFF)
            else:
                sa = 0x8000 + (a_ & 0x7FFF)
            rom[table_off + 2 * i] = sa & 0xFF
            rom[table_off + 2 * i + 1] = sa >> 8
        print('  table 0x%06X: %d pointers rebuilt' % (table_off, count))

    slotpairs, slothi, npairs, win_pairs = build_slotpairs()
    r5_end = active[-1][0] + len(chunks[active[-1][0]])
    assert r5_end <= B3_SANITIZE_END, (hex(r5_end), hex(B3_SANITIZE_END))
    rom[E3_SLOTPAIR:E3_SLOTPAIR + len(slotpairs)] = slotpairs
    # high byte of every entry's tile: 1 only for the label sets, which moved out
    # of the font window, 0 for everything else
    rom[E3_SLOTHI:E3_SLOTHI + len(slothi)] = slothi
    held_hud = hud_pairs()
    assert len(held_hud) <= 16
    rom[HUDPAIR_ROM:HUDPAIR_ROM + len(held_hud)] = bytes(t & 255 for t in held_hud)
    rom[HUDPAIR_ROM + 16:HUDPAIR_ROM + 16 + len(held_hud)] = bytes(t >> 8 for t in held_hud)
    message_tiles = {int(lo) | int(hi) << 8 for lo, hi in zip(slotpairs, slothi)}
    assert not message_tiles.intersection(held_hud), 'HUD/message glyph reservation collision'

    # row -> label pair set, right after the pair table (the drawer reads it)
    global E3_ROWSET
    E3_ROWSET = E3_SLOTPAIR + len(slotpairs)
    rom[E3_ROWSET:E3_ROWSET + 16] = bytes(r % LABEL_SETS for r in range(16))
    assert E3_ROWSET + 16 <= E3_DRAWER, (hex(E3_ROWSET), hex(E3_DRAWER))

    print('slots: %d free tile pairs, %d pair-pair slots used, %d label pair '
          'sets (table %d B + %d B high at $%02X:%04X/$%02X:%04X)'
          % (npairs, SLOTS, LABEL_SETS, len(slotpairs), len(slothi),
             *snes_of_rom(E3_SLOTPAIR), *snes_of_rom(E3_SLOTHI)))

    drawer = build_drawer_copy()
    rom[E3_DRAWER:E3_DRAWER + len(drawer)] = drawer
    # the macro sanitizer is gone: its only callers copy kana only now, and its
    # range would swallow the one byte codes $d2..$df
    assert E3_SLOTPAIR + len(slotpairs) <= E3_DRAWER, (len(slotpairs),)
    assert E3_DRAWER + len(drawer) < E3_MSG, (len(drawer),)
    assert E3_MSG < CODE_ROM + 0x8000
    for name, code in (('drawer', drawer),):
        bad = scratch_hits(code)
        assert not bad, '%s touches live game data: %r' % (name, bad)

    db, da = snes_of_rom(E3_DRAWER)
    assert rom[HOOK_DRAWER:HOOK_DRAWER + 4] == bytes([0xAD, 0x6F, 0x03, 0xC9]), \
        rom[HOOK_DRAWER:HOOK_DRAWER + 6].hex(' ')
    # JML is 4 bytes: opcode + 16-bit address + bank.  Only 4 bytes may be
    # replaced here, or the ROM shifts by one byte from 0x01FA30 on.
    rom[HOOK_DRAWER:HOOK_DRAWER + 4] = bytes([0x5C, da & 0xFF, da >> 8, db])
    for hook in (HOOK_COPY1, HOOK_COPY2):
        assert rom[hook:hook + 3] == bytes([0x9D, 0xEA, 0x03]), \
            'the sanitizer call has already been removed: %s' % rom[hook:hook + 3].hex(' ')
    print('drawer %d B @ROM 0x%06X ($%02X:%04X)' % (len(drawer), E3_DRAWER, db, da))

    assert rom[HOOK_DRIVER:HOOK_DRIVER + 4] == bytes([0x08, 0x8B, 0xE2, 0x30]), \
        rom[HOOK_DRIVER:HOOK_DRIVER + 4].hex(' ')   # untouched: no hook needed
    # the row loader stays untouched: it runs from the main loop, where even a
    # DMA does not reach VRAM (measured: $3F:8000 -> $7c00 with a marker value in
    # the source table left the box reading $2c00), while the queue's own DMA,
    # fired from VBlank, does.  Blanking therefore rides the queue.
    assert rom[HOOK_LOAD:HOOK_LOAD + 5] == bytes([0xA9, 0x40, 0x0C, 0x73, 0x03]), \
        rom[HOOK_LOAD:HOOK_LOAD + 5].hex(' ')
    print('box blanking: the drawer wipes a row through the upload queue when the '
          'row starts')

    # ---- 4b. the untranslated Japanese is drawn with the original font, so its
    # katakana is rewritten to hiragana: same reading, same length, and 38 font
    # tiles fewer stay reserved (each freed tile pair buys two glyph slots).
    print('font tiles protected: %d of 256; %d free consecutive tile pairs'
          % (len(protected_tiles()), len(free_pairs())))
    # Only rewrite kana for text whose original tiles we still reserve.  When a
    # group is not protected its font tiles go to the pool, so the rewrite buys
    # nothing -- and leaving the original bytes alone keeps the patch smaller.
    if not HUD_ORIG and 'item' in PROTECT_GROUPS:
        rom[0x01DCA1:0x01E096] = rewrite_kana(bytes(rom[0x01DCA1:0x01E096]))
    # ---- 4c. every speaker name record: hanzi label codes --------------------
    # The label glyphs live in banks $3A/$3B (own storage, own tile pairs), so
    # the record carries [prefix][glyph id] instead of a pool code.  Records
    # that are not kana names (42 of the 560 hold other data) keep their kana.
    names = json.load(open(BASE + NAME_HANZI_FILE, encoding='utf-8'))
    ids = {}
    for name in names.values():
        for ch in name:
            ids.setdefault(ch, len(ids))
    per_page = 256 - LABEL_ID0
    need = -(-len(ids) // per_page)
    if need > PAGES:
        raise SystemExit('name glyphs need %d pages, the pool has %d'
                         % (need, PAGES))
    for ch, gid in ids.items():
        page, idx = divmod(gid, per_page)
        off = POOL_ROM + page * 0x8000 + (LABEL_ID0 + idx) * POOL_STRIDE
        rom[off:off + POOL_STRIDE] = glyph64(ch)
    n_name = n_kana = 0
    for i in range(NAME_RECORDS):
        o = NAME_RECORD_BASE + i * 16
        raw = bytes(rom[o:o + 4])
        kana = ''.join(km.CODE.get(b, '') for b in raw).strip()
        hanzi = names.get(kana)
        if hanzi:
            codes = bytearray()
            for ch in hanzi:
                page, idx = divmod(ids[ch], per_page)
                codes += bytes([PREFIX0 + page, LABEL_ID0 + idx])
            assert len(codes) <= 4, (kana, hanzi)
            rom[o:o + 4] = bytes(codes) + b'\x00' * (4 - len(codes))
            n_name += 1
        else:
            # The 42 records that are not kana names are leftover data (codes
            # like $c8/$d6 that no name uses).  Their font tiles are not
            # protected - 20 more tiles would cost 14 slot pairs - and their
            # codes sit inside the Chinese range, so a stray draw would decode
            # as a Chinese glyph.  Blanking them is the only safe answer: a
            # blank label beats a hijacked code.
            rom[o:o + 4] = b'\x00' * 4
            n_kana += 1
    print('speaker names: %d records in hanzi (%d distinct glyphs, %d pages of '
          'label cells), %d leftover records blanked'
          % (n_name, len(ids), need, n_kana))
    # The choice prompt's region used to be run through rewrite_kana, on the
    # theory that its bytes were kana codes.  They are not: the region holds the
    # three drawing scripts and the two block pointer tables, so the rewrite
    # silently corrupted it -- $A4 (the lower left corner's v-flip) became $54
    # and, worse, the second prompt set's pointers $F4AD/$F4C1/$F4D5 became
    # $F45D/$F471/$F455, which the interpreter would follow into the middle of
    # its own tables and copy a few hundred bytes into $040A.  The tiles the
    # prompt draws are protected instead (PROTECT_TILES), so nothing is owed to
    # the tile budget for dropping the rewrite.
    if os.environ.get('STATUS_LABELS', '1') == '1':
        status_labels(rom, ITEM_CHARS)
    else:
        # no label codes: every entry $FF, so the hook always falls
        # through to the engine's own FA/FB path
        rom[STATUS_SLOT_TABLE:STATUS_SLOT_TABLE + 256] = bytes([0xFF]) * 256
        print('status labels: left in Japanese (bisect build)')
    choice_box(rom)
    nrun = 0
    if not HUD_ORIG:
        for s, e in status_script_code_runs():
            rom[s:e] = rewrite_kana(bytes(rom[s:e]))
            nrun += 1
    print('kana: %s, 560 speaker name records and %d status script runs '
          'rewritten to hiragana'
          % ('item window' if 'item' in PROTECT_GROUPS else 'item window left alone',
             nrun))

    # The stale-row wipe: the row above a new message still holds the previous
    # message's cells, which point at pool slots the new message re-uploads, so
    # it comes out as glyph fragments.  The stub blanks that row when the drawer
    # is on the message's second row (see build_stalerow for the measurement
    # behind the gate).  STALEROW=count installs the counter variant instead,
    # which only bumps $0BF9 so a probe can see how often the gate fires.
    if STALEROW_ON:
        build_stalerow(rom, count_only=os.environ.get('STALEROW') == 'count')

    if CMDWIN == 1:
        cmdwin_static(rom, win_pairs)
        build_menuclose(rom)
    elif CMDWIN == 2:
        _chars, _tab = cmdwin_pool(rom, enc, slotpairs)
        build_menuclose(rom)
        build_menuload(rom, _tab)
        # $03:F841 starts with LDY $039A / LDA $F851,Y; the stub replays both and
        # returns at $F847.
        bk, ad = snes_of_rom(MENU_STUB)
        assert rom[MENU_HOOK:MENU_HOOK + 6] == bytes([0xAC, 0x9A, 0x03, 0xB9, 0x51, 0xF8]),             rom[MENU_HOOK:MENU_HOOK + 6].hex(' ')
        rom[MENU_HOOK:MENU_HOOK + 5] = bytes([0x5C, ad & 0xFF, ad >> 8, bk, 0xEA])
        print("menu label loader hooked at $%04X (the menu input state)" % MENU_HOOK)
    else:
        print('command window: off (labelled pairs stay inside the font window)')

    # Every short-name field is limited by the original 13-byte row buffer.
    # Columns 0/13 are reserved separators in this build, hence 12 data bytes.
    for table,count in ((0x1DBC3,110),(0x1E096,35)):
        for ident in range(1,count+1):
            ptr=int.from_bytes(rom[table+ident*2:table+ident*2+2],'little')
            off=0x10000+ptr
            end=rom.find(b'\xf2',off,off+64)
            assert end>=off and end-off<=12, ('menu field does not fit',hex(table),ident,end-off)
    from menulist_patch import install as install_menu_list
    result=install_menu_list(rom,Asm,E3_SLOTPAIR,E3_SLOTHI,SLOTS,PAGES,POOL_BANK0,len(slotpairs)//2)
    print('short-name list renderer: %d bytes @ ROM %06X; original command window bypassed' % (result['bytes'],result['rom']))

    # ---- 5. checksum (this ROM stores the complement first)
    rom[0x7FDC:0x7FE0] = b'\x00\x00\x00\x00'
    t = sum(rom) & 0xFFFF
    chk = (t + 0x1FE) & 0xFFFF
    rom[0x7FDC] = (chk ^ 0xFFFF) & 0xFF
    rom[0x7FDD] = (chk ^ 0xFFFF) >> 8
    rom[0x7FDE] = chk & 0xFF
    rom[0x7FDF] = chk >> 8
    rom[0x7FD7] = 0x0B                      # 16 Mbit
    assert len(rom) == 0x200000, len(rom)
    ver = sum(rom) & 0xFFFF
    assert ver == chk, (hex(ver), hex(chk))
    print('checksum 0x%04X / complement 0x%04X ; verify sum&FFFF = 0x%04X'
          % (chk, chk ^ 0xFFFF, ver))

    out_rom = os.environ.get('OUT_ROM', OUT_ROM)
    open(out_rom, 'wb').write(rom)
    n = make_ips(open(ORIG_ROM, 'rb').read(), bytes(rom), OUT_IPS)
    print('wrote %s (IPS: %d records)' % (os.path.basename(out_rom), n))


if __name__ == '__main__':
    if os.environ.get('PYTHONHASHSEED') != '0':
        raise SystemExit('Set PYTHONHASHSEED=0 before launching the builder (deterministic tile allocation).')
    main()