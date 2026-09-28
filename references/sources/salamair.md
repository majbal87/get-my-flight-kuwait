# SalamAir (OV) — BLOCKED (reCAPTCHA Enterprise + AWS WAF on search)
Tested 2026-09-27. No script. Not an EveryMundo tenant.

**What was found:** booking app `https://booking.salamair.com/` (React, `static/js/main.*.js`, loads AWS WAF
`challenge.js`). API `https://api.salamair.com/`:
1. `POST api/session` (no body) → 204, header `X-Session-Token: <JWT>` (works).
2. `GET api/flights?TripType=2&OriginStationCode=KWI&DestinationStationCode=MCT&DepartureDate=2026-12-10
   &ReturnDate=2026-12-17&AdultCount=1&ChildCount=0&InfantCount=0&extraCount=0&days=7&currencyCode=KWD`
   with headers `X-Session-Token`, `Culture: en`, `X-Recaptcha-Attempt: 1` → **428
   `[{"errorCode":730,"message":"We could not verify your browser. Please try again."}]`**. The app sends
   `X-Recaptcha-Token` from `grecaptcha.enterprise.execute(..., {action:"search_flights"})` → needs a real
   browser. (`days=7` means the reply would carry a 7-day fare strip — a calendar, if ever reachable.)
   TripType: 1 one way, 2 return, 3 multi. Also public: `GET api/resources/routes`.

**Deep link (browser):** `https://booking.salamair.com/en/search?tripType=return&origin=KWI&destination=MCT&departureDate=2026-12-10&returnDate=2026-12-17&adult=1&child=0&infant=0`
(param names from www.salamair.com links; adult/child names not verified).

**Retry idea:** if error 730 stops appearing, the GET above is all that's needed.
