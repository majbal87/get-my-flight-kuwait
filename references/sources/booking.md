# Booking.com Flights (scripts/booking.py)

**Good for:** multi-city / open-jaw; round trips Google leaves empty; the cheapest price per airline over ALL offers
(`airline_min`) and the cheapest nonstop (`nonstop_min`, `nonstop_airline`); real child ages; codeshares (who flies
the plane) and per-flight cabin. Sold through Booking.com's travel-agency partner. Prices: Qatar +0.3% vs Qatar's own
7,354.60; Kuwait Airways 0.7-6.5% BELOW its own published fare (round 4). No per-option link: the Book link is the search.

**Request:** plain GET, no key. `https://flights.booking.com/api/flights/` with headers
`Accept: application/json`, `x-requested-from: clientFetch`, `Referer: https://flights.booking.com/flights/`.
Params: `type=ROUNDTRIP|ONEWAY|MULTISTOP`, `adults=4`, `children=8,5` (ages; infants as `1`), `cabinClass=ECONOMY|
PREMIUM_ECONOMY|BUSINESS|FIRST`, `sort=CHEAPEST`, `currency=KWD`, `travelPurpose=leisure`, `enableVI=1`,
`locale=en-gb`, `salesCountry=kw`, `limit=60` (offers per reply: 15 without it, 60 at most; the site pages with
`page=2`), optional `airlines=QR,EY`.
Round trip / one way: `from=KWI.AIRPORT&to=NRT.AIRPORT&depart=2026-12-19[&return=2026-12-30]`.
Multi-city: `from=KWI.AIRPORT|HND.AIRPORT&to=KIX.AIRPORT|KWI.AIRPORT&multiStopDates=2026-12-19|2026-12-30`.

**Reply (JSON):** `flightOffers[]` = the 60 cheapest (`limit=60`; 15 by default left out TK 252.76 and KU 294.90 on
the KWI-ATH / VIE-KWI open-jaw, 2026-09-28: airlines in the rows 5 -> 12; TBS 5 -> 14; CAI-KUL 2 -> 7). Same search
time (fresh pairs 60/15: 7.3/7.5, 8.2/5.9, 4.1/4.0, 11.0/12.1 s); reply ~1 MB instead of ~300 KB.
- Total, all passengers, whole trip: `priceBreakdown.total` = `units + nanos/1e9`, `currencyCode`.
- `segments[]` = one per trip leg (`totalTime` s); `segments[].legs[]` = flights: `flightInfo.flightNumber`,
  `flightInfo.carrierInfo.marketingCarrier` / `operatingCarrier` (JL7996 operated by QR), `departureAirport.code /
  country / city`, `departureTime`, `cabinClass` (can be lower than asked: mixed cabin), `totalTime`.
- Bags per trip leg: `segments[].travellerCheckedLuggage[]` (one per traveller) `.luggageAllowance`: `PIECE_BASED`
  `maxPiece` 2 + `maxWeightPerPiece` 23 -> {"checked": 2, "unit": "pc"}; `WEIGHT_BASED` `maxTotalWeight` 30 ->
  {"checked": 30, "unit": "kg"}; empty list -> {"checked": 0, "unit": null} (no checked bag: matches
  `includedProducts` and `brandedFareInfo.checkinBaggageExcluded`); no field -> null. Script: `bags` = one per leg,
  the smallest over travellers, null when no leg states it. Checked on the site (H4, RJ643+RJ131 / PC902+PC858 220.43):
  no checked bag either way = [0, 0]. Not kept: carry-on vs personal item only (`travellerCabinLuggage`,
  Pegasus return: personal item only), add-on bag prices (`ancillaries.checkedInBaggage`).
- `aggregation.airlines[]` {iataCode, name, minPrice} (counts an airline on ANY flight, feeders too);
  `aggregation.stops[]` {numberOfStops, minPrice, cheapestAirline} (cumulative: "up to N stops").
- `cabinClassExtension.text` set = some offers mix cabins.

**Speed / limits:** 4-13.4 s (one open-jaw >20 s). Max 2 in flight, starts ~1.5 s apart, 25 s per request
(search.py waits 35 s).
Block signs: HTTP 403 / 429 or HTML instead of JSON (a 202 bot-check page) → off for the run.
Only 60 offers per reply (CAI-KUL: 7 of 26 airlines in them): to see an airline missing from them, call again with
`--airlines XX` (`airline_min` has every airline's cheapest price).

**Broken?** Signs: HTML or a 400 naming a parameter, or `flightOffers` missing. Fix: open flights.booking.com in a
browser, run a search, DevTools → Network → filter `api/flights`, copy the new params/fields into `_params()` /
`_option()`. The web link (`results_url`) is the same search at `/flights/<FROM>.AIRPORT-<TO>.AIRPORT/` or `/flights/multicity/`.

**CLI:** `.venv/bin/python scripts/booking.py KWI-KIX:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR`
(`--child-ages 8,5`, `--infants N`, `--currency KWD`).
