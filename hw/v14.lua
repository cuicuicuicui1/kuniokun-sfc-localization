-- v14.lua : per-frame ground truth.  Reads the real BG1 tilemap out of VRAM and
-- counts entries whose tile number belongs to the Chinese glyph slots (taken
-- straight from the patched ROM's slot-pair table at ROM 0x01E900), so no
-- pixel is ever judged by eye.  Also dumps the text engine's own counters.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v14"
local FROM = tonumber(os.getenv("HW_FROM") or "1370")
local TO = tonumber(os.getenv("HW_TO") or "1450")
local CNROM = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

-- Chinese glyph tile numbers, from the slot-pair table my build writes.
local slots = {}
do
  local f = io.open(CNROM, "rb")
  if f then
    f:seek("set", 0x1E900)
    local raw = f:read(114)
    f:close()
    -- valid entries are consecutive tile pairs in the free part of the font
    -- window; the table ends where the sanitizer routine starts.
    -- one byte per slot: the value is the slot's TOP tile number
    for i = 0, 113 do
      local t = string.byte(raw, i + 1)
      if not t or t == 0 then break end
      slots[t] = true
      slots[t + 1] = true
    end
  end
end
local nslots = 0
for _ in pairs(slots) do nslots = nslots + 1 end

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
-- one tilemap entry: word address W -> byte 2W in BizHawk's VRAM domain
local function tile_at(w)
  local lo = memory.read_u8(w * 2, "VRAM")
  local hi = memory.read_u8(w * 2 + 1, "VRAM")
  return (lo + (hi % 4) * 256)
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()) .. " cnslots=" .. nslots)
local idx = 0
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
  if f >= FROM then
    say(string.format(
      "F=%d e8=%02X e9=%02X col=%02X row=%02X 73=%02X 74=%02X 8a=%02X 90=%02X 94=%02X 9dd=%02X 9df=%02X",
      f, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E), rd(0x0373), rd(0x0374),
      rd(0x038A), rd(0x0390), rd(0x0394), rd(0x09DD), rd(0x09DF)))
    for r = 0, 3 do
      local t, cn, nz = {}, 0, 0
      for c = 0, 27 do
        local v = tile_at(0x7C00 + r * 64 + 3 + c)
        t[#t + 1] = string.format("%03X", v)
        if v ~= 0 then nz = nz + 1 end
        if slots[v] then cn = cn + 1 end
      end
      -- count via the lower half too (a cell is two tilemap rows)
      for c = 0, 27 do
        local v = tile_at(0x7C00 + r * 64 + 3 + c + 32)
        if slots[v] then cn = cn + 1 end
      end
      say(string.format("   row%d cn=%d nz=%d  %s", r, cn, nz, table.concat(t, " ")))
      if r == 0 then
        local b = {}
        for c = 0, 27 do
          b[#b + 1] = string.format("%03X", tile_at(0x7C00 + r * 64 + 3 + c + 32))
        end
        say("   bot0 " .. table.concat(b, " "))
      end
    end
  end
end
log:close()