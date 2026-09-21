-- menu22: open the menu through the state machine, dump VRAM every 20 frames,
-- close it, keep dumping.  The dumps are diffed offline to find every tile the
-- engine writes (our own slot tiles are known from the builder).
local TAG  = os.getenv('HW_TAG') or 'menu22'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function dump(n)
  local f = assert(io.open(OUT .. TAG .. '_' .. n .. '_vram.bin', 'wb'))
  for a = 0, 65535 do f:write(string.char(vb(a))) end
  f:close()
end
local ok = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('state ' .. tostring(ok))
for _ = 1, 60 do emu.frameadvance() end
dump('00_idle')
line('idle 92=%02X 74=%02X 6E=%02X' % (w(0x0392), w(0x0374), w(0x036E)))
-- open the menu: gate + step 26
memory.write_u8(0x0374, w(0x0374) | 0x10, 'WRAM')
memory.write_u8(0x0392, 26, 'WRAM')
for i = 1, 8 do
  for _ = 1, 20 do emu.frameadvance() end
  dump(string.format('%02d_menu', i))
  line(string.format('menu %d 92=%02X 74=%02X 6E=%02X 91=%02X', i, w(0x0392), w(0x0374), w(0x036E), w(0x0391)))
end
-- close it
memory.write_u8(0x0392, 31, 'WRAM')
for i = 1, 4 do
  for _ = 1, 20 do emu.frameadvance() end
  dump(string.format('%02d_after', i))
  line(string.format('after %d 92=%02X 74=%02X 6E=%02X', i, w(0x0392), w(0x0374), w(0x036E)))
end
line('done')
