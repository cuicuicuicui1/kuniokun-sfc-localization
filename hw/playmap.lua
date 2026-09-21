-- playmap: wait out the title, advance the opening narration, then press each
-- button in turn and sample frames so the action can be read off screen.
-- env: HW_TAG
local TAG = os.getenv('HW_TAG') or 'playmap'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

local function wait(n) for _ = 1, n do emu.frameadvance() end end
local function hold(tbl, n, tag, every)
  for k = 0, n - 1 do
    joypad.set(tbl)
    if tag and (k % (every or 5) == 0) then
      client.screenshot(string.format('%s_f%05d_%s_%02d', TAG, emu.framecount(), tag, k))
    end
    emu.frameadvance()
  end
end

wait(1300)
log:write('title passed F=' .. emu.framecount() .. '\n')

-- advance the opening narration: tap A regularly
for i = 1, 40 do hold({A = true}, 8); hold({}, 22) end
log:write('intro tapped, F=' .. emu.framecount() .. '\n')
log:flush()

-- does the hero walk?
hold({}, 20)
hold({Right = true}, 90, 'RIGHT', 15)
log:write('right done F=' .. emu.framecount() .. '\n')

-- one button at a time, standing still
for _, b in ipairs({{'Y', 'Y'}, {'B', 'B'}, {'X', 'X'}, {'A', 'A'}}) do
  hold({}, 20)
  hold({[b[1]] = true}, 30, b[2], 5)
  log:write(b[2] .. ' tested F=' .. emu.framecount() .. '\n')
  log:flush()
end

-- combinations that matter in a brawler
for _, c in ipairs({{'Right', 'B', 'RB'}, {'Right', 'Y', 'RY'}, {'Right', 'A', 'RA'},
                    {'Left', 'B', 'LB'}, {'Down', 'B', 'DB'}}) do
  hold({}, 20)
  hold({[c[1]] = true, [c[2]] = true}, 40, c[3], 10)
end
log:write('done F=' .. emu.framecount() .. '\n')
log:flush()