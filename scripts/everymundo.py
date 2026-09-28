"""EveryMundo fare calendar (plain HTTP, no browser) for airlines whose own sites are bot-walled.

EveryMundo (airTRFX) runs the "cheap flights to X" pages of Air Arabia (g9), Saudia (sv), flynas (xy) and
Oman Air (wy). Those pages read a public JSON API that returns, for every departure day in a window, the
cheapest fare that real shoppers were shown on the airline's own booking site in the last ~48 h.
One call = up to ~180 days. 0.4-1 s. Prices are PER PERSON (1 adult) and include taxes and fees, no bags.
They are cached shopper results, not a live quote: good for "which days are cheap", not for booking totals.
Days nobody searched are simply missing.

Calendar contract (shared by the *_calendar.py scripts in this folder):
calendar(origin, dest, date_from, date_to, trip="oneway"|"return", cabin="economy", currency="KWD")
 -> {"ok", "source", "error", "search_url", "secs",
     "days": [{"date", "return_date", "price", "currency", "per": "adult", "trip", "cabin",
               "found_at", "converted"}]}   # price = whole trip for ONE adult (out+back when trip=return)

CLI: python everymundo.py g9 KWI-SHJ 2026-12-01 2026-12-31 --trip return --cabin economy
"""
import argparse, datetime, json, threading, time
from primp import Client

API = "https://openair-california.airtrfx.com/airfare-sputnik-service/v3/%s/fares/histogram-distribution"
KEY = "HeQpRjsFI5xlAaSx2onkjc1HTK0ukqA1IrVvd5fvaMhNtzLTxInTpeYB1MK93pah"  # public, printed in every EveryMundo page
# tenant -> (airline name, site Origin the API accepts, a page a person can open)
TENANTS = {
    "g9": ("Air Arabia", "https://flights.airarabia.com", "https://www.airarabia.com/en"),
    "sv": ("Saudia", "https://www.saudia.com", "https://www.saudia.com/"),
    "xy": ("flynas", "https://www.flynas.com", "https://booking.flynas.com/"),
    "wy": ("Oman Air", "https://www.omanair.com", "https://www.omanair.com/kw/en"),
}
CABINS = {"economy": "ECONOMY", "premium": "PREMIUM_ECONOMY", "business": "BUSINESS", "first": "FIRST"}
USD_TO_KWD = 0.307  # fallback only; normally the rate is read from KWD fares in the same reply
SLOTS = threading.BoundedSemaphore(2)
_lock, _next = threading.Lock(), [0.0]
_client = Client(impersonate="chrome_126", timeout=20)


def _wait(gap=1.5):
    with _lock:
        start = max(time.time(), _next[0])
        _next[0] = start + gap
    time.sleep(max(0.0, start - time.time()))


def calendar(tenant, origin, dest, date_from, date_to, trip="oneway", cabin="economy", currency="KWD"):
    name, site, page = TENANTS[tenant]
    out = {"ok": False, "source": "everymundo-" + tenant, "error": None, "search_url": page, "days": []}
    today = datetime.date.today()
    d0 = (datetime.date.fromisoformat(date_from) - today).days
    d1 = (datetime.date.fromisoformat(date_to) - today).days
    body = {"origin": origin, "destination": dest, "departureDaysInterval": {"start": max(0, d0), "end": max(0, d1)},
            "journeyType": "ROUND_TRIP" if trip == "return" else "ONE_WAY", "travelClasses": [CABINS[cabin]]}
    hdr = {"em-api-key": KEY, "Content-Type": "application/json", "Accept": "application/json",
           "Origin": site, "Referer": site + "/"}
    t = time.time()
    try:
        with SLOTS:
            _wait()
            t = time.time()
            r = _client.post(API % tenant, content=json.dumps(body).encode(), headers=hdr)
            out["secs"] = round(time.time() - t, 1)
        if r.status_code != 200 or not r.text.lstrip().startswith("{"):
            out["error"] = "EveryMundo HTTP %s (403 = Origin header rejected, 404 = unknown tenant)" % r.status_code
            return out
        fares = [f for day in r.json().get("histogram") or [] for f in day.get("fares") or []]
        rates = [f["priceSpecification"]["totalPrice"] / f["priceSpecification"]["usdTotalPrice"] for f in fares
                 if f["priceSpecification"].get("currencyCode") == currency and f["priceSpecification"].get("usdTotalPrice")]
        rate = sorted(rates)[len(rates) // 2] if rates else (USD_TO_KWD if currency == "KWD" else None)
        for f in fares:
            p = f["priceSpecification"]
            conv = p.get("currencyCode") != currency
            price = p.get("totalPrice") if not conv else (round(p["usdTotalPrice"] * rate, 3) if rate and p.get("usdTotalPrice") else None)
            if price is None:
                continue
            out["days"].append({"date": f.get("departureDate"), "return_date": f.get("returnDate"), "price": round(price, 3),
                                "currency": currency, "per": "adult", "trip": trip,
                                "cabin": (f.get("outboundFlight") or {}).get("fareClass", "").lower(),
                                "found_at": (f.get("searchDate") or "")[:16], "converted": conv})
        out["days"].sort(key=lambda x: x["date"])
        out["ok"] = bool(out["days"])
        if not out["ok"]:
            out["error"] = "no cached %s fares for %s-%s in that window (nobody searched it lately)" % (name, origin, dest)
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error="EveryMundo failed: " + why, secs=round(time.time() - t, 1))
    return out


def cli(tenant=None):
    ap = argparse.ArgumentParser()
    if not tenant:
        ap.add_argument("tenant", choices=list(TENANTS))
    ap.add_argument("route", help="FROM-TO, e.g. KWI-SHJ")
    ap.add_argument("date_from")
    ap.add_argument("date_to")
    ap.add_argument("--trip", default="oneway", choices=["oneway", "return"])
    ap.add_argument("--cabin", default="economy", choices=list(CABINS))
    ap.add_argument("--currency", default="KWD")
    a = ap.parse_args()
    fr, to = a.route.upper().split("-")
    print(json.dumps(calendar(tenant or a.tenant, fr, to, a.date_from, a.date_to, a.trip, a.cabin, a.currency.upper()),
                     indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cli()
