-- menu15: where does the game get to, and does Start ever open the menu?
local TAG  = os.getenv('HW_TAG') or 'menu15'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end
local function wincells()
  local n = 0
  for _, r in ipairs({0,1,2,3,28,29,30,31}) do
    for c = 0, 31 do
      local v = vw(0x7C00 + r * 0x20 + c) % 0x400
      if v >= 0xCB and v <= 0xE5 then n = n + 1 end
    end
  end
  return n
end
line('start')
for f = 1, 60000 do
  local k = f % 200
  if k < 3 then joypad.set({ Start = true })
  elseif k >= 60 and k < 63 then joypad.set({ A = true })
  elseif k >= 120 and k < 123 then joypad.set({ B = true })
  else joypad.set({}) end
  if f % 3000 == 0 then
    line(string.format('F=%d 6E=%02X 73=%02X 74=%02X 92=%02X win=%d',
      f, w(0x036E), w(0x0373), w(0x0374), w(0x0392), wincells()))
    client.screenshot(string.format('%s_%05d', TAG, f))
  end
  if wincells() >= 8 then
    line('WINDOW at F=' .. f)
    client.screenshot(TAG .. '_WINDOW')
    break
  end
  emu.frameadvance()
end
line('end')
