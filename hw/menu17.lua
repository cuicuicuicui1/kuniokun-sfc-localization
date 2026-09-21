-- menu17: load the user's own battery save, pick file 1 and dump everything at
-- the story point they are stuck on (the room with the choice prompt): the box
-- content map rows, VRAM, CGRAM and screenshots.
-- env: HW_TAG HW_ROM HW_SRAM
local TAG  = os.getenv('HW_TAG') or 'menu17'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v10.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function rowcells(r)
  local t = {}
  for c = 0, 31 do
    local v = vw(0x7C00 + r * 0x20 + c)
    t[#t + 1] = (v == 0x2C00) and '.' or string.format('%03X', v % 0x400)
  end
  return table.concat(t, ' ')
end
local function mapdump(tag)
  line('--- box map $7C00 ' .. tag)
  for r = 0, 31 do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 91=%02X 92=%02X 9E=%02X 9C=%02X 9B=%02X 9A=%02X C1=%02X pend=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0391), w(0x0392),
    w(0x039E), w(0x039C), w(0x039B), w(0x039A), w(0x03C1), w(0x0BFB))
end
local function dump(tag)
  local f = assert(io.open(OUT .. TAG .. '_' .. tag .. '_vram.bin', 'wb'))
  for a = 0, 65535 do f:write(string.char(vb(a))) end
  f:close()
  local ok, cg = pcall(function()
    local t = {}
    for a = 0, 511 do t[#t + 1] = string.char(memory.read_u8(a, 'CGRAM')) end
    return table.concat(t)
  end)
  if ok then
    local g = assert(io.open(OUT .. TAG .. '_' .. tag .. '_cgram.bin', 'wb'))
    g:write(cg); g:close()
    line('cgram dumped')
  end
  local f2 = assert(io.open(OUT .. TAG .. '_' .. tag .. '_wram.bin', 'wb'))
  for a = 0, 0x1FFF do f2:write(string.char(w(a))) end
  f2:close()
  line('vram/wram dumped for ' .. tag)
end

-- the battery save, written into the SRAM domain before the game reads it
local sf = io.open(SRAM, 'rb')
if sf then
  local data = sf:read('*a')
  sf:close()
  for i = 1, #data do memory.write_u8(i - 1, data:byte(i), 'SRAM') end
  line('sram written: ' .. #data .. ' bytes')
else
  line('sram file not found: ' .. SRAM)
end
client.reboot_core()
line('rebooted')
for _ = 1, 120 do emu.frameadvance() end
line('after reset ' .. st())
client.screenshot(TAG .. '_00_boot')

-- pick file 1 on the file select screen
for round = 1, 4 do
  for _ = 1, 3 do joypad.set({ A = true }); emu.frameadvance() end
  joypad.set({})
  for _ = 1, 45 do emu.frameadvance() end
  line(string.format('press %d %s', round, st()))
  client.screenshot(string.format('%s_%02d', TAG, round))
end
mapdump('after file select')
dump('after')

-- walk a bit and watch for the choice prompt (the option window shows up as
-- cells in rows 28..31 while a message is on screen)
for i = 1, 40 do
  local k = i % 8
  if k < 3 then joypad.set({ A = true })
  elseif k == 4 or k == 5 then joypad.set({ Start = true })
  else joypad.set({}) end
  emu.frameadvance()
  if i % 8 == 0 then
    line(string.format('step %d %s', i, st()))
    mapdump('step ' .. i)
    client.screenshot(string.format('%s_s%02d', TAG, i))
  end
end
dump('end')
line('done')
