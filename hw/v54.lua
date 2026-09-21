-- v54: find genuinely free low WRAM over a full run (boot -> title -> first dialogue -> menu)
-- logs every change in the watch region (default $0C00-$0FFF) and, at the end,
-- prints runs of bytes that never changed during the whole run.
local function env(n, d) return os.getenv(n) or d end
local TAG  = env('HW_TAG', 'v54')
local FROM = tonumber(env('HW_FROM', '0'))
local TO   = tonumber(env('HW_TO', '2200'))
local WLO  = tonumber(env('HW_WLO', '0x0C00'))
local WHI  = tonumber(env('HW_WHI', '0x0FFF'))
local DLOG = tonumber(env('HW_DLOG', '0x0D00'))   -- verbose per-change log region start
local DLOGE= tonumber(env('HW_DLOGE','0x0DFF'))   -- ... end
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

w(string.format('# v54 tag=%s frames=%d..%d region=$%04X-$%04X rom=%s',
  TAG, FROM, TO, WLO, WHI, gameinfo.getromhash()))
w(string.format('# wram init at F=%d', emu.framecount()))

local lastchange = {}

while emu.framecount() < TO do
  local f = emu.framecount()
  -- input pattern: Start at 150/300/450, A every 30 frames (same as v46/v53)
  if f == 150 or f == 300 or f == 450 then joypad.set({Start = true}) end
  if f % 30 == 0 then joypad.set({A = true}) end
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
  if nchg > 0 then
    w(string.format('F=%d chg=%d%s', emu.framecount(), nchg, line))
  end
  prev = cur
end

-- summary: runs of never-changed bytes
w('# ---- never changed during run (runs of >= 8 bytes) ----')
local run = 0
for i = 1, N + 1 do
  local zero = (i <= N) and (cnt[i] == 0)
  if zero then run = run + 1 else
    if run >= 8 then
      w(string.format('free $%04X-$%04X  (%d bytes)', WLO + i - 1 - run, WLO + i - 2, run))
    end
    run = 0
  end
end
-- summary: busiest bytes
local idx = {}
for i = 1, N do idx[i] = i end
table.sort(idx, function(a, b) return cnt[a] > cnt[b] end)
w('# ---- busiest ----')
for k = 1, math.min(24, N) do
  local i = idx[k]
  w(string.format('$%04X changed %d times, last F=%s', WLO + i - 1, cnt[i],
    lastchange[i] and tostring(lastchange[i]) or 'never'))
end
w('# done at F=' .. tostring(emu.framecount()))
log:close()