-- v25.lua : does the display read the font window at $6000?
-- Controlled experiment: run to frame 1395, screenshot A; step one frame, screenshot B;
-- reload the 1395 savestate, poke marker patterns into the tiles the on-screen glyphs use
-- (0x98 = the name's first glyph, 0x9C = the slot of the first CJK char), step one frame,
-- screenshot C.  B vs C differ only by the poke, so a pixel diff proves the display reads
-- those VRAM locations.  Also prints whether the markers survive.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v25"
local TO = tonumber(os.getenv("HW_TO") or "1400")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function hex(t) local s = ""; for i = 0, 7 do s = s .. string.format("%02X", t[i] % 256) end; return s end
local function read32(base)
  local t = {}
  for i = 0, 31 do t[i] = memory.read_u8(base + i, "VRAM") or -1 end
  return t
end
local function poke(base, seed)
  for i = 0, 31 do memory.write_u8(base + i, (seed + i) % 256, "VRAM") end
end

local idx = 0
while emu.framecount() < 1395 do
  idx = idx + 1
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
end
say(string.format("reached F=%d e8=%02X e9=%02X col=%02X 73=%02X", emu.framecount(),
  rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x0373)))
client.screenshot(OUT .. "/" .. TAG .. "_A_f1395.png")
say("A t98=" .. hex(read32(0xC980)) .. "  t9C=" .. hex(read32(0xC9C0)))
savestate.save(OUT .. "/" .. TAG .. "_f1395.state")

emu.frameadvance()
say("B frame=" .. tostring(emu.framecount()) .. " t98=" .. hex(read32(0xC980)) .. "  t9C=" .. hex(read32(0xC9C0)))
client.screenshot(OUT .. "/" .. TAG .. "_B_f1396.png")

savestate.load(OUT .. "/" .. TAG .. "_f1395.state")
say("reloaded F=" .. tostring(emu.framecount()))
poke(0xC980, 0x80)   -- tile 0x98 (name's first glyph)
poke(0xC9C0, 0xA0)   -- tile 0x9C (slot 0x3F, CJK char 1)
say("CVRAM t98=" .. hex(read32(0xC980)) .. "  t9C=" .. hex(read32(0xC9C0)))
emu.frameadvance()
say("C frame=" .. tostring(emu.framecount()) .. " t98=" .. hex(read32(0xC980)) .. "  t9C=" .. hex(read32(0xC9C0)))
client.screenshot(OUT .. "/" .. TAG .. "_C_f1396.png")

-- a couple more frames: do the markers survive on screen?
for i = 1, 3 do emu.frameadvance() end
say(string.format("D frame=%d t98=%s t9C=%s", emu.framecount(), hex(read32(0xC980)), hex(read32(0xC9C0))))
client.screenshot(OUT .. "/" .. TAG .. "_D_f1399.png")
log:close()