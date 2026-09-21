-- clashwatch.lua: how many of the item-name tiles are NOT holding their font
-- glyph, frame by frame?
--
-- The glyph pool uploads Chinese glyphs into 45 of the tiles the item-name
-- renderer ($01:FC75) names.  If nothing puts the font back, that count stays
-- above zero once a dialogue has drawn a glyph; if the engine reloads the font
-- block when the status screen opens (CPU $00:8775 DMAs ROM $1F:$8000 to VRAM
-- $6000), the count returns to zero exactly at that moment.
--
-- env: HW_TAG HW_NF HW_START HW_DOWN HW_A HW_DUMP
local TAG   = os.getenv('HW_TAG') or 'clash'
local NF    = tonumber(os.getenv('HW_NF') or '3600')
local START_AT = tonumber(os.getenv('HW_START') or '1500')
local DOWN_AT  = tonumber(os.getenv('HW_DOWN') or '1560')
local A_AT     = tonumber(os.getenv('HW_A') or '1680')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

local TILES = dofile(OUT .. '_clash.lua')

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local want = {}
for _, e in ipairs(TILES) do
  local t = {}
  for b in e[2]:gmatch('%x%x') do t[#t + 1] = tonumber(b, 16) end
  want[e[1]] = t
end

local function bad()
  local n = 0
  for _, e in ipairs(TILES) do
    local t = want[e[1]]
    for i = 0, 15 do
      if memory.read_u8(0xC000 + e[1] * 16 + i, 'VRAM') ~= t[i + 1] then
        n = n + 1
        break
      end
    end
  end
  return n
end

line('watching ' .. #TILES .. ' item-name tiles; a nonzero count means the pool has overwritten them')
local held = {}
for f = 1, NF do
  for k in pairs(held) do held[k] = nil end
  if f >= START_AT and f < START_AT + 4 then held.Start = true end
  if f >= DOWN_AT and f < DOWN_AT + 2 then held.Down = true end
  if f >= DOWN_AT + 16 and f < DOWN_AT + 18 then held.Down = true end
  if f >= DOWN_AT + 32 and f < DOWN_AT + 34 then held.Down = true end
  if f >= A_AT and f < A_AT + 4 then held.A = true end
  joypad.set(held)
  emu.frameadvance()
  if f % 60 == 0 then
    client.screenshot(TAG .. string.format('_f%04d', f))
  end
  local n = bad()
  if n ~= (last or -1) then
    line(string.format('f%5d  overwritten tiles: %2d / %d', f, n, #TILES))
    last = n
  end
end
line('done')
log:close()
