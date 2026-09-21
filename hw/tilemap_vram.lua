-- tilemap_vram: tile-level write coverage of the only window a tile number can
-- address, $C000-$FFFF (1024 tiles of 16 bytes).  For each tile: how often its
-- sampled bytes changed, and the most non-zero samples seen.
local TAG = os.getenv('HW_TAG') or 'tilemap_vram'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '20000') or 20000
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function b(a) return memory.read_u8(a, 'VRAM') end
local NT = 1024
local prev, chg, mxnz = {}, {}, {}
for t = 0, NT - 1 do prev[t] = -1; chg[t] = 0; mxnz[t] = 0 end
local function sample()
  for t = 0, NT - 1 do
    local base = 0xC000 + t * 16
    local nz = 0
    for k = 0, 15 do
      if b(base + k) ~= 0 then nz = nz + 1 end
    end
    if prev[t] ~= -1 and nz ~= prev[t] then chg[t] = chg[t] + 1 end
    prev[t] = nz
    if nz > mxnz[t] then mxnz[t] = nz end
  end
end
while emu.framecount() < 1300 do emu.frameadvance() end
while emu.framecount() < UNTIL do
  local i = emu.framecount()
  if i % 30 < 8 then joypad.set({A=true}) end
  if i > 3000 and i % 700 < 100 then joypad.set({Right=true}) end
  if i > 5000 and i % 1100 < 90 then joypad.set({Up=true}) end
  if i % 40 == 0 then sample() end
  emu.frameadvance()
end
local free, used = {}, {}
for t = 0, NT - 1 do
  if mxnz[t] == 0 then free[#free+1] = t else used[#used+1] = t end
end
log:write('tiles never non-zero: ' .. #free .. '\n')
log:write('  ' .. table.concat(free, ' ') .. '\n')
-- runs of consecutive free tiles, which is what a pair/quad allocation needs
local runs, s = {}, nil
for t = 0, NT do
  if t < NT and mxnz[t] == 0 then if s == nil then s = t end
  else if s ~= nil then runs[#runs+1] = {s, t - 1}; s = nil end end
end
table.sort(runs, function(a, c) return (a[2]-a[1]) > (c[2]-c[1]) end)
log:write('longest free runs (start..end, length):\n')
for k = 1, math.min(#runs, 25) do
  local r = runs[k]
  log:write(string.format('  %4d..%4d  %d\n', r[1], r[2], r[2]-r[1]+1))
end
log:write('changes>0 tiles: ' .. (#used) .. '\n')
log:write('done\n'); log:flush()
