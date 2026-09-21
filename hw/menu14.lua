-- menu14: long drive to reach the real Start menu, then close it and watch the
-- wipe.  Presses A to advance the story and Start now and then; as soon as the
-- command window's own tiles (0xCB..0xE5) show up in the box map it dumps
-- everything, closes the menu and follows the four rows for 200 frames.
-- env: HW_TAG HW_ROM HW_MAX
local TAG  = os.getenv('HW_TAG') or 'menu14'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
local MAX  = tonumber(os.getenv('HW_MAX') or '40000') or 40000
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
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 91=%02X 92=%02X 9E=%02X pend=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0391), w(0x0392),
    w(0x039E), w(0x0BFB))
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

line('rom ' .. ROMF .. ' fresh boot, max ' .. MAX)
local phase, best, seenframes = 'drive', 0, 0
for f = 1, MAX do
  local cells = wincells()
  if phase == 'drive' then
    local k = f % 120
    if k < 3 then joypad.set({ Start = true })
    elseif k >= 30 and k < 33 then joypad.set({ A = true })
    else joypad.set({}) end
    if cells > best then
      best = cells
      line(string.format('window cells %d at %s', cells, st()))
      client.screenshot(string.format('%s_win%d_f%d', TAG, cells, f))
    end
    if cells >= 8 then
      phase = 'close'
      line('window found: ' .. st())
      mapdump('menu open')
      local g = assert(io.open(OUT .. TAG .. '_vram_open.bin', 'wb'))
      for a = 0, 65535 do g:write(string.char(vb(a))) end
      g:close()
    end
    emu.frameadvance()
  elseif phase == 'close' then
    line('closing ' .. st())
    for _ = 1, 3 do joypad.set({ Start = true }); emu.frameadvance() end
    joypad.set({})
    for i = 1, 60 do
      emu.frameadvance()
      if i % 5 == 0 then line(string.format('  +%02d %s', i, st())) end
    end
    line('after close ' .. st())
    client.screenshot(TAG .. '_closed')
    mapdump('after close')
    phase = 'watch'
    seenframes = 0
  else
    emu.frameadvance()
    seenframes = seenframes + 1
    if seenframes % 20 == 0 then
      line(string.format('watch +%d %s', seenframes, st()))
      if seenframes % 60 == 0 then
        mapdump('watch ' .. seenframes)
        client.screenshot(string.format('%s_w%03d', TAG, seenframes))
      end
    end
    if seenframes > 200 then break end
  end
end
line('done ' .. st() .. ' win=' .. wincells())
mapdump('final')
