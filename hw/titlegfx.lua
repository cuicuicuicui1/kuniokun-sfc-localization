-- titlegfx: dump VRAM+CGRAM+PPU register shadow at the title screen, then press
-- Start and sample the frames right after, so we see whether an opening menu exists.
-- env: HW_TAG HW_ROM
local TAG  = os.getenv('HW_TAG') or 'titlegfx'
local ROMF = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
local OUT  = 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/'

pcall(function() emu.limitframerate(false) end)
local log = assert(io.open(OUT .. TAG .. '.log', 'w'))

-- PPU register shadow: last value written to each register.
local REG = {0x01,0x05,0x06,0x07,0x08,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,
             0x10,0x11,0x12,0x13,0x15,0x1A,0x1B,0x1C,0x1D,0x1E,0x1F,0x20,
             0x22,0x23,0x24,0x25,0x26,0x27,0x28,0x29,0x2A,0x2B,0x2C,0x2D,
             0x2E,0x2F,0x30,0x31,0x32,0x33}
local state, seen = {}, {}
for _, r in ipairs(REG) do state[r] = -1; seen[r] = 0 end
for _, r in ipairs(REG) do
  event.onmemorywrite(function(addr, value)
    local k = addr - 0x2100
    state[k] = value
    seen[k] = seen[k] + 1
  end, 0x2100 + r, 0x2100 + r, 'System Bus')
end

-- DMA descriptors at each MDMAEN trigger (bounded ring buffer).
local dmas = {}
local function snap_dma(mask)
  for ch = 0, 7 do
    if math.floor(mask / math.pow(2, ch)) % 2 == 1 then
      local b = 0x4300 + ch * 0x10
      local a0 = memory.read_u8(b + 0, 'System Bus')
      local a1 = memory.read_u8(b + 1, 'System Bus')
      local a2 = memory.read_u8(b + 2, 'System Bus')
      local a3 = memory.read_u8(b + 3, 'System Bus')
      local a4 = memory.read_u8(b + 4, 'System Bus')
      local a5 = memory.read_u8(b + 5, 'System Bus')
      local a6 = memory.read_u8(b + 6, 'System Bus')
      local a7 = memory.read_u8(b + 7, 'System Bus')
      dmas[#dmas + 1] = string.format('%d ch%d ctl=%02X A=%02X%02X%02X B=%02X%02X sz=%02X%02X',
        emu.framecount(), ch, a0, a2, a1, a3, a5, a4, a7, a6)
      if #dmas > 3000 then table.remove(dmas, 1) end
    end
  end
end
event.onmemorywrite(function(a, v) snap_dma(v) end, 0x420B, 0x420B, 'System Bus')

local function regline()
  local t = {}
  for _, r in ipairs(REG) do
    t[#t + 1] = string.format('%02X=%02X', r, state[r])
  end
  return table.concat(t, ' ')
end

local function dump(frame, tag)
  local f = assert(io.open(string.format('%s%s_f%05d_%s_vram64.bin', OUT, TAG, frame, tag), 'wb'))
  local t = {}
  for i = 0, 0xFFFF do t[i] = memory.read_u8(i, 'VRAM') end
  for i = 0, 0xFFFF do f:write(string.char(t[i])) end
  f:close()
  local c = assert(io.open(string.format('%s%s_f%05d_%s_cgram.bin', OUT, TAG, frame, tag), 'wb'))
  for i = 0, 0x1FF do c:write(string.char(memory.read_u8(i, 'CGRAM'))) end
  c:close()
  client.screenshot(string.format('%s_f%05d_%s.png', TAG, frame, tag))
  log:write(string.format('F=%d [%s] %s\n', frame, tag, regline()))
  log:flush()
end

-- Run to the title screen, then press Start once and watch what follows.
local START_AT = 700
local pressed = false
local sampled = {}
for i = 700, 1000 do sampled[i] = true end

while emu.framecount() < 1010 do
  local i = emu.framecount()
  if i == 500 or i == 620 or i == 690 then dump(i, 'pre') end
  if i >= START_AT and not pressed then joypad.set({ Start = true }); pressed = true end
  if i > START_AT and i <= START_AT + 8 then joypad.set({ Start = true }) end
  if i > 640 and i % 10 == 0 and i <= 1000 then dump(i, 'post') end
  emu.frameadvance()
end
dump(emu.framecount(), 'end')

log:write('--- dma ---\n')
for _, l in ipairs(dmas) do log:write(l .. '\n') end
log:write('done\n')
log:flush()