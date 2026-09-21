-- seq2: verify on hardware that the rows above the current message are blank.
--   At every row start ($036f == 0) log the four map rows that hold the two
--   text rows before the message's first row ($0391-1, $0391-2): after the
--   stale-row stub they must be the blank cell $2C00, not glyph tiles.
-- env: HW_TAG HW_SRAM HW_F0 HW_F1
local TAG  = os.getenv('HW_TAG') or 'seq2'
local SRAM = os.getenv('HW_SRAM') or 'F:/emulators/snes9x/Saves/kunio_cn_v12.srm'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local F0   = tonumber(os.getenv('HW_F0') or '2500')
local F1   = tonumber(os.getenv('HW_F1') or '3100')
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end
local function w(a) return memory.read_u8(a, 'WRAM') end
local function vb(a) return memory.read_u8(a, 'VRAM') end
local function vw(x) return vb(x * 2) + vb(x * 2 + 1) * 256 end

local sf = io.open(SRAM, 'rb')
if sf then
  local d = sf:read('*a'); sf:close()
  for i = 1, #d do memory.write_u8(i - 1, d:byte(i), 'SRAM') end
end
client.reboot_core()
for _ = 1, 120 do emu.frameadvance() end

-- count the non-blank cells of the 4 map rows for text rows r-1 and r-2
local function stalecells(r91)
  local n, tiles = 0, {}
  for _, tr in ipairs({ (r91 - 2) % 16, (r91 - 1) % 16 }) do
    for half = 0, 1 do
      local base = 0x7C00 + (tr * 2 + half) * 0x20
      for c = 3, 28 do
        local v = vw(base + c)
        if v ~= 0x2C00 and v ~= 0 then
          n = n + 1
          if #tiles < 6 then tiles[#tiles + 1] = string.format('%03X', v % 0x400) end
        end
      end
    end
  end
  return n, table.concat(tiles, ' ')
end

local dirs = { 'Right', 'Left', 'Down', 'Up' }
local last = -1
for f = 1, F1 do
  local k = f % 300
  local pad = {}
  if k < 3 or (k >= 30 and k < 33) or (k >= 170 and k < 174) then
    pad = { A = true }
  elseif k == 60 then
    pad = { Start = true }
  elseif k == 160 then
    pad = { B = true }
  elseif k >= 180 and k < 240 then
    pad = { [dirs[math.floor(f / 300) % 4 + 1]] = true }
  end
  joypad.set(pad)
  emu.frameadvance()
  if f >= F0 and (w(0x0374) & 0x10) ~= 0 and w(0x036F) >= 3
     and (w(0x036E) ~= last or f % 300 == 0) then
    last = w(0x036E)
    local n, tiles = stalecells(w(0x0391))
    line(string.format('f%05d 6E=%02X 91=%02X 92=%02X stale-cells=%3d %s',
      f, w(0x036E), w(0x0391), w(0x0392), n, tiles))
  end
end
line('done')