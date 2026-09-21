-- menu10: finish the dialogue, then really open and close the Start menu and
-- watch the box content map (word $7C00) rows 0-3 / 28-31, which is where the
-- command window writes and where the band shows up.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'menu10'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
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
  for _, r in ipairs({ 0, 1, 2, 3, 26, 27, 28, 29, 30, 31 }) do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 92=%02X 9E=%02X DD=%02X DF=%02X 14=%02X 63=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0392), w(0x039E),
    w(0x09DD), w(0x09DF), w(0x0314), w(0x0363))
end
local function blank()
  for _, r in ipairs({ 0, 1, 2, 3 }) do
    for c = 0, 31 do
      local v = vw(0x7C00 + r * 0x20 + c)
      if v ~= 0x2C00 and c > 2 and c < 29 then return false end
    end
  end
  return true
end
local function press(btn, n)
  for _ = 1, n do joypad.set(btn); emu.frameadvance() end
  joypad.set({}); emu.frameadvance()
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' state ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())

-- advance the dialogue until the box is empty
for round = 1, 25 do
  if blank() then break end
  press({ A = true }, 3)
  for _ = 1, 20 do emu.frameadvance() end
end
line('box empty? ' .. tostring(blank()) .. ' ' .. st())
client.screenshot(TAG .. '_00_field')
mapdump('field, no box')

-- open the menu
press({ Start = true }, 3)
for _ = 1, 40 do emu.frameadvance() end
line('after Start ' .. st())
client.screenshot(TAG .. '_01_menu')
mapdump('menu open?')
for r = 1, 30 do
  line(string.format('  f%02d %s', r, st()))
  emu.frameadvance()
end

-- close it
press({ Start = true }, 3)
for _ = 1, 40 do emu.frameadvance() end
line('after second Start ' .. st())
client.screenshot(TAG .. '_02_closed')
mapdump('after close')
for _ = 1, 90 do emu.frameadvance() end
line('later ' .. st())
client.screenshot(TAG .. '_03_later')
mapdump('90 frames later')

-- dumps for offline analysis
local f = assert(io.open(OUT .. TAG .. '_vram.bin', 'wb'))
for a = 0, 65535 do f:write(string.char(vb(a))) end
f:close()
local okc, cg = pcall(function()
  local t = {}
  for a = 0, 511 do t[#t + 1] = string.char(memory.read_u8(a, 'CGRAM')) end
  return table.concat(t)
end)
if okc then
  local g = assert(io.open(OUT .. TAG .. '_cgram.bin', 'wb')); g:write(cg); g:close()
  line('cgram dumped')
else
  line('cgram domain unavailable: ' .. tostring(cg))
end
line('done')
