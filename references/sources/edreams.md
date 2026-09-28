# eDreams: not working yet (API open, search request rejected) · no script

**Would be good for:** a big European OTA (ODIGEO: eDreams, Opodo, GO Voyages), one way / round trip / multi-city.

**What works:** `POST https://www.edreams.com/travel/service/graphql` (Cloudflare in front, but no challenge).
`{"query":"{__typename}"}` → 200 `{"data":{"__typename":"Query"}}`. **Introspection is on**
(`{__schema{types{name kind fields{...} inputFields{...} enumValues{name}}}}` → 150 KB schema, ~5 s).
The full SDL is also inside the JS chunk that contains `mainAirportsOnly` (was `/travel/static-content/js/1271110.*.js`,
listed in `GET https://www.edreams.com/travel/`).

**Search shape from the schema:** `searchItinerary(searchItineraryRequest: SearchItineraryRequest!)`:
`{buyPath:Int, tripType: ONE_WAY|ROUND_TRIP|MULTIPLE_DESTINATIONS, itinerary:{numAdults, numChildren, numInfants,
cabinClass:String, segments:[{date: String @yyyyMMddTHHmmssZZZZZ, departure:{iata}, destination:{iata}}]}}`.
Reply: `itineraries[{key, fees[{price{amount currency} type}], legs[{segmentId}]}]`, plus lookup lists `segments`,
`sections` (flightCode, dates, cabinClass BUSINESS|FIRST|TOURIST|PREMIUM_ECONOMY|ECONOMIC_DISCOUNTED), `carriers`, `locations`.
The older `search(searchRequest)` is deprecated.

**What failed:** every real search (old `search` and new `searchItinerary`; dates as `2026-12-10`, `...T00:00:00Z`,
`...T00:00:00.000Z`; with and without warm cookies from `/travel/`, `buyPath` 36, `operationName`) → HTTP 400/500 after
5–7 s with an HTML error page (the GraphQL error text is hidden). 22 requests used (6 were JS chunks).

**Next step (cheap):** find the client's own `searchItinerary` query document and variables (grep the other `/travel/static-content/js/*.js`
chunks for `searchItinerary(` or `SearchItinerary`), or ask the user for one DevTools "Copy as cURL" of the search call.
The 5–7 s before the error suggests the search runs and a required value (date format, `buyPath`, or a visit/session header) is wrong.
