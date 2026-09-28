# Saudia (SV) — BLOCKED (Imperva); calendar via EveryMundo works
Tested 2026-09-27. Script: `scripts/everymundo.py`, tenant `sv`.

**Good for:** cheap-day hints KWI⇄JED/RUH, per adult, KWD (some rows converted from AED/EUR), taxes in,
cached shopper fares (~48 h). Sparse: KWI-JED Oct–Jan had 4–8 days with a fare; December return: 1 day
(2026-12-09→12-12 KWD 88.3). Business rarely cached (none Oct–Mar).

**Blocked:** `https://www.saudia.com/` and `/en-KW` return a 6 KB **Imperva/Incapsula** "Pardon Our
Interruption" page (cookie `incap_ses_*`, JS challenge). Booking engine is behind the same wall, so no endpoint
could be read. Two requests made, then stopped.

**Calendar call:** see cards/everymundo.md, Origin `https://www.saudia.com`.
`python scripts/everymundo.py sv KWI-JED 2026-12-01 2026-12-31 --trip return`

**Booking link:** https://www.saudia.com/ (no prefilled deep link available without the site).

**Broken?** If EveryMundo answers 403, change Origin to the domain of Saudia's "flights to X" pages.
