# Expedia and Travelocity: blocked ("Bot or Not?" page: Akamai + DataDome/Arkose captcha) · no script

**Would be good for:** a big OTA (Expedia Group) price list; Travelocity is the same platform.

**What happened:** one GET each of the results page
`https://www.expedia.com/Flights-Search?trip=roundtrip&leg1=from:KWI,to:IST,departure:12/10/2026TANYT&leg2=from:IST,to:KWI,departure:12/17/2026TANYT&passengers=adults:1&options=cabinclass:economy&mode=search`
(and the same on www.travelocity.com) → **HTTP 429**, HTML title "Bot or Not?", Akamai headers (`bm_sz`), captcha page
referencing DataDome and Arkose (`captcha-pwa`). No results, no API calls reachable. 1 request per site.

**Block sign:** 429 + `<title>Bot or Not?` = Expedia Group bot wall. Don't retry in the same run.
**Retry idea:** none cheap; results load through Expedia's GraphQL (`/graphql`) only after the page passes the bot check.
