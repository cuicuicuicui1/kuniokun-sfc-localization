-- menu11: boot the ROM fresh, drive the intro with Start/A, and catch the
-- command window: as soon as the window's own tiles (203..229, our hanzi)
-- appear in the box content map ($7C00) rows 0-3 or 28-31, dump everything,
-- close the menu with Start and keep watching those rows.
-- env: HW_TAG HW_ROM HW_MAX
local TAG  = os.getenv('HW_TAG') or 'menu11'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
local MAX  = tonumber(os.getenv('HW_MAX') or '9000') or 9000
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)

local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function st()
  return string.format('F=%d 6E=%02X 6F=%02X 73=%02X 74=%02X 92=%02X 9E=%02X DD=%02X DF=%02X',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x0374), w(0x0392), w(0x039E),
    w(0x09DD), w(0x09DF))
end
local function winrow(r)
  local n = 0
  for c = 0, 31 do
    local v = vw(0x7C00 + r * 0x20 + c) % 0x400
    if v >= 0xCB and v <= 0xE5 then n = n + 1 end
  end
  return n
end
local function wincells()
  local n = 0
  for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do n = n + winrow(r) end
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
local function mapdump(tag)
  line('--- box map $7C00 ' .. tag)
  for _, r in ipairs({ 0, 1, 2, 3, 28, 29, 30, 31 }) do
    line(string.format('  r%02d %s', r, rowcells(r)))
  end
end
local function dumpvram(tag)
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
  end
end

line('rom ' .. ROMF .. ' fresh boot, max ' .. MAX .. ' frames')
local phase, seen, lastdump = 'boot', 0, -1
for f = 1, MAX do
  local cells = wincells()
  if phase == 'boot' then
    -- title / intro: Start skips, A advances
    if f % 60 < 3 then joypad.set({ Start = true }) else joypad.set({}) end
    if f % 240 == 0 then
      line(string.format('boot %s win=%d', st(), cells))
      client.screenshot(string.format('%s_b%04d', TAG, f))
    end
    if f > 900 then phase = 'drive' end
  elseif phase == 'drive' then
    -- advance the story: A mostly, Start now and then to try the menu
    local k = f % 90
    if k < 3 then joypad.set({ A = true })
    elseif k == 45 or k == 46 then joypad.set({ Start = true })
    else joypad.set({}) end
    if f % 300 == 0 then
      line(string.format('drive %s win=%d', st(), cells))
      client.screenshot(string.format('%s_d%04d', TAG, f))
    end
    if cells > seen then
      seen = cells
      line(string.format('window cells now %d  %s', cells, st()))
      client.screenshot(string.format('%s_win%d_f%d', TAG, cells, f))
      mapdump('window growing')
    end
    if cells >= 40 then
      phase = 'open'
      line('window looks complete: ' .. st())
      client.screenshot(TAG .. '_open')
      mapdump('menu open')
      dumpvram('open')
      local ok, cg = pcall(function() return memory.read_u8(0, 'CGRAM') end)
      line('cgram ok=' .. tostring(ok))
    end
  elseif phase == 'open' then
    -- let it settle, then close with Start
    if f % 30 == 0 then line('open-wait ' .. st()) end
    if f > 60 + (seen * 0) and (f % 120 == 0) then
      -- close
      for _ = 1, 3 do joypad.set({ Start = true }); emu.frameadvance() end
      joypad.set({})
      line('pressed Start to close ' .. st())
      phase = 'closed'
      client.screenshot(TAG .. '_closed0')
      mapdump('just closed')
      dumpvram('closed0')
    else
      emu.frameadvance()
    end
  elseif phase == 'closed' then
    if f % 20 == 0 then line('closed ' .. st()) end
    if f % 60 == 0 then
      client.screenshot(string.format('%s_c%04d', TAG, f))
      if lastdump < 0 then
        mapdump('closed, 60 frames later')
        dumpvram('closed1')
        lastdump = f
      end
    end
    emu.frameadvance()
  end
  if phase ~= 'open' and phase ~= 'closed' then emu.frameadvance() end
  if phase == 'closed' and f > MAX - 400 then break end
end
line('done ' .. st() .. ' win=' .. wincells())
mapdump('final')
