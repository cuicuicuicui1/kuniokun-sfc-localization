-- pchist: which code does this scene actually execute?  Samples the program
-- counter every frame and histograms it, so the mode's main loop can be
-- identified (field loop $00:F1xx / map engine $07:F0xx / scene script $03:89xx).
-- env: HW_TAG HW_UNTIL
local TAG = os.getenv('HW_TAG') or 'pchist'
local UNTIL = tonumber(os.getenv('HW_UNTIL') or '3000') or 3000
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function w(a) return memory.read_u8(a, 'WRAM') end
local function line(m) log:write(m .. '\n'); log:flush(); print(m) end

local getreg = nil
for _, cand in ipairs({ 'PC', 'pc' }) do
  for _, fn in ipairs({ function(n) return memory.getregister(n) end,
                        function(n) return emu.getregister(n) end }) do
    local ok, v = pcall(fn, cand)
    if ok and type(v) == 'number' then getreg = fn; break end
  end
  if getreg then break end
end
if not getreg then
  line('no PC access: memory.getregister / emu.getregister both failed')
  for _, fn in ipairs({ function() return tostring(memory.getregister) end,
                        function() return tostring(emu.getregister) end }) do
    local ok, v = pcall(fn); line('  probe: ' .. tostring(ok) .. ' ' .. tostring(v))
  end
else
  line('PC access ok')
end

local ok, err = pcall(function() savestate.load(OUT .. 'kw1a.state') end)
line('load ok=' .. tostring(ok) .. ' ' .. tostring(err))
for _ = 0, 30 do emu.frameadvance() end

local hist, pages = {}, {}
local first = emu.framecount()
while emu.framecount() < first + UNTIL do
  local i = emu.framecount()
  if i % 20 == 0 and w(0x0373) ~= 0 then joypad.set({ A = true }) end
  -- two samples at different phases of the frame
  if getreg then
    local pc = getreg('PC')
    if pc then
      hist[pc] = (hist[pc] or 0) + 1
      local pg = pc >> 8
      pages[pg] = (pages[pg] or 0) + 1
    end
  end
  for _ = 0, 7 do emu.frameadvance() end
  if getreg then
    local pc = getreg('PC')
    if pc then
      hist[pc] = (hist[pc] or 0) + 1
      local pg = pc >> 8
      pages[pg] = (pages[pg] or 0) + 1
    end
  end
end
line('frames ' .. first .. '..' .. emu.framecount())
local pl = {}
for pg, n in pairs(pages) do pl[#pl + 1] = { pg, n } end
table.sort(pl, function(a, b) return a[2] > b[2] end)
line('--- top code pages ---')
for k = 1, math.min(20, #pl) do
  line(string.format('  $%02X:%02Xxx  %d', pl[k][1] >> 8, pl[k][1] & 0xFF, pl[k][2]))
end
local al = {}
for pc, n in pairs(hist) do al[#al + 1] = { pc, n } end
table.sort(al, function(a, b) return a[2] > b[2] end)
line('--- top addresses ---')
for k = 1, math.min(30, #al) do
  line(string.format('  $%06X  %d', al[k][1], al[k][2]))
end
line('done')
