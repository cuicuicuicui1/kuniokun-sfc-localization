-- findstatus.lua: press Start until the status screen appears, then prove it.
--
-- The status screen is the only moment all 23 label slots hold their label
-- glyphs at once: the label drawer uploads each one into its pool slot, and
-- nothing else draws those tiles.  So watch those slots' VRAM bytes every frame
-- and, the first time every one of them matches, dump the whole label area and
-- screenshot.  That is a byte-level check of the on-screen result, not just a
-- picture.
--
-- env: HW_TAG HW_NF HW_START HW_EVERY
local TAG   = os.getenv('HW_TAG') or 'find'
local NF    = tonumber(os.getenv('HW_NF') or '40000')
local S0    = tonumber(os.getenv('HW_START') or '2600')
local EVERY = tonumber(os.getenv('HW_EVERY') or '120')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

local LABELS = dofile(OUT .. '_labelglyphs.lua')

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local function matches(slot, tile, want)
  for i = 0, 15 do
    if memory.read_u8(0xC000 + tile * 16 + i, 'VRAM') ~= want[i + 1] then
      return false
    end
  end
  -- the lower half of the cell is the tile after the slot's base
  for i = 0, 15 do
    if memory.read_u8(0xC000 + (tile + 1) * 16 + i, 'VRAM') ~= want[i + 17] then
      return false
    end
  end
  return true
end

local function all_labels_up()
  for _, e in ipairs(LABELS) do
    if not matches(e[1], e[2], e[3]) then return false end
  end
  return true
end

local f = 0
local function wait(n)
  for _ = 1, n do joypad.set({}); emu.frameadvance() end
  f = f + n
end
local function hold(btn, n)
  for _ = 1, n do joypad.set({[btn] = true}); emu.frameadvance() end
  f = f + n
  joypad.set({}); emu.frameadvance(); f = f + 1
end

wait(S0)
local tries, found = 0, false
while f < NF and not found do
  tries = tries + 1
  hold('Start', 3)
  -- give the screen time to draw, then look
  for _ = 1, 40 do
    joypad.set({}); emu.frameadvance(); f = f + 1
    if all_labels_up() then found = true break end
  end
  if found then
    client.screenshot(TAG .. '_status')
    -- dump the label rows: rows 8..19, columns 0..31 of the map at $7800
    local dump = assert(io.open(OUT .. TAG .. '_vram.txt', 'w'))
    for row = 8, 19 do
      local cells = {}
      for col = 0, 31 do
        local w = memory.read_u16_le(0x6000 * 2 + (row * 32 + col) * 2, 'VRAM')
        cells[#cells + 1] = string.format('%03X', w & 0x3FF)
      end
      dump:write(string.format('row %2d: %s\n', row, table.concat(cells, ' ')))
    end
    dump:close()
    line(string.format('STATUS at f%d after %d Start presses', f, tries))
    break
  end
  -- not yet: nudge the menu cursor so a later press lands on 状态
  hold('Down', 3)
  wait(EVERY - 50)
end
if not found then line(string.format('%d tries, no status screen', tries)) end
log:close()
