-- prev16: deep preview run for the final 16x16 build.  Same input script as
-- v70, but instead of a fixed ATS list it takes a screenshot + VRAM dump
-- ~15 frames after every message completes ($0373 C0/80 -> 00).  Files carry
-- the .png extension (client.screenshot does not add one).
-- env: HW_TAG HW_UNTIL HW_ROM
local TAG   = os.getenv('HW_TAG') or 'kwdeep'
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kw1.smc'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '16000') or 16000
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function rd(a) return memory.read_u8(a, 'WRAM') end
local function vramb(a) return memory.read_u8(a, 'VRAM') end
local function vramw(w) return vramb(w * 2) + vramb(w * 2 + 1) * 256 end

local function rows()
  local t = {}
  for r = 0, 15 do
    local s = {}
    for c = 0, 25 do
      local a = vramw(0x7C00 + r * 0x40 + 3 + c)
      local b = vramw(0x7C00 + r * 0x40 + 3 + 0x20 + c)
      if a == 0x2C00 and b == 0x2C00 then s[#s + 1] = '.'
      else s[#s + 1] = (c < 10 and string.char(48 + c) or 'X') end
    end
    t[#t + 1] = string.format('%X %s', r, table.concat(s))
  end
  return table.concat(t, ' | ')
end

local function dump(frame)
  local name = string.format('%s_f%05d_vram.bin', TAG, frame)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 0, 0x3FFF do t[i] = vramb(0xC000 + i) end
  for i = 0, 0x3FFF do f:write(string.char(t[i])) end
  f:close()
  local up, lo, blank = 0, 0, 0
  for r = 0, 15 do
    for c = 0, 63 do
      local w = vramw(0x7C00 + r * 0x40 + c)
      if w == 0x2C00 then blank = blank + 1
      elseif c < 32 then up = up + 1 else lo = lo + 1 end
    end
  end
  log:write(string.format('F=%d SHOT cells upper=%d lower=%d blank=%d col=%02X row=%02X line=%02X 73=%02X df=%02X\n',
    frame, up, lo, blank, rd(0x036F), rd(0x036E), rd(0x036D), rd(0x0373), rd(0x09DF)))
  log:write('  rows ' .. rows() .. '\n')
  log:flush()
  client.screenshot(string.format('%s_f%05d.png', TAG, frame))
end

local pending = nil
local prev73 = nil
while emu.framecount() < UNTIL do
  local i = emu.framecount()
  local s73 = rd(0x0373)
  if prev73 and prev73 ~= s73 and s73 == 0x00 and (prev73 == 0xC0 or prev73 == 0x80) then
    if not pending then pending = i + 15 end
  end
  prev73 = s73
  if pending and i >= pending then
    pending = nil
    dump(i)
  end
  if i == 150 or i == 300 or i == 450 then joypad.set({Start = true}) end
  if i > 900 then
    if i % 1200 == 1100 then joypad.set({Start = true}) end
    if i % 120 < 55 then joypad.set({Right = true}) end
  end
  if i >= 200 and i % 20 == 0 then joypad.set({A = true}) end
  emu.frameadvance()
end
dump(emu.framecount())
log:write('done\n')
log:flush()
