# Wizz Air (W6) — timetable (daily fares) WORKS; full search BLOCKED (Kasada)
Tested 2026-09-27. Scripts (lab only, NOT in the skill: nothing flies from Kuwait): tests/sources/airlines/wizzair_calendar.py, wizzair.py.

**Still flying the Gulf?** Yes, but only to Europe: AUH and DXB (8 routes each: BUD, SOF, OTP, KRK, KTW, CLJ,
BBU, LCA), JED (BUD, FCO, MXP), AMM (BUD). Nothing from Kuwait (`InvalidMarket` for AUH-KWI).
Route list: `GET https://be.wizzair.com/<ver>/Api/asset/map?languageCode=en-gb` (cities[].connections).

**Endpoint:** `POST https://be.wizzair.com/<ver>/Api/search/timetable` (ver was `29.18.0`; read it from
wizzair.com HTML `be.wizzair.com/<ver>/Api`). Headers: `Content-Type: application/json`,
`Origin: https://wizzair.com`. Body:
`{"flightList":[{"departureStation":"AUH","arrivalStation":"BUD","from":"2026-12-01","to":"2026-12-31"},
{"departureStation":"BUD","arrivalStation":"AUH","from":"2026-12-01","to":"2026-12-31"}],
"priceType":"regular","adultCount":1,"childCount":0,"infantCount":0}`
Reply: `outboundFlights[]` / `returnFlights[]`: `departureStation`, `departureDate`, `price.amount`,
`price.currencyCode`, `departureDates[]` (times), `hasMacFlight`. Price = one seat (same for 2A+1C), basic fare
with taxes, no bags; AED from AUH/DXB. AUH and DXB are merged (row says which airport).

**Test:** AUH⇄BUD 10→17 Dec, 2 adults + 1 child: 1,369 + 969 = 2,338 AED per seat → **7,014 AED** total
(`wizzair.py`, 0.7 s). Children pay the adult fare at Wizz; infants (fee) not supported.

**Blocked:** `POST .../Api/search/search` (real itineraries/bundles) → **429 empty body with
`x-kpsdk-ct` header = Kasada**, even after loading wizzair.com for cookies. Not verified against the
booking page for that reason.

**Booking link:** `https://wizzair.com/en-gb/booking/select-flight/AUH/BUD/2026-12-10/2026-12-17/2/1/0/null`

**Broken?** 404/HTML = version bumped (script re-reads it from the homepage once). 400 `InvalidMarket` =
route not flown. 429 + `x-kpsdk-*` = Kasada now guards timetable too.
