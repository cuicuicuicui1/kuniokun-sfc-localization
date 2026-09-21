-- v36.lua: dump VRAM bytes 0xC000-0xFFFF (= words $6000-$7FFF) at a given frame.
-- env: HW_TAG, HW_AT (frame), HW_ROM
local TAG = os.getenv('HW_TAG') or 'v36'
local AT  = tonumber(os.getenv('HW_AT') or '1560')
local ROMF = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix2.smc'
local out = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/' .. TAG .. '_vram.bin'
while emu.framecount() < AT do
  local idx = emu.framecount()
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  emu.frameadvance()
end
local t = {}
for i = 0, 0x3FFF do t[i] = memory.read_u8(0xC000 + i, 'VRAM') end
local f = io.open(out, 'wb')
for i = 0, 0x3FFF do f:write(string.char(t[i])) end
f:close()
local fh = io.open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/' .. TAG .. '.log', 'w')
fh:write(string.format('F=%d dumped %d bytes\n', emu.framecount(), 0x4000))
fh:write(string.format('e8=%02X e9=%02X col=%02X row=%02X line=%02X 73=%02X 74=%02X\n',
  memory.read_u8(0x03E8,'WRAM'), memory.read_u8(0x03E9,'WRAM'), memory.read_u8(0x036F,'WRAM'),
  memory.read_u8(0x036E,'WRAM'), memory.read_u8(0x036D,'WRAM'),
  memory.read_u8(0x0373,'WRAM'), memory.read_u8(0x0374,'WRAM')))
fh:close()
while true do emu.frameadvance() end