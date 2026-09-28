# Oman Air (WY) — booking BLOCKED (Imperva); calendar via EveryMundo works (incl. business)
Tested 2026-09-27. Script: `scripts/everymundo.py`, tenant `wy`.

**Good for:** cheap-day hints KWI⇄MCT and beyond, per adult, KWD, taxes in, cached shopper fares (~48 h).
Best-covered of the EveryMundo airlines: KWI-MCT 0–150 days had 33 days with a fare; December return economy
5 days (e.g. 12-09→12-12 KWD 60, 12-10→12-24 KWD 65); **business** return December 5 days
(12-09→12-12 KWD 256, 12-10→12-24 KWD 288). Economy one-way December: empty.

**Blocked:** booking engine is Amadeus DX `https://bookings.omanair.com/dx/WYDX/` (found in
www.omanair.com/build/995.*.js, also `https://book.omanair.com/`) → 6 KB **Imperva** "Pardon Our Interruption"
page. www.omanair.com itself loads (Symfony, Imperva cookie `incap_ses_*`), no fare API on it except EveryMundo
(`em-frontend-assets.airtrfx.com/mm/x-start.js`, pages under www.omanair.com/flights/en/…).

**Calendar call:** see cards/everymundo.md, Origin `https://www.omanair.com`.
`python scripts/everymundo.py wy KWI-MCT 2026-12-01 2026-12-31 --trip return --cabin business`

**Booking link:** https://www.omanair.com/kw/en (no prefilled deep link without the DX site).
