-- v40: watch the message buffer bookkeeping across messages.
-- Logs, once per frame: $03E8 (length), $03E9 (read index), $0011 (write index),
-- $036E (row), $036F (col), $036D (line counter), $0373/$0374 (state flags).
-- The question: does $03E9 go back to 0 for each LINE of an entry, or only once
-- per entry?  (A per-entry reset is what lets the box be wiped once a message.)
local tag = os.getenv('HW_TAG') or 'v40'
local to = tonumber(os.getenv('HW_TO') or '1800')
local step = tonumber(os.getenv('HW_STEP') or '1')
local apress = tonumber(os.getenv('HW_APRESS') or '25')
local log = io.open(string.format('C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/%s.log', tag), 'w')

local function u8(a) return memory.read_u8(a, 'WRAM') end
local function u16(a) return memory.read_u16_le(a, 'WRAM') end

local idx = 0
local prev = {}
while emu.framecount() < to do
    if idx < 420 and (idx % 150) == 0 then joypad.set({ Start = true }, 1) end
    if apress > 0 and (idx % apress) == 0 then joypad.set({ A = true }, 1) end
    if idx > 600 and (idx % 37) == 0 then joypad.set({ Right = true }, 1) end
    if idx >= tonumber(os.getenv('HW_FROM') or '1200') and (idx % step) == 0 then
        local e8, e9, w11 = u8(0x03E8), u8(0x03E9), u16(0x0011)
        local row, col, ln = u8(0x036E), u8(0x036F), u8(0x036D)
        local s3, s4 = u8(0x0373), u8(0x0374)
        local mark = ''
        if prev.e9 and e9 < prev.e9 then mark = mark .. ' E9RESET' end
        if prev.e8 and e8 ~= prev.e8 then mark = mark .. ' E8NEW' end
        log:write(string.format('F=%d e8=%02X e9=%02X w11=%02X row=%02X col=%02X ln=%02X 73=%02X 74=%02X%s\n',
            idx, e8, e9, w11, row, col, ln, s3, s4, mark))
        log:flush()
        prev.e8, prev.e9 = e8, e9
    end
    emu.frameadvance()
    idx = idx + 1
end
log:close()