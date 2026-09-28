# Pegasus (PC) — BLOCKED (Akamai Bot Manager)
Tested 2026-09-27. No script. Not an EveryMundo tenant.

**Tried (4 requests):**
- `https://www.flypgs.com/en` → 200 but a 2.6 KB Akamai sensor page (script `/6gDyLB_xsc7H_/...`), no content.
- `POST https://www.flypgs.com/apint/cheapfare/flight-calender-prices` body
  `{"depPort":"KWI","arrPort":"SAW","flightDate":"2026-12-01","currency":"KWD"}` (their public lowest-fare
  calendar) → **429 `{"cpr_chlge":"true","t":"…"}`** = Akamai crypto challenge.
- `https://web.flypgs.com/booking?...` (booking app) → Akamai behavioural CAPTCHA page (`sec-if-cpt-container`).

**Good for:** nothing over plain HTTP today. Booking.com / Google already list Pegasus (KWI⇄SAW/IST).

**Booking link (browser):** `https://web.flypgs.com/booking?language=en&adultCount=1&departurePort=KWI&arrivalPort=SAW&currency=KWD&dateOption=1&departureDate=2026-12-10&returnDate=2026-12-17`
(param names from memory, not verified).

**Retry idea:** the cheapfare endpoint above is the prize (whole month per call) — retry it occasionally;
a JSON list instead of `cpr_chlge` means the wall is off.
