# Royal Jordanian (RJ) — BLOCKED (Imperva on the Amadeus booking engine)
Tested 2026-09-27. No script. Not an EveryMundo tenant.

**What works:** www.rj.com (Sitecore) builds the booking hand-off:
`POST https://www.rj.com/redirect/to/Bookings/BookRestFlight` JSON
`{"Org":"KWI","Des":"AMM","Date1":"20261210","Date2":"20261217","Adult":"1","Child":"0","Infant":"0",
"Youth":"0","Cabin":"E","Direct":true,"Flex":false,"PromoCode":"","datasourceID":"1D2032BC-6DC9-4FB0-A8F2-8C787C723AB0","Language":"EN"}`
with header `RequestVerificationToken: <CookieToken>:<FormToken>` (both from `window.AntiForgery = {…}` in the
www.rj.com/en HTML, same cookie session) → 200 HTML form posting to
`https://booking.rj.com/plnext/royaljordanianB2CDX/Override.action` with `EMBEDDED_TRANSACTION=FlexPricerAvailability`,
`SITE=BDSUBNEW`, `LANGUAGE=GB`, `ENCT=1`, `ENC=<encrypted search>`.
(Cabin letter for business not checked; the page's radio values give it.)

**Blocked:** posting that form → **Imperva "Pardon Our Interruption"** (booking.rj.com). No prices.

**Booking link:** the form above only works as a browser POST; for a person use https://www.rj.com/en.

**Retry idea:** if booking.rj.com stops the Imperva page, the Amadeus plnext result page embeds the fares
(look for JSON in the HTML).
