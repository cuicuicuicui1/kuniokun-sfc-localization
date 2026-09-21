-- v9.lua : push into the game and watch the story dialog path (bank $03 drawer).
-- Dumps dialog state + VRAM tilemap/glyphs as soon as a message becomes active,
-- saves a savestate at that moment, and reports whether drawing happens in
-- vblank ($4212 bit 7 snapshot at $0BE7) and whether the game then continues.
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "v9"
local MAXF = tonumber(os.getenv("HW_FRAMES") or "9000")

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
  say(string.format("--- tiles @%s frame=%d draws=%d ppustat=%02X", label,
    emu.framecount(), rd(0x0BE6), rd(0x0BE7)))
  say(string.format("  row=%02X col=%02X stage=%02X len=%02X idx=%02X flag=%02X 036D=%02X 0011=%02X",
    rd(0x036E), rd(0x036F), rd(0x09DF), rd(0x03E8), rd(0x03E9), rd(0x0374), rd(0x036D), rd(0x0011)))
  say(string.format("  INSTR code=%02X idx_in=%02X col_in=%02X dbr_in=%02X idx_out=%02X col_out=%02X draws=%d ppu=%02X dbr_out=%02X s_out=%02X",
    rd(0x0BE0), rd(0x0BE1), rd(0x0BE2), rd(0x0BE3), rd(0x0BE4), rd(0x0BE5), rd(0x0BE6), rd(0x0BE7), rd(0x0BE8), rd(0x0BEA)))
  local t = {}
  for i = 0, 0x37 do t[#t + 1] = string.format("%02X", rd(0x03EA + i)) end
  say("  msg 03EA: " .. table.concat(t, " "))
  t = {}
  for i = 0, 0x5F do t[#t + 1] = string.format("%02X", rd(0x0B00 + i)) end
  say("  scr 0B00: " .. table.concat(t, " "))
  for row = 0, 5 do
    local base = 0x7C00 + row * 0x40
    local w, seen = {}, {}
    for c = 0, 25 do
      local v = vw(base + c)
      w[#w + 1] = string.format("%04X", v)
      seen[v % 1024] = true
    end
    say(string.format("  tm row%d %04X: %s", row, base, table.concat(w, " ")))
    for tile = 2, 1023 do
      if seen[tile] then
        local b = {}
        local bbase = 0x6000 + tile * 8
        for k = 0, 15 do
          b[#b + 1] = string.format("%02X%02X", vb(bbase + k * 2), vb(bbase + k * 2 + 1))
        end
        say(string.format("    glyph tile=%d pair=%d: %s", tile, math.floor(tile / 2), table.concat(b, " ")))
      end
    end
  end
end

say("tag=" .. TAG .. " rom=" .. tostring(gameinfo.getromname()) .. " " .. tostring(gameinfo.getromhash()))
local idx, same, lastd, sawdlg, saved = 0, 0, -1, false, false
local dlgframes = 0
while emu.framecount() < MAXF do
  idx = idx + 1
  -- title: Start/A taps first, then wander with the d-pad like a player would
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 then
    local dirs = { "Right", "Down", "Left", "Up" }
    joypad.set({ [dirs[(math.floor(idx / 37) % 4) + 1]] = true }, 1)
  end
  emu.frameadvance()
  local d = digest()
  if d == lastd then same = same + 1 else same = 0 end
  lastd = d

  local len, flag, col = rd(0x03E8), rd(0x0374), rd(0x036F)
  if (idx % 60) == 0 then
    say(string.format("i *INSTR code=%02X idx_in=%02X col_in=%02X dbr_in=%02X | idx_out=%02X col_out=%02X draws=%d ppu=%02X dbr_out=%02X s_out=%02X",
      rd(0x0BE0), rd(0x0BE1), rd(0x0BE2), rd(0x0BE3), rd(0x0BE4), rd(0x0BE5), rd(0x0BE6), rd(0x0BE7), rd(0x0BE8), rd(0x0BEA)))
  end
  local active = (len > 0) or (flag % 128 >= 64) or (col > 0)
  if active then
    dlgframes = dlgframes + 1
    if not sawdlg then
      sawdlg = true
      say("FIRST ACTIVE DIALOG at frame " .. emu.framecount())
      pcall(function() savestate.save(OUT .. "/" .. TAG .. "_dlg.state") end)
      say("  savestate saved: " .. tostring(pcall(function() savestate.save(OUT .. "/" .. TAG .. "_dlg.state") end)))
    end
    if dlgframes <= 40 or (dlgframes % 200) == 0 then dumptiles("dlg" .. dlgframes) end
  end
  if (idx % 800) == 0 then
    say(string.format("f=%d draws=%d ppu=%02X len=%02X idx=%02X col=%02X flag=%02X dlgframes=%d",
      emu.framecount(), rd(0x0BE6), rd(0x0BE7), len, rd(0x03E9), col, flag, dlgframes))
    client.screenshot(string.format("%s/%s_f%05d.png", OUT, TAG, emu.framecount()))
  end
  if same >= 120 and sawdlg then
    say("STALLED at frame " .. emu.framecount() .. " with a dialog active")
    dumptiles("stalled")
    client.screenshot(string.format("%s/%s_STALL.png", OUT, TAG))
    break
  end
end
client.screenshot(string.format("%s/%s_END.png", OUT, TAG))
say(string.format("done frame=%d draws=%d sawdialog=%s dlgframes=%d", emu.framecount(), rd(0x0BE6), tostring(sawdlg), dlgframes))
log:close()