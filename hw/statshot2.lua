-- statshot2.lua: press Start at several frames, then walk to 状态 and open it.
--
-- The street scenes run long dialogue, so a single Start press may land while
-- the box is up and be ignored.  Press Start every HW_EVERY frames from
-- HW_START; each time, 40 frames later, screenshot and then try the menu walk
-- (Down x3, A) with another screenshot.  The frames that actually opened the
-- window are the ones worth looking at.
--
-- env: HW_TAG HW_NF HW_START HW_EVERY HW_TRIES
local TAG   = os.getenv('HW_TAG') or 'stat'
local NF    = tonumber(os.getenv('HW_NF') or '6000')
local S0    = tonumber(os.getenv('HW_START') or '2800')
local EVERY = tonumber(os.getenv('HW_EVERY') or '300')
local TRIES = tonumber(os.getenv('HW_TRIES') or '6')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

local function hold(btn, n)
  for _ = 1, n do joypad.set({[btn] = true}); emu.frameadvance() end
  joypad.set({}); emu.frameadvance()
end
local function wait(n)
  for _ = 1, n do joypad.set({}); emu.frameadvance() end
end

-- run to the first Start
wait(S0)
for t = 1, TRIES do
  hold('Start', 4)
  wait(40)
  client.screenshot(TAG .. string.format('_t%d_menu', t))
  hold('Down', 4); wait(14)
  hold('Down', 4); wait(14)
  hold('Down', 4); wait(14)
  hold('A', 4)
  wait(60)
  client.screenshot(TAG .. string.format('_t%d_open', t))
  line(string.format('try %d at about f%d', t, S0 + t * EVERY))
  wait(EVERY - 200)
end
line('done')
log:close()
