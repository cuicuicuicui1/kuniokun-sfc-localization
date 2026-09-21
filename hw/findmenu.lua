-- findmenu.lua: press Start every HW_EVERY frames and photograph the result.
--
-- The street dialogue runs long and Start is ignored while the box is up, so
-- rather than guess a frame, poke Start repeatedly and keep a picture of each
-- attempt: whichever frame opened the command window shows it.
--
-- env: HW_TAG HW_NF HW_START HW_EVERY
local TAG   = os.getenv('HW_TAG') or 'find'
local NF    = tonumber(os.getenv('HW_NF') or '9000')
local S0    = tonumber(os.getenv('HW_START') or '2600')
local EVERY = tonumber(os.getenv('HW_EVERY') or '150')
local OUT   = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

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
local t = 0
while f < NF do
  t = t + 1
  hold('Start', 3)
  wait(30)
  client.screenshot(TAG .. string.format('_%02d', t))
  wait(EVERY - 33)
end
line(string.format('%d attempts, ended at f%d', t, f))
log:close()
