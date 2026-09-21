-- fontreload.lua: does the engine reload the font block into VRAM when the
-- status screen opens?
--
-- The item-name renderer ($01:FC75) writes tile numbers, not glyphs: the kana
-- it names have to already be in VRAM.  The glyph pool overwrites 45 of those
-- tiles whenever a Chinese glyph is drawn, so the item names stay correct only
-- if something puts the font back.  CPU $00:8775 DMAs ROM bank $1F:$8000 (the
-- font block) to VRAM word $6000, then DMAs WRAM $7F:0000 to VRAM $7800 --
-- which is exactly the status screen's map base.  So watch tile $7E (the kana
-- せ, used by "せった") and log every time its 16 bytes change, marking whether
-- they match the font ROM.
--
-- env: HW_TAG HW_NF HW_FONT (hex, 16 bytes) HW_START HW_DOWN HW_A
local TAG   = os.getenv('HW_TAG') or 'fontreload'
local NF    = tonumber(os.getenv('HW_NF') or '4000')
local FONT  = os.getenv('HW_FONT') or '44 22 44 22 FE 01 44 BB 48 24 40 28 3C 42 00 3E'
local START_AT = tonumber(os.getenv('HW_START') or '900')
local DOWN_AT  = tonumber(os.getenv('HW_DOWN') or '960')
local A_AT     = tonumber(os.getenv('HW_A') or '1080')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local want = {}
for b in FONT:gmatch('%x%x') do want[#want + 1] = tonumber(b, 16) end
local BASE = 0xC7E0                       -- VRAM byte addr of tile $7E

local function tile()
  local t = {}
  for i = 0, 15 do t[i + 1] = memory.read_u8(BASE + i, 'VRAM') end
  return t
end
local function isfont(t)
  for i = 1, 16 do if t[i] ~= want[i] then return false end end
  return true
end

line('watch VRAM $C7E0 (tile $7E); font = ' .. FONT)
local prev = tile()
line(string.format('f%5d  initial  font=%s  %s', 0, tostring(isfont(prev)),
     table.concat(prev, ' ')))

local held = {}
local function hold(btn, frames)
  held[btn] = true
end
local function release(btn) held[btn] = nil end

for f = 1, NF do
  -- release anything held from the previous frame
  for k in pairs(held) do held[k] = nil end
  if f >= START_AT and f < START_AT + 4 then held.Start = true end
  if f >= DOWN_AT and f < DOWN_AT + 2 then held.Down = true end
  if f >= DOWN_AT + 16 and f < DOWN_AT + 18 then held.Down = true end
  if f >= DOWN_AT + 32 and f < DOWN_AT + 34 then held.Down = true end
  if f >= A_AT and f < A_AT + 4 then held.A = true end
  joypad.set(held)
  emu.frameadvance()
  if f % 200 == 0 then
    client.screenshot(TAG .. string.format('_f%04d', f))
  end
  local t = tile()
  local changed = false
  for i = 1, 16 do if t[i] ~= prev[i] then changed = true break end end
  if changed then
    line(string.format('f%5d  CHANGED  font=%s  %s', f, tostring(isfont(t)),
         table.concat(t, ' ')))
    prev = t
  end
end
line('done')
log:close()
