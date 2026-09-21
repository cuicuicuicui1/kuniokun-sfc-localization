-- menu3: load the in-game street savestate, clear the dialogue box, press Start
-- and watch for the command window (label table at $040A + a screenshot).
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'menu3'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function nz() local n = 0 for k = 0, 51 do if w(0x040A + k) ~= 0 then n = n + 1 end end return n end
local function tbl() local t = {} for k = 0, 51 do t[#t + 1] = string.format('%02X', w(0x040A + k)) end return table.concat(t, ' ') end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
-- the four tile map rows a window would use, as tile numbers
local function rows(a)
  local t = {}
  for r = 0, 5 do
    local s = {}
    for c = 0, 25 do s[#s + 1] = string.format('%03X', vw(a + r * 0x20 + c) % 0x400) end
    t[#t + 1] = table.concat(s, ' ')
  end
  return table.concat(t, ' / ')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line(string.format('load ok=%s %s F=%d', tostring(ok), tostring(err), emu.framecount()))
for _ = 0, 40 do emu.frameadvance() end
line(string.format('settled F=%d row=%02X col=%02X nz=%d e8=%02X e9=%02X 73=%02X 74=%02X dd=%02X df=%02X',
  emu.framecount(), w(0x036E), w(0x036F), nz(), w(0x03E8), w(0x03E9), w(0x0373), w(0x0374), w(0x09DD), w(0x09DF)))
client.screenshot(TAG .. '_f0')

-- 1) does Start do anything while the box is still up?
for k = 0, 5 do joypad.set({ Start = true }); emu.frameadvance() end
for _ = 0, 50 do emu.frameadvance() end
line(string.format('start-with-box  F=%d nz=%d row=%02X', emu.framecount(), nz(), w(0x036E)))
client.screenshot(TAG .. '_start_with_box')

-- 2) tap A to clear the dialogue
for round = 1, 10 do
  for k = 0, 5 do joypad.set({ A = true }); emu.frameadvance() end
  for _ = 0, 40 do emu.frameadvance() end
  line(string.format('A%d F=%d nz=%d row=%02X col=%02X 73=%02X', round, emu.framecount(), nz(), w(0x036E), w(0x036F), w(0x0373)))
end
client.screenshot(TAG .. '_afterA')

-- 3) now Start again
for round = 1, 4 do
  for k = 0, 5 do joypad.set({ Start = true }); emu.frameadvance() end
  for _ = 0, 60 do emu.frameadvance() end
  line(string.format('START%d F=%d nz=%d row=%02X tbl=%s',
    round, emu.framecount(), nz(), w(0x036E), tbl()))
  client.screenshot(string.format('%s_start%d', TAG, round))
end
line('rows ' .. rows(0x7C00))
line('done')
