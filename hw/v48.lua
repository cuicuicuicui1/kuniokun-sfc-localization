-- v48: decode the upload queue page every frame (entries between $09DD and $09DF)
-- plus the wipe state, so we can see whether a 112 byte row wipe is ever staged.
local TAG = os.getenv('HW_TAG') or 'v48'
local FROM = tonumber(os.getenv('HW_FROM') or '1400')
local TO = tonumber(os.getenv('HW_TO') or '1460')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', TAG), 'w')
log:write('v48 start tag=', TAG, '\n')

local function u8(a) return memory.read_u8(a, 'WRAM') end
local function word(w)
  local b = w * 2
  return memory.read_u8(b, 'VRAM') + memory.read_u8(b + 1, 'VRAM') * 256
end

local frames = 0
while frames < TO do
  if frames >= FROM then
    local dd, df = u8(0x09DD), u8(0x09DF)
    -- decode the pending region as [addr lo, addr hi, vmain, count, data...]
    local entries, p = {}, dd
    while p < df do
      local alo, ahi, vm, cnt = u8(0x0B00 + p), u8(0x0B00 + p + 1), u8(0x0B00 + p + 2), u8(0x0B00 + p + 3)
      entries[#entries + 1] = string.format('@%02X:%02X%02X vmain=%02X n=%d', p, ahi, alo, vm, cnt)
      if cnt == 0 then break end
      p = p + 4 + cnt
    end
    local cells = {}
    for r = 0, 2 do
      local base = 0x7C00 + r * 0x40
      local n = 0
      for c = 0, 29 do
        if word(base + 3 + c) % 0x400 ~= 0x200 and word(base + 3 + c) % 0x400 ~= 0x000 then n = n + 1 end
      end
      cells[#cells + 1] = string.format('r%d=%d', r, n)
    end
    log:write(string.format('F=%d dd=%02X df=%02X T=%02X B=%02X CUR=%02X LO=%02X P=%02X row=%02X col=%02X %s\n  %s\n',
      frames, dd, df, u8(0x0D40), u8(0x0D41), u8(0x0D42), u8(0x0D58), u8(0x0D43),
      u8(0x036E), u8(0x036F), table.concat(cells, ' '),
      table.concat(entries, '  ')))
    log:flush()
  end
  if (emu.framecount() % 30) == 0 then joypad.set({ A = true }, 1) end
  if emu.framecount() < 420 and (emu.framecount() % 150) == 0 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
  frames = frames + 1
end
log:write('v48 done\n')
log:close()