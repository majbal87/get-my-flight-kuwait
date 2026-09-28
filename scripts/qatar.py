"""Qatar Airways own fares over plain HTTP (no browser): the booking widget's fare calendar.

POST qatarairways.com/dapi/public/bff/web/affinity-search/affinity-fare-calendars (the calendar
the homepage search box shows). One call (~0.5 s) returns Qatar's lowest fare PER ADULT for the
asked departure date with every return date for ~30 days (round trip), or ~30 departure dates
(one way). Price is in the currency of the origin country (KWD from Kuwait). No flight numbers.
Total = fare x adults (checked: 1,838.65 x 4 = 7,354.60 vs Qatar site 7,355). Children, infants,
premium economy, first (the calendar has no first fare; it answers with business) and multi-city are not supported (ok=False). The real flight search
(dapi/.../flight-search/flight-offers) is behind Akamai Bot Manager (403) - not used.
Needs one homepage GET first for Akamai cookies (bm_sz/_abck); without them the POST can be denied.

CLI: python qatar.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business
"""
import argparse, json, sys, random, string, threading, time, uuid
from primp import Client

HOME = "https://www.qatarairways.com/en-kw/homepage.html"
API = "https://www.qatarairways.com/dapi/public/bff/web/affinity-search/affinity-fare-calendars"
CABINS = {"economy": "ECONOMY", "business": "PREMIUM"}  # PREMIUM = business (first would be priced as business: refused)
SLOTS = threading.BoundedSemaphore(2)
_lock, _last, _warm = threading.Lock(), [0.0], [False]
_client = Client(impersonate="chrome_126", timeout=15, cookie_store=True)
_hdr = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*", "qr-lang": "en",
        "Origin": "https://www.qatarairways.com", "Referer": HOME,
        "X-AssignedDeviceID": "".join(random.choice(string.ascii_letters + string.digits) for _ in range(32)),
        "Session-Id": str(uuid.uuid4())}
_down = False


def _pace(gap=1.5):
    with _lock:
        wait = _last[0] + gap - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def booking_url(legs, adults, cabin):
    rt = len(legs) == 2
    q = ("widget=QR&searchType=F&addTaxToFare=Y&minPurTime=0&selLang=en&tripType=%s&fromStation=%s&toStation=%s"
         "&departing=%s%s&bookingClass=%s&adults=%d&children=0&infants=0&ofw=0&teenager=0&flexibleDate=off"
         "&allowRedemption=N") % ("R" if rt else "O", legs[0]["from"], legs[0]["to"], legs[0]["date"],
                                  "&returning=" + legs[1]["date"] if rt else "", {"economy": "E"}.get(cabin, "B"), adults)
    return "https://www.qatarairways.com/app/booking/flight-selection?" + q


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None):
    global _down
    out = {"ok": False, "source": "qatar", "error": None, "search_url": booking_url(legs, adults, cabin), "results": []}
    rt = len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]
    if airlines and "QR" not in [a.upper() for a in airlines]:
        out["error"] = "Qatar Airways not among the asked airlines"
    elif len(legs) > 2 or (len(legs) == 2 and not rt):
        out["error"] = "Qatar fare calendar: one way and round trip only (no multi-city)"
    elif children or infants or cabin not in CABINS:
        out["error"] = "Qatar fare calendar prices adults only, economy or business (no premium economy or first)"
    elif _down:
        out["error"] = "Qatar blocked us earlier in this run (skipped)"
    if out["error"]:
        return out
    its = [{"origin": legs[0]["from"], "destination": legs[0]["to"], "departureDate": legs[0]["date"]}]
    if rt:
        its.append({"origin": legs[0]["to"], "destination": legs[0]["from"]})
    body = {"cabinClass": CABINS[cabin], "itineraries": its, "channel": "WEB_DESKTOP"}
    t0 = time.time()
    try:
        with SLOTS:
            if not _warm[0]:
                _pace()
                _client.get(HOME)
                _warm[0] = True
                with _lock:  # the price call goes right after the homepage; the next search waits the gap from now
                    _last[0] = time.time()
            else:
                _pace()
            t0 = time.time()
            r = _client.post(API, json=body, headers=_hdr)
        out["secs"] = round(time.time() - t0, 1)
        if r.status_code in (403, 429) or not r.text.lstrip().startswith("{"):
            _down = True
            out["error"] = "Qatar blocked (HTTP %s, Akamai)" % r.status_code
            return out
        fares = r.json().get("affinityCalendarFares") or []
        want = legs[1]["date"] if rt else legs[0]["date"]
        key = "returnDate" if rt else "departureDate"
        cal = [{"depart": f.get("departureDate"), "return": f.get("returnDate"),
                "price_total": round(f["tripPrice"]["amount"] * adults, 2), "currency": f.get("currencyCode")}
               for f in fares if (f.get("tripPrice") or {}).get("amount")]
        out["calendar"] = cal  # same query, other dates: handy for flexible dates
        hit = next((f for f in fares if f.get(key) == want and (f.get("tripPrice") or {}).get("amount")), None)
        print("qatar: %d calendar fares, asked date %s" % (len(fares), "found" if hit else "missing"), file=sys.stderr, flush=True)
        if not hit:
            out["error"] = "Qatar has no fare for that date" if fares else "Qatar HTTP %s: %s" % (r.status_code, r.text[:120])
            return out
        cur = hit.get("currencyCode")
        out["results"] = [{"airlines": ["Qatar Airways"], "price_total": round(hit["tripPrice"]["amount"] * adults, 2),
                           "currency": cur, "stops": None, "duration_min": None, "flights": [],
                           "seller": "Qatar Airways (direct)", "cabin": hit.get("cabinType"),
                           "price_per_adult": hit["tripPrice"]["amount"]}]
        if cur != currency:
            out["note"] = "Qatar prices in the origin country's currency (%s)" % cur
        out["ok"] = True
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error="Qatar failed: " + why, secs=round(time.time() - t0, 1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("legs", nargs="+", help="FROM-TO:YYYY-MM-DD")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--infants", type=int, default=0)
    ap.add_argument("--cabin", default="economy", choices=["economy", "premium", "business", "first"])
    ap.add_argument("--currency", default="KWD")
    ap.add_argument("--airlines", default=None, help="comma-separated IATA codes, e.g. QR,EY")
    a = ap.parse_args()
    legs = []
    for x in a.legs:
        route, date = x.split(":")
        fr, to = route.upper().split("-")
        legs.append({"from": fr, "to": to, "date": date})
    print(json.dumps(search(legs, a.adults, a.children, a.infants, a.cabin, a.currency.upper(),
                            a.airlines.split(",") if a.airlines else None), indent=1, ensure_ascii=False))
