# Source cards: index

One card per site: endpoint, request shape, reply fields, speed, block signs, how to repair it.
Scripts are in `scripts/` and share one contract and CLI:
`.venv/bin/python scripts/<source>.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business [--airlines QR]`.
The calendar script (everymundo) and kiwi_grid have their own CLI (see the card).

"Default" = search.py uses it on its own. Speeds: 2026-09-27 lab tests and the round-3 Japan run (4 adults, business).
Exact = the site's own KWD total. Converted = the site sells in another currency; shown as "≈", never the pick.
Other plan currencies (not KWD) are untested live: search.py drops rows not in the plan's currency with a note.

| Source (card) | Good for | Speed per search | Currency | Trip types | Exact / converted | Default |
|---|---|---|---|---|---|---|
| google | fastest check, price closest to what you pay; outbound flights only on round trips; 5–7 options, no J9/PC; RT price can be 10–18% low | 0.3–1.2 s | KWD | OW, RT | exact | yes: every RT/OW |
| almosafer | main exact KWD source, many channels (GDS, Travelfusion, Jazeera, flydubai); RT via the site's v2 search + inbound-result (only fares the site sells); per-flight cabin, codeshare, checked bags | RT 2–3 s (up to ~6–8 s), OW 1.4–2.8 s; polls up to 10 s while Amadeus is pending, then "no answer in time" | KWD | OW, RT, multi-city | exact | yes: every trip |
| booking | multi-city when Almosafer fails; per-airline cheapest (`airline_min`), cheapest nonstop | 4–13.4 s | KWD | OW, RT, multi-city | exact (agency) | backup; filtered call for a named airline nobody listed |
| qatar | Qatar's own fare calendar: 1 call = 1 departure day × ~30 return days; adults only, economy/business (first refused), no flight numbers | 0.4–1.1 s (2–3 s cold) | KWD (origin) | OW, RT | exact only within ±2% of a real Qatar itinerary; business can be 8–32% low (NRT 4,999.60 vs 7,356) | yes when QR named |
| kuwaitairways | KU's own Amadeus calendar: 7×7 date pairs in 1 call, no flight numbers | 0.8–2.1 s | KWD | OW, RT | KU published fare; kept at −2%…+10% of a real KU itinerary | yes when KU named |
| flyin | cross-check seller, many airlines incl. LCCs; RT can be 2 one-way fares (two bookings) | 0.9–3 s RT business, ~3.4 s OW, 6–10 s family London | SAR → KWD (no rate: refused) | OW, RT | converted (±1%) | extra seller when airlines named or "sellers": "all" |
| kiwi (kiwi_grid) | date grid: ±N days each end (≤ 10) in ONE call, a month in 2 (`--nights`), then confirm top pairs elsewhere; a missing pair may be the same price | 1.9–3.2 s live (10–16 s cold seen), limit 10 s | KWD | OW, RT | Kiwi's own (+4–10%) | yes for "flex_days" trips (grid only) |
| matrix | backup when no exact price | 16–47 s | KWD | all | 0–10% off, can't sell | backup only |
| cleartrip | same backend as Flyin (cleartrip.ae), own queue; no J9 | 0.8–13 s | AED → KWD | OW, RT | converted | no (toolbox) |
| everymundo | cheap-day hints for Air Arabia (g9), Saudia (sv), flynas (xy), Oman Air (wy) | 0.4–1 s | KWD | OW, RT | per adult hint, not a total | no (hints only) |

Archived (the lab's archive/, 2026-09-27 round 4): skyscanner, kayak, tripcom, octotrip, skiplagged, flydubai_calendar.

Calendar hints (everymundo) are PER ADULT and cached shopper fares: use them to pick cheap days, then price
those days on a real source. Never show them as a whole-trip price.

Cards without a script in the skill (blocked or not built; each card says what to retry): airarabia, saudia, flynas,
omanair (use everymundo.py), aviasales-price-matrix, edreams, egyptair, emirates, etihad, expedia, gulfair, jazeera,
mea, pegasus, rehlat, royaljordanian, salamair, turkish, wego, wizzair (lab scripts in tests/sources/airlines, nothing
flies from Kuwait).
