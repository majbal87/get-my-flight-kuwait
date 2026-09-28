# Kuwait Airways (kuwaitairways.com) - WORKS as a fare calendar (tested 2026-09-27)

**Good for:** KU's own lowest fare for every date pair +/-3 days in ONE call (7x7 grid round trip, 7 days one way),
native KWD, total for all passengers. Great for flexible dates on KU routes (LHR, IST, Europe, Asia).
No flight numbers or times (calendar level). Economy and business. One way, round trip. Script: `scripts/kuwaitairways.py`.

**Calls (2, token reusable ~30 min):**
1. `POST https://airlines.api.amadeus.com/v1/security/oauth2/token`, form body:
   `client_id=rd47SmVxC8079PaYyKzy8Ih5a6ldb2V6&client_secret=dN5J0QBZKAFqWHSb&grant_type=client_credentials&guest_office_id=KWIKU08AA`
   (public values printed in the kuwaitairways.com/en home page, function `getToken()`). -> `access_token`.
2. `POST https://airlines.api.amadeus.com/v2/search/air-calendars`, `Authorization: Bearer <token>`, JSON:
   `{"commercialFareFamilies":["CFFKU"],"itineraries":[{"departureDateTime":"2026-12-10T00:00:00.000","originLocationCode":"KWI","destinationLocationCode":"IST","isRequestedBound":true},{"departureDateTime":"2026-12-17T00:00:00.000","originLocationCode":"IST","destinationLocationCode":"KWI","isRequestedBound":false}],"travelers":[{"passengerTypeCode":"ADT"},{"passengerTypeCode":"ADT"}],"searchPreferences":{"showMilesPrice":false}}`
   Economy `CFFKU`, business `CFFBUS` (no first / premium). Children `CHD` work (tested LHR 2A+2C); infants not built.
Origin/Referer www.kuwaitairways.com sent; not checked whether needed.

**Reply:** `data[]` {`departureDate`, `returnDate`, `prices.totalPrices[0].total` (integer in the currency's smallest
unit: 71600 = 71.600 KWD; divide by 10^`dictionaries.currency.<code>.decimalPlaces`, 3 for KWD, 2 for USD: the
script reads it per currency, before it cut USD 10x), `currencyCode`, `fareFamilyCode` (ECOZERO/ECOSAVER/BUSSAVER/BUSPLUS), `bounds[]` airports}.

**Speed / limits:** 0.8-2.1 s per search (token + calendar call back to back; token kept ~30 min). 1.5 s between
calendar calls, max 2 in flight. 18 calls, no limit seen.

**Quirks:** a round trip may mix fare types (`fareFamilyCode` is the outbound's); KWI-IST can come back via SAW
(`bounds` airports); a route KU doesn't fly comes back via other airlines (KWI-HND via DEL, KD 12,984.60 for 4 in
business), so never read a price as a KU nonstop without its `bounds`.

**Checked:** KWI-IST 10-17 Dec 1A economy 71.600 = Almosafer's KU fare (exact). KWI-LHR 2A: eco 682.10, business 2,710.30.
Round 4 vs real itineraries: never lower; = the KU published fare on ITA Matrix (LHR 2A 0.0%, IST 0.0%); Booking.com
sells KU 0.7-6.5% below it (LHR family +0.7-1.3%, LHR 2A +1.7%, IST +5.3%, CAI +6.9%). So search.py keeps a KU
calendar price when it is −2% … +10% of a real KU itinerary priced exactly by another site.

**Not usable:** `/v2/search/air-bounds` (flight list) -> 400 "AIR-BOUNDS RESOURCE NOT SUPPORTED" for this client.
Booking site digital.kuwaitairways.com = Imperva wall ("Pardon Our Interruption"), so the link is /en/book-a-flight.

**If it breaks:** fetch https://www.kuwaitairways.com/en, find `function getToken()` for new client id/secret and
`service_WEP_API_URL`; office id per departure city comes from the SharePoint list "Stations" (`OfficeId`).
401 = token expired; 38412 = resource not allowed for this client.
