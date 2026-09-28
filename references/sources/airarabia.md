# Air Arabia (G9) — booking site BLOCKED; calendar via EveryMundo works
Tested 2026-09-27. Script: `scripts/everymundo.py`, tenant `g9` (the lab wrapper airarabia_calendar.py is not in the skill).

**Good for:** cheap-day hints KWI⇄SHJ (G9 flies KWI-SHJ nonstop; KWI-IST is via SHJ). Per adult, KWD, taxes
in, no bags, cached shopper fares from the last ~48 h. No live totals, no children/business totals.

**Blocked: live search.** `https://reservations.airarabia.com/service-app/ibe/reservation.html` (the IBE, also
reservationsad/eg/ma hosts) returns an HAProxy "Are you human?" page with a **Cloudflare Turnstile CAPTCHA**
(title "HAProxy Challenge", posts to `/.well-known/proxy/captcha_callback`). The IBE JavaScript (and so its API)
is only served after the CAPTCHA. Not attempted further (no CAPTCHA solving).
Tried: www.airarabia.com (Sitecore, 200, no fare API), flights.airarabia.com (EveryMundo, Cloudflare but passes).

**Calendar:** see cards/everymundo.md. Example:
`python scripts/everymundo.py g9 KWI-SHJ 2026-12-01 2026-12-31 --trip return`
→ 2 days, e.g. 2026-12-01→12-10 KWD 58.46, 2026-12-03→12-05 KWD 58.92 (0.6–1.1 s). KWI-IST: empty.
Wider window (0–150 days) KWI-SHJ: ~29 of 151 days had a fare (one way from KWD 25.95).

**Booking link:** https://www.airarabia.com/en (no working prefilled deep link found).

**Fix/retry idea:** if Air Arabia ever drops the Turnstile gate, fetch reservation.html, read its JS bundle and
grep for `availability` / `fareQuote`. Until then only EveryMundo.
