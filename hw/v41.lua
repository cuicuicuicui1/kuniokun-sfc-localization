-- v41: 16x16 build probe.
--   * reads the slot table (2 arrays of pairs at ROM 0x1F0180) and the glyph pool
--     (64 B/glyph at (0x21+page)*0x8000 + slot*64)
--   * per frame classifies the four VRAM tiles of every probed cell as POOL / orig / other
--   * tracks box tilemap occupancy (upper halves of rows 0..3, cols 0..25) plus engine state
--   * saves a screenshot per sampled frame so py41.py can template-match the 16x16 glyphs
-- env: HW_TAG HW_FROM HW_TO HW_STEP HW_ROM HW_CELLS("page:slot:char,...") HW_SHOT(1/0)
local TAG   = os.getenv("HW_TAG") or "v41"
local FROM  = tonumber(os.getenv("HW_FROM") or "1370")
local TO    = tonumber(os.getenv("HW_TO")   or "1420")
local STEP  = tonumber(os.getenv("HW_STEP") or "1")
local ROM   = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
local SHOT  = (os.getenv("HW_SHOT") or "1") == "1"
local CELLS = os.getenv("HW_CELLS") or ""
local OUT   = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/"

local SLOTS = 53
local SLOT_TAB_ROM = 0x1F0180

local rom = assert(io.open(ROM, "rb"))
local function rombyte(off)
  rom:seek("set", off)
  local b = rom:read(1)
  if not b then return 0 end
  return string.byte(b)
end
local function rombytes(off, n)
  rom:seek("set", off)
  return rom:read(n) or string.rep("\0", n)
end

-- slot table: left pairs then right pairs
local left, right = {}, {}
for s = 0, SLOTS - 1 do
  left[s]  = rombyte(SLOT_TAB_ROM + s)
  right[s] = rombyte(SLOT_TAB_ROM + SLOTS + s)
end

-- probed cells: "page:slot:char" entries
local probes = {}
for entry in string.gmatch(CELLS, "[^,]+") do
  local p, s, ch = string.match(entry, "(%d+):(%d+):(.*)")
  if p then
    p, s = tonumber(p), tonumber(s)
    local pool = rombytes((0x21 + p) * 0x8000 + s * 64, 64)
    probes[#probes + 1] = { page = p, slot = s, ch = ch, pool = pool }
  end
end

-- tiles used by my glyph slots (for tilemap occupancy)
local myset = {}
for s = 0, SLOTS - 1 do
  myset[left[s] * 2] = true; myset[left[s] * 2 + 1] = true
  myset[right[s] * 2] = true; myset[right[s] * 2 + 1] = true
end

local log = assert(io.open(OUT .. TAG .. ".log", "w"))
local function w(...)
  local t = {}
  for i = 1, select("#", ...) do t[i] = tostring((select(i, ...))) end
  log:write(table.concat(t, " "), "\n"); log:flush()
end

local function vram(addr) return memory.read_u8(addr, "VRAM") end
local function vramstr(addr, n)            -- n bytes starting at VRAM byte addr
  local t = {}
  for i = 0, n - 1 do t[#t + 1] = string.char(vram(addr + i)) end
  return table.concat(t)
end
local function word(addr)                  -- VRAM word read at word address
  local lo, hi = vram(addr * 2), vram(addr * 2 + 1)
  return lo + hi * 256
end
local function tileaddr(t) return 0xC000 + t * 16 end   -- VRAM byte addr of tile t

w("v41 start tag=" .. TAG .. " rom=" .. ROM)
w("slot table L:", (function() local t = {} for s = 0, 7 do t[#t+1] = string.format("%02X", left[s]) end return table.concat(t, " ") end)(),
  " R:", (function() local t = {} for s = 0, 7 do t[#t+1] = string.format("%02X", right[s]) end return table.concat(t, " ") end)())
for _, pr in ipairs(probes) do
  w(string.format("probe %s page=%d slot=%d tiles L=%02X/%02X R=%02X/%02X",
    pr.ch, pr.page, pr.slot, left[pr.slot] * 2, left[pr.slot] * 2 + 1,
    right[pr.slot] * 2, right[pr.slot] * 2 + 1))
end

local function classify(pr)
  local a = tileaddr(left[pr.slot] * 2)
  local s1 = vramstr(a, 32)          -- TL then BL
  local s2 = vramstr(tileaddr(right[pr.slot] * 2), 32)   -- TR then BR
  local pool_a = string.sub(pr.pool, 1, 32)
  local pool_b = string.sub(pr.pool, 33, 64)
  local function tag(obs, poolpart, pair, base)     -- pair index for the "orig" comparison
    if obs == poolpart then return "POOL" end
    if obs == rombytes(0x0F8000 + pair * 2 * 16, 32) then return "orig" end
    return "other(" .. string.format("%02X%02X%02X%02X", string.byte(obs, 1, 4)) .. ")"
  end
  return tag(s1, pool_a, left[pr.slot]) .. "/" .. tag(s2, pool_b, right[pr.slot])
end

local function occ()
  -- returns string of rows 0..3 with the tiles of the upper halves, marking my tiles
  local out = {}
  for row = 0, 3 do
    local t = {}
    for col = 0, 25 do
      local tl = word(0x7C00 + row * 0x40 + 3 + col) & 0x3FF
      t[#t + 1] = (myset[tl] and "*" or ".") .. string.format("%03X", tl)
    end
    out[#out + 1] = "r" .. row .. "[" .. table.concat(t, ",") .. "]"
  end
  return table.concat(out, " ")
end

local prev = ""
local idx = 0
while true do
  local f = emu.framecount()
  if f > TO then break end
  if f >= FROM and (idx % STEP) == 0 then
    local e8  = memory.read_u8(0x03E8)
    local e9  = memory.read_u8(0x03E9)
    local col = memory.read_u8(0x036F)
    local row = memory.read_u8(0x036E)
    local ln  = memory.read_u8(0x036D)
    local f73 = memory.read_u8(0x0373)
    local f74 = memory.read_u8(0x0374)
    local wt, wb = memory.read_u8(0x0D40), memory.read_u8(0x0D41)
    local wc, wp = memory.read_u8(0x0D42), memory.read_u8(0x0D43)
    local cls = {}
    for _, pr in ipairs(probes) do cls[#cls + 1] = pr.ch .. "=" .. classify(pr) end
    local line = string.format("F=%d e8=%02X e9=%02X col=%02X row=%02X ln=%02X 73=%02X 74=%02X wipe=%02X/%02X/%02X/%02X %s",
      f, e8, e9, col, row, ln, f73, f74, wt, wb, wc, wp, table.concat(cls, " "))
    local oc = occ()
    if oc ~= prev or (f % 30) == 0 then
      w(line); w("   " .. oc)
      prev = oc
    else
      w(line)
    end
    if SHOT then client.screenshot(string.format("%s%s_f%05d.png", OUT, TAG, f)) end
  end
  if (f % 30) == 0 then joypad.set({ A = true }, 1) end
  if f < 420 and (f % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  idx = idx + 1
end
w("v41 done")
log:close()
rom:close()