-- menu8: run the NEW build in the in-game street state: the speaker label
-- ("りき:" in the original) is the path that now uses the moved label pair
-- outside the font window, so a few messages are enough to see whether the
-- 16 bit tiles and the moved pairs behave.
-- env: HW_TAG HW_ROM
local TAG = os.getenv('HW_TAG') or 'menu8'
local ROMF = os.getenv('HW_ROM') or 'kuniokun_cn.smc'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function nz() local n = 0 for k = 0, 51 do if w(0x040A + k) ~= 0 then n = n + 1 end end return n end
local function st()
  return string.format('F=%d 6e=%02X 6f=%02X 73=%02X dd=%02X df=%02X e8=%02X e9=%02X state=%02X 040A_nz=%d',
    emu.framecount(), w(0x036E), w(0x036F), w(0x0373), w(0x09DD), w(0x09DF), w(0x03E8), w(0x03E9),
    w(0x1FF0), nz())
end
local function buf()
  local t = {}
  for i = 0, 23 do t[#t + 1] = string.format('%02X', w(0x03EA + i)) end
  return table.concat(t, ' ')
end
-- the label row's tiles, upper and lower, for the first 12 cells
local function labeltiles(row)
  local up, lo = {}, {}
  for c = 0, 11 do
    up[#up + 1] = string.format('%03X', vw(0x7C00 + row * 0x20 + 3 + c) % 0x400)
    lo[#lo + 1] = string.format('%03X', vw(0x7C00 + (row + 1) * 0x20 + 3 + c) % 0x400)
  end
  return table.concat(up, ' ') .. ' | ' .. table.concat(lo, ' ')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('rom ' .. ROMF .. ' load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
client.screenshot(TAG .. '_init')
for round = 1, 8 do
  for k = 0, 5 do joypad.set({ A = true }); emu.frameadvance() end
  for k = 0, 45 do emu.frameadvance() end
  local r = w(0x036E)
  line(string.format('A%d %s row=%02X', round, st(), r))
  line('   buf ' .. buf())
  if r >= 1 and r <= 14 then
    line('   tiles r%d ' .. string.format('%d', r) .. ': ' .. labeltiles(r - 1))
  end
  client.screenshot(string.format('%s_a%d', TAG, round))
end
line('done')
