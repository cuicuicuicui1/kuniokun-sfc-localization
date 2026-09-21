-- v35a.lua: box tilemap occupancy (fill-aware).
-- For rows 0..15 of the box area ($7C00 + row*$40), count text cells (cols 3..28) whose
-- tile is in my slot table but is NOT part of the row's uniform fill pattern.
-- env: HW_TAG, HW_FROM, HW_TO, HW_STEP, HW_ROM, HW_NSLOT, HW_STRIDE
local TAG   = os.getenv('HW_TAG')  or 'v35'
local FROM  = tonumber(os.getenv('HW_FROM') or '1330')
local TO    = tonumber(os.getenv('HW_TO')   or '2400')
local STEP  = tonumber(os.getenv('HW_STEP') or '2')
local ROMF  = os.getenv('HW_ROM') or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/dl/roms/kfix2.smc'
local NSLOT = tonumber(os.getenv('HW_NSLOT') or '86')
local STRIDE= tonumber(os.getenv('HW_STRIDE') or '1')

local fh = io.open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/' .. TAG .. '.log', 'w')
if not fh then error('cannot open log') end
local function log(s) fh:write(s .. '\n'); fh:flush() end

local f = io.open(ROMF, 'rb')
local rom = f:read('*a'); f:close()
local function romoff(bank, addr) return (bank % 0x40) * 0x8000 + (addr - 0x8000) end
local slots = {}
for i = 0, NSLOT - 1 do slots[i] = rom:byte(romoff(4, 0xE900) + i * STRIDE + 1) end
local s2t = {}
for i = 0, NSLOT - 1 do s2t[slots[i]] = i; s2t[slots[i] + 1] = i end
log('TAG ' .. TAG .. ' nslot ' .. NSLOT .. ' stride ' .. STRIDE)

local function rd(vw) return memory.read_u16_le(vw * 2, 'VRAM') end
local lastkey = ''
local maxN = 0
local maxDetail = ''
while emu.framecount() < TO do
  local F = emu.framecount()
  if F >= FROM and (F % STEP) == 0 then
    local cells = {}
    local seen = {}
    local rowinfo = {}
    local maxrow = -1
    for row = 0, 15 do
      -- modal tile of this row over the text columns (fill detection)
      local cnt = {}
      local cols = {}
      for col = 3, 28 do
        local t = rd(0x7C00 + row * 0x40 + col) % 1024
        cols[col] = t
        cnt[t] = (cnt[t] or 0) + 1
      end
      local modal, mn = nil, -1
      for t, c in pairs(cnt) do if c > mn then modal, mn = t, c end end
      local n = 0
      for col = 3, 28 do
        local t = cols[col]
        local s = s2t[t]
        if s and not (mn >= 14 and t == modal) then
          n = n + 1
          if not seen[s] then seen[s] = true end
          cells[#cells + 1] = string.format('%d:%d=s%d', row, col, s)
        end
      end
      rowinfo[row] = n
      if n > 0 then maxrow = row end
    end
    local nd = 0
    for _ in pairs(seen) do nd = nd + 1 end
    if nd > maxN then maxN = nd; maxDetail = table.concat(cells, ' ') end
    local rs = ''
    for row = 0, maxrow do rs = rs .. string.format('%d:%d ', row, rowinfo[row]) end
    local key = nd .. '|' .. rs
    if key ~= lastkey then
      log(string.format('F=%d distinct=%d maxN=%d rows[%s] e8=%02X e9=%02X col=%02X row=%02X line=%02X',
        F, nd, maxN, rs,
        memory.read_u8(0x03E8, 'WRAM'), memory.read_u8(0x03E9, 'WRAM'),
        memory.read_u8(0x036F, 'WRAM'), memory.read_u8(0x036E, 'WRAM'),
        memory.read_u8(0x036D, 'WRAM')))
      lastkey = key
    end
  end
  if F < 420 and (F % 150) == 0 then joypad.set({ Start = true }, 1) end
  if (F % 24) == 0 then joypad.set({ A = true }, 1) end
  if F > 900 and (F % 53) == 0 then joypad.set({ Down = true }, 1) end
  if F > 900 and (F % 149) == 7 then joypad.set({ Start = true }, 1) end
  emu.frameadvance()
end
log('MAXDISTINCT ' .. maxN)
log('MAXCELLS ' .. maxDetail)
fh:close()