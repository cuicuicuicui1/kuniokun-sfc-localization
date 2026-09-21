-- menu16: drive the command window's state machine directly.
--   * arm: $0374 bit 4 gates the handler table, $0392 is the step index; step 26
--     is the menu's first step, so poking both should make the engine draw the
--     window (and run the arm hook at step 27) without any button press.
--   * close: step 30 waits for input, so a Start press should take it to step 31,
--     which is where the wipe stub is hooked.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'menu16'
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
  for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 91=%02X 92=%02X 9E=%02X pend=%02X C1=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0391), w(0x0392),
    w(0x039E), w(0x0BFB), w(0x03C1))
end
local function wincells()
  local n = 0
  for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do
    for c = 0, 31 do
      local v = vw(0x7C00 + r * 0x20 + c) % 0x400
      if v >= 0xCB and v <= 0xE5 then n = n + 1 end
    end
  end
  return n
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' state ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
mapdump('before')
client.screenshot(TAG .. '_00_before')

-- start the menu's script steps
memory.write_u8(0x0374, w(0x0374) | 0x10, 'WRAM')
memory.write_u8(0x0392, 26, 'WRAM')
for i = 1, 120 do
  emu.frameadvance()
  if i % 10 == 0 then
    line(string.format('  open +%02d %s win=%d', i, st(), wincells()))
  end
end
line('menu should be drawn ' .. st() .. ' win=' .. wincells())
client.screenshot(TAG .. '_01_menu')
mapdump('menu drawn')

-- step 30 waits for input; run the close step ($0392 = 31) directly instead,
-- which is where the wipe stub is hooked
memory.write_u8(0x0392, 31, 'WRAM')
line('poked step 31')
for i = 1, 90 do
  emu.frameadvance()
  if i % 5 == 0 then line(string.format('  close +%02d %s', i, st())) end
end
line('after close ' .. st() .. ' win=' .. wincells())
client.screenshot(TAG .. '_02_closed')
mapdump('after close')
for i = 1, 120 do
  emu.frameadvance()
  if i % 20 == 0 then line(string.format('  later +%03d %s win=%d', i, st(), wincells())) end
end
mapdump('later')
client.screenshot(TAG .. '_03_later')
line('done')
