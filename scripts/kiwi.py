"""Kiwi.com prices over its free public MCP server (https://mcp.kiwi.com, tool `search-flight`). No key, no login.

One way and round trip (no multi-city). Native KWD, business, whole-trip total for all passengers,
whole KWD (rounded). 10-16 s per call, returns at most 15 itineraries sorted by price, both legs, with
per-flight cabin and minutes.
Kiwi mixes airlines on separate tickets ("self-transfer"); each option gets `tickets` (1 = one ticket,
2 = two one-ways, 3+ = self-transfer with connections you make yourself) and its own Kiwi booking link.
"IST" etc. are read as the city, so answers may use another airport of that city (SAW).
Gentle: max 2 in flight, 1.5 s between request starts, 20 s per request.

CLI: python kiwi.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business [--airlines QR] [--no-self-transfer]
"""
import json, re, sys, time
from mcp_http import MCP, parse_cli, trip_type

CABINS = {"economy": "M", "premium": "W", "business": "C", "first": "F"}
CABIN_NAME = {"Economy": "economy", "Premium Economy": "premium", "Business": "business", "First": "first"}
_mcp = MCP("https://mcp.kiwi.com")


def dmy(iso):
    y, m, d = iso.split("-")
    return "%s/%s/%s" % (d, m, y)


def args_for(legs, adults, children, infants, cabin, currency, airlines, self_transfer=True):
    a = {"flyFrom": legs[0]["from"], "flyTo": legs[0]["to"], "departureDate": dmy(legs[0]["date"]),
         "adults": adults, "children": children, "infants": infants, "cabinClass": CABINS[cabin],
         "currency": currency, "sort": "price", "allow_self_transfer": self_transfer}
    if len(legs) == 2:
        a["returnDate"] = dmy(legs[1]["date"])
    if airlines:
        a["select_airlines"] = ",".join(airlines)
    return a


def search_url(legs, adults, children, infants, cabin):
    ret = legs[1]["date"] if len(legs) == 2 else "no-return"
    return ("https://www.kiwi.com/en/search/results/%s/%s/%s/%s?adults=%d&children=%d&infants=%d&cabinClass=%s-false&sortBy=price"
            % (legs[0]["from"].lower(), legs[0]["to"].lower(), legs[0]["date"], ret, adults, children, infants,
               {"M": "ECONOMY", "W": "PREMIUM_ECONOMY", "C": "BUSINESS", "F": "FIRST_CLASS"}[CABINS[cabin]]))


def option(it, currency):
    """One itinerary. Currency: the reply's own label ("4476 KWD"), else the asked one."""
    m = re.search(r"\b([A-Z]{3})\b", it.get("priceFormatted") or "")
    currency = m.group(1) if m else currency.upper()
    dirs = [d for d in (it.get("outbound"), it.get("inbound")) if d]
    fl, names = [], []
    for d in dirs:
        for s in d.get("segments") or []:
            fl.append({"flight": s.get("flightNumber"), "from": s.get("from"), "to": s.get("to"),
                       "dep": (s.get("departureTime") or "")[:16].replace("T", " ") or None,
                       "arr": (s.get("arrivalTime") or "")[:16].replace("T", " ") or None,
                       "cabin": CABIN_NAME.get(s.get("cabinClass")),
                       "min": round(s["durationSeconds"] / 60) if s.get("durationSeconds") else None})
            names.append(s.get("carrierName"))
    tickets = len({p.split("_")[0] for p in (it.get("id") or "").split("|") if p})
    return {"airlines": list(dict.fromkeys(n for n in names if n)), "price_total": it.get("price"),
            "currency": currency, "stops": [d.get("stops") for d in dirs],
            "duration_min": [round(d["durationSeconds"] / 60) if d.get("durationSeconds") else None for d in dirs],
            "flights": fl, "seller": "Kiwi.com (travel agency)", "tickets": tickets or None,
            "out": dirs[0]["departureTime"][:10], "ret": dirs[1]["departureTime"][:10] if len(dirs) > 1 else None,
            "booking_url": it.get("bookingUrl")}


def raw(args):
    """One tools/call. Returns (itineraries, error, secs)."""
    t = time.time()
    try:
        txt, sc, err = _mcp.call("search-flight", args)
        d = sc or json.loads(txt)
        return d.get("itineraries") or [], d.get("error") or (txt[:200] if err else None), round(time.time() - t, 1)
    except Exception as e:
        why = "timed out" if "timed out" in str(e).lower() else "%s: %s" % (type(e).__name__, str(e)[:150])
        return [], "Kiwi failed: " + why, round(time.time() - t, 1)


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None, self_transfer=True):
    out = {"ok": False, "source": "kiwi", "error": None, "results": [],
           "search_url": search_url(legs, adults, children, infants, cabin)}
    if trip_type(legs) == "multi":
        out["error"] = "Kiwi MCP does one way and round trip only"
        return out
    its, err, out["secs"] = raw(args_for(legs, adults, children, infants, cabin, currency, airlines, self_transfer))
    out["results"] = sorted((option(i, currency) for i in its if i.get("price")), key=lambda o: o["price_total"])
    out["ok"] = bool(out["results"])
    out["error"] = err if err else (None if out["ok"] else "Kiwi found no flights")
    return out


if __name__ == "__main__":
    a = parse_cli(extra=[("--no-self-transfer", {"action": "store_true"})])
    print("kiwi: searching...", file=sys.stderr)
    r = search(a.legs, a.adults, a.children, a.infants, a.cabin, a.currency, a.airlines, not a.no_self_transfer)
    print("kiwi: %s in %ss, %d options" % ("ok" if r["ok"] else r["error"], r.get("secs"), len(r["results"])), file=sys.stderr)
    print(json.dumps(r, indent=1, ensure_ascii=False))
