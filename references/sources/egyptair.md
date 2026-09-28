# EgyptAir (MS) — BLOCKED (Cloudflare challenge)
Tested 2026-09-27. No script. Not an EveryMundo tenant.

**Tried (3 requests):** `https://www.egyptair.com/en/Pages/HomePage.aspx` and `https://www.egyptair.com/en/`
→ **403 Cloudflare "Just a moment…"** managed challenge. `https://booking.egyptair.com/` → connection error (host did not answer).
No page, so no booking endpoint could be read. Stopped.

**Good for:** nothing over plain HTTP. KWI⇄CAI is on Google Flights / Booking.com.

**Booking link:** https://www.egyptair.com/

**Retry idea:** a 200 HTML homepage would allow grepping for the booking host (Amadeus DX expected).
