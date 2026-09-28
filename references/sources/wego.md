# Wego - BLOCKED (Cloudflare challenge on the API) (tested 2026-09-27)

**Would be good for:** metasearch across many OTAs, KWD (siteCode KW).

**Tried:**
- `https://www.wego.com.kw/...` -> connection error (host refuses).
- `https://www.wego.com/en/flights/searches/KWI-IST-2026-12-10:IST-KWI-2026-12-17/economy/1a:0c:0i` -> 200 (page shell only).
- Main bundle `/roxana/main.<hash>.bundle.js` holds `https://srv.wego.com` + `/v3/metasearch/flights/searches/<id>` (GET results)
  and `/v3/metasearch/flights/calendar/cheapest-prices` (POST). Search creation is in a lazy chunk (not fetched).
- `POST https://srv.wego.com/v3/metasearch/flights/searches` with the usual JSON (`search:{legs,cabin,adultsCount,siteCode:"KW",
  currencyCode:"KWD",...}`) -> **403 "Just a moment..." Cloudflare managed challenge** (primp chrome_126). Stopped there.

**If retried later:** only if the srv.wego.com wall is gone (a plain POST returns JSON, not the challenge HTML).
`/v3/metasearch/flights/calendar/cheapest-prices` would be the interesting one (many dates per call).
