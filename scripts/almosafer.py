"""Almosafer (kw.almosafer.com) flight prices over plain HTTP (no browser).

One way / multi-city: GET /api/v3/flights/flight/search?query=<path> starts the search and names the supplier
channels (Amadeus AMD, Travelfusion TFN, Jazeera / flydubai direct ...), then POST .../flight/async-search-result
(body = the previous reply) returns their itineraries. Same prices as the website's own one-way list.
Round trip: that old call also returns round-trip fares the website does NOT sell (Japan business: EY 4,308 where
the site sells Etihad from 5,784: its v2 fare search has fewer fares). The website uses .../flight/v2/search +
v2/async-search-result: OUTBOUND flights, each with its one-way price and its cheapest round-trip fare
(cheapestRoundtripTotal when "roundtrip" is true, else cheapestAboveCombinedRoundtripTotal); picking one calls
.../flight/inbound-result, which lists the returns: at a round-trip fare, or at outbound one-way + return one-way
(two one-way fares: Jazeera J9121 12.00 + J9124 32.50 = 44.50, below its 45.01 round-trip fare).
So a round trip runs the old search and the v2 search + one inbound-result call side by side (2 in flight), and
returns only what the site sells, at the site's price:
  - each old round trip whose outbound is a v2 outbound and whose price is exactly that outbound's round-trip fare
    (several returns can share it: the site lists them all); if outbound one-way + that return's one-way is lower,
    that lower price, as two one-way fares;
  - per outbound, the cheapest return on the same airline(s) as two one-way fares, among returns the old reply
    has no round-trip fare for with that outbound (else the site may sell that pair at a round-trip fare we can't see).
  Two one-way fares carry tickets 2 and seller_note "2 one-way fares" (search.py shows it on the seller).
  Dearer round-trip returns of an outbound are not returned (the site sells some; only a per-outbound
  inbound-result call would say which).
  - a channel v2 never answered (Jazeera / flydubai "ONE" channels answer at once or hang on v2: 20 s seen, the
    site's round-trip page then shows none): the old call's round trips from it, at their own (airline round-trip)
    fare, seller_note "may be missing from Almosafer's round-trip list; ...". Never Amadeus rows.
Polling: until no channel is pending; while Amadeus (AMD, most airlines) is pending, up to AMD_WAIT (10) s from the
start; once it answered, other channels get POLL_BUDGET (5) s from the 1st poll (v2: V2_GRACE 2.5 s), and Travelfusion
(TFN: TK, OV, EK) TFN_GRACE (2) s from Amadeus' answer (it often comes 1-2.6 s after Amadeus; sometimes 10 s: not waited).
Polls 0.5 s apart (1 s from the 4th). Amadeus still pending at the end: error / note say "no answer in time",
never "no flights".
Pacing: search starts >= 1.5 s apart (a round trip's old + v2 pair counts as one start); a slot (max 2 requests in
flight) is held only during each request.
Per option: stops per leg = segments - 1 (a technical stop inside one flight number is not a connection); per
flight cabin (from the fare), minutes, "op" for codeshares; bags = one entry per leg {"checked": N, "unit": "kg"|"pc"}
(the smallest allowance on that leg; checked 0 = cabin bag only; null = not stated).
Almosafer reads an airport as its city (HND also gives NRT): search.py drops options for other airports.
Header `token` is the public apiToken printed in every Almosafer page (see references/sources/almosafer.md).

CLI: python almosafer.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR
"""
import argparse, json, sys, threading, time
from primp import Client

BASE = "https://kw.almosafer.com"
API = BASE + "/api/v3/flights/flight/"
TOKEN = "su4uj27$27ks384!3slKy"  # "apiToken" in the page HTML; changes rarely
CABINS = {"economy": "Economy", "premium": "Premium Economy", "business": "Business", "first": "First"}
CABIN_TEXT = {v: k for k, v in CABINS.items()}  # per-flight cabin from the fare: cabinText "Business" or cabinCode "C"
CABIN_CODES = {"M": "economy", "Y": "economy", "W": "premium", "C": "business", "J": "business", "F": "first"}
NAMES = {"QR": "Qatar Airways", "EK": "Emirates", "EY": "Etihad Airways", "KU": "Kuwait Airways", "J9": "Jazeera Airways",
         "TK": "Turkish Airlines", "RJ": "Royal Jordanian", "GF": "Gulf Air", "SV": "Saudia", "MS": "EgyptAir",
         "PC": "Pegasus", "FZ": "flydubai", "G9": "Air Arabia", "XY": "flynas", "WY": "Oman Air", "ME": "MEA",
         "SM": "Air Cairo", "ET": "Ethiopian Airlines", "JL": "Japan Airlines", "NH": "ANA", "CX": "Cathay Pacific",
         "SQ": "Singapore Airlines", "TG": "Thai Airways", "BA": "British Airways", "LH": "Lufthansa", "AF": "Air France",
         "KL": "KLM", "AI": "Air India", "6E": "IndiGo", "UL": "SriLankan", "MH": "Malaysia Airlines", "KE": "Korean Air",
         "OZ": "Asiana", "CA": "Air China", "MU": "China Eastern", "CZ": "China Southern", "PK": "PIA", "OV": "SalamAir"}
SLOTS = threading.BoundedSemaphore(2)
FIRST_POLL_WAIT = 0.5  # seconds before the 1st poll (0.5 s after each reply for 3 polls, then 1 s)
AMD_WAIT = 10.0  # seconds from the search start that polling may wait for Amadeus (search.py LIMIT is 25 s)
POLL_BUDGET = 5.0  # once Amadeus answered: polling s (from the 1st poll) for other channels
TFN_GRACE = 2.0  # and s from Amadeus' answer for Travelfusion (TK KWI-ATH +1.3 s, OV KWI-MCT +2.6 s; TK BKK +10 s: lost)
V2_GRACE = 2.5  # v2 (round trip): the same for its airline-direct "ONE" channels: they answer at once or hang
                # (20 s seen); the old call's round trips cover a channel v2 left pending
_lock, _next = threading.Lock(), [0.0]
_client = Client(impersonate="chrome_126", timeout=20)


def _wait(gap=1.5):
    with _lock:
        start = max(time.time(), _next[0])
        _next[0] = start + gap
    time.sleep(max(0.0, start - time.time()))


def _is_rt(legs):
    return len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]


def _query(legs, adults, children, infants, cabin):
    parts = ["%s-%s" % (legs[0]["from"], legs[0]["to"]), legs[0]["date"], legs[1]["date"]] if _is_rt(legs) \
        else [x for l in legs for x in ("%s-%s" % (l["from"], l["to"]), l["date"])]  # one way / multi-city pairs
    parts += [CABINS[cabin], "%dAdult" % adults]
    parts += ["%dChild" % children] if children else []
    parts += ["%dInfant" % infants] if infants else []
    return "/".join(parts)


def _code(fc):  # "FZ-064" -> "FZ64"
    a, _, n = fc.partition("-")
    return a + (str(int(n)) if n.isdigit() else n)


def _mins(dur):  # {"value": 1585} or {"value": null, "text": "26h 25m"} -> minutes
    dur = dur or {}
    if dur.get("value") is not None:
        return dur["value"]
    h, _, m = (dur.get("text") or "").replace("m", "").partition("h ")
    return int(h) * 60 + int(m) if h.strip().isdigit() and m.strip().isdigit() else None


def _flight(s, fare):  # one segment; fare = this itinerary's own fare line for it (cabin)
    f = {"flight": _code(s["flightCode"]), "from": s["departureAirport"]["code"], "to": s["arrivalAirport"]["code"],
         "dep": s["departure"][:16].replace("T", " "), "arr": s["arrival"][:16].replace("T", " "),
         "cabin": CABIN_CODES.get(fare.get("cabinCode")) or CABIN_TEXT.get(fare.get("cabinText")),
         "min": (s.get("duration") or {}).get("value")}
    op = s.get("operatingCarrierId") or ""
    if len(op) == 2 and op != f["flight"][:2]:  # codeshare: QR6843 flown by JL
        f["op"] = op
    return f


def _bag(fares):  # checked allowance of one leg: the smallest over its segments; 0 = cabin bag only; None = not stated
    got = []
    for x in fares:
        if "freeBaggage" not in x:
            return None
        c = (x.get("freeBaggage") or {}).get("checkIn") or {}
        n, u = c.get("allowance"), (c.get("unit") or c.get("text") or "").upper()  # "K"/"KG"; unit null + "2 PIECE"
        got.append({"checked": 0, "unit": None} if not n else
                   {"checked": n, "unit": "pc" if "P" in u else "kg" if "K" in u else None})
    return min(got, key=lambda b: b["checked"]) if got else None


def _rows(res, currency):
    """Every itinerary of a reply as an option (id, raw totals and per-leg flights kept under _ keys)."""
    rows, seen = [], set()
    for r in res:
        d, ch = r.get("data") or {}, ((r.get("info") or {}).get("code"), (r.get("info") or {}).get("chnr"))
        legs = {l["id"]: l for l in d.get("leg") or []}
        segs = {s["id"]: s for s in d.get("segment") or []}
        for it in d.get("itinerary") or []:
            if it.get("id") in seen:  # v2 polls repeat earlier channels
                continue
            seen.add(it.get("id"))
            p = (it.get("price") or {}).get("totals") or {}
            ls = [legs[i] for i in it.get("legId") or [] if i in legs]
            fares = [x.get("segment") or [] for x in (it.get("fare") or {}).get("legDetails") or []]  # same order as legs
            per_leg, bags = [], []
            for i, l in enumerate(ls):
                ss = [segs[x] for x in l.get("segmentId") or [] if x in segs]
                fs = fares[i] if i < len(fares) and len(fares[i]) == len(ss) else [{}] * len(ss)
                per_leg.append([_flight(s, fs[j]) for j, s in enumerate(ss)])
                bags.append(_bag(fs))
            fl = [f for leg in per_leg for f in leg]
            if not p.get("total") or not fl or not all(per_leg):
                continue
            codes = list(dict.fromkeys(f["flight"][:2] for f in fl))
            rows.append({"airlines": [NAMES.get(c, c) for c in codes], "codes": codes, "price_total": round(p["total"], 2),
                         "currency": p.get("currency") or currency,
                         "stops": [len(leg) - 1 for leg in per_leg],  # a technical stop (ET672 ADD-ICN-NRT) is no change
                         "duration_min": [_mins(l.get("duration")) for l in ls], "flights": fl, "bags": bags,
                         "seller": "Almosafer", "_id": it.get("id") or "", "_t": p, "_legs": per_leg, "_ch": ch})
    return rows


def _key(flights):
    return tuple((f["flight"], f["dep"]) for f in flights)


def _cheapest(rows):  # one option per flight set (several channels sell the same flights): the cheapest
    best = {}
    for o in rows:
        k = _key(o["flights"])
        if k not in best or o["price_total"] < best[k]["price_total"]:
            best[k] = o
    return sorted(best.values(), key=lambda o: o["price_total"])


def _roundtrips(old, outs, ins, pending=()):
    """What the website sells for a round trip, at its price. old: the old call's round-trip rows; outs: v2
    outbound rows; ins: inbound-result rows (the returns). The site prices outbound o + return i as
    one-way(o) + one-way(i), except o's own round-trip fare pair: the lower of that fare and the two one-ways.
    pending: (code, chnr) of v2 channels that never answered (Jazeera / flydubai "ONE" often hang on v2 only):
    the old call's round trips from those channels are kept at their own fare (airline-direct fares; the unsold
    combinations came from Amadeus), with a note that the site's round-trip page may not list them."""
    by_out = {}
    for r in old:
        by_out.setdefault(_key(r["_legs"][0]), []).append(r)
    ow_back = {}
    for r in ins:
        if not r["_t"].get("roundtrip") and len(r["_legs"]) == 1:  # a one-way return fare (the same for every outbound)
            k = _key(r["flights"])
            if k not in ow_back or r["price_total"] < ow_back[k]["price_total"]:
                ow_back[k] = r

    def two(o, b):  # outbound one-way + return one-way
        return {"airlines": o["airlines"], "codes": o["codes"], "price_total": round(o["price_total"] + b["price_total"], 2),
                "currency": o["currency"], "stops": o["stops"] + b["stops"],
                "duration_min": o["duration_min"] + b["duration_min"], "flights": o["flights"] + b["flights"],
                "bags": o["bags"] + b["bags"], "seller": "Almosafer", "tickets": 2, "seller_note": "2 one-way fares"}

    keep = []
    for o in outs:
        if len(o["_legs"]) != 1:
            continue
        t = o["_t"]  # its round-trip fare: cheapestRoundtripTotal when "roundtrip", else the one above the 2 one-ways
        fare = t.get("cheapestRoundtripTotal") if t.get("roundtrip") else t.get("cheapestAboveCombinedRoundtripTotal")
        for r in by_out.get(_key(o["flights"]), []) if fare else []:  # the old reply's round trips at exactly that fare
            if abs(r["price_total"] - fare) < 0.005:
                b = ow_back.get(_key(r["_legs"][1]))
                keep.append(two(o, b) if b and o["price_total"] + b["price_total"] < fare - 0.005 else r)
        rt_backs = {_key(r["_legs"][1]) for r in by_out.get(_key(o["flights"]), [])}
        back = [r for k, r in ow_back.items() if set(r["codes"]) == set(o["codes"]) and k not in rt_backs]
        if back:  # + the cheapest return one-way on the same airline(s), when no round-trip fare is known for the pair
            keep.append(two(o, min(back, key=lambda r: r["price_total"])))  # (the site may sell that pair cheaper)
    for r in old:  # channels v2 never answered (not Amadeus): the old call's own round trips from them
        if r["_ch"] in pending and r["_ch"][0] != "AMD":
            keep.append(dict(r, seller_note="may be missing from Almosafer's round-trip list; its one-way pages sell "
                                            "these flights"))
    return _cheapest(keep)


def _poll(api, q, hdr, t0, log, budget=POLL_BUDGET):
    """Start one search on `api` and poll it. Returns (first reply with the last `next`, all res, pending channels
    as (code, chnr), error). budget: polling s (from the 1st poll) for non-Amadeus channels once Amadeus answered."""
    with SLOTS:
        r = _client.get(api + "search", params={"query": q}, headers=hdr)
    if r.status_code != 200 or not r.text.startswith("{"):
        return {}, [], [], "Almosafer blocked or failed (HTTP %s)" % r.status_code
    first = body = r.json()
    res, wait, chans, n, t_poll, t_amd = [], ["?"], [], 0, time.time(), None
    while True:
        time.sleep(FIRST_POLL_WAIT if n < 3 else 1.0)
        n += 1
        with SLOTS:
            r = _client.post(api + "async-search-result", headers=hdr, content=json.dumps(body).encode())
        if r.status_code != 200:
            return first, res, chans, "Almosafer poll HTTP %s" % r.status_code
        d = r.json()
        res += d.get("res") or []
        first["next"] = d.get("next") or first.get("next")
        chans = [((c.get("info") or {}).get("code"), (c.get("info") or {}).get("chnr")) for c in (d.get("next") or {}).get("get") or []]
        wait = [c for c, _ in chans]
        print("almosafer%s: poll %d at %.1f s, still waiting for: %s" % (
            log, n, time.time() - t0, ",".join(c if c == "AMD" else "%s/%s" % (c, x) for c, x in chans) or "nothing"),
              file=sys.stderr)
        if not wait or time.time() - t0 > AMD_WAIT:
            break
        if "AMD" not in wait:  # Amadeus has answered: don't wait long for slow ones
            t_amd = t_amd or time.time()
            if time.time() > max(t_poll + budget if any(c != "TFN" for c in wait) else 0,
                                 t_amd + TFN_GRACE if "TFN" in wait else 0):
                break
        body = {"next": d["next"], "request": first.get("request")}
    return first, res, chans, None


def _v2(q, hdr, t0, currency):
    """The website's round-trip flow: v2 search + polls (outbounds), then one inbound-result call (the returns sold
    as one-way fares; the same list for every outbound). Returns (outbound rows, return rows, pending, error)."""
    try:
        first, res, wait, err = _poll(API + "v2/", q, hdr, t0, " v2", V2_GRACE)
    except Exception as e:
        return [], [], [], "Almosafer v2 failed: %s: %s" % (type(e).__name__, str(e)[:150])
    outs, ins = _rows(res, currency), []
    one_way = [o for o in outs if not o["_t"].get("roundtrip")]
    if one_way and not err:  # not needed when every outbound's cheapest is a round-trip fare
        try:
            with SLOTS:
                r = _client.post(API + "inbound-result", headers=hdr, content=json.dumps(
                    {"id": one_way[0]["_id"], "nid": (first.get("next") or {}).get("nid"),
                     "request": first.get("request")}).encode())
            ins = _rows(r.json().get("res") or [], currency) if r.status_code == 200 else []
        except Exception as e:  # without it: round-trip fares only, no two-one-way prices
            print("almosafer v2: inbound-result failed: %s" % str(e)[:100], file=sys.stderr)
    return outs, ins, wait, err


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None):
    q = _query(legs, adults, children, infants, cabin)
    out = {"ok": False, "source": "almosafer", "error": None, "search_url": "%s/en/flights/%s" % (BASE, q), "results": []}
    hdr = {"Accept": "application/json, text/javascript", "Content-Type": "application/json; charset=UTF-8",
           "x-locale": "en", "x-currency": currency, "token": TOKEN, "Origin": BASE, "Referer": out["search_url"]}
    t = time.time()
    try:
        _wait()  # search starts >= 1.5 s apart; a slot is held only while a request is in flight
        if not _is_rt(legs):
            _, res, chans, err = _poll(API, q, hdr, t, "")
            rows, wait = _cheapest(_rows(res, currency)), [c for c, _ in chans]
        else:  # the old call (round-trip itineraries) and v2 (what the site sells) side by side
            got = {}
            th = threading.Thread(target=lambda: got.update(v2=_v2(q, hdr, t, currency)))
            th.start()
            _, res, chans, err = _poll(API, q, hdr, t, "")
            th.join()
            outs, ins, chans2, err2 = got.get("v2") or ([], [], [], "Almosafer v2 search failed")
            rows = _roundtrips(_rows(res, currency), outs, ins, set(chans2))
            err, wait = err or err2, list(dict.fromkeys(c for c, _ in chans + chans2))
        out["secs"] = round(time.time() - t, 1)
        for o in rows:
            for k in [k for k in o if k.startswith("_")]:
                del o[k]
        if airlines:
            want = {a.upper() for a in airlines}
            rows = [o for o in rows if set(o["codes"]) <= want]
        out["results"] = rows
        out["ok"] = bool(rows)
        if "AMD" in wait:
            out["note"] = "Amadeus (most airlines) gave no answer in %d s: Almosafer results may be incomplete" % AMD_WAIT
        if not rows:
            out["error"] = err or ("Almosafer: no answer in time (Amadeus still searching after %d s)" % AMD_WAIT
                                   if "AMD" in wait else "Almosafer found no flights")
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error="Almosafer failed: " + why, secs=round(time.time() - t, 1))
    return out


def cli(fn):
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
    print(json.dumps(fn(legs, a.adults, a.children, a.infants, a.cabin, a.currency.upper(),
                        a.airlines.split(",") if a.airlines else None), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    cli(search)
