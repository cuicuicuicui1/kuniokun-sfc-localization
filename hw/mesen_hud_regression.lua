-- Deterministic Mesen CPU regression, using an instrumented COPY of the ROM.
-- The ROM harness calls the game's real HUD routine, not a Lua reimplementation.
local OUT = assert(os.getenv('HUD_OUT'))
local tag = assert(os.getenv('HUD_TAG'))
local donepc = tonumber(assert(os.getenv('HUD_DONE')))
local cell = tonumber(os.getenv('HUD_CELL') or '0')
local slot = tonumber(os.getenv('HUD_SLOT') or '0')
local cursor = tonumber(os.getenv('HUD_CURSOR') or '0')
local rec = assert(os.getenv('HUD_REC'))
local mem = emu.memType.snesMemory
local f = assert(io.open(OUT .. '/' .. tag .. '.log', 'w'))
local started, finished, frame = false, false, 0
local function p(s) f:write(s .. '\n'); f:flush() end
local function w(a,v) emu.write(a,v,mem) end
local function r(a) return emu.read(a,mem) & 255 end
local function finish(ok)
  if finished then return end
  finished = true
  p(ok and 'RETURNED' or (started and 'FAIL: HUD never returned to its caller' or 'FAIL: harness entry was not reached'))
  p(string.format('cursor=%d tiles=%02X/%02X scratch=%02X%02X',r(0x9DF)+r(0x9E0)*256,r(0x22),r(0x23),r(0x1F),r(0x1E)))
  local g=assert(io.open(OUT .. '/' .. tag .. '.wram','wb'))
  local t={} for i=0,0x1FFF do t[#t+1]=string.char(r(i)) end
  g:write(table.concat(t));g:close();f:close();emu.stop(ok and 0 or 1)
end
emu.addMemoryCallback(function()
  if started then return end
  started=true
  p('ENTER real HUD routine')
  w(0x10,slot);w(0x18,slot*4+cell);w(0x1C03+slot,0x20)
  for i=0,3 do w(0x1B46+slot*4+i,tonumber(rec:sub(i*2+1,i*2+2),16)) end
  w(0x9DF,cursor & 255);w(0x9E0,cursor >> 8)
  w(0x9DD,0);w(0x9DE,0);w(0x24,0x24)
  w(0x1E,0xEF);w(0x1F,0xBE)
  for i=0,255 do w(0xB00+i,0xA5) end
  w(0xC00,0x6D)
end,emu.callbackType.exec,0xF2AA,0xF2AA,emu.cpuType.snes,mem)
emu.addMemoryCallback(function() finish(true) end,emu.callbackType.exec,donepc,donepc,emu.cpuType.snes,mem)
emu.addEventCallback(function()
  frame=frame+1
  if frame>=120 then finish(false) end
end,emu.eventType.endFrame)
