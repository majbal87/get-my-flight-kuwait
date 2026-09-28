"""Flyin (www.flyin.com, Cleartrip's Gulf brand) flight prices over plain HTTP (no browser).

One GET: /flight/search/v2/results?data=<encrypted query>. The query is the results-page URL query,
encrypted the way the site's JS does it (CryptoJS AES passphrase + HMAC-SHA256, key in the JS bundle).
AES is done with the system `openssl` command (LibreSSL on macOS), so no extra Python package.
Flyin sells in SAR (Saudi point of sale); KWD here = SAR x the rate Flyin ships in the same reply
(`jsons.currencyList` SAR->KWD), so KWD totals are a conversion, about +/-1%. No rate for the asked currency
in the reply: ok False (never SAR passed off as the asked currency).
One way and round trip. Round trip pairs an outbound card with a return card: special round-trip
fare (SPLRT, both halves) or two one-way fares added (the cheapest return leaving from the airport the
outbound lands at); two one-way fares on different airlines are two tickets (`tickets: 2`, seller_note
"2 one-way fares"). Flyin reads airports as cities (LHR also gives STN/LGW): options on the asked airports are
kept first, before the cut to 40. Multi-city is a different POST (not built).
Stops per leg = segments - 1 (ET672 ADD-ICN-NRT is one segment for Flyin; its "stops" says 2).
Pacing per host (Flyin and Cleartrip each: 2 in flight, starts 1.5 s apart). 0.9-1.5 s RT business, ~3 s OW,
~10 s for a family London search.

CLI: python flyin.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business
"""
import hashlib, hmac, json, subprocess, sys, threading, time, urllib.parse
from primp import Client

BASE = "https://www.flyin.com"
KEY = "GtoLdmQ4OHl+F+O8QjqJVqCQ0T1GL/9yRMAhAM/H6PA="  # in the JS chunk that holds "srpFlightResultsApi"
CABINS = {"economy": "Economy", "premium": "Premium Economy", "business": "Business", "first": "First"}
CABIN_NAME = {"Economy": "economy", "Premium Economy": "premium", "Business": "business", "First": "first"}
_lock, _next, _slots = threading.Lock(), {}, {}  # per host: Flyin and Cleartrip each get their own queue and pace
_client = Client(impersonate="chrome_126", timeout=20)


def _wait(host, gap=1.5):
    """Request starts >= gap s apart per host; returns that host's 2-slot semaphore."""
    with _lock:
        start = max(time.time(), _next.get(host, 0.0))
        _next[host] = start + gap
        slots = _slots.setdefault(host, threading.BoundedSemaphore(2))
    time.sleep(max(0.0, start - time.time()))
    return slots


def _enc(q):
    ct = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-md", "md5", "-salt", "-pass", "pass:" + KEY,
                         "-base64", "-A"], input=q.encode(), capture_output=True, check=True).stdout.decode().strip()
    mac = hmac.new(KEY.encode(), ct.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.quote(ct, safe="") + ":" + mac


def _dmy(d):  # 2026-12-19 -> 19/12/2026
    y, m, dd = d.split("-")
    return "%s/%s/%s" % (dd, m, y)


def _sector(d, key):
    s = d["sectors"][key]
    fl = []
    for g in s["flights"]["segments"]:
        a, _, n = g["flightNumber"].partition("-")
        dep, arr, t = g["departure"], g["arrival"], g.get("durationTime") or {}
        f = {"flight": a + n, "from": dep["airportCode"], "to": arr["airportCode"],
             "dep": "%s %s" % ("-".join(reversed(dep["date"].split("/"))), dep["time"]),
             "arr": "%s %s" % ("-".join(reversed(arr["date"].split("/"))), arr["time"]),
             "cabin": CABIN_NAME.get(g.get("flightClass")),  # empty on business searches, "Economy" on economy ones
             "min": (t.get("hh", 0) * 60 + t.get("mm", 0)) or None}
        if len(g.get("oa") or "") == 2 and g["oa"] != a:  # codeshare: operating airline
            f["op"] = g["oa"]
        fl.append(f)
    # stops = segments - 1 (Flyin counts ET672's technical stop in ICN); minutes = flying + layovers
    # (totalDuration is flying time only)
    mins = (s.get("totalSectorDuration") or 0) + (s.get("totalSectorLayoverDuration") or 0)
    return fl, len(fl) - 1, mins or None


def _ends(d, card):  # (first departure airport, last arrival airport) of a one-way card
    segs = [g for k in card["sectorKeys"] for g in d["sectors"][k]["flights"]["segments"]]
    return segs[0]["departure"]["airportCode"], segs[-1]["arrival"]["airportCode"]


def _splrt(card, other_fn):
    v = ((card["priceBreakup"].get("SPLRT") or {}).get(other_fn)) or {}
    v = next((x for x in v.values() if isinstance(x, dict) and "pr" in x), None) if isinstance(v, dict) else None
    return v["pr"] if v else None


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None,
           base_url=BASE, source="flyin"):
    """base_url https://www.cleartrip.ae (AED) works the same way: see cleartrip.py."""
    rt = len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]
    currency = (currency or "KWD").upper()
    q = "adults=%d&childs=%d&infants=%d&class=%s&depart_date=%s&from=%s&to=%s&intl=y" % (
        adults, children, infants, CABINS[cabin], _dmy(legs[0]["date"]), legs[0]["from"], legs[0]["to"])
    if rt:
        q += "&return_date=" + _dmy(legs[1]["date"])
    name = source.capitalize()
    out = {"ok": False, "source": source, "error": None, "search_url": base_url + "/en/flights/results?" + q, "results": []}
    if len(legs) > 1 and not rt:
        out["error"] = name + " script does one way and round trip only"
        return out
    hdr = {"Accept": "application/json", "Content-Type": "application/json", "app-agent": "DESKTOP",
           "X_CT_SOURCETYPE": "B2C", "x-multi-airline": "true", "Preferred-Language": "en",
           "x-time-zone": "Asia/Kuwait", "Referer": out["search_url"]}
    t = time.time()
    try:
        with _wait(base_url):
            print("%s: searching" % source, file=sys.stderr)
            r = _client.get(base_url + "/flight/search/v2/results?data=" + _enc(q), headers=hdr)
        out["secs"] = round(time.time() - t, 1)
        if r.status_code != 200 or not r.text.startswith("{"):
            out["error"] = "%s blocked or failed (HTTP %s)" % (name, r.status_code)
            return out
        d = r.json()
        st = d["jsons"]["searchType"]
        base = st.get("sellCurr") or "SAR"
        rate = 1.0 if currency == base else next((x["rate"] for x in d["jsons"].get("currencyList") or []
                                                   if x["from"] == base and x["to"] == currency), None)
        if rate is None:  # no conversion for this currency: refuse rather than show SAR as if exact
            out["error"] = "%s has no %s->%s rate (sells in %s only)" % (name, base, currency, base)
            return out
        names = d["jsons"].get("airline_names") or {}
        cards = d.get("cards") or []
        combos = []  # (price in base currency, [cards], tickets)
        if rt and len(cards) == 2:
            back = {c["splRtFn"]: c for c in cards[1]}
            cheapest_back = {}  # per departure airport: London returns leave from LHR, LGW, STN...
            for b in sorted(cards[1], key=lambda c: c["priceBreakup"]["pr"]):
                cheapest_back.setdefault(_ends(d, b)[0], b)
            for c in cards[0]:
                for fn in (c["priceBreakup"].get("SPLRT") or {}):
                    b = back.get(fn)
                    p1, p2 = _splrt(c, fn), b and _splrt(b, c["splRtFn"])
                    if p1 and p2:
                        combos.append((p1 + p2, [c, b], 1))  # special round-trip fare: one booking
                b = cheapest_back.get(_ends(d, c)[1])  # return from the airport this outbound lands at
                if b:  # two one-way fares: two tickets when the airlines differ
                    combos.append((c["priceBreakup"]["pr"] + b["priceBreakup"]["pr"], [c, b],
                                   1 if set(c.get("airlineCodes") or []) == set(b.get("airlineCodes") or []) else 2))
        elif cards:
            combos = [(c["priceBreakup"]["pr"], [c], 1) for c in cards[0]]
        best = {}
        for price, cs, tickets in combos:
            fl, stops, dur, ends = [], [], [], []
            for c in cs:
                for k in c["sectorKeys"]:
                    f, s, m = _sector(d, k)
                    fl += f; stops.append(s); dur.append(m); ends.append((f[0]["from"], f[-1]["to"]))
            key = tuple((f["flight"], f["dep"]) for f in fl)
            if key in best and best[key]["price_base"] <= price:
                continue
            codes = list(dict.fromkeys(f["flight"][:2] for f in fl))
            best[key] = {"airlines": [names.get(a, a) for a in codes], "codes": codes,
                         "price_total": round(price * rate, 2), "currency": currency, "price_base": price,
                         "base_currency": base, "stops": stops, "duration_min": dur, "flights": fl, "_ends": ends,
                         "seller": "%s (sold in %s)" % (name, base), "tickets": tickets}
            if tickets == 2:  # out and back on two one-way fares: two bookings (make_page: a note, not a flag)
                best[key]["seller_note"] = "2 one-way fares"
            if rate != 1.0:
                best[key]["converted_from"] = base
        rows = sorted(best.values(), key=lambda o: o["price_total"])
        if airlines:
            want = {a.upper() for a in airlines}
            rows = [o for o in rows if set(o["codes"]) <= want]
        # Flyin reads an airport as its city (HND gives NRT, LHR gives STN): keep the asked airports before the cut
        # to 40 (all rows if none match, e.g. a city code was asked)
        ask = [(l["from"], l["to"]) for l in legs]
        rows = [o for o in rows if o["_ends"] == ask] or rows
        for o in rows:
            del o["_ends"]
        out["results"] = rows[:40]
        out["ok"] = bool(rows)
        if not rows:
            out["error"] = name + " found no flights"
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error=name + " failed: " + why, secs=round(time.time() - t, 1))
    return out


if __name__ == "__main__":
    from almosafer import cli
    cli(search)
