# Qatar Airways: fare calendar (works) · script: qatar.py

**Good for:** Qatar's own lowest fare, one way or round trip, economy or business, adults only.
Any route Qatar sells. Currency is the origin country's (KWD from KWI). One call also gives the
same trip for ~30 other return dates (round trip: the departure day is fixed) or ~181 departure dates (one way,
~69 of them unpriced; the last round-trip return day is unpriced too).
**Not for:** multi-city/open-jaw (400 "Invalid parameter" 1000316), children/infants, premium economy, first (the
calendar has no first fare and answers with business: the script refuses first, no request), flight numbers.
**Not always bookable:** the calendar is Qatar's lowest filed fare, not a seat check. It can be far below what the
site sells, mostly in business: KWI⇄NRT business 19→30 Dec KD 4,999.60 vs the site's 7,356 (−32%). So search.py keeps
a calendar price only when it is within ±2% of a real Qatar itinerary another site priced exactly; otherwise dropped.

**Endpoint:** `POST https://www.qatarairways.com/dapi/public/bff/web/affinity-search/affinity-fare-calendars`
1. First `GET https://www.qatarairways.com/en-kw/homepage.html` in the same primp session (Akamai cookies bm_sz, _abck, ak_bmsc).
2. Headers: `Content-Type: application/json`, `Origin: https://www.qatarairways.com`, `Referer: <homepage>`,
   `qr-lang: en`, `X-AssignedDeviceID: <32 random letters/digits>`, `Session-Id: <uuid4>`.
3. Body (round trip; the return leg has NO date):
```json
{"cabinClass":"PREMIUM","channel":"WEB_DESKTOP",
 "itineraries":[{"origin":"KWI","destination":"HND","departureDate":"2026-12-19"},{"origin":"HND","destination":"KWI"}]}
```
   `cabinClass`: `ECONOMY`, or `PREMIUM` (= business; also what it answers for first). One way: only the first itinerary.

**Reply:** `affinityCalendarFares[]`, each `{departureDate, returnDate, cabinType, currencyCode, tripPrice{amount}}`.
`tripPrice.amount` is the fare **per adult** for the whole round trip. Total = amount × adults.
Other fields: `lowestFareIndicator`, `premiumFareIndicator` (none explains a too-low fare).
Checked (round 4, vs a real itinerary): HND business 0.0% (1,838.65 × 4 = 7,354.60 vs site 7,355); NRT business −32%
(19→30) and −21% (19→29); LHR business −0.5%; CDG business −7.6%; BKK economy −1.9%; MNL economy −1.4%; IST one way
economy +1–2%. More than 2% off on 3 of 8, all business, always lower.

**Speed / limits:** 0.4–1.1 s per call; 2–3 s cold (homepage GET, then the price call right away). About 21 calls
in one session, no block. Keep 1.5 s between price calls, max 2 in flight. A block (403/429/HTML) = off for the run.

**Booking link:** `https://www.qatarairways.com/app/booking/flight-selection?widget=QR&searchType=F&addTaxToFare=Y&minPurTime=0&selLang=en&tripType=R&fromStation=KWI&toStation=HND&departing=2026-12-19&returning=2026-12-30&bookingClass=B&adults=4&children=0&infants=0&ofw=0&teenager=0&flexibleDate=off&allowRedemption=N` (`tripType` O/R, `bookingClass` E/B/F).

**Blocked parts:** the real flight list `POST /dapi/public/bff/web/flight-search/flight-offers`
(body `{channel, itineraries[{origin,destination,departureDate,isRequested}], cabinClass, passengers[{type:ADT,count}], promoCode:"", ignoreInvalidPromoCode:false}`)
returns Akamai "Access Denied" 403 even with warm cookies (needs the browser sensor). `/app/booking/*` loads Akamai sensor JS.

**Broken? signs:** HTML instead of JSON, 403 "Access Denied" (Akamai), or 400 `code 1000283` (body shape changed).
**Find it again:** homepage HTML → `src=".../qr-core-components/booking-widget/clientlibs.<ver>.min.js"`; in it grep
`affinity-fare-calendars`, `affinityFareBaseUrl`, `setAffinityFareParamsToDefault` (body builder), `getFlightsUrl` (booking link).
