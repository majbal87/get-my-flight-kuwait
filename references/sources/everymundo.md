# EveryMundo (airTRFX) fare calendar — shared by Air Arabia, Saudia, flynas, Oman Air
Tested 2026-09-27. Script: `scripts/everymundo.py <tenant>` (g9 Air Arabia, sv Saudia, xy flynas, wy Oman Air; the lab
wrappers airarabia/saudia/flynas/omanair_calendar.py are not copied into the skill).

**Good for:** "which days are cheap" on airlines whose booking sites are bot-walled. One call covers up to
~180 departure days. Not a live quote, not a booking total.

**Endpoint:** `POST https://openair-california.airtrfx.com/airfare-sputnik-service/v3/<tenant>/fares/histogram-distribution`
- Headers: `em-api-key: HeQpRjsFI5xlAaSx2onkjc1HTK0ukqA1IrVvd5fvaMhNtzLTxInTpeYB1MK93pah` (public, in every
  EveryMundo page), `Content-Type: application/json`, **`Origin: <airline site>`** (no Origin = 403 empty body).
  Origins used: g9 `https://flights.airarabia.com`, sv `https://www.saudia.com`, xy `https://www.flynas.com`,
  wy `https://www.omanair.com`.
- Body: `{"origin":"KWI","destination":"MCT","departureDaysInterval":{"start":70,"end":100},
  "journeyType":"ROUND_TRIP","travelClasses":["BUSINESS"]}` — days counted from today.
  Optional `returnDaysInterval` (same shape) filters the return day. `journeyType` ONE_WAY | ROUND_TRIP.
- Tenants: g9 Air Arabia, sv Saudia, xy flynas, wy Oman Air, w6 Wizz (empty). Not tenants (404 "tenant [x]
  was not found"): fz, gf, ov, pc, rj, me, ms.

**Reply:** `histogram[] = {date, fares[]}`; each fare: `priceSpecification.totalPrice` + `currencyCode` +
`usdTotalPrice`, `departureDate`, `returnDate`, `journeyType`, `outboundFlight.fareClass`, `searchDate`
(when a shopper saw it). Price is PER PERSON, taxes and fees included, no bags. Currency is whatever the
shopper used (mostly KWD from Kuwait; some AED/EUR/USD) — the script converts via `usdTotalPrice` and
marks `converted: true`. No flight numbers or times.

**Speed/limits:** 0.4–1.2 s. ~40 calls in a few minutes caused no block. Sparse: only days someone searched
in the last ~48 h (KWI-IST on Air Arabia and KWI-RUH on flynas were empty for December; Saudia empty in round 4).
Round 4 hints (per adult): Air Arabia 58.46, flynas 45.69, Oman Air 65.0 KWD. flydubai is not a tenant; its calendar
script was archived (Almosafer and Booking.com sell flydubai at exact prices).

**Broken?** 403 with empty body = Origin rejected (try the airline's own "flights to X" page domain).
400 Whitelabel page = body field renamed; the Spring error names the missing field. New key/URL: open any
airline "cheap flights to X" page (e.g. flights.airarabia.com/en/flights-from-kuwait-city-to-istanbul), grep
the HTML for `sputnik` / `em-api-key`. Related endpoint in the same config: `.../fares/search`.
