# flynas (XY) — BLOCKED (Cloudflare + Akamai); calendar via EveryMundo works
Tested 2026-09-27. Script: `scripts/everymundo.py`, tenant `xy`.

**Good for:** cheap-day hints KWI⇄RUH/JED etc., per adult, KWD, taxes in, no bags, cached (~48 h), sparse
(KWI-RUH: 3–4 days in six months; December empty).

**Blocked: live search.**
- `https://www.flynas.com/en` → 403 **Cloudflare** "Just a moment…" challenge.
- `https://booking.flynas.com/` (Angular, Navitaire behind) loads (Akamai cookies `bm_so`, `ak_bmsc`).
  Its API base is `/api/`: `POST /api/SessionCreate {"session":{"channel":"web"}}` → 201 + header
  `X-Session-Token`; `GET /api/SessionCheck` → 200 with that header. But
  `POST /api/LowFareCalendarAvailability {"calendarLowFare":{"lowFareAvailabilityRequest":{"currency":"KWD",
  "origin":"KWI","destination":"RUH","requestedMonths":["2026-12"]}}}` → **401 empty**, and
  `POST /api/FlightSearch {"flightSearch":{"flights":[{"origin","destination","date"}],"adultCount":1,...,
  "flightMode":"round","selectedCurrencyCode":"KWD"}}` → **403 Akamai "Access Denied"** (Bot Manager needs
  the browser sensor cookie `_abck`). Stopped there.

**Calendar call:** see cards/everymundo.md, Origin `https://www.flynas.com`.
`python scripts/everymundo.py xy KWI-RUH 2026-10-01 2027-03-31` → 2026-11-03 KWD 21.75, 2027-02-27 KWD 31.70 …

**Booking link:** https://booking.flynas.com/

**Broken / retry:** endpoints are in `booking.flynas.com/AngularBundle/main.js` (grep `CreateBookingUrls`).
