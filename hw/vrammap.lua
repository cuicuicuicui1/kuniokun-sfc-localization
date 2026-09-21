-- vrammap: run a long scripted session and record, per 4 KB VRAM block, whether
-- anything ever wrote there.  A block that never changes and never leaves zero
-- over a run that crosses many scenes is a safe place to park the glyph pool.
local TAG = os.getenv('HW_TAG') or 'vrammap'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '26000') or 26000
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function b(a) return memory.read_u8(a, 'VRAM') end
local NB = 16
local prev, changed, everNonzero = {}, {}, {}
for blk = 0, NB - 1 do prev[blk] = -1; changed[blk] = 0; everNonzero[blk] = 0 end
local function sample(frame)
  for blk = 0, NB - 1 do
    local base = blk * 0x1000
    local h, nzv = 0, 0
    for i = 0, 0x0FFF, 64 do
      local v = b(base + i)
      h = (h * 31 + v) % 65521
      if v ~= 0 then nzv = nzv + 1 end
    end
    if prev[blk] ~= -1 and h ~= prev[blk] then changed[blk] = changed[blk] + 1 end
    prev[blk] = h
    if nzv > everNonzero[blk] then everNonzero[blk] = nzv end
  end
end
while emu.framecount() < 1300 do emu.frameadvance() end
local last = 0
while emu.framecount() < UNTIL do
  local i = emu.framecount()
  if i % 30 < 8 then joypad.set({A=true}) end
  if i > 3000 and i % 700 < 100 then joypad.set({Right=true}) end
  if i > 5000 and i % 1100 < 90 then joypad.set({Up=true}) end
  if i % 8 == 0 then sample(i) end
  if i - last > 2000 then
    last = i
    local c, z = {}, {}
    for blk = 0, NB - 1 do c[#c+1] = tostring(changed[blk]); z[#z+1] = tostring(everNonzero[blk]) end
    log:write(string.format('F=%d changes/block: %s | maxnonzero: %s\n',
      i, table.concat(c, ' '), table.concat(z, ' ')))
    log:flush()
  end
  emu.frameadvance()
end
log:write('done\n'); log:flush()
