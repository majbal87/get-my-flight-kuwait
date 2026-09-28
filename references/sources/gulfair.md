# Gulf Air (GF) — BLOCKED (Imperva Advanced Bot Protection on the search call)
Tested 2026-09-27. No script (nothing returns prices). Not an EveryMundo tenant.

**What was found (useful if the wall ever drops):** booking engine `https://flights.gulfair.com/` (Angular,
Anixe "falcon" IBE; bundle `main-*.js`). API base `https://flights.gulfair.com/falcon/b2c/api/v2/`.
1. `POST token/get` body `{"request":{"account_name":"ibe_anixe","type":"b2c","client_device":"web_browser"},"locale":"en"}`
   → 200 `{"response":{"token":"<JWT>"}}` (works, 1 s).
2. `POST flights/avail` (and `flights/calendar` = fare calendar) with `Authorization: Bearer <JWT>`, body
   `{"adt":1,"chd":0,"tnn":0,"inf":0,"flight_type":"return"|"single","origin":"KWI","destination":"BAH",
   "departure_date":"20261210","return_date":"20261217","cabin_class":"Y",
   "show_datalayers":true,"timestamp":<ms>,"ht":<hash>,"locale":"en"}`.
   `ht` = md5 applied N times to `reverse(token) + reverse(str(ts))[1:] + reverse(str(ts))[0]`,
   N = first digit of the reversed timestamp (min 1). (Decoded from the obfuscated `zm$1` function.)
   → **403 "Hold Up … something about your browser made us think you were a bot"** (Imperva ABP / Distil,
   script `/6657193977244c13`, CAPTCHA). 0.3 s. Stopped.

**Deep link (browser):** `https://flights.gulfair.com/falcon/deeplink?locale=en&adt=1&tnn=0&inf=0&chd=0&cabin_class=Y&origin=KWI&destination=BAH&flight_type=return&departure_date=20261210&return_date=20261217&page=flights`
(template `List2URL` in www.gulfair.com HTML; business probably `cabin_class=C`).

**Retry idea:** check again if `flights/avail` answers JSON; path list: grep `main-*.js` for `Le(i)}flights/`.
