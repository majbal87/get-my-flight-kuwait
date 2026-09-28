"""ITA Matrix flight prices over plain HTTP (no browser).

POSTs to Matrix's own JSON API (content-alkalimatrix-pa.googleapis.com/v1/search) with the public
web key read from Matrix's page (same approach as github ak2k/flight-cli), kept in ../cache/ for 24 h.
Handles one-way, round trip and multi-city / open-jaw. Takes 20-55 s per search, 75 s limit per request.
A block (403 / 429) switches Matrix off for the rest of the run at once (no waiting).
Airport changes inside a connection are switched off (changeOfAirport false).
Prices are Matrix estimates (no seller), totals for all passengers.

CLI: python matrix.py KWI-KIX:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --currency KWD
"""
import argparse, base64, json, os, re, threading, time, urllib.parse
from primp import Client
from pace import Pace

CABINS = {"economy": "COACH", "premium": "PREMIUM-COACH", "business": "BUSINESS", "first": "FIRST"}
SLOTS = threading.BoundedSemaphore(2)  # max 2 Matrix searches in flight
KEY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "cache", "matrix_key.json")
_KEY = None
_lock = threading.RLock()
_client = None
_pace = Pace(1.0)
_down = False  # set on the first block


def _cl():
    global _client
    with _lock:
        if _client is None:
            _client = Client(impersonate="chrome_126", verify=False, timeout=75)
    return _client


def _key(fresh=False):
    """Public API key, read from Matrix's JS bundle (it changes now and then). Kept on disk for 24 h."""
    global _KEY
    with _lock:  # one thread fetches, the others wait for it
        if not _KEY and not fresh and os.path.exists(KEY_FILE) and time.time() - os.path.getmtime(KEY_FILE) < 86400:
            _KEY = json.load(open(KEY_FILE))["key"]
        if not _KEY or fresh:
            home = _cl().get("https://matrix.itasoftware.com/search").text
            js = re.search(r'src="((?:https:)?//www\.gstatic\.com/alkali/[^"]+\.js)"', home).group(1)
            js = _cl().get(("https:" + js) if js.startswith("//") else js).text
            _KEY = re.search(r'["\'.]matrix["\']?\s*[=:]\s*["\'](AIzaSy[A-Za-z0-9_-]{33})["\']', js).group(1)
            os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)
            json.dump({"key": _KEY}, open(KEY_FILE, "w"))
    return _KEY


def _is_round_trip(legs):
    return len(legs) == 2 and legs[0]["from"] == legs[1]["to"] and legs[0]["to"] == legs[1]["from"]


def _pax(adults, children, infants, as_str=False):
    p = {"adults": adults, "children": children, "infantsInLap": infants}
    return {k: (str(v) if as_str else v) for k, v in p.items() if v or k == "adults"}


def matrix_url(legs, adults, children, infants, cabin):
    """Link that opens the same search on matrix.itasoftware.com (format from ak2k/flight-cli)."""
    def sl(leg, ret=None):
        return {"origin": [leg["from"]], "dest": [leg["to"]], "dates": {
            "searchDateType": "specific", "departureDate": leg["date"], "departureDateType": "depart",
            "departureDateModifier": "0", "departureDatePreferredTimes": [],
            "returnDate": ret["date"] if ret else "", "returnDateType": "depart",
            "returnDateModifier": "0", "returnDatePreferredTimes": []}}
    if len(legs) == 1:
        trip, slices = "one-way", [sl(legs[0])]
    elif _is_round_trip(legs):
        trip, slices = "round-trip", [sl(legs[0], legs[1])]
    else:
        trip, slices = "multi-city", [sl(l) for l in legs]
    state = {"type": trip, "slices": slices, "pax": _pax(adults, children, infants, True),
             "options": {"cabin": CABINS[cabin], "stops": "-1", "extraStops": "1",
                         "allowAirportChanges": "false", "showOnlyAvailable": "true"}}
    b = base64.b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()
    return "https://matrix.itasoftware.com/flights?search=" + urllib.parse.quote(b)


def _t(iso):
    return iso[:16].replace("T", " ") if iso else None  # "2026-12-19T04:35+03:00" -> local "2026-12-19 04:35"


def _flights(s):
    """Per-flight rows. Matrix's summary gives only each slice's first departure and last arrival."""
    airports = [s["origin"]["code"]] + [x["code"] for x in s.get("stops", [])] + [s["destination"]["code"]]
    fl, n = s.get("flights", []), len(s.get("flights", []))
    if len(airports) != n + 1:
        airports = [None] * (n + 1)
    return [{"flight": f, "from": airports[i], "to": airports[i + 1],
             "dep": _t(s.get("departure")) if i == 0 else None,
             "arr": _t(s.get("arrival")) if i == n - 1 else None} for i, f in enumerate(fl)]


def _option(sol, currency, airlines):
    it = sol["itinerary"]
    codes = {c["code"] for c in it["carriers"]}
    if airlines and not codes <= set(airlines):
        return None
    total = sol.get("displayTotal", "")
    return {"airlines": [c["shortName"] for c in it["carriers"]],
            "price_total": float(re.sub(r"^[A-Z]{3}", "", total)) if total else None,
            "currency": total[:3] or currency,
            "stops": [len(s.get("stops", [])) for s in it["slices"]],
            "duration_min": [s.get("duration") for s in it["slices"]],
            "flights": [f for s in it["slices"] for f in _flights(s)],
            "seller": None}


def _post(body):
    for fresh_key in (False, True):
        _pace.wait()
        r = _cl().post(f"https://content-alkalimatrix-pa.googleapis.com/v1/search?key={_key(fresh_key)}&alt=json",
                       json=body, headers={"origin": "https://matrix.itasoftware.com",
                                           "referer": "https://matrix.itasoftware.com/"})
        if not (r.status_code in (400, 403) and "API key" in r.text[:2000]):
            break  # a stale saved key gets one retry with a fresh key
    blocked = r.status_code in (403, 429) or "RESOURCE_EXHAUSTED" in r.text[:2000]
    return r, blocked


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None, child_ages=None):
    """child_ages: accepted for the shared contract; Matrix only takes a child count."""
    out = {"ok": False, "source": "matrix", "error": None,
           "search_url": matrix_url(legs, adults, children, infants, cabin), "results": []}
    airlines = [a.upper() for a in airlines] if airlines else None
    route = (",".join(airlines) + "+") if airlines else None  # Matrix routing language: flights on these airlines only
    slices = [dict(origins=[l["from"]], destinations=[l["to"]], date=l["date"], dateModifier=dict(minus=0, plus=0),
                   isArrivalDate=False, filter=dict(warnings=dict(values=[])), selected=False,
                   **({"routeLanguage": route} if route else {})) for l in legs]
    inputs = dict(filter={}, page=dict(current=1, size=25), pax=_pax(adults, children, infants), slices=slices,
                  firstDayOfWeek="SUNDAY", internalUser=False, sliceIndex=0, sorts="default", cabin=CABINS[cabin],
                  maxLegsRelativeToMin=1, changeOfAirport=False, checkAvailability=True, currency=currency,
                  salesCity="KWI" if currency == "KWD" else legs[0]["from"])
    body = dict(summarizers=["solutionList"], inputs=inputs, summarizerSet="wholeTrip", name="specificDatesSlice")
    global _down
    t = time.time()
    try:
        with SLOTS:
            if _down:
                out["error"] = "ITA Matrix blocked us earlier in this run (skipped)"
                return out
            r, blocked = _post(body)
            out["secs"] = round(time.time() - t, 1)
        if blocked:
            _down = True
            out["error"] = f"ITA Matrix blocked (HTTP {r.status_code})"
            return out
        d = r.json()
        if "error" in d:
            out["error"] = "ITA Matrix error: " + str(d["error"].get("message", d["error"]))[:200]
            return out
        res = [o for o in (_option(s, currency, airlines) for s in d.get("solutionList", {}).get("solutions", [])) if o]
        out["results"] = sorted(res, key=lambda o: o["price_total"] if o["price_total"] is not None else 1e12)
        out["ok"] = True
    except Exception as e:
        out["error"] = f"ITA Matrix failed: {type(e).__name__}: " + re.sub(r"key=[^&\s)]+", "key=hidden", str(e))[:200]
        out["secs"] = round(time.time() - t, 1)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("legs", nargs="+", help="FROM-TO:YYYY-MM-DD")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--child-ages", default=None, help="comma-separated ages 2-11, e.g. 8,5 (sets --children)")
    ap.add_argument("--infants", type=int, default=0)
    ap.add_argument("--cabin", default="economy", choices=list(CABINS))
    ap.add_argument("--currency", default="KWD")
    ap.add_argument("--airlines", default=None, help="comma-separated IATA codes, e.g. QR,EY")
    a = ap.parse_args()
    legs = []
    for x in a.legs:
        route, date = x.split(":")
        fr, to = route.upper().split("-")
        legs.append({"from": fr, "to": to, "date": date})
    ages = [int(x) for x in a.child_ages.split(",")] if a.child_ages else None
    print(json.dumps(search(legs, a.adults, len(ages) if ages else a.children, a.infants, a.cabin, a.currency.upper(),
                            a.airlines.split(",") if a.airlines else None, ages), indent=1, ensure_ascii=False))
