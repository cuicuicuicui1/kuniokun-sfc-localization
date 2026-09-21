-- statshot.lua: drive to the status screen and photograph it.
--
-- The intro runs for about 2600 frames; after that the player has control and
-- Start opens the command window (气力 / 道具 / 装备 / 状态 / 扔掉).  状态 is
-- the fourth row, so Start, Down x3, A.  Screenshots land in hw/ as
-- <tag>_<label> (BizHawk appends no extension).
--
-- env: HW_TAG HW_NF HW_START
local TAG = os.getenv('HW_TAG') or 'stat'
local NF  = tonumber(os.getenv('HW_NF') or '4200')
local S0  = tonumber(os.getenv('HW_START') or '2700')
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function line(m) log:write(m .. '\n'); log:flush() end

-- (frame, buttons held for 4 frames, screenshot label after 40 more)
local plan = {
  {S0,        {Start = true}, 'menu'},
  {S0 + 120,  {Down = true},  nil},
  {S0 + 150,  {Down = true},  nil},
  {S0 + 180,  {Down = true},  nil},
  {S0 + 210,  {Down = true},  nil},
  {S0 + 240,  {A = true},     'status'},
}
local at = {}
for _, e in ipairs(plan) do at[e[1]] = e end

for f = 1, NF do
  local e = at[f]
  local held = {}
  if e then held = e[2] end
  joypad.set(held)
  emu.frameadvance()
  if e and e[3] then
    for k = 1, 40 do joypad.set({}); emu.frameadvance() end
    client.screenshot(TAG .. '_' .. e[3])
    line(string.format('f%5d  shot %s', f + 40, e[3]))
  end
end
line('done')
log:close()
