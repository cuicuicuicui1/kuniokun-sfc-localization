-- menu21: long drive from the user's battery save, looking for the strip above
-- the box.  Presses A/Start steadily; dumps the whole screen + VRAM + WRAM the
-- moment any cell appears in rows 28..31 of the box content map.
local TAG  = os.getenv('HW_TAG') or 'menu21'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v11.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function band()
  local n = 0
  for r = 28, 31 do
    for c = 0, 31 do
      local v = vw(0x7C00 + r * 0x20 + c)
      if v ~= 0x2C00 and v ~= 0x0000 then n = n + 1 end
    end
  end
  return n
end
local function rowcells(r)
  local t = {}
  for c = 0, 31 do
    local v = vw(0x7C00 + r * 0x20 + c)
    t[#t + 1] = (v == 0x2C00) and '.' or string.format('%03X', v % 0x400)
  end
  return table.concat(t, ' ')
end
local sf = io.open(SRAM, 'rb')
if sf then
  local data = sf:read('*a'); sf:close()
  for i = 1, #data do memory.write_u8(i - 1, data:byte(i), 'SRAM') end
  line('sram written ' .. #data)
end
client.reboot_core()
for _ = 1, 180 do emu.frameadvance() end
line('booted')
for f = 1, 30000 do
  local k = f % 40
  if k < 3 then joypad.set({ A = true })
  elseif k == 20 or k == 21 then joypad.set({ Start = true })
  else joypad.set({}) end
  if f % 1000 == 0 then
    line(string.format('f%05d 6E=%02X 92=%02X band=%d', f, w(0x036E), w(0x0392), band()))
    client.screenshot(string.format('%s_f%05d', TAG, f))
  end
  if band() >= 4 then
    line('BAND at f=' .. f)
    client.screenshot(TAG .. '_BAND')
    for r = 28, 31 do line('  r' .. r .. ' ' .. rowcells(r)) end
    local g = assert(io.open(OUT .. TAG .. '_vram.bin', 'wb'))
    for a = 0, 65535 do g:write(string.char(vb(a))) end
    g:close()
    local h = assert(io.open(OUT .. TAG .. '_wram.bin', 'wb'))
    for a = 0, 0x1FFF do h:write(string.char(w(a))) end
    h:close()
    line('dumped')
    break
  end
  emu.frameadvance()
end
line('done')
