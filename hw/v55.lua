-- v55: same as v54 but with a richer input script (dialogue -> walk -> menus)
-- and a watch window over the two store-free candidate blocks ($1500-$17FF).
local function env(n, d) return os.getenv(n) or d end
local TAG  = env('HW_TAG', 'v55')
local FROM = tonumber(env('HW_FROM', '0'))
local TO   = tonumber(env('HW_TO', '3000'))
local WLO  = tonumber(env('HW_WLO', '0x1500'))
local WHI  = tonumber(env('HW_WHI', '0x17FF'))
local DLOG = tonumber(env('HW_DLOG', '0x1700'))
local DLOGE= tonumber(env('HW_DLOGE','0x17FF'))
local MAXPERF = tonumber(env('HW_MAXPERF','14'))
local OUT = env('HW_OUT', 'C:/Users/<user>/.zcode/workspace/default/sfc-recon/hw/')

local log = io.open(OUT .. TAG .. '.log', 'w')
local function w(s) log:write(s, '\n'); log:flush() end

local function readwin(lo, hi)
  local ok, arr = pcall(memory.read_bytes_as_array, lo, hi - lo + 1, 'WRAM')
  if ok and type(arr) == 'table' then return arr end
  local t = {}
  for a = lo, hi do t[#t + 1] = memory.read_u8(a, 'WRAM') end
  return t
end

local N = WHI - WLO + 1
local prev = readwin(WLO, WHI)
local cnt = {}
for i = 1, N do cnt[i] = 0 end
w(string.format('# v55 tag=%s frames=%d..%d region=$%04X-$%04X rom=%s',
  TAG, FROM, TO, WLO, WHI, gameinfo.getromhash()))

local lastchange = {}
while emu.framecount() < TO do
  local f = emu.framecount()
  -- input: identical to v54 up to F=1300 (so the first dialogue still appears at F~1381),
  -- then walk around / open menus to exercise other game modes.
  if f == 150 or f == 300 or f == 450 then joypad.set({Start = true}) end
  if f % 30 == 0 then joypad.set({A = true}) end
  if f >= 1600 and f < 2000 and (f % 120) < 40 then joypad.set({Down = true}) end
  if f >= 2000 and f < 2200 and (f % 120) < 40 then joypad.set({Right = true}) end
  if f == 2260 or f == 2600 then joypad.set({Start = true}) end     -- open the menu
  if f >= 2300 and f < 2500 and f % 20 == 0 then joypad.set({A = true}) end
  if f == 2700 then joypad.set({B = true}) end
  emu.frameadvance()
  local cur = readwin(WLO, WHI)
  local nchg, shown = 0, 0
  local line = ''
  for i = 1, N do
    if cur[i] ~= prev[i] then
      local a = WLO + i - 1
      cnt[i] = cnt[i] + 1
      lastchange[i] = emu.framecount()
      nchg = nchg + 1
      if a >= DLOG and a <= DLOGE and shown < MAXPERF then
        line = line .. string.format(' %04X:%02X>%02X', a, prev[i], cur[i])
        shown = shown + 1
      end
    end
  end
  if nchg > 0 then w(string.format('F=%d chg=%d%s', emu.framecount(), nchg, line)) end
  prev = cur
end

w('# ---- never changed during run (runs of >= 16 bytes) ----')
local run = 0
for i = 1, N + 1 do
  local zero = (i <= N) and (cnt[i] == 0)
  if zero then run = run + 1 else
    if run >= 16 then w(string.format('free $%04X-$%04X  (%d bytes)', WLO + i - 1 - run, WLO + i - 2, run)) end
    run = 0
  end
end
w('# ---- bytes in $1700-$17FF that DID change ----')
local any = false
for i = 1, N do
  local a = WLO + i - 1
  if a >= 0x1700 and cnt[i] > 0 then
    w(string.format('$%04X changed %d times, last F=%s', a, cnt[i], lastchange[i] and tostring(lastchange[i]) or 'never'))
    any = true
  end
end
if not any then w('(none)') end
w('# done at F=' .. tostring(emu.framecount()))
log:close()