# Cleartrip Gulf (www.cleartrip.ae) - WORKS, sells in AED (tested 2026-09-27)

**Good for:** same as Flyin (same company, backend, endpoint, headers and encryption key); UAE point of sale, AED.
Adds little over Flyin: same content, slightly different prices. KWD = AED x rate from the same reply (no rate for
the asked currency: refused, as Flyin). Round trips on two one-way fares are two bookings, as Flyin. Script:
`scripts/cleartrip.py` (calls `flyin.search(..., base_url="https://www.cleartrip.ae", source="cleartrip")`).

**Call:** `GET https://www.cleartrip.ae/flight/search/v2/results?data=<ENC>` - see cards/flyin.md for ENC, headers,
reply layout and round-trip pairing. Booking link: `https://www.cleartrip.ae/en/flights/results?<Q>`.

**Other Cleartrip hosts:**
- kw.cleartrip.com -> redirects to www.cleartrip.com (India site, INR, Akamai `bm_sz` cookies). Not used.
- The JS lists KWD hosts (`www.cleartrip.com.kw`, `www.cleartrip.kw`, `kw.cleartrip.sa`) - untested; may give KWD natively.
- Old `/flight/orchestrator/v2/search` is gone (404).

**Speed / limits:** 0.8-1.5 s RT business, ~3 s OW, 3-13 s family London. The very first .ae call timed out at 20 s
(cold), the retry answered in 1.4 s. Own queue and pace per host (flyin.py keys them by base_url), so a Flyin search
no longer waits for a Cleartrip one (both start at the same moment). No J9 on KWI-IST (PC 35.13 to SAW is its cheapest).

**Checked:** 4A business KWI-HND: QR 7,401.58 (ref 7,355, +0.6%). KWI-NRT: ET 5,495.72; EY only 6,971.33 (EY656,
the cheaper EY652 is not sold on .ae). KWI-LHR 2A+2C economy: TK 945.36 / RJ 971.42. KU155 KWI-IST 45.38.

**If it breaks:** as Flyin, but the chunks are under `ui.cltp.co/akaashpath-cleartrip/_next/static/chunks/`.
