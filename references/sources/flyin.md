# Flyin (www.flyin.com) - WORKS, sells in SAR (tested 2026-09-27)

**Good for:** one way and round trip, any route, economy/business/first; many airlines incl. LCCs (PC, J9, FZ) and
Amadeus NDC (QR); round trips also offered as two one-way tickets on different airlines (cheap mixes like PC out + J9 back).
Flyin is Cleartrip's Gulf brand (same backend as cleartrip.ae). Point of sale Saudi Arabia: prices in SAR; KWD is a
conversion with the rate list in the same reply (+/-1%). No rate for the asked currency in the reply: the script
refuses (`ok` false), never SAR shown as the asked currency. Multi-city not built. Script: `scripts/flyin.py`.

**Call (1, no cookies):** `GET https://www.flyin.com/flight/search/v2/results?data=<ENC>`
Headers: `Accept: application/json`, `app-agent: DESKTOP`, `X_CT_SOURCETYPE: B2C`, `x-multi-airline: true`,
`Preferred-Language: en`, `x-time-zone: Asia/Kuwait`.
Q (plain query, same as the results page URL, which is also the booking link `https://www.flyin.com/en/flights/results?<Q>`):
`adults=4&childs=0&infants=0&class=Business&depart_date=19/12/2026&from=KWI&to=HND&intl=y&return_date=30/12/2026`
ENC = `urlencode(CT) + ":" + hex(HMAC_SHA256(key=K, msg=CT))`, CT = CryptoJS `AES.encrypt(Q, K)` =
`openssl enc -aes-256-cbc -md md5 -salt -pass pass:K -base64 -A`, K = `GtoLdmQ4OHl+F+O8QjqJVqCQ0T1GL/9yRMAhAM/H6PA=`.
`utm_currency=KWD` and a `currency` header did NOT change the currency.

**Reply:** `cards[0]` = outbound options, `cards[1]` = return options (round trip). Card: `priceBreakup.pr` (total for all
pax for that one-way ticket, SAR), `splRtFn` ("1077$812" flight numbers), `sectorKeys[]` -> `sectors[key].flights.segments[]`
(`flightNumber` "QR-1077", `departure{airportCode,date dd/mm/yyyy,time}`, `durationTime{hh,mm}`, `oa` operating
airline on codeshares, `flightClass` "Economy" on economy searches but "" on business ones), `sectors[key].stops`
(counts technical stops: ET672 ADD-ICN-NRT is one segment but stops 2, so the script uses segments - 1),
`.totalDuration{hh,mm}` = flying time only; door-to-door = `totalSectorDuration + totalSectorLayoverDuration` (=
the card's `tripDurationMapBySector`; a technical stop's ground time is not in it). `changeAirport` (not read).
Round-trip fare: `out.priceBreakup.SPLRT[ret.splRtFn].{R|N}.pr + ret.priceBreakup.SPLRT[out.splRtFn].{R|N}.pr`
(each side holds its half; one booking). Else two one-way fares (two bookings; on the page "2 one-way fares (two
bookings)", not a separate-tickets flag, since out and back have no connection to miss): `out.pr + ret.pr`, with the cheapest return that leaves from the airport
the outbound lands at (before 2026-09-27 it took the cheapest return from ANY airport: all 40 London options came back
from STN and none fitted).
City reading: `from=HND` also gives NRT, `LHR` also STN/LGW, `IST` also SAW. The script keeps options on the asked
airports first, then cuts to 40 (all options if none match, e.g. a city code was asked). Rates: `jsons.currencyList[] {from:SAR,to:KWD,rate}`;
`jsons.searchType.sellCurr` = SAR; airline names `jsons.airline_names`.

**Speed / limits:** 0.9-3 s RT business (one 12.3 s), ~3.4 s OW economy, 6-10 s family London (3.7 MB reply);
one search took 18.5 s (cold). Own queue (2 in flight, starts 1.5 s apart), separate from Cleartrip's. ~25 requests, no wall. openresty in front.

**Checked:** 4A business KWI-HND: QR 7,379.96 (ref 7,355, +0.3%, other return). KWI-NRT: EY 4,314.93 (ref 4,308, +0.2%),
ET 5,473.66 (Almosafer 5,148.80). KWI-LHR 2A+2C economy: RJ 944.92 (Almosafer 941.80). KU KWI-IST RT 72.26 vs KU own
71.60 (+0.9%, conversion). OW KWI-IST: J9 26.99 to SAW (a SAW option; dropped when IST options exist).
Children are sent as a count (`childs=2`), no ages.

**If it breaks:**
- 404 page / HTML -> path changed. On a results page, list `ui.cltp.co/akaashpath-flyin/_next/static/chunks/*.js`
  and grep for `srpFlightResultsApi` (RTK Query slice with `getSrpResults` / `getMulticityResults` URLs) and the
  `encrypt(e,"...")` key next to it (module with `r.n(...)` crypto-js imports). Header list: grep `X_CT_SOURCETYPE`.
- 4xx JSON error with a valid path -> key or HMAC changed (check the `n=e=>{...encrypt...}` function).
- Multi-city: `POST /flight/search/v2/multicity/results` with a JSON body (shape not captured yet).
