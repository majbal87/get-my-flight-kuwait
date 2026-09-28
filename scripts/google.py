"""Google Flights search over plain HTTP (no browser).

GETs the public results page https://www.google.com/travel/flights?tfs=... and reads the
flights Google inlines in it (AF_initDataCallback 'ds:1'). One-way and round trip only:
the page shows no flights for multi-city, so those are refused without a request.
For a round trip the list is the outbound flights, each with the round-trip total price.
A page that comes without its list (ds:1 slots empty) gets one more request, the site's own POST GetShoppingResults
(same layout, streamed; what came in FEED_SECS is kept). If Google refuses it (error 13), page rows only for the run.
Gentle with Google: max 2 requests in flight, starts ~2.5 s apart, 20 s per request. On 429 / captcha
Google rests 45 s (or Retry-After); trips meanwhile fail fast to the next source. Blocked again after the
rest = Google is skipped for the rest of the run. Return-leg details are not on the page (they need one
more request per option), so round-trip options list the outbound flights only.
Each flight carries its cabin (Google sells some "business" fares with an economy leg, e.g. QR1083 KWI-DOH) and
its minutes. The flight number shown is the operating airline's (codeshare codes are not used).
Currency: read from each result's price token (Google's own label), else the asked one.

CLI: python google.py KWI-HND:2026-12-19 HND-KWI:2026-12-30 --adults 4 --cabin business --airlines QR
"""
import argparse, base64, json, re, sys, threading, time
from primp import Client
from pace import Pace, retry_after

PAGE = "https://www.google.com/travel/flights"
FEED = "https://www.google.com/_/FlightsFrontendUi/data/travel.frontend.flights.FlightsFrontendService/GetShoppingResults"
CABINS = {"economy": 1, "premium": 2, "business": 3, "first": 4}
CABIN_NAME = {v: k for k, v in CABINS.items()}
_sem = threading.BoundedSemaphore(2)
_lock = threading.Lock()
_client = None
_pace = Pace(2.5)  # 0.7 s drew 429s after 1-8 requests in test round 1
PAUSE = 45  # seconds Google is left alone after a 429
_pause_end = 0.0  # set when Google first blocks us
_down = False  # blocked again after the pause: skip Google for the rest of the run
FEED_SECS = 4  # follow-up feed: Google streams its list over 0.2-45 s; we keep what came in 4 s
_feed_off = False  # Google refused the feed: page rows only for the rest of the run


def _cl():
    global _client
    with _lock:
        if _client is None:
            _client = Client(impersonate="chrome_126", verify=False, timeout=20)
    return _client


# --- tiny protobuf writer for the tfs= parameter ---
def _v(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def _int(field, n):
    return _v(field << 3) + _v(n)


def _str(field, s):
    s = s.encode() if isinstance(s, str) else s
    return _v(field << 3 | 2) + _v(len(s)) + s


def _tfs(legs, trip, adults, children, infants, cabin, airlines):
    """trip 1 = round trip, 2 = one way. Passengers: 1 adult, 2 child, 4 infant on lap."""
    p = _int(1, 28) + _int(2, 2)
    for leg in legs:
        seg = _str(2, leg["date"]) + b"".join(_str(6, a) for a in airlines)
        seg += _str(13, _int(1, 1) + _str(2, leg["from"])) + _str(14, _int(1, 1) + _str(2, leg["to"]))
        p += _str(3, seg)
    pax = [1] * adults + [2] * children + [4] * infants
    p += b"".join(_int(8, x) for x in pax) + _int(9, CABINS[cabin]) + _int(14, 1) + _int(19, trip)
    return base64.urlsafe_b64encode(p).decode().rstrip("=")


def _cur(it, asked):
    """The price's own currency: each result's price token (base64 protobuf) holds it, e.g. b"\\x10\\x03\\x1a\\x03KWD";
    else the asked one."""
    try:
        m = re.search(rb"\x10[\x00-\x7f]\x1a\x03([A-Z]{3})", base64.b64decode(it[1][1] + "=="))
        return m.group(1).decode() if m else asked
    except Exception:
        return asked


def _ds(html, key):
    m = re.search(r"AF_initDataCallback\(\{key: '%s'.*?data:(\[.*?\]), sideChannel" % key, html, re.S)
    return json.loads(m.group(1)) if m else None


def _parse(html, currency):
    return _rows(_ds(html, "ds:1"), currency)


def _rows(d, currency):
    """Itineraries from Google's results list (page ds:1, or a GetShoppingResults reply: same layout)."""
    currency = currency.upper()
    out = []
    for bi in (2, 3):  # 2 = "best" flights, 3 = other flights
        if d and len(d) > bi and d[bi]:
            for it in d[bi][0]:
                f = it[0]
                price = it[1][0][1] if it[1] and it[1][0] else None
                flights = [{"flight": l[22][0] + l[22][1], "from": l[3], "to": l[6],
                            "dep": "%d-%02d-%02d %s" % (l[20][0], l[20][1], l[20][2], _hm(l[8])),
                            "arr": "%d-%02d-%02d %s" % (l[21][0], l[21][1], l[21][2], _hm(l[10])),
                            "cabin": CABIN_NAME.get(l[16]) if len(l) > 16 else None,  # per flight: mixed cabins show here
                            "min": l[11] if len(l) > 11 else None}
                           for l in f[2]]
                out.append(dict(airlines=f[1], price_total=float(price) if price is not None else None,
                                currency=_cur(it, currency), stops=[len(f[2]) - 1], duration_min=[f[9]],
                                flights=flights, seller=None))
    return out


def _blocked(r):
    return r.status_code == 429 or "/sorry/" in str(r.url) or "unusual traffic" in r.text


def _feed(html, d, currency):
    """The request the site itself sends when the page came without its list: POST GetShoppingResults with the
    page's search (ds:0 d[1][1], decoded from tfs) and session token (ds:1 d[0][4]), straight after the page like
    the site. The reply streams (rt=c) a fuller list as Google finds flights; what came within FEED_SECS is kept.
    Returns (blocked, text); text None if nothing usable came (the page's own rows are kept)."""
    global _feed_off
    if _feed_off:
        return False, None
    buf = b""
    try:
        inner = [[None, None, None, d[0][4]], _ds(html, "ds:0")[1][1], 0, 0, 0, 1]
        body = {"f.req": json.dumps([None, json.dumps(inner, separators=(",", ":"))], separators=(",", ":"))}
        hdr = {"x-same-domain": "1",
               "x-goog-ext-259736195-jspb": json.dumps(["en-US", "KW", currency, 1, None, [-180], None, None, 6, []])}
        r = _cl().post(FEED, params={"hl": "en", "gl": "KW", "rt": "c"}, data=body, headers=hdr, timeout=FEED_SECS)
        if r.status_code == 429 or "/sorry/" in str(r.url):
            return True, None
        for chunk in r.stream():  # primp: post() returns at the headers; timeout= ends the stream at FEED_SECS
            buf += chunk
    except Exception:
        pass  # time budget hit mid-stream: keep what came
    text = buf.decode("utf-8", "replace")
    if '"wrb.fr",null,null' in text[:300]:  # refused (error 13: it wants the site's browser check); stop asking
        _feed_off = True
        print("google: results feed refused, page rows only for this run", file=sys.stderr, flush=True)
    return False, text or None


def _feed_rows(text):
    """Reply: )]}' then length-prefixed chunks [["wrb.fr",null,"<json>"]]; the last one is the full list."""
    last = None
    try:
        for line in text.splitlines():
            if line.startswith("[["):
                for e in json.loads(line):
                    if e[0] == "wrb.fr" and e[2]:
                        last = json.loads(e[2])
    except ValueError:
        pass
    return last


def _hm(t):
    t = (t or []) + [None, None]
    return "%02d:%02d" % (t[0] or 0, t[1] or 0)


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None, child_ages=None):
    """child_ages: accepted for the shared contract; Google prices every child 2-11 the same."""
    global _pause_end, _down
    currency = (currency or "KWD").upper()
    res = dict(ok=False, source="google", error=None, search_url="", results=[], secs=0.0)
    if len(legs) == 1:
        trip = 2
    elif len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]:
        trip = 1
    else:
        res["error"] = "multi-city not supported by Google page"
        return res
    t = _tfs(legs, trip, adults, children, infants, cabin, [a.upper() for a in (airlines or [])])
    res["search_url"] = "%s?tfs=%s&hl=en&curr=%s" % (PAGE, t, currency)
    params = {"tfs": t, "hl": "en", "gl": "KW", "curr": currency}
    paused = lambda: _down or time.time() < _pause_end
    if not paused():
        _pace.wait()
    if paused():  # fail fast: the next source takes this trip
        res["error"] = "Google rate-limited, skipped for now"
        return res
    t0 = time.time()
    try:
        with _sem:
            r = _cl().get(PAGE, params=params)
            blocked = _blocked(r)
            d = None if blocked else _ds(r.text, "ds:1")
            if d and not (d[2] and d[3]):  # a result slot is empty: the site loads its list with one more request
                blocked, text = _feed(r.text, d, currency)
                d = None if blocked else (_feed_rows(text or "") or d)
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else str(e)[:150]
        res.update(error="Google request failed: " + why, secs=round(time.time() - t0, 1))
        return res
    res["secs"] = round(time.time() - t0, 1)
    if blocked:
        res["error"] = "Google rate-limited"
        with _lock:
            if _pause_end and t0 >= _pause_end:
                _down = True  # blocked again after our one pause
            else:
                _pause_end = max(_pause_end, time.time() + min(retry_after(r) or PAUSE, 120))
                _pace.hold(_pause_end - time.time())
        print("google: rate-limited, %s" % ("off for this run" if _down else "paused %d s" % PAUSE),
              file=sys.stderr, flush=True)
        return res
    rows = _rows(d, currency)
    if rows:
        if trip == 1:  # only the outbound is on the page; return leg unknown
            for o in rows:
                o["stops"].append(None)
                o["duration_min"].append(None)
        res.update(ok=True, results=rows)
    else:  # e.g. LHR with children: Google shows "no results" + nearby airports; the next source takes it
        res["error"] = "Google page had no flights for this search (unknown, not 'no flights')" + (
            "; its results feed refused plain requests" if _feed_off else "")
    return res


def main():
    ap = argparse.ArgumentParser(description="Google Flights search (plain HTTP)")
    ap.add_argument("legs", nargs="+", help="FROM-TO:YYYY-MM-DD, e.g. KWI-HND:2026-12-19")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--child-ages", default=None, help="comma-separated ages 2-11, e.g. 8,5 (sets --children)")
    ap.add_argument("--infants", type=int, default=0)
    ap.add_argument("--cabin", default="economy", choices=list(CABINS))
    ap.add_argument("--currency", default="KWD")
    ap.add_argument("--airlines", default="", help="IATA codes, e.g. QR,EY")
    a = ap.parse_args()
    legs = []
    for s in a.legs:
        route, date = s.split(":")
        fr, to = route.upper().split("-")
        legs.append({"from": fr, "to": to, "date": date})
    al = [x.strip() for x in a.airlines.split(",") if x.strip()] or None
    ages = [int(x) for x in a.child_ages.split(",")] if a.child_ages else None
    out = search(legs, a.adults, len(ages) if ages else a.children, a.infants, a.cabin, a.currency.upper(), al, ages)
    json.dump(out, sys.stdout, indent=1, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
