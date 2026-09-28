# ITA Matrix (scripts/matrix.py)

**Good for:** a backup when Google and Booking both fail; one-way, round trip and multi-city; airline routing rules.
Prices are estimates 0-10% off Google, fewer airlines, no seller: its link shows the search, book elsewhere.

**Request:** POST JSON to `https://content-alkalimatrix-pa.googleapis.com/v1/search?key=<KEY>&alt=json`,
headers `origin: https://matrix.itasoftware.com`, `referer: https://matrix.itasoftware.com/`.
KEY = Matrix's public web key: GET `https://matrix.itasoftware.com/search`, follow the `//www.gstatic.com/alkali/…js`
script, regex `matrix… "AIzaSy…"` (33 chars after AIzaSy). Kept in `cache/matrix_key.json` for 24 h; a stale key
("API key" in a 400/403) is refetched once. Body (see `search()`):
```
{"summarizers":["solutionList"], "summarizerSet":"wholeTrip", "name":"specificDatesSlice",
 "inputs":{"slices":[{"origins":["KWI"],"destinations":["NRT"],"date":"2026-12-19","routeLanguage":"QR+"}],
  "pax":{"adults":4,"children":2,"infantsInLap":0}, "cabin":"BUSINESS", "currency":"KWD", "salesCity":"KWI",
  "changeOfAirport":false, "maxLegsRelativeToMin":1, "checkAvailability":true, "page":{"current":1,"size":25}, ...}}
```
Cabins: COACH, PREMIUM-COACH, BUSINESS, FIRST. `routeLanguage` "QR,EY+" = only those airlines. Children: count only.

**Reply (JSON):** `solutionList.solutions[]`: total all passengers `displayTotal` ("KWD7902.00");
`itinerary.carriers[]` {code, shortName}; `itinerary.slices[]` per leg: `origin.code`, `destination.code`,
`stops[]` (codes), `flights[]` ("QR1077"), `duration` (min), `departure`, `arrival` (first/last only).

**Speed / limits:** 16-47 s per search (round 4), 75 s request limit (search.py waits 90 s), max 2 in flight, ~1 s
apart. Block signs: HTTP 403 / 429 or `RESOURCE_EXHAUSTED` → off for the run. An `error` object in the reply = bad
request (read its message). search.py asks it only when no site gave an exact price for a trip.

**Checked (round 4):** HND business 7,354.20 (Qatar 7,354.60); open-jaw KIX/HND 7,902.20 (Almosafer 7,902.60); IST
one way KU 41.80 (KU published fare); NRT business QR 6,684 (−9% vs Qatar's 7,356); LHR family only 2 options
(`maxLegsRelativeToMin:1` may hide one-stop itineraries; try 2 by hand if a route looks thin).

**Broken?** Key regex fails → open the Matrix page in a browser, DevTools → Network → the `v1/search` call shows the
current key and body. Reference implementation: github ak2k/flight-cli. `changeOfAirport` false works (tested live
round 4).

**CLI:** `.venv/bin/python scripts/matrix.py KWI-KIX:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR`
