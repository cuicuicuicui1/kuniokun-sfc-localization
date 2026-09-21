-- v70: row blanking test.  Per frame it logs the drawer state and the box
-- contents, dumps VRAM at HW_ATS frames, dumps the upload queue at HW_QS
-- frames, and can chain runs through a savestate (HW_LOAD / HW_SAVE).
-- env: HW_TAG HW_ATS HW_QS HW_SHOTS HW_LOAD HW_SAVE HW_UNTIL HW_ROM
local TAG   = os.getenv('HW_TAG') or 'v70'
local ATS   = os.getenv('HW_ATS') or '1570,1600,1640,1690'
local QS    = os.getenv('HW_QS') or ''
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kw1.smc'
local SHOTS = (os.getenv('HW_SHOTS') or '0') == '1'
local LOAD  = os.getenv('HW_LOAD') or ''
local SAVE  = os.getenv('HW_SAVE') or ''
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '0') or 0
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)

local want, wantq = {}, {}
local last = UNTIL
for s in string.gmatch(ATS, '%d+') do
  local n = tonumber(s); want[n] = true
  if n > last then last = n end
end
for s in string.gmatch(QS, '%d+') do
  local n = tonumber(s); wantq[n] = true
  if n > last then last = n end
end
if last == 0 then last = 1700 end

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

-- fingerprint of every text row: '#' for a cell that is not blank
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
  local name = string.format('%s_f%d_vram.bin', TAG, frame)
  local f = assert(io.open(OUT .. name, 'wb'))
  local t = {}
  for i = 0, 0x3FFF do t[i] = vramb(0xC000 + i) end
  for i = 0, 0x3FFF do f:write(string.char(t[i])) end
  f:close()
  local up, lo, blanks = counts()
  local buf = {}
  for i = 0, 47 do buf[#buf + 1] = string.format('%02X', rd(0x03EA + i)) end
  log:write(string.format(
    'F=%d cells upper=%d lower=%d blank=%d e8=%02X e9=%02X col=%02X row=%02X line=%02X 73=%02X 74=%02X dd=%02X df=%02X\n',
    frame, up, lo, blanks, rd(0x03E8), rd(0x03E9), rd(0x036F), rd(0x036E),
    rd(0x036D), rd(0x0373), rd(0x0374), rd(0x09DD), rd(0x09DF)))
  log:write('  buf ' .. table.concat(buf, ' ') .. '\n')
  log:write('  rows ' .. rows() .. '\n')
  if SHOTS then client.screenshot(string.format('%s_f%d', TAG, frame)) end
  log:flush()
end

local function dumpqueue(frame)
  local n = rd(0x09DF)
  local t = {}
  for i = 0, math.min(n, 0xE0) do t[#t + 1] = string.format('%02X', rd(0x0B00 + i)) end
  log:write(string.format('F=%d QUEUE df=%02X dd=%02X col=%02X row=%02X : %s\n',
    frame, n, rd(0x09DD), rd(0x036F), rd(0x036E), table.concat(t, ' ')))
  log:flush()
end

if LOAD ~= '' then
  local ok, err = pcall(function() savestate.load(LOAD) end)
  log:write(string.format('load %s ok=%s %s\n', LOAD, tostring(ok), tostring(err)))
  log:flush()
end

local lm = ''
while emu.framecount() < last do
  local i = emu.framecount()
  local mk = string.format('%02X %02X %02X %02X %02X', rd(0x03E9), rd(0x036F),
    rd(0x036E), rd(0x0373), rd(0x09DF))
  if mk ~= lm then
    lm = mk
    log:write(string.format('F=%d MARK e9=%02X col=%02X row=%02X 73=%02X df=%02X\n',
      i, rd(0x03E9), rd(0x036F), rd(0x036E), rd(0x0373), rd(0x09DF)))
    log:flush()
  end
  if wantq[i] then dumpqueue(i) end
  if want[i] then dump(i) end
  if LOAD == '' then
    if i == 150 or i == 300 or i == 450 then joypad.set({Start = true}) end
    if i >= 200 and i % 20 == 0 then joypad.set({A = true}) end
  else
    if i % 20 == 0 then joypad.set({A = true}) end
  end
  emu.frameadvance()
end
dump(emu.framecount())
if SAVE ~= '' then
  local ok, err = pcall(function() savestate.save(SAVE) end)
  log:write(string.format('save %s ok=%s %s\n', SAVE, tostring(ok), tostring(err)))
end
log:write('done\n')
log:flush()