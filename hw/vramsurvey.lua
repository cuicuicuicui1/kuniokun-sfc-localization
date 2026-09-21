-- vramsurvey: at several gameplay moments, report which 4KB VRAM blocks are
-- completely zero, so the glyph pool can be moved out of the font area.
local TAG = os.getenv('HW_TAG') or 'vramsurvey'
local OUT = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'
pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))
local function b(a) return memory.read_u8(a, 'VRAM') end
local snap = {}
local function survey(frame)
  local out = {}
  for blk = 0, 15 do           -- 16 blocks of 4 KB
    local nz, n = 0, 0
    for i = 0, 0x0FFF, 4 do
      n = n + 1
      local v = b(blk * 0x1000 + i)
      if v ~= 0 then nz = nz + 1 end
    end
    out[blk] = nz
  end
  log:write(string.format('F=%d  nonzero-per-4K-block (sampled/1024): %s\n',
    frame, table.concat(out, ' ')))
  log:flush()
end
while emu.framecount() < 1300 do emu.frameadvance() end
for i = 1, 40 do
  for k = 0, 7 do joypad.set({A=true}); emu.frameadvance() end
  for k = 0, 22 do emu.frameadvance() end
  if i % 5 == 0 then survey(emu.framecount()) end
end
for k = 0, 120 do joypad.set({Right=true}); emu.frameadvance() end
survey(emu.framecount())
log:write('done\n'); log:flush()
