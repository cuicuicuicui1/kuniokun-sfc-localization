-- wramwatch: at every message-completion shot, dump low WRAM (0x0000-0x1FFF),
-- VRAM (font window + box tilemap), and a screenshot.  Offline, the label is
-- decoded from the box's first row tiles and matched against the record pool;
-- then WRAM cells holding the speaker-record index are found by value scan.
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'wramwatch'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '2500') or 2500
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function rd(a) return memory.read_u8(a, 'WRAM') end
local function vramb(a) return memory.read_u8(a, 'VRAM') end
local function vramw(w) return vramb(w * 2) + vramb(w * 2 + 1) * 256 end
local function dump(frame)
  local f = assert(io.open(string.format('%s%s_f%05d_wram.bin', OUT, TAG, frame), 'wb'))
  for i = 0, 0x1FFF do f:write(string.char(rd(i))) end
  f:close()
  local g = assert(io.open(string.format('%s%s_f%05d_vram.bin', OUT, TAG, frame), 'wb'))
  for i = 0, 0x3FFF do g:write(string.char(vramb(0xC000 + i))) end
  g:close()
  local n = rd(0x09DF)
  local b2 = assert(io.open(string.format('%s%s_f%05d_buf.bin', OUT, TAG, frame), 'wb'))
  for i = 0, 96 do b2:write(string.char(rd(0x03E9 + i))) end
  b2:close()
  log:write(string.format('F=%d SHOT df=%02X\n', frame, n))
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
  if i >= 200 and i % 20 == 0 then joypad.set({A = true}) end
  emu.frameadvance()
end
dump(emu.framecount())
log:write('done')
log:flush()
