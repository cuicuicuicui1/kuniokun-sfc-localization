-- v16.lua : glyph-content dump.  At one settled frame it prints every message
-- cell whose tiles belong to the Chinese glyph slots, together with the 32 bytes
-- that are actually in VRAM for that slot.  Nothing is judged by eye: the bytes
-- are compared against the built glyph pool and the intended characters.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v16"
local TO = tonumber(os.getenv("HW_TO") or "1540")
local AT = tonumber(os.getenv("HW_AT") or "1500")
local CNROM = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

-- the slot table: one byte per slot, the value is the slot's TOP tile number
local slots = {}
do
  local f = io.open(CNROM, "rb")
  if f then
    f:seek("set", 0x1E900)
    local raw = f:read(114)
    f:close()
    for i = 0, 113 do
      local t = string.byte(raw, i + 1)
      if not t or t == 0 then break end
      slots[t] = i            -- slot index -> the id byte the engine stores
    end
  end
end

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function tile_at(w)
  local lo = memory.read_u8(w * 2, "VRAM")
  local hi = memory.read_u8(w * 2 + 1, "VRAM")
  return (lo + (hi % 4) * 256)
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()) .. " at=" .. AT)
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
  if emu.framecount() == AT then
    for r = 0, 3 do
      for c = 0, 27 do
        local top = tile_at(0x7C00 + r * 64 + 3 + c)
        local bot = tile_at(0x7C00 + r * 64 + 3 + c + 32)
        if slots[top] then
          -- the slot's glyph: 16 words starting at $6000 + top*8
          local by = {}
          for k = 0, 31 do
            by[#by + 1] = string.format("%02X", memory.read_u8((0x6000 + top * 8) * 2 + k, "VRAM"))
          end
          say(string.format("CELL row=%d col=%d top=%03X bot=%03X slot=%d glyph=%s",
                            r, c, top, bot, slots[top], table.concat(by)))
        end
      end
    end
    say("DUMP-END")
  end
end