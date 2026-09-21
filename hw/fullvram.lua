-- fullvram: dump the ENTIRE 64KB VRAM + 512B CGRAM + key screen regs at fixed
-- frames (HW_ATS list), on whatever ROM is loaded.  For graphics recon.
-- env: HW_TAG HW_ATS HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'fullvram'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '500') or 500
local want = {}
local last = UNTIL
for s in string.gmatch(os.getenv('HW_ATS') or '440', '%d+') do
  local n = tonumber(s); want[n] = true; if n > last then last = n end
end

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

local function dump(frame)
  local f = assert(io.open(string.format('%s%s_f%05d_vram64.bin', OUT, TAG, frame), 'wb'))
  local t = {}
  for i = 0, 0xFFFF do t[i] = memory.read_u8(i, 'VRAM') end
  for i = 0, 0xFFFF do f:write(string.char(t[i])) end
  f:close()
  local c = assert(io.open(string.format('%s%s_f%05d_cgram.bin', OUT, TAG, frame), 'wb'))
  for i = 0, 0x1FF do c:write(string.char(memory.read_u8(i, 'CGRAM'))) end
  c:close()
  log:write(string.format('F=%d dumped vram64+cg\n', frame))
  log:flush()
  client.screenshot(string.format('%s_f%05d.png', TAG, frame))
end

while emu.framecount() < last do
  local i = emu.framecount()
  if want[i] then dump(i) end
  if i == 150 or i == 300 then joypad.set({ Start = true }) end
  emu.frameadvance()
end
dump(emu.framecount())
log:write('done\n')
log:flush()
