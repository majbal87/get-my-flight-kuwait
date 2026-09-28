# Etihad: blocked (Akamai tarpit on the API, Imperva on the booking engine) · no script

**Would be good for:** Etihad's own fares (lowest-fare calendar), KWD from Kuwait.

**What exists (found in the homepage):**
- The homepage (`GET https://www.etihad.com/en-kw/`, 200, Akamai cookies) holds `var configData = "..."` (hex-escaped JSON).
  `azureEndpoints.instantFlightSearchAPIURL` = `/ada-services/bff-calendar-pricing/service/instant-search/v2/fetch-prices`.
- Body (from `clientlib-flightsearchv2.js`, function that builds `searchDataData`):
```json
{"originAirportCode":"KWI","originAirportCityCode":"KWI","originAirportCountryCode":"KW","destinationAirportCode":"NRT",
 "cabinClass":"BUSINESS","passengerTypeCode":"ADT","tripType":"RT","departureDate":"2026-12-19","tripDuration":"11"}
```
  `tripType` OW/RT; the reply should have `currency`, `monthAggregatePrice[0]{yyyymm:{lowestPrice}}`, `pricePerDay[]`.
  Only routes listed in `calendarPricingOND.json` (configData `calendarPricingOndConfig`) show calendar prices on the site.
- Booking deep link: `https://digital.etihad.com/book/search?LANGUAGE=EN&CHANNEL=DESKTOP&B_LOCATION=KWI&E_LOCATION=NRT&TRIP_TYPE=R&CABIN=B&TRAVELERS=ADT,ADT,ADT,ADT&TRIP_FLOW_TYPE=AVAILABILITY&SITE_EDITION=EN-KW&DATE_1=202612190000&DATE_2=202612300000&FLOW=REVENUE`

**What happened:** the POST to fetch-prices hung until timeout (20 s, then 15 s with `sec-fetch-*` headers), twice, after a
warm homepage GET. That is Akamai Bot Manager's tarpit for requests without a valid sensor cookie (`_abck`).
`digital.etihad.com/book/search` answers 200 with "Pardon Our Interruption" (Imperva/Incapsula `reese84` challenge).
8 requests to www.etihad.com, 1 to digital.etihad.com.

**Retry idea (cheap):** a new Akamai config could let it through; try one POST with a 10 s limit. A reply that is JSON with
`pricePerDay` = working; a hang/timeout or 403 = still blocked. To find the endpoint again: homepage → `configData` →
`instantFlightSearchAPIURL`; body builder in `/etc.clientlibs/etihadairways/clientlibs/react/clientlib-flightsearchv2.js`
(grep `searchDataData`); the POST helper is `e6` in `clientlib-shared-components.js`.
Etihad prices are also in Almosafer, Google and Booking.com (use `--airlines EY`).
