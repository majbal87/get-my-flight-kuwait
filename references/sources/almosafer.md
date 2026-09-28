# Almosafer (kw.almosafer.com) - WORKS (tested 2026-09-28)

**Good for:** any route; one way, round trip, multi-city/open-jaw; native KWD; totals for all passengers.
Mixes GDS (Amadeus "cont-amd-kwt", code AMD), Travelfusion (code TFN: EK, TK, 6E, OV), "ONE" channels (airline
direct: Jazeera J9, flydubai FZ, Air Arabia G9, flynas XY, 3L). Amadeus carries most of the options.
Airlines seen: QR, EK, KU, J9, TK, RJ, GF, SM, PC, FZ, MS, EY. Script: `scripts/almosafer.py`.

**Which call the website uses (2026-09-28, seen in the browser):**
- round trip: `/api/v3/flights/flight/v2/search` + `v2/async-search-result` (outbounds), then `inbound-result` (returns).
- one way and multi-city: the older `/api/flights/search?query=` + `GET /api/flights/search/<id>` polls. The script's
  `/api/v3/flights/flight/search` gives the same one-way prices (KWI-IST: 35 of 35 identical to v2 and to the page).
- **Round trip on the old v3 call is WRONG:** it returns round-trip fares the website does not sell. Japan KWI-NRT
  20->31 Dec 4A business: EY656/EY800 + EY801/EY653 at 4,308 (fare ZNN08V79 back); the site sells Etihad from 5,784
  (EY801/EY651 back) and its return list for EY656 has no EY653 at all. The v2 fare search simply has fewer fares
  (London: the old call has extra fare "recommendations", so their ids `EY12_0_...` vs v2 `EY10_0_...` don't match).

**Calls (no cookies needed).** Headers: `token: su4uj27$27ks384!3slKy`, `x-currency: KWD`, `x-locale: en`,
`Content-Type: application/json; charset=UTF-8`, `Accept: application/json, text/javascript`, Origin/Referer kw.almosafer.com.
1. `GET https://kw.almosafer.com/api/v3/flights/flight/search?query=<Q>` (v2: `.../flight/v2/search?query=<Q>`)
2. `POST .../flight/async-search-result` (v2: `.../flight/v2/async-search-result`), body = the whole JSON reply of
   step 1 (`{"next":{...},"request":{...}}`). Repeat with `{"next": <new next>, "request": ...}` while `next.get` (the
   channels still pending, `next.get[].info.code`) is not empty. v2 polls repeat earlier channels' results (dedupe by id).
3. round trip only: `POST .../flight/inbound-result`, body `{"id": <a v2 outbound itinerary id>, "nid": next.nid,
   "request": <step-1 request>}` -> the returns for that outbound: `roundtrip: false` items are one-way return fares
   (`total`, the same for every outbound; `roundtripTotal` = outbound one-way + it); `roundtrip: true` items are that
   outbound's round-trip fares (`roundtripTotal`). One call, 0.3-1 s.
Polling (script): until nothing is pending; while Amadeus is pending up to 10 s from the start (bug D: the old 5-poll
cap gave up at ~2.5 s and said "no flights"); once Amadeus answered, 5 s of polling (from the 1st poll) for other
channels (v2: 2.5 s), and Travelfusion (TFN: TK, OV, EK) 2 s more from the moment Amadeus answered (was 2.5 s from the
1st poll, so a late Amadeus left TFN no time). Measured live 2026-09-28 (probe_tk.py, 14 poll sequences, 10 trips): TFN/TK
usually answers before or with Amadeus; after it by 1.3 s (KWI-ATH one way: 4 TK rows from 73.20 were lost), 1.9 s
(TBS v2), SalamAir TFN/OV 2.6 s (KWI-MCT 67.07, the trip's cheapest, was lost on v2); once 10 s (KWI-BKK: not waited
for). Where TK is missing with TFN/TK answered (KWI-KTM, open-jaw KWI-ATH/VIE-KWI: multi-city is Amadeus only), Almosafer
simply has no TK fare. Cost: +0-1.5 s when a TFN channel never answers (the 10 s cap still holds). Amadeus still pending at the end -> `error` "Almosafer: no answer in time (...)" or, with
results, `note`. Each `res[]` and `next.get[]` item names its channel: `info.code` + `info.chnr` (ONE/J9, ONE/FZ, TFN/EK).
v2 "ONE" channels (J9, FZ, XY, AA) on round trips answer at once or hang (KWI-DXB 15->22 Jan, 2026-09-28: all still
pending after 20 s; the website's round-trip page then shows no Jazeera, though its one-way pages do) while the old
call returns them on its 1st poll. So the script keeps the old call's round trips from a channel v2 left pending (never
Amadeus) at their own fare, `seller_note` "may be missing from Almosafer's round-trip list; its one-way pages sell these
flights". That fare is the airline's round-trip fare, a little above the two one-ways: DXB 16->21 39.01 (one-ways 12.00
+ 26.58 = 38.58), 15->22 46.01 (45.50), BEY 15->22 77.97 (73.98).

**Currency:** KWD only. `x-currency: AED` is what the site sends after you switch currency, but the API still returns
KWD (`resultSet.currency`, `price.totals.currency`); the page converts on screen with `/api/system/currency/list`
(KWD base, AED 11.898974 on 2026-09-26: J9 27.000 KWD shown as AED 321). So there is no real AED/SAR/USD price:
search.py drops Almosafer rows for a non-KWD plan with a note (checked 2026-09-28).

**Q (same as the results-page path, so search_url = https://kw.almosafer.com/en/flights/<Q>):**
- round trip `KWI-HND/2026-12-19/2026-12-30/Business/4Adult`
- one way `KWI-IST/2026-12-10/Economy/1Adult`
- multi-city `KWI-KIX/2026-12-19/HND-KWI/2026-12-30/Business/4Adult` (route/date pairs; `KWI-KIX/HND-KWI/d1/d2` is WRONG, parsed as one way)
- cabins `Economy`, `Premium Economy`, `Business`, `First`; pax parts `2Adult/1Child/1Infant`. Step-1 reply echoes the parsed `request` - check it.

**Reply (step 2):** `res[]` one per supplier channel: `res[].data.itinerary[]` -> `price.totals.total` (all pax, KWD),
`legId[]` -> `res[].data.leg[]` (`duration`, `segmentId[]`) -> `res[].data.segment[]`
(`flightCode` "QR-1077", `departureAirport.code`, `departure` ISO, `operatingCarrierId`, `duration.value`).
Failed channels have `status: 400` + `error` (normal). Same flights come from several channels: keep the cheapest.
- v2 itinerary = one OUTBOUND leg: `total` = its one-way fare; `roundtrip: true` -> `cheapestRoundtripTotal` is its
  cheapest round-trip fare (the card price, "Round-trip"); `roundtrip: false` -> the card shows outbound + the
  cheapest return one-way of ANY airline (`cheapestRoundtripTotal`, e.g. Gulf Air out + Etihad bus back), and
  `cheapestAboveCombinedRoundtripTotal` is its cheapest real round-trip fare. `roundtripId` / `cheapestRoundtripId` name it.
- How the script prices a round trip like the site: keep an old-call round trip only when its outbound is a v2 outbound
  and its price is exactly that outbound's round-trip fare (several returns can share it: London EY652/61 + EY66/653 and
  + EY68/655 both 989.40, the site lists both); if outbound one-way + that return's one-way is lower, the site charges
  that (Jazeera J9121 12.00 + J9124 32.50 = 44.50 < its 45.01 round-trip fare) -> marked 2 one-way fares. Plus per
  outbound the cheapest same-airline return as 2 one-way fares when no round-trip fare is known for that pair.
  2 one-way fares: `tickets: 2`, `seller_note: "2 one-way fares"`. Dearer round-trip returns of an outbound are left out.
- `stopCount` counts technical stops (ET672 ADD-ICN-NRT is one segment, stopCount 2): the script uses segments - 1.
- `leg.duration.value` is null on most Amadeus legs: read `duration.text` ("26h 25m").
- Per-flight cabin: `itinerary.fare.legDetails[i].segment[j]` (same order as the legs and their segments):
  `cabinCode` C/F/M/W (Amadeus) or text like "Business" / "Economy With Restrictions" (Travelfusion), `cabinText`
  "Business"/"First"/"Economy". Mixed-cabin fares also carry `containsDifferentCabin: "First"`. `segment[].cabinCode`
  is often null: don't use it.
- Bags: `...segment[j].freeBaggage.checkIn` -> `allowance` + `unit` ("K"/"KG") or unit null + text "2 PIECE"; null
  checkIn = cabin bag only (J9, FZ, G9, KU light fares). Script: `bags` = one per leg `{"checked": 35, "unit": "kg"}`,
  `{"checked": 2, "unit": "pc"}`, `{"checked": 0, "unit": null}` (cabin bag only), or null (not stated); the smallest
  allowance on the leg's segments.
- Codeshare: `segment.operatingCarrierId` (QR6843 flown by JL) -> "op".

**Speed / limits (2026-09-28, 4 trips, fixed script vs the old one):** round trip now runs the old call and v2 +
inbound-result side by side: Japan 2.3-2.8 s, twice 5.0 / 8.2 s on slow v2 Travelfusion polls (old 1.4-2.0), London family 2.1-2.5 s (old 1.7-3.0), Dubai 2.9-5.8 s
(old 1.5-2.2; 5.8 s when v2 ONE channels hang for the 5 s budget; 2026-09-28 with the 2.5 s v2 grace: DXB 3.5-3.8 s,
7.1 s when the OLD call's ONE channels hang; CAI 3.7, BEY 4.6, Japan 2.7-3.4); one way unchanged (IST 1.4-2.8 s). A slot (2 in
flight) is held per request only; search starts stay 1.5 s apart (the old+v2 pair counts as one). ~100 requests in one
session, no 429 or wall seen. Cloudflare in front (`__cf_bm`). City codes expand (IST also gives SAW; HND also gave NRT;
DXB also gives XNB bus station).

**Checked against the website (2026-09-28):** KWI-NRT 4A business: EY 5,784.00, QR 5,780.40, ET 4,844.80, TK 5,909.80,
UL 6,628.40 = site cards. KWI-LHR 2A+2C: RJ 941.80, QR 968.60, EY 989.40 = cards; KU101/KU104 1,196.60 = site's return
list. KWI-IST one way: J9 27.00, KU 41.80, TK 46.30, PC 49.15, RJ 52.65 = page. KWI-DXB 17->24 Jan: J9 44.50 (2 one-way
fares) = site (2026-09-27 23:52); later the site had no J9 at all (v2 ONE hang); the script now keeps the old call's
J9 round trips then (see Polling). KWI-NRT 19->30 Dec 4A business: EY 4,308 (EY652/658 + EY800, EY801 + EY651) IS on the
site (card 4,308, return EY 17:20 "+0.00"); only the 20->31 EY 4,308 (EY653 back) was unsold.
Older: QR KWI-HND 4A business 7,354.60 (ref 7,355); QR open-jaw KIX/HND 7,902.60 (ref ~7,902, multi-city: old call,
not re-checked against the site's older multi-city API).

**Not covered:** dearer round-trip returns per outbound (the site sells some; needs one inbound-result call per
outbound); a v2 round-trip fare whose flights the old call doesn't have (London EK858/EK11 to LGW 907.80); mixed-airline
2-one-way combos the site's cards show (outbound + cheapest return of any airline).

**If it breaks:**
- 401 "Authentication token is required" -> the token changed: fetch any results page HTML and read `"apiToken":"..."`.
- 404/405 -> paths moved: fetch the results page, get `/flights/assets/desktop/_next/static/chunks/pages/_app-*.js`,
  grep `ASYNC_SEARCH_V3` / `ASYNC_SEARCH_RESULTS_V3` (a constants map of all flight API paths).
- 400 `"next" must be of type object` -> poll body shape changed; the message names the missing field.
- Challenge HTML ("Just a moment") -> Cloudflare wall; stop for the run.
- Round trips suddenly all empty while one-ways work -> the v2 / inbound-result shape changed: open a results page in a
  browser once, watch `flight/v2/*` and `inbound-result`, compare with the field names above.
