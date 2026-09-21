-- v8.lua : verify the rebuilt patch in BizHawk -- does the dialog draw glyphs
-- into VRAM, does the game keep running, and does drawing happen in vblank?
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v8"
local MAXF = tonumber(os.getenv("HW_FRAMES") or "3000")

pcall(function() client.speedmode("turbo") end)
pcall(function() emu.limitframerate(false) end)

local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
local function rd(a) return memory.read_u8(a, "WRAM") end
local function vw(a) return memory.read_u16_le(a, "VRAM") end
local function vb(a) return memory.read_u8(a, "VRAM") end

local function digest()
  local h = 5381
  for a = 0x0000, 0x07FF do h = (h * 33 + rd(a)) % 4294967296 end
  for a = 0x0B00, 0x0BFF do h = (h * 33 + rd(a)) % 4294967296 end
  return h
end

local function dumptiles(label)
  say(string.format("--- tiles @%s frame=%d draws=$0BE6=%d ppustat=$0BE7=%02X",
    label, emu.framecount(), rd(0x0BE6), rd(0x0BE7)))
  say(string.format("  row=%02X col=%02X stage/09DF=%02X len/03E8=%02X idx/03E9=%02X flag/0374=%02X",
    rd(0x036E), rd(0x036F), rd(0x09DF), rd(0x03E8), rd(0x03E9), rd(0x0374)))
  local t = {}
  for i = 0, 0x1F do t[#t + 1] = string.format("%02X", rd(0x03EA + i)) end
  say("  msg 03EA: " .. table.concat(t, " "))
  for row = 0, 5 do
    local base = 0x7C00 + row * 0x40
    local w, seen = {}, {}
    for c = 0, 25 do
      local v = vw(base + c)
      w[#w + 1] = string.format("%04X", v)
      local tile = v % 1024
      seen[tile] = true
    end
    say(string.format("  tm row%d %04X: %s", row, base, table.concat(w, " ")))
    -- glyph bytes for the tiles actually used in this row
    for tile = 0, 1023 do
      if seen[tile] and tile >= 2 then
        local g, b = {}, {}
        local bbase = 0x6000 + tile * 8
        for k = 0, 15 do
          local v = vb(bbase + k * 2)
          local hi = vb(bbase + k * 2 + 1)
          b[#b + 1] = string.format("%02X%02X", v, hi)
        end
        say(string.format("    glyph tile=%d pair=%d: %s", tile, math.floor(tile / 2),
          table.concat(b, " ")))
      end
    end
  end
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()) .. " " .. tostring(gameinfo.getromhash()))
local idx, same, lastd = 0, 0, -1
while emu.framecount() < MAXF do
  idx = idx + 1
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if (idx % 200) == 150 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  local d = digest()
  if d == lastd then same = same + 1 else same = 0 end
  lastd = d
  if (idx % 60) == 0 then
    local draws = rd(0x0BE6)
    say(string.format("f=%d draws=$0BE6=%d ppu=$0BE7=%02X row=%02X col=%02X stage=%02X len=%02X idx=%02X 0374=%02X",
      emu.framecount(), draws, rd(0x0BE7), rd(0x036E), rd(0x036F), rd(0x09DF), rd(0x03E8), rd(0x03E9), rd(0x0374)))
  end
  if idx == tonumber(os.getenv("HW_DUMP") or "300") then dumptiles("first") end
  if idx == (tonumber(os.getenv("HW_DUMP") or "300") + 120) then dumptiles("second") end
  if (idx % 600) == 0 then
    client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, emu.framecount()))
  end
  if same == 90 then
    say("STUCK at frame " .. emu.framecount())
    dumptiles("stuck")
    client.screenshot(string.format("%s/%s_STUCK.png", OUT, TAG))
    break
  end
end
client.screenshot(string.format("%s/%s_END.png", OUT, TAG))
say("done frame=" .. emu.framecount() .. " draws=$0BE6=" .. rd(0x0BE6))
log:close()