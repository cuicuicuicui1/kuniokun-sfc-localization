-- v38: does the box scroll shift tilemap cells, or does the window move?
-- Prints, every HW_STEP frames, which box rows (0..15) hold slot tiles, plus the
-- engine's row counters.  "cells moved" == my cell-address map would go stale.
local TAG   = os.getenv('HW_TAG')   or 'v38'
local FROM  = tonumber(os.getenv('HW_FROM') or '1350')
local TO    = tonumber(os.getenv('HW_TO')   or '2400')
local STEP  = tonumber(os.getenv('HW_STEP') or '10')
local ROM   = os.getenv('HW_ROM')   or 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/kuniokun_cn.smc'
local NSLOT = tonumber(os.getenv('HW_NSLOT') or '86')
local STRIDE= tonumber(os.getenv('HW_STRIDE') or '1')
local log = io.open('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/' .. TAG .. '.log', 'w')

-- slot table -> tile -> slot index
local slot_of = {}
local f = io.open(ROM, 'rb')
f:seek('set', 0x1E900)
for i = 0, NSLOT - 1 do
    local v = f:read(1):byte(1)
    slot_of[v] = i
    if STRIDE == 1 then slot_of[(v + 1) % 256] = i end
end
f:close()

local W = 0x7C00
local function word(addr)                     -- VRAM word (byte addr = word*2)
    local lo = memory.read_u8(addr * 2, 'VRAM')
    local hi = memory.read_u8(addr * 2 + 1, 'VRAM')
    return lo + (hi % 4) * 256
end

local seen_frame = {}
local last = ''
local idx = 0
while emu.framecount() < TO do
    if idx >= FROM and (idx - FROM) % STEP == 0 then
        local rows = {}
        for r = 0, 15 do
            local cells = {}
            for c = 0, 25 do
                local s = slot_of[word(W + r * 0x40 + 3 + c)]
                if s then cells[#cells + 1] = ('%d:%d'):format(c, s) end
            end
            if #cells > 0 then rows[#rows + 1] = ('r%d[%s]'):format(r, table.concat(cells, ' ')) end
        end
        local e8 = memory.read_u8(0x03E8, 'WRAM')
        local e9 = memory.read_u8(0x03E9, 'WRAM')
        local col = memory.read_u8(0x036F, 'WRAM')
        local row = memory.read_u8(0x036E, 'WRAM')
        local ln  = memory.read_u8(0x036D, 'WRAM')
        local s = ('F=%d e8=%02X e9=%02X col=%02X row=%02X ln=%02X | %s')
            :format(idx, e8, e9, col, row, ln, table.concat(rows, ' '))
        if s ~= last then
            log:write(s .. '\n'); log:flush(); last = s
        end
    end
    if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
    if (idx % 20) == 0 then joypad.set({ A = true }, 1) end
    emu.frameadvance()
    idx = idx + 1
end
log:close()