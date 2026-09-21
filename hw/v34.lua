-- v34.lua : box occupancy timeline.
--   For every logged frame it lists which box cells (row:col) hold one of MY
--   glyph tiles (the slot table from ROM 0x01E900) and which slot that is, plus
--   the message length/index registers.  Purpose: find out whether the engine
--   clears the message box when a new message starts (-> no two messages are
--   ever on screen together -> colouring windows of one message are enough) or
--   whether old text stays visible while the new message draws.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v34"
local FROM = tonumber(os.getenv("HW_FROM") or "1340")
local TO = tonumber(os.getenv("HW_TO") or "2000")
local STEP = tonumber(os.getenv("HW_STEP") or "5")
local ROM = os.getenv("HW_ROM") or
    "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"
local NSLOT = tonumber(os.getenv("HW_NSLOT") or "114")   -- bytes to read as slot table
local GLYPHSTRIDE = tonumber(os.getenv("HW_STRIDE") or "32")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local f = io.open(ROM, "rb")
local rom = f:read("*a")
f:close()
local function u8(a) return rom:byte(a + 1) end

-- slot -> (top tile, bottom tile).  1 byte per slot in the 8x16 build,
-- 1 byte per tile pair in the 16x16 build (two pairs per glyph).
local tileslot = {}
for s = 0, NSLOT - 1 do
  local t = u8(0x1E900 + s)
  if t > 0 then
    tileslot[t] = s
    tileslot[t + 1] = s
    if GLYPHSTRIDE == 64 then
      local t2 = u8(0x1E900 + s + 1)
      if t2 > 0 then tileslot[t2] = s; tileslot[t2 + 1] = s end
    end
  end
end

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end

local idx = 0
local function tick()
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
end

while emu.framecount() < FROM do tick(); emu.frameadvance() end

local lastrows = nil
while emu.framecount() <= TO do
  local fr = emu.framecount()
  if ((fr - FROM) % STEP) == 0 then
    local cells = {}
    local rows = {}
    for row = 0, 15 do
      local bits = ""
      for col = 0, 25 do
        local addr = 0x7C00 + row * 0x40 + 3 + col
        local v = memory.read_u16_le(addr * 2, "VRAM")
        local t = v % 256
        local s = tileslot[t]
        if s then
          cells[#cells + 1] = string.format("%d:%d=s%d", row, col, s)
          bits = bits .. "#"
        else
          bits = bits .. "."
        end
      end
      if bits:find("#") then rows[#rows + 1] = string.format("r%d[%s]", row, bits) end
    end
    say(string.format("F=%d e8=%02X e9=%02X col=%02X row=%02X n=%d",
        fr, memory.read_u8(0x03E8, "WRAM"), memory.read_u8(0x03E9, "WRAM"),
        memory.read_u8(0x036F, "WRAM"), memory.read_u8(0x036E, "WRAM"),
        #cells))
    if #cells > 0 then say("    " .. table.concat(cells, " ")) end
    if #rows > 0 then say("    " .. table.concat(rows, " ")) end
  end
  tick()
  emu.frameadvance()
end
say(string.format("done frames %d..%d", FROM, TO))
log:close()