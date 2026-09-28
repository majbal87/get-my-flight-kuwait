# Emirates: blocked (Akamai behavioural challenge) · no script

**Would be good for:** Emirates' own fares via Dubai (Japan, Istanbul and more from Kuwait).

**What happened:**
- `GET https://www.emirates.com/kw/english/` → 200 but only 2.7 KB: an Akamai "Powered and protected by Akamai"
  behavioural challenge page (`sec-if-cpt-container`, script `/bMUzUX/...?...&t=...`). No site content, so no JS bundles to read.
- `GET https://www.emirates.com/service/featured-fares?departureAirport=KWI&language=en&country=KW` → 200 JSON, but it
  ignored the parameters and returned Dubai promo "from" fares (`results.data.fares[].destinations[] {callOutPrice "AED 2,050",
  travelClassCode, ticketType, travelFrom, travelUntil}`). Not dated, not per trip, not usable for totals.
- Published scrapers say the search needs a browser flow (Akamai + branded-fares XHR).
2 requests used.

**Retry idea:** one homepage GET; if the HTML is larger than ~50 KB and has no `sec-if-cpt`, the challenge is off and
the booking widget JS can be read for a fare endpoint. Otherwise leave it. Emirates fares show up in Almosafer, Google and
Booking.com (`--airlines EK`).
