-- v63: v61's VRAM dumps plus a marker line whenever the message hook's debug
-- counters or the two CPU store probes change.  Probe A writes $6008 with
-- single byte stores, probe B writes $6009 with a 16 bit store, and the queue
-- probe (still in the old build) wrote $7FFE, so one line shows which store
-- forms can reach VRAM at all.
-- env: HW_TAG HW_ATS("1381,1400,...") HW_ROM HW_SHOTS
local TAG   = os.getenv('HW_TAG') or 'v63'
local ATS   = os.getenv('HW_ATS') or '1381,1400,1420,1440,1460,1490,1520,1560,1600,1700,1800,2000,2200,2400'
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix10.smc'
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

local function counts()
  local up, lo, blanks = 0, 0, 0
  for r = 0, 15 do
    for c = 0, 63 do
      local w = vramw(0x7C00 + r * 0x40 + c)
      if w == 0x2C00 then blanks = blanks + 1
      elseif c < 32 then up = up + 1 else lo = lo + 1 end
    end
  end
  return up, lo, blanks
end

local function dump(frame, up, lo, blanks)
  local name = string.format('%s_f%d_vram.bin', TAG, frame)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 0, 0x3FFF do t[i] = vramb(0xC000 + i) end
  for i = 0, 0x3FFF do f:write(string.char(t[i])) end
  f:close()
  local buf = {}
  for i = 0, 47 do buf[#buf + 1] = string.format('%02X', rd(0x03EA + i)) end
  log:write(string.format(
    'F=%d cells upper=%d lower=%d blank=%d  e8=%02X e9=%02X col=%02X row=%02X line=%02X 73=%02X 74=%02X dd=%02X df=%02X\n',
    frame, up, lo, blanks, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E),
    rd(0x036D), rd(0x0373), rd(0x0374), rd(0x09DD), rd(0x09DF)))
  log:write('  buf ' .. table.concat(buf, ' ') .. '\n')
  if SHOTS then client.screenshot(string.format('%s_f%d', TAG, frame)) end
  log:flush()
end

local lm = ''
while emu.framecount() < last do
  local i = emu.framecount()
  -- marker line when anything the hook does changes
  local mk = string.format('%d %d %d %04X %04X %04X %04X %04X', rd(0x0DF1), rd(0x0DF2),
    rd(0x0DF3), vramw(0x6008), vramw(0x6009), vramw(0x600A), vramw(0x7FFE), vramw(0x7C03))
  if mk ~= lm then
    lm = mk
    log:write(string.format('  %s\n', mk))
    log:write(string.format('F=%d MARKER entries=%d blanked=%d done=%d probeA_6008=%04X probeB_6009=%04X probeC_600A=%04X q_7FFE=%04X q_7C03=%04X\n',
      i, rd(0x0DF1), rd(0x0DF2), rd(0x0DF3), vramw(0x6008), vramw(0x6009), vramw(0x600A), vramw(0x7FFE), vramw(0x7C03)))
    log:flush()
  end
  if i % 200 == 0 then
    log:write('H F=' .. i)
    log:write(string.char(10))
    log:flush()
  end
  if want[i] then
    local ok, err = pcall(function()
      local up, lo, blanks = counts()
      dump(i, up, lo, blanks)
    end)
    if not ok then
      log:write('ERR ' .. tostring(err))
      log:write(string.char(10))
      log:flush()
    end
  end
  if i == 420 then
    log:write('--- input: start every 150 frames, A every 30\n')
    log:flush()
  end
  -- input: Start at 150/300/450, then A every 20 frames
  if i == 150 or i == 300 or i == 450 then joypad.set({Start = true}) end
  if i >= 200 and i % 20 == 0 then joypad.set({A = true}) end
  emu.frameadvance()
end
local up, lo, blanks = counts()
dump(emu.framecount(), up, lo, blanks)
log:write('done\n')
log:close()