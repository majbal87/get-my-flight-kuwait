# Google Flights (scripts/google.py)

**Good for:** round trips and one-ways; the price closest to what you pay; the fast first check (0.3-0.5 s warm,
~1.2 s cold). Not for multi-city (page shows nothing). Shows Jazeera (J9) now (KWI⇄DXB 10→17 Dec: 4 J9 rows from
52 KWD, checked 2026-09-28); Pegasus (PC) not seen. Usually 5-10 options per search.
Pages that come without their list (uncached routes, lap infants, airline filter, big groups: KWI⇄LCA, KWI⇄MNL with an
infant, KWI⇄CAI MS only, KWI⇄IST 9 pax) are filled by a 2nd request, the one the site sends (see Request 2), but
Google refuses it (error 13) once it wants its browser check: then empty = unknown, use Almosafer / Booking.
Round-trip prices with an unseen return can be 10-18% below exact sellers (KWI-NRT: ET 4,194 vs 5,148.80 Almosafer;
QR 6,604 vs 7,356): confirm a Google-only cheapest round trip on an exact seller before making it the pick.

**Request:** plain GET, no key. `https://www.google.com/travel/flights?tfs=<T>&hl=en&gl=KW&curr=KWD`
`T` = URL-safe base64 (no `=`) of a tiny protobuf, built by `_tfs()`:
`1:28, 2:2`, one `3:{2:"2026-12-19", 6:"QR"(airline filter, repeat), 13:{1:1,2:"KWI"}, 14:{1:1,2:"NRT"}}` per leg,
`8:` once per passenger (1 adult, 2 child, 4 infant on lap), `9:` cabin (1 eco, 2 prem, 3 business, 4 first), `14:1`,
`19:` 1 round trip / 2 one way. Example:
`.venv/bin/python -c "import google; print(google.search([{'from':'KWI','to':'NRT','date':'2026-12-19'},{'from':'NRT','to':'KWI','date':'2026-12-30'}], adults=4, cabin='business')['results'][0])"`

**Request 2 (only when `ds:1` `d[2]` or `d[3]` is null):** `POST https://www.google.com/_/FlightsFrontendUi/data/`
`travel.frontend.flights.FlightsFrontendService/GetShoppingResults?hl=en&gl=KW&rt=c`, sent straight after the page
like the site. Form body `f.req=[null,"<inner JSON>"]`, inner = `[[null,null,null,<token ds:1 d[0][4]>],
<search ds:0 d[1][1]>,0,0,0,1]`: the page's own search, already decoded from tfs (e.g. `[null,null,1,null,[],1,
[2,0,0,1],...,[[[[["KWI",0]]],[[["MNL",0]]],null,0,null,null,"2026-12-15",...,3],...]`; trip 1 rt / 2 ow, cabin,
passengers [adults, children, 0, lap infants], legs with airline filter `["MS"]` at leg[4]). Headers `x-same-domain: 1`,
`x-goog-ext-259736195-jspb: ["en-US","KW","KWD",1,null,[-180],null,null,6,[]]` (currency here). No cookie, no key.
Reply: `)]}'` then length-prefixed lines `[["wrb.fr",null,"<JSON>"]]`; the JSON has the same layout as `ds:1` (rows at
`d[2][0]`/`d[3][0]`, same parser `_rows()`), prices whole-trip for all travellers, currency in each price token.
With `rt=c` Google streams a fuller list as it finds flights: 0.2-0.4 s when it already ran that search, 5-10 s
(KWI⇄CAI MS 5.7 s, KWI⇄IST 9 pax 9.3 s), up to 45 s (KWI⇄MNL infant; the list was stable after the first ~10% of
chunks). google.py keeps what came in `FEED_SECS` (4 s) and the last complete list. Refusal = the reply
`[["wrb.fr",null,null,null,null,[13]]]` in ~0.1 s: the site's POST carries a JS bot-check header
(`x-goog-batchexecute-bgr`) that plain requests can't make; Google accepted ~6 POSTs without it, then refused every
one from this IP (browser `fetch` without the header too) for 30+ min. google.py then stops asking for the run
(`_feed_off`) and keeps the page's rows; don't fight it.

**Reply:** HTML. JSON inside `AF_initDataCallback({key: 'ds:1', ... data:[...], sideChannel`.
- `d[2][0]` = "best" itineraries, `d[3][0]` = the rest. Each `it`: price total (all passengers, whole trip) `it[1][0][1]`.
- `f = it[0]`: `f[1]` airline names, `f[9]` minutes, `f[2]` flights. Flight `l`: `l[3]`→`l[6]` airports,
  `l[20]`+`l[8]` departure date/time, `l[21]`+`l[10]` arrival, `l[11]` minutes, `l[16]` cabin (1-4; a lower number
  than asked = mixed cabin, e.g. QR1083 economy in a "business" fare), `l[22]` = [code, number, _, name] of the
  operating flight, `l[15]` codeshare codes.
- Round trip: only the outbound flights are listed; the price is still the round-trip total. Return = one more
  request per option (not done). Such an outbound-only row never joins a ticket sold as 2 tickets.
- Currency: read from each result's price token (`it[1][1]`, base64 protobuf holding e.g. "KWD"), else the asked
  one; search.py drops rows not in the plan's currency.

**Speed / limits:** 1-2 s. Max 2 in flight, starts ~2.5 s apart (0.7 s drew 429s). In search.py a running Google
request gets only 5 s more once Almosafer answered the same trip (full 30 s when Almosafer has no answer). Block signs: HTTP 429, URL
`/sorry/`, text "unusual traffic". Script rests 45 s after the first block, off for the run after the second.

**Broken?** Signs: `ok` false with "no flights" on a route that always works (try KWI-DXB one way), or a JSON error.
Fix: save the page (`google._cl().get(...)`), check `ds:1` still exists (`grep -o "key: 'ds:[0-9]*'"`), then
print one itinerary and find the price and airports by value; update the indexes in `_rows()`. Request 2 broken
(not refused): open the route in a browser, read the GetShoppingResults request body in the network log and compare
with `_feed()`. If the tfs format
changed, open Google Flights in a browser, run the search, copy the new `tfs=` and decode it (base64 → protobuf).

**CLI:** `.venv/bin/python scripts/google.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR`
(`--children N` or `--child-ages 8,5`, `--infants N`, `--currency KWD`). Prints the shared-contract JSON.
