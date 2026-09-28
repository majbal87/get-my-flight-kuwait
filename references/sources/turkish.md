# Turkish Airlines: blocked (PerimeterX / HUMAN captcha on the API) · no script

**Would be good for:** Turkish's own fares (IST hub; Kuwait to Istanbul, Japan via IST).

**What happened:**
- `GET https://www.turkishairlines.com/en-kw/` → 200 (Next.js page). It loads both Akamai (`/akam/13/...`) and HUMAN
  (`/web4js/human-bot-protection.js`, PerimeterX app id `PXDqLTvkTO`).
- `POST https://www.turkishairlines.com/api/v1/availability/cheapest-prices` in the same warm session, headers
  `x-platform: WEB`, `x-country: kw`, JSON body (moduleType TICKETING, origin/destination, dates dd-MM-yyyy, passengerTypeList,
  cabinClass, tripType ROUND_TRIP) → **403** JSON `{"appId":"PXDqLTvkTO","blockScript":".../captcha/captcha.js", ...}`:
  a PerimeterX captcha block before the app ever reads the body. Same as the first research round.
- The page JS is module-federated (`_app-*.js` is a 66 KB loader), so the real request shape was not read.
4 requests used.

**Block sign:** 403 with `appId` / `blockScript` / `px-cloud.net` in the reply = PerimeterX. Do not retry in the same run.
The official TK developer API needs a key + secret (not allowed here). Turkish fares are in Almosafer, Google and Booking.com (`--airlines TK`).
