-- hudprobe: read the widget's name-pointer table out of WRAM and the tilemap
-- words it wrote, so we know where the HUD name comes from.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'hudprobe'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function ww(a) return w(a) + w(a + 1) * 256 end
local function vw(a) return memory.read_u8(a * 2, 'VRAM') + memory.read_u8(a * 2 + 1, 'VRAM') * 256 end

while emu.framecount() < 1400 do emu.frameadvance() end
for i = 1, 12 do
  for k = 0, 7 do joypad.set({ A = true }); emu.frameadvance() end
  for k = 0, 24 do emu.frameadvance() end
  local f = emu.framecount()
  log:write(string.format('F=%d  $1BA6=%02X  $01E5..=%02X %02X %02X  $01E7..=%02X %02X %02X\n',
    f, w(0x1BA6), w(0x01E5), w(0x01E6), w(0x01E7), w(0x01E7), w(0x01E8), w(0x01E9)))
  local idxs = { w(0x01E5 + w(0x1BA6)), w(0x01E7 + w(0x1BA6)), w(0x01E9 + w(0x1BA6)) }
  for n, ix in ipairs(idxs) do
    local p = ww(0xDBC3 + ix * 2)
    local s = {}
    for j = 0, 7 do s[#s + 1] = string.format('%02X', w(0x0000)) end
    log:write(string.format('  widget%d idx=%02X ptr=$%04X  base=$%02X\n', n, ix, p, w(0x0024)))
  end
  local words = {}
  for a = 0x79C0, 0x7A10 do words[#words + 1] = string.format('%04X', vw(a)) end
  log:write('  tilemap $79C0..: ' .. table.concat(words, ' ') .. '\n')
  log:flush()
end
log:write('done\n'); log:flush()
