-- v19.lua : timeline of the slot tiles' content.  For each of the five cells of
-- the first dialogue it reports, frame by frame, whether VRAM already holds the
-- built glyph pool bytes for that (page, slot).  This separates "the write never
-- landed" from "something later overwrote the font window".
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v19"
local TO = tonumber(os.getenv("HW_TO") or "1420")
local CNROM = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

-- slot table and the glyph pool, straight out of the ROM file
local SLOTPAIR = {}
do
  local f = assert(io.open(CNROM, "rb"))
  f:seek("set", 0x1E900)
  local raw = f:read(114)
  for i = 0, 113 do
    local t = string.byte(raw, i + 1)
    if not t or t == 0 then break end
    SLOTPAIR[i] = t
  end
  f:close()
end
-- (page, slot) per cell, in column order, as the game's own buffer decoded
local CELLS = {
  { col = 5, page = 6, slot = 0x3F, ch = "zhu" },
  { col = 6, page = 8, slot = 0x49, ch = "rou" },
  { col = 7, page = 1, slot = 0x01, ch = "bao" },
  { col = 8, page = 0, slot = 0x15, ch = "yi" },
  { col = 9, page = 0, slot = 0x29, ch = "ge" },
}
for _, c in ipairs(CELLS) do
  local f = assert(io.open(CNROM, "rb"))
  f:seek("set", (0x21 + c.page) * 0x8000 + c.slot * 32)
  c.pool = f:read(32)
  f:close()
  c.tile = SLOTPAIR[c.slot]
end

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

local function vbyte(a) return memory.read_u8(a, "VRAM") end
local function tile_at(w) return vbyte(w * 2) + (vbyte(w * 2 + 1) % 4) * 256 end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()))
local idx = 0
local marks = { [1380] = 1, [1381] = 1, [1382] = 1, [1383] = 1, [1384] = 1, [1385] = 1,
  [1386] = 1, [1387] = 1, [1388] = 1, [1389] = 1, [1390] = 1, [1391] = 1, [1392] = 1,
  [1393] = 1, [1395] = 1, [1397] = 1, [1400] = 1, [1410] = 1, [1450] = 1, [1500] = 1 }
while emu.framecount() < TO do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
  local f = emu.framecount()
  if marks[f] then
    local parts = {}
    for _, c in ipairs(CELLS) do
      local a = (0x6000 + c.tile * 8) * 2
      local got = {}
      for k = 0, 31 do got[#got + 1] = string.char(vbyte(a + k)) end
      got = table.concat(got)
      local map = tile_at(0x7C00 + 3 + c.col)
      parts[#parts + 1] = string.format("%s t%03X map%03X %s", c.ch, c.tile, map,
        got == c.pool and "POOL" or "orig")
    end
    say(string.format("F=%d  %s", f, table.concat(parts, "  ")))
  end
end