# Rehlat (www.rehlat.com) - NO (endpoint found, returns empty results) (tested 2026-09-27)

**Would be good for:** Kuwaiti OTA, KWD native. No bot wall on pages or API.

**What the site does (Angular, `/Scripts/AG_FlightAPP_PROD/main-es2015.js` + lazy SRP chunk `2-es2015.js`):**
1. `POST https://www.rehlat.com/Flights/GetSearchToken` `{"dat": "<JS Date().toString()>"}` -> token string (works).
2. `POST https://www.rehlat.com/flights/SearchForm` <body below> -> `{"Status":"Success"}` (works).
3. For EACH of ~34 supplier codes (GA00001, SA00003, VI00004, LCC0001, LCC0002, PD00001, FL00009, FD00019, UA60016,
   JDA000R5, LCC000xx ...): `POST https://api.rehlat.com/v1/Rehlat/apiva/<code>` with body
   `{TripType:"RoundTrip", Segments:[{From,To,DepartureDate:"20261210",ReturnDate:"20261217"},1], Adults, Children, Infant,
   Class:"Economy", Currency:"KWD", ClientCode:"B2C", Key:<client timestamp key>, SessionKey, SearchTokenKey:<token>, ...}`
   (full field list in `getAllSplrAPIs` in main-es2015.js; the stray `1` in Segments is what the site sends).
   API host = base64 in page var `agconsolid`.

**Result:** HTTP 200 but `{"results":[],"airlines":[],...,"toNearAirport":"...SAW"}` for all 6 suppliers tried, with and
without the home-page cookie and SearchForm call. Probably a server check on token/session we could not reproduce.
~21 requests used. Also a poor fit: 34 requests per search by design.

**Next step if retried:** capture one real search from a browser (DevTools "Copy as cURL") and diff the body/headers;
look at `apiva/GetPriceRangeDatainUserCur` (price calendar) too.
