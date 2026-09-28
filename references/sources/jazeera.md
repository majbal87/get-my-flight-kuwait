# Jazeera Airways (jazeeraairways.com) - BLOCKED (Cloudflare challenge) (tested 2026-09-27)

**Would be good for:** J9 low fares from Kuwait (GCC, Turkey, Egypt, India, Europe), KWD.

**Tried:** `GET https://www.jazeeraairways.com/en-kw` -> **403 "Just a moment..." Cloudflare managed challenge**
(primp chrome_126). One request, stopped per the rules.

**Workaround (already working):** Almosafer returns Jazeera fares from its airline-direct channel
(`uid: KWMOSAAPI`, `chnr: J9`) - e.g. KWI-SAW RT J9 61.29 KWD - and Flyin/Cleartrip list J9 too (Flyin 56.70).
So J9 prices are covered without the J9 site.

**If retried later:** check whether the home page returns 200; J9 runs on Navitaire, so look for a
`/api/nsk/...` or `availability` call in the booking app bundle.
