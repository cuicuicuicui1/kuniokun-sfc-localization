-- v61: dump everything an analysis needs, at a list of frames.
--   * VRAM bytes $C000-$FFFF = words $6000-$7FFF (glyph tiles $6000-$67FF and
--     the whole tile map $7800-$7FFF) into hw/<TAG>_f<frame>_vram.bin
--   * one log line per frame with the engine's text state and the message buffer
--   * optional PNG per frame (HW_SHOTS=1) for py41-style pixel checks
-- env: HW_TAG HW_ATS("1381,1400,...") HW_ROM HW_SHOTS
local TAG   = os.getenv('HW_TAG') or 'v61'
local ATS   = os.getenv('HW_ATS') or '1381,1400,1420,1440,1460,1490,1520,1560,1600,1700,1800,2000,2200,2400'
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix8.smc'
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

local function dump(frame)
  local name = string.format('%s_f%d_vram.bin', TAG, frame)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 0, 0x3FFF do t[i] = vramb(0xC000 + i) end
  for i = 0, 0x3FFF do f:write(string.char(t[i])) end
  f:close()
  -- how many text cells are non blank, upper and lower half, rows 16..31
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
  if want[i] then
    dump(i)
    want[i] = false
  end
  if i < 420 and (i % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (i % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
  if emu.framecount() > i + 60 then           -- the probe itself must not stall
    log:write('stalled at ' .. tostring(i) .. '\n')
    break
  end
end
log:write('done at F=' .. tostring(emu.framecount()) .. '\n')
log:close()