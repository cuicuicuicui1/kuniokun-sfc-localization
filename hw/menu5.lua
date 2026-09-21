-- menu5: open the command window on purpose.  The Start handler is $00:F539:
-- it needs $0373 == 0 (no dialogue running) and $1254/$1255 bit7 clear, then it
-- sets $0314 |= $80, $0363 = 3 and calls JSL $03EB3D (the script engine), which
-- runs the window script (steps $16.. of the handler table at $F101).
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'menu5'
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
  return string.format('F=%d 92=%02X 9E=%02X 91=%02X 6E=%02X 6F=%02X 63=%02X 73=%02X 14=%02X nz=%d dd=%02X df=%02X',
    emu.framecount(), w(0x0392), w(0x039E), w(0x0391), w(0x036E), w(0x036F), w(0x0363), w(0x0373),
    w(0x0314), nz(), w(0x09DD), w(0x09DF))
end
local function rows()
  local t = {}
  for r = 0, 7 do
    local s = {}
    for c = 0, 25 do s[#s + 1] = string.format('%03X', vw(0x7C00 + r * 0x20 + c) % 0x400) end
    t[#t + 1] = string.format('r%d %s', r, table.concat(s, ' '))
  end
  return table.concat(t, '\n')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 40 do emu.frameadvance() end
line('settled ' .. st())
line(string.format('  1254/55=%02X/%02X 0303=%02X/%02X 0E01=%02X/%02X',
  w(0x1254), w(0x1255), w(0x0303), w(0x0304), w(0x0E01), w(0x0E02)))
client.screenshot(TAG .. '_init')

-- clear the dialogue-block flag and press Start
poke(0x0373, 0)
for k = 0, 5 do joypad.set({ Start = true }); emu.frameadvance() end
line('start1 ' .. st())
for f = 1, 16 do
  for k = 0, 7 do emu.frameadvance() end
  line(string.format('  f%-2d %s', f, st()))
  client.screenshot(string.format('%s_s1_%02d', TAG, f))
end
line('040A=' .. tbl())
line('rows:\n' .. rows())

-- if nothing, try poking the script state directly
if nz() == 0 then
  line('--- no window yet: poke 0392 = $16 with 0373 = 0')
  poke(0x039E, 0); poke(0x039A, 0); poke(0x0363, 3); poke(0x0392, 0x16)
  for f = 1, 14 do
    for k = 0, 7 do emu.frameadvance() end
    line(string.format('  p%-2d %s', f, st()))
    client.screenshot(string.format('%s_p_%02d', TAG, f))
  end
  line('040A=' .. tbl())
  line('rows:\n' .. rows())
end
line('done')
