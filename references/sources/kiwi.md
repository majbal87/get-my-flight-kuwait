# Kiwi.com MCP (kiwi.py, kiwi_grid.py)

**Good for:** date grids (one call covers ±N days both ways, N ≤ 10), extra RT/OW list, self-transfer combos. Any route Kiwi sells. Native KWD, economy/premium/business/first. No multi-city.

**Endpoint:** `POST https://mcp.kiwi.com` (MCP streamable HTTP, JSON-RPC 2.0). No key, no login.
Headers: `Content-Type: application/json`, `Accept: application/json, text/event-stream`, `MCP-Protocol-Version: 2025-06-18`; after `initialize` send back `Mcp-Session-Id` from the reply header.
Order: `initialize` → `notifications/initialized` (no id) → `tools/call`. Tools: `search-flight`, `feedback-to-devs`.
Example arguments (`tools/call` name `search-flight`):
```
{"flyFrom":"KWI","flyTo":"HND","departureDate":"19/12/2026","returnDate":"30/12/2026","adults":4,
 "cabinClass":"C","currency":"KWD","sort":"price","allow_self_transfer":false,"select_airlines":"QR"}
```
Dates are dd/mm/yyyy. cabinClass M/W/C/F. Grid: add `departureDateTo` / `returnDateTo` (or `departureDateFlexDays` / `returnDateFlexDays`).
Fixed trip length: `kiwi_grid.py --nights N` sends `nights_in_dst_from/to` = N-1..N (Kiwi counts nights at the
destination, one fewer when the flight lands the next day; live KWI-DAC nights 10 gave only 11-day trips). Callers
still check the length. A whole month (`flex_days: "month"`) = 2 grid calls (1st-16th, 17th-end) with `--nights`
(nights_in_dst_* not re-checked live after 2026-09-28).
Other args: children, infants, max_sector_stopovers, exclude_airlines, nights_in_dst_from/to, dtime_from/to…

**Reply:** `result.structuredContent` (same JSON also in `content[0].text`): `{currency, resultsCount, itineraries[], error}`.
- `itineraries[].price` = whole trip, all passengers (whole KWD). `bookingUrl` = kiwi.com/u/… short link.
- Currency: read from each itinerary's `priceFormatted` ("4476 KWD"), else the asked one (never assumed KWD).
- `outbound` / `inbound`: `departureTime`, `stops`, `durationSeconds`, `cabinClass`, `segments[] {from,to,flightNumber (has carrier code),carrierName,departureTime,arrivalTime,durationSeconds,cabinClass}` (per-flight cabin "Business" and minutes are read into each flight).
- Tickets: count distinct prefixes before `_` in `id` split on `|` (1 = one ticket, 2 = two one-ways, 3+ = self-transfer).
- Max 15 itineraries per call (grid too). A missing date pair is NOT proof it is dearer: repeat itineraries can crowd
  it out (NRT ±2, 4A business: 19→30 missing while 6-7 other pairs all showed the same EY 4,476).

**Speed / limits:** 10–16 s per call cold (grid 9.5–13.6 s of server time), 0.9 s warm (same query again), `searchTimeMs` in reply.
Later live grids: 1.9–3.2 s per call; search.py gives a grid 10 s, then falls back to diagonal pairs / sample days.
Handshake (initialize + notification) ~1 s: it is not paced, so the first call goes straight after it (was ~3 s with
1.5 s pacing on each handshake step). 30 requests in one session: no block. Keep 20 s timeout, 1.5 s spacing between
real calls, 2 in flight.
**Accuracy (2026-09-27):** QR 8,054 vs 7,355 (+9.5 %), EY 4,476 vs 4,308 (+3.9 %). Grid price = its normal search price.
**Quirks:** IATA code may be read as the city (IST → also SAW, HND → Tokyo). Default allows self-transfer.

**Broken signs:** HTTP 4xx/5xx, `error` field set, `isError: true`, 0 itineraries on a busy route, tool name not `search-flight`.
**Repair:** call `tools/list` and read the `inputSchema` (arg names change there first). Official docs: kiwi.com MCP page / `https://mcp.kiwi.com` description in the Claude/ChatGPT connector directories.
