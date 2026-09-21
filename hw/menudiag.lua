local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v19.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. 'mdiag.log', 'w'))
local sf = io.open(SRAM, 'rb')
if sf then local d = sf:read('*a'); sf:close(); for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end
for f = 1, 4000 do
  local k = f % 240
  local pad = {}
  if k % 20 < 3 then pad = { A = true } end
  if k == 100 or k == 130 then pad = { Start = true } end
  joypad.set(pad)
  emu.frameadvance()
  if f % 250 == 0 then
    local tab = memory.read_bytes_as_array(0x040A, 52, 'WRAM')
    local nz = 0
    for i = 1, 52 do if tab[i] ~= 0 then nz = nz + 1 end end
    log:write(string.format('f=%5d 040A nz=%2d  first=%02X %02X %02X  0363=%02X 0392=%02X 0395=%02X 0368=%02X 0374=%02X 03B7=%02X\n',
      f, nz, tab[1], tab[2], tab[3],
      memory.read_u8(0x0363,'WRAM'), memory.read_u8(0x0392,'WRAM'), memory.read_u8(0x0395,'WRAM'),
      memory.read_u8(0x0368,'WRAM'), memory.read_u8(0x0374,'WRAM'), memory.read_u8(0x03B7,'WRAM')))
    log:flush()
    client.screenshot(string.format('mdiag_f%05d', f))
  end
end
log:write('done\n'); log:flush(); client.exit()
