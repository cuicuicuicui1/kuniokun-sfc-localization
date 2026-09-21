local OUT = "C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw"
local f = assert(io.open(OUT .. "/hello.log", "w"))
f:write("hello from lua\n")
f:write("rom=" .. tostring(gameinfo.getromname()) .. "\n")
f:write("frame=" .. tostring(emu.framecount()) .. "\n")
f:close()