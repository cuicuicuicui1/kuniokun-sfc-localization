-- v32.lua : determine the PPU's real tile bit layout.
-- SNES 2bpp tiles are documented as plane-interleaved (bytes 0-7 = plane 0),
-- while my writer (sfc_tools.pack_8x8) emits row-interleaved
-- (byte[y*2]=plane0, byte[y*2+1]=plane1).  If they disagree, every glyph I
-- upload is displayed permuted -- and my own readers, sharing the wrong
-- assumption, would still report perfect matches.
--
-- Method: at frame 1395 the message row shows my 5 CJK glyphs in cells
-- col5..col9, whose TOP tiles are 0x9C 0xE6 0x04 0x3E 0x68.  Poke each of
-- those tiles with a pattern that decodes differently under the two layouts,
-- then read the resulting screen cells.  Screenshots B (no poke) and C (poke)
-- are one frame apart from the same savestate, so any pixel difference is the
-- poke's effect alone.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v32"
local TO = tonumber(os.getenv("HW_TO") or "1400")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function rd32(base)
  local s = ""
  for i = 0, 31 do s = s .. string.format("%02X", memory.read_u8(base + i, "VRAM") or -1) end
  return s
end

-- tile index -> 16-byte pattern written row-interleaved (as my writer would)
local TESTS = {
  { 0x9C, 0xFF, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0xE6, 0x00, 0x00, 0x00, 0x00, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0x04, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0 },
  { 0x3E, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF },
  { 0x68, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF, 0x00, 0xFF },
}

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

savestate.save(OUT .. "/" .. TAG .. "_f1395.state")
emu.frameadvance()
client.screenshot(OUT .. "/" .. TAG .. "_B_f1396.png")
say("B (no poke) frame=" .. tostring(emu.framecount()))

savestate.load(OUT .. "/" .. TAG .. "_f1395.state")
for _, t in ipairs(TESTS) do
  local tile = t[1]
  for i = 0, 15 do
    memory.write_u8(0xC000 + tile * 16 + i, t[2 + i] % 256, "VRAM")
  end
  say(string.format("poked tile %02X -> %s", tile, rd32(0xC000 + tile * 16)))
end
emu.frameadvance()
say("C (poked) frame=" .. tostring(emu.framecount()))
client.screenshot(OUT .. "/" .. TAG .. "_C_f1396.png")
log:close()