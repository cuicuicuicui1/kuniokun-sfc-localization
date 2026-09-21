-- v62: v61 + the message-hook debug markers.
--   per frame: log a line whenever $0DF1/$0DF2/$0DF3 (hook entries, blank
--   branch taken, blank loop finished) or the probe word at VRAM $7FFE change;
--   at each frame in HW_ATS also dump the VRAM image and the engine state.
-- env: HW_TAG HW_ATS("1381,1400,...") HW_ROM HW_SHOTS
local TAG   = os.getenv('HW_TAG') or 'v62'
local ATS   = os.getenv('HW_ATS') or '1381,1400,1420,1440,1460,1490,1520,1560,1600,1700,1800,2000,2200,2400'
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix9d.smc'
local SHOTS = (os.getenv('HW_SHOTS') or '0') == '1'
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)

local want = {}
local last = 0
for s in string.gmatch(ATS, '%d+') do
  local n = tonumber(s)
  want[n] = true
  if n > last then last = n end
end

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function rd(a) return memory.read_u8(a, 'WRAM') end
local function vramb(a) return memory.read_u8(a, 'VRAM') end
local function vramw(w) return vramb(w * 2) + vramb(w * 2 + 1) * 256 end

local prev_m1, prev_m2, prev_m3, prev_mkr, prev_pat = -1, -1, -1, -1, -1

local function markers(frame)
  local m1, m2, m3 = rd(0x0DF1), rd(0x0DF2), rd(0x0DF3)
  local mkr = vramw(0x7FFE)
  local pat = vramw(0x6008) + vramw(0x6009) * 65536
  if m1 ~= prev_m1 or m2 ~= prev_m2 or m3 ~= prev_m3 or mkr ~= prev_mkr or pat ~= prev_pat then
    log:write(string.format('F=%d MARKER entries=%d blanked=%d done=%d word7FFE=%04X pattern6008=%08X\n',
      frame, m1, m2, m3, mkr, pat))
    prev_m1, prev_m2, prev_m3, prev_mkr, prev_pat = m1, m2, m3, mkr, pat
  end
end

local function dump(frame)
  local name = string.format('%s_f%d_vram.bin', TAG, frame)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 0, 0x3FFF do t[i] = vramb(0xC000 + i) end
  for i = 0, 0x3FFF do f:write(string.char(t[i])) end
  f:close()
  local up, lo, blanks = 0, 0, 0
  for r = 0, 15 do
    for c = 0, 63 do
      local w = vramw(0x7C00 + r * 0x40 + c)
      if w == 0x2C00 then blanks = blanks + 1
      elseif c < 32 then up = up + 1 else lo = lo + 1 end
    end
  end
  local buf = {}
  for i = 0, 47 do buf[#buf + 1] = string.format('%02X', rd(0x03EA + i)) end
  log:write(string.format(
    'F=%d cells upper=%d lower=%d blank=%d  e8=%02X e9=%02X col=%02X row=%02X line=%02X 73=%02X 74=%02X dd=%02X df=%02X\n',
    frame, up, lo, blanks, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E),
    rd(0x036D), rd(0x0373), rd(0x0374), rd(0x09DD), rd(0x09DF)))
  log:write('  buf ' .. table.concat(buf, ' ') .. '\n')
  log:write(string.format('  %s\n', name))
  log:flush()
  if SHOTS then
    client.screenshot(string.format('%s_f%d', TAG, frame))
  end
end

while emu.framecount() < last do
  local i = emu.framecount()
  markers(i)
  if want[i] then
    dump(i)
    want[i] = false
  end
  if i < 420 and (i % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (i % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  if emu.framecount() > i + 60 then
    log:write('stalled at ' .. tostring(i) .. '\n')
    break
  end
end
log:write('done at F=' .. tostring(emu.framecount()) .. '\n')
log:close()