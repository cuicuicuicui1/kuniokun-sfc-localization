-- v20.lua : dump all of VRAM at one settled frame and locate the built glyph
-- pool bytes inside it.  Distinguishes "the write landed at the wrong address"
-- from "the write never reached VRAM at all".
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v20"
local TO = tonumber(os.getenv("HW_TO") or "1510")
local AT = tonumber(os.getenv("HW_AT") or "1500")
local CNROM = os.getenv("HW_ROM") or "C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc"

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

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
    local t = {}
    for a = 0, 0xFFFF do t[#t + 1] = string.char(memory.read_u8(a, "VRAM")) end
    local dump = table.concat(t)
    local bf = io.open(OUT .. "/" .. TAG .. "_vram.bin", "wb")
    bf:write(dump)
    bf:close()
    for _, c in ipairs(CELLS) do
      local full = string.find(dump, c.pool, 1, true)
      local half = string.find(dump, c.pool:sub(1, 8), 1, true)
      local want = (0x6000 + c.tile * 8) * 2 + 1
      say(string.format("%s slot %02X tile %03X  expect byte %d  full=%s  first8=%s",
        c.ch, c.slot, c.tile, want,
        full and string.format("%d(word %04X)", full, math.floor((full - 1) / 2)) or "absent",
        half and string.format("%d(word %04X)", half, math.floor((half - 1) / 2)) or "absent"))
    end
    say("DUMP-END")
  end
end