-- whichrom.lua : log exactly which ROM BizHawk loaded and its header
local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local TAG = os.getenv("HW_TAG") or "whichrom"
local log = io.open(OUT .. "/" .. TAG .. ".log", "w")
local function say(s) log:write(s, "\n"); log:flush() end
for i = 1, 10 do emu.frameadvance() end
say("romname  = " .. tostring(gameinfo.getromname()))
say("romhash  = " .. tostring(gameinfo.getromhash()))
say("boardtype= " .. tostring(gameinfo.getboardtype()))
say("status   = " .. tostring(gameinfo.getstatus()))
say("hash domain CARTRAM? " .. tostring(memory.hash_region(0x0000, 16, "CARTROM")))
-- LoROM header: title at 0x7FC0, checksum at 0x7FDE, romsize at 0x7FD7
local t = {}
for i = 0, 20 do t[#t + 1] = string.format("%02X", memory.read_u8(0x7FC0 + i, "CARTROM")) end
say("header 7FC0: " .. table.concat(t, " "))
say("romsize byte = " .. string.format("%02X", memory.read_u8(0x7FD7, "CARTROM")))
say("checksum = " .. string.format("%04X", memory.read_u16_le(0x7FDE, "CARTROM")))
say("cartrom size = " .. tostring(memory.getmemorydomainsize("CARTROM")))
-- first bytes of the font and of the drawer patch site, read through the cart
local t2 = {}
for i = 0, 7 do t2[#t2 + 1] = string.format("%02X", memory.read_u8(0x0F8000 + i, "CARTROM")) end
say("font 0F8000: " .. table.concat(t2, " "))
t2 = {}
for i = 0, 7 do t2[#t2 + 1] = string.format("%02X", memory.read_u8(0x01FA30 + i, "CARTROM")) end
say("drawer 01FA30: " .. table.concat(t2, " "))
t2 = {}
for i = 0, 7 do t2[#t2 + 1] = string.format("%02X", memory.read_u8(0x1F0200 + i, "CARTROM")) end
say("mycopy 1F0200: " .. table.concat(t2, " "))
log:close()