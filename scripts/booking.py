"""Booking.com Flights prices over plain HTTP (no browser).

GETs Booking's own flight-search JSON (flights.booking.com/api/flights/). One way, round trip and
multi-city / open-jaw, 5-10 s per search. Prices are totals for all passengers in the asked currency.
Returns the 60 cheapest offers (limit=60, the API's most; 15 without it left out TK / KU on an open-jaw; no slower)
with full itineraries and bags per leg, plus each airline's cheapest price over all offers
(`airline_min`) and the cheapest nonstop (`nonstop_min`, airline in `nonstop_airline`). Booking.com sells through a
travel agency. Each flight carries its cabin, minutes and, for codeshares, the operating airline (`op`); "bags" = one
per leg {"checked": N, "unit": "kg"|"pc"} (0 = no checked bag; the smallest over travellers), null if not stated; the option's
airline names follow who flies the plane, e.g. "Qatar Airways (sold as Japan Airlines)".
Gentle: max 2 searches in flight, starts ~1.5 s apart, 25 s per request
(one unfiltered open-jaw took over 20 s once; usually 7-13 s). A block (403 / 429 / not JSON)
switches Booking off for the rest of the run.

CLI: python booking.py KWI-KIX:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR
     python booking.py KWI-LHR:2026-12-10 LHR-KWI:2026-12-20 --adults 2 --child-ages 8,5
"""
import argparse, json, threading, time, urllib.parse
from primp import Client
from pace import Pace

API = "https://flights.booking.com/api/flights/"
CABINS = {"economy": "ECONOMY", "premium": "PREMIUM_ECONOMY", "business": "BUSINESS", "first": "FIRST"}
CABIN_NAME = {v: k for k, v in CABINS.items()}
HDR = {"Accept": "application/json", "x-requested-from": "clientFetch", "Referer": "https://flights.booking.com/flights/"}
SLOTS = threading.BoundedSemaphore(2)
_pace = Pace(1.5)
_client = Client(impersonate="chrome_126", timeout=25)
_down = False  # set on the first block


def _money(p):
    return round((p or {}).get("units", 0) + (p or {}).get("nanos", 0) / 1e9, 2) if p else None


def _params(legs, adults, children, infants, cabin, currency, airlines, child_ages=None):
    kids = [str(a) for a in child_ages] if child_ages else ["8"] * children  # real ages when known
    ages = ",".join(kids + ["1"] * infants)  # Booking takes child ages; under 2 = infant
    q = {"adults": str(adults), "cabinClass": CABINS[cabin], "children": ages, "sort": "CHEAPEST", "limit": "60",
         "travelPurpose": "leisure", "currency": currency, "enableVI": "1", "locale": "en-gb", "salesCountry": "kw"}
    ap = lambda c: c + ".AIRPORT"
    if len(legs) == 1:
        q.update(type="ONEWAY", depart=legs[0]["date"])
    elif len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]:
        q.update(type="ROUNDTRIP", depart=legs[0]["date"], **{"return": legs[1]["date"]})
    else:
        q.update(type="MULTISTOP", multiStopDates="|".join(l["date"] for l in legs))
    q["from"] = "|".join(ap(l["from"]) for l in legs) if q["type"] == "MULTISTOP" else ap(legs[0]["from"])
    q["to"] = "|".join(ap(l["to"]) for l in legs) if q["type"] == "MULTISTOP" else ap(legs[0]["to"])
    if airlines:
        q["airlines"] = ",".join(airlines)
    return q


def results_url(legs, q):
    """The same search on the normal flights.booking.com page."""
    path = "multicity" if q["type"] == "MULTISTOP" else "%s.AIRPORT-%s.AIRPORT" % (legs[0]["from"], legs[0]["to"])
    web = {k: v for k, v in q.items() if k not in ("enableVI", "salesCountry", "locale", "limit")}
    return "https://flights.booking.com/flights/%s/?%s" % (path, urllib.parse.urlencode(web, safe="|,"))


def _bag(seg):  # checked allowance of one trip leg: the smallest over travellers; [] = none; no field = not stated
    if "travellerCheckedLuggage" not in seg:
        return None
    got = []
    for x in seg["travellerCheckedLuggage"] or []:
        a = x.get("luggageAllowance") or {}
        got.append({"checked": a["maxTotalWeight"], "unit": "kg"} if a.get("maxTotalWeight")  # WEIGHT_BASED 30 kg
                   else {"checked": a.get("maxPiece") or 0, "unit": "pc" if a.get("maxPiece") else None})
    return min(got, key=lambda b: b["checked"]) if got else {"checked": 0, "unit": None}


def _option(o, currency):
    segs = o.get("segments") or []
    fl, names = [], {}  # names: who flies -> names it is sold under, when not its own
    for s in segs:
        for l in s.get("legs") or []:
            fi = l.get("flightInfo") or {}
            ci = fi.get("carrierInfo") or {}
            code = ci.get("marketingCarrier") or ""
            op = ci.get("operatingCarrier") or code  # codeshare: JL7996 flown by QR
            name = {c.get("code"): c.get("name") for c in l.get("carriersData") or []}
            f = {"flight": "%s%s" % (code, fi.get("flightNumber") or ""),
                 "from": (l.get("departureAirport") or {}).get("code"), "to": (l.get("arrivalAirport") or {}).get("code"),
                 "dep": (l.get("departureTime") or "")[:16].replace("T", " ") or None,
                 "arr": (l.get("arrivalTime") or "")[:16].replace("T", " ") or None,
                 "cabin": CABIN_NAME.get(l.get("cabinClass")), "min": round(l["totalTime"] / 60) if l.get("totalTime") else None}
            if op != code:
                f["op"] = op
            fl.append(f)
            sold = names.setdefault(name.get(op) or ci.get("operatingCarrierDisclosureText") or op, [])
            if op != code and (name.get(code) or code) not in sold:
                sold.append(name.get(code) or code)
    bags = [_bag(s) for s in segs]
    total = (o.get("priceBreakdown") or {}).get("total") or {}
    airlines = [n + (" (sold as %s)" % " / ".join(v) if v else "") for n, v in names.items() if n]
    return {"airlines": airlines, "price_total": _money(total),
            "currency": total.get("currencyCode") or currency,
            "stops": [len(s.get("legs") or []) - 1 for s in segs],
            "duration_min": [round(s["totalTime"] / 60) if s.get("totalTime") else None for s in segs],
            "flights": fl, "bags": bags if any(bags) else None, "seller": "Booking.com (travel agency)"}


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None, child_ages=None):
    global _down
    airlines = [a.upper() for a in airlines] if airlines else None
    q = _params(legs, adults, children, infants, cabin, currency, airlines, child_ages)
    out = {"ok": False, "source": "booking", "error": None, "search_url": results_url(legs, q), "results": []}
    if _down:
        out["error"] = "Booking.com blocked us earlier in this run (skipped)"
        return out
    t = time.time()
    try:
        with SLOTS:
            _pace.wait()
            t = time.time()
            r = _client.get(API, params=q, headers=HDR)
            out["secs"] = round(time.time() - t, 1)
        if r.status_code in (403, 429) or not r.text.lstrip().startswith("{"):
            _down = True
            out["error"] = "Booking.com blocked (HTTP %s)" % r.status_code
            return out
        d = r.json()
        if r.status_code != 200:
            out["error"] = "Booking.com HTTP %s" % r.status_code
            return out
        rows = [_option(o, currency) for o in d.get("flightOffers") or []]
        if airlines:  # keep only itineraries sold or flown by the asked airlines
            rows = [o for o in rows if all({f["flight"][:2], f.get("op")} & set(airlines) for f in o["flights"])]
        out["results"] = sorted((o for o in rows if o["price_total"]), key=lambda o: o["price_total"])
        agg = d.get("aggregation") or {}
        out["airline_min"] = [{"code": a.get("iataCode"), "name": a.get("name"), "price_total": _money(a.get("minPrice"))}
                              for a in agg.get("airlines") or []]
        ns = next((s for s in agg.get("stops") or [] if s.get("numberOfStops") == 0), {})
        out["nonstop_min"] = _money(ns.get("minPrice"))
        out["nonstop_airline"] = (ns.get("cheapestAirline") or {}).get("name")
        out["ok"] = bool(out["results"])
        if not out["ok"]:
            out["error"] = "Booking.com found no flights"
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error="Booking.com failed: " + why, secs=round(time.time() - t, 1))
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
