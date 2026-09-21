-- origmenu: run the ORIGINAL rom with its own savestate, press Start with the
-- dialogue-block flag cleared, and dump what the real command window looks like
-- plus which font tiles the HUD occupies.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'origmenu'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function poke(a, v) memory.write_u8(a, v, 'WRAM') end
local function nz() local n = 0 for k = 0, 51 do if w(0x040A + k) ~= 0 then n = n + 1 end end return n end
local function tbl()
  local t = {}
  for k = 0, 51 do t[#t + 1] = string.format('%02X', w(0x040A + k)) end
  return table.concat(t, ' ')
end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function st()
  return string.format('F=%d 92=%02X 9E=%02X 91=%02X 6E=%02X 6F=%02X 63=%02X 73=%02X 74=%02X 68=%02X 14=%02X nz=%d dd=%02X df=%02X',
    emu.framecount(), w(0x0392), w(0x039E), w(0x0391), w(0x036E), w(0x036F), w(0x0363), w(0x0373),
    w(0x0374), w(0x0368), w(0x0314), nz(), w(0x09DD), w(0x09DF))
end

-- dump the whole VRAM (64K) and the two tile maps as text
local function dumpvram(name)
  local f = assert(io.open(OUT .. name, 'wb'))
  for i = 0, 0xFFFF do f:write(string.char(vb(i))) end
  f:close()
end
local function tilemap(base, rows)
  local t = {}
  for r = 0, rows - 1 do
    local s = {}
    for c = 0, 31 do s[#s + 1] = string.format('%04X', vw(base + r * 0x20 + c)) end
    t[#t + 1] = string.format('%02X %s', r, table.concat(s, ' '))
  end
  return table.concat(t, '\n')
end

local ok, err = pcall(function() savestate.load(OUT .. 'v9orig_dlg.state') end)
line('load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
client.screenshot(TAG .. '_init')
dumpvram(TAG .. '_init_vram.bin')

-- try to open the menu: clear the dialogue block, press Start
for round = 1, 6 do
  poke(0x0373, 0)
  for k = 0, 5 do joypad.set({ Start = true }); emu.frameadvance() end
  for k = 0, 25 do emu.frameadvance() end
  line(string.format('round%d %s', round, st()))
  client.screenshot(string.format('%s_s%d', TAG, round))
  if nz() > 0 then break end
end
line('040A=' .. tbl())
line('tilemap $7800 (HUD screen?):\n' .. tilemap(0x7800, 8))
line('tilemap $7C00:\n' .. tilemap(0x7C00, 8))
dumpvram(TAG .. '_after_vram.bin')
line(string.format('HUD cells 79C6=%04X 7A06=%04X 7A46=%04X 7A86=%04X',
  vw(0x79C6), vw(0x7A06), vw(0x7A46), vw(0x7A86)))
line('done')
