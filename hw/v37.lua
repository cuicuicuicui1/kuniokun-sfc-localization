-- v37.lua : find WRAM 0x40-byte blocks in $0C00-$1FFF that the game never writes.
-- logs, per block, the first frame at which its 64 bytes stopped matching the frame-0 image.
local TAG   = os.getenv('HW_TAG') or 'v37'
local FROM  = tonumber(os.getenv('HW_FROM') or '0')
local TO    = tonumber(os.getenv('HW_TO') or '2500')
local STEP  = tonumber(os.getenv('HW_STEP') or '5')
local BASE  = 0x0C00
local NB    = (0x2000 - BASE) / 0x40
local log = io.open(string.format('%s.log', TAG), 'w')
local ref, first, ever = {}, {}, {}
for b = 0, NB - 1 do ref[b] = nil; first[b] = nil; ever[b] = false end
local frames = 0
while emu.framecount() < TO do
  local idx = emu.framecount()
  -- deterministic-ish input: advance menus, talk, walk
  if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
  if idx < 420 and (idx % 150) == 30 then joypad.set({ Start = true }, 1) end
  if (idx % 30) == 0 then joypad.set({ A = true }, 1) end
  if idx > 600 and (idx % 37) == 0 then joypad.set({ Down = true }, 1) end
  if idx > 1200 and (idx % 53) == 0 then joypad.set({ Right = true }, 1) end
  if idx > 1800 and (idx % 500) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  if idx >= FROM and (idx % STEP) == 0 then
    frames = frames + 1
    for b = 0, NB - 1 do
      local a = BASE + b * 0x40
      local s = 0
      for i = 0, 0x3F do s = (s * 31 + memory.read_u8(a + i, 'WRAM')) % 4294967296 end
      if ref[b] == nil then ref[b] = s
      elseif s ~= ref[b] and first[b] == nil then
        first[b] = idx; ever[b] = true
      end
    end
  end
end
log:write(string.format('# frames sampled: %d  (frames %d..%d step %d)\n', frames, FROM, TO, STEP))
log:write('# blocks whose contents never changed across the whole run:\n')
for b = 0, NB - 1 do
  if not ever[b] then log:write(string.format('FREEBLOCK $%04X-$%04X\n', BASE + b * 0x40, BASE + b * 0x40 + 0x3F)) end
end
log:write('# blocks that DID change (first-change frame):\n')
for b = 0, NB - 1 do
  if ever[b] then log:write(string.format('USED $%04X first=%d\n', BASE + b * 0x40, first[b])) end
end
log:close()