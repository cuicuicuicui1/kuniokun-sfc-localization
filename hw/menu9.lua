-- menu9: open the command window, close it, and watch the box map.
-- Reports the drawer state every frame and dumps the box map (word $7C00)
-- before/after, plus screenshots, so the leftover window cells and the band
-- can be compared between builds in the very same state.
-- env: HW_TAG HW_ROM HW_START (frame to press Start at, default 60)
local TAG  = os.getenv('HW_TAG') or 'menu9'
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
  line('--- box map (word $7C00) ' .. tag)
  for _, r in ipairs({ 0, 1, 2, 3, 4, 5, 26, 27, 28, 29, 30, 31 }) do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 92=%02X 9E=%02X DD=%02X DF=%02X 14=%02X 63=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0392), w(0x039E),
    w(0x09DD), w(0x09DF), w(0x0314), w(0x0363))
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' state load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
client.screenshot(TAG .. '_00_init')
mapdump('at load')

-- open the menu
local function press(btn, n)
  for _ = 1, n do joypad.set(btn); emu.frameadvance() end
end
press({ Start = true }, 4)
press({}, 2)
line('after Start press ' .. st())
for _ = 1, 60 do emu.frameadvance() end
line('menu should be open ' .. st())
client.screenshot(TAG .. '_01_open')
mapdump('menu open')
for r = 1, 12 do
  line(string.format('  f%03d %s', r, st()))
  emu.frameadvance()
end

-- close it
press({ Start = true }, 4)
press({}, 2)
line('after Start release ' .. st())
for _ = 1, 60 do emu.frameadvance() end
line('menu should be closed ' .. st())
client.screenshot(TAG .. '_02_closed')
mapdump('menu closed')
for _ = 1, 120 do emu.frameadvance() end
line('later ' .. st())
client.screenshot(TAG .. '_03_later')
mapdump('120 frames later')

-- dump VRAM for offline analysis
local f = assert(io.open(OUT .. TAG .. '_vram.bin', 'wb'))
for a = 0, 65535 do f:write(string.char(vb(a))) end
f:close()
line('vram dumped')
line('done')
