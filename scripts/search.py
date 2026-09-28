"""Run every trip in plan.json through the flight sources and save results.json.

Usage: python scripts/search.py plan.json [results.json] [--fresh] [--deadline 150] [--extra-budget 20] [--sources-dir DIR]

The plan is checked once at load (check_plan): cabin names normalised ("premium economy" -> premium), child ages
12+ counted as adults and under 2 as lap infants, codes / currency uppercased, numbers given as text accepted, a
missing label generated, duplicate trips searched once; a plan that can't be searched (unknown cabin, bad or past
date, > 330 days ahead, legs out of order, more than 9 seats, more infants than adults...) stops with a plain message.

Routing per trip (sources run side by side; each source has its own pool of 2, so never more than 2 requests in flight):
- Round trip / one way: google + almosafer at the same time (fast, exact KWD); Google empty or failed -> booking right
  away beside Almosafer (Google's page is often empty with children, infants, 9 seats or some routes). Once Almosafer has answered, a running
  Google request gets at most GRACE (5) s more; with no Almosafer answer, Google keeps its full limit.
- Multi-city / open-jaw: almosafer + booking at the same time (a second seller for the same flights); once Almosafer
  has answered, a running Booking.com request gets at most GRACE (10) s more; Flyin (extra seller) 8 s more
  (live: Flyin hung 18 s then 404 on a Bali search, round 5).
- Named airlines (plan "airlines" or "prefer"), round trip / one way: Qatar (QR) and Kuwait Airways (KU) fare
  calendars. One calendar call answers many trips (Qatar: one departure day x ~30 return days; KU: 7x7 days), so it
  is made once and shared. A named airline missing from every itinerary (a calendar fare alone doesn't count: it is
  never shown without one): one booking call filtered to it (extra budget); when that finds nothing, later trips on
  the same route skip it.
- Extra seller: flyin (round trip / one way, converted from SAR) when the plan names airlines or says "sellers": "all".
  It counts only when done within --extra-budget seconds (default 20) of the start.
- No exact price yet (nothing answered, or only a calendar / converted price): matrix (slow backup). Not when the plan
  has "airlines" and Almosafer or Booking.com answered "found no flights" (the airline filter left nothing): then one
  line "no <airlines> fares found on <sites>" instead, so the agent can offer all airlines.
Flexible dates: "flex_days" is N (+-N days both ends), [out, back] (e.g. [0, 3]: departure fixed, return +-3; 0-10
each) or "month" (any departure day in the month of the trip's date; a return trip keeps its length). kiwi_grid is
asked once per route (a month: 2 calls, each <= 21 days), then the 3 cheapest date pairs inside that window (one
ticket, or one airline on 2 tickets: only a date hint, priced on the real sources) that no other trip covers, never
before tomorrow, are searched. Grid failed (limit 10 s): the diagonal pairs (a 0 end stays fixed) or, for a month,
sample days (at most 7). flex_days on a multi-city trip is ignored (a note is printed). A "month" trip whose own date
is the month's first searchable day (the 1st, or today / tomorrow) only names the month: it is not searched itself,
the month search picks the days (that day too when it is among the cheapest).
Named Qatar / Kuwait Airways: their calendars add their 2 cheapest date pairs (searched on the real sources).
Calendar prices are never shown alone: they only join a real itinerary of that airline known at an exact price,
inside CAL_WINDOW (as the airline's own seller).
Merge: the same flights from several sources become ONE option with a "sellers" list (source, seller, price_total,
currency, converted, booking_url), cheapest first. The option price is the cheapest exact (not converted) seller.
Rows not in the plan's currency (and not marked converted_from) are dropped with one printed note; bad rows (price
not a finite positive number, odd stops, non-text names) are skipped one by one; at most 300 rows per source.
An option's tickets = the fewest among its exact sellers; a Google outbound-only row never joins a 2-ticket option.
Hard limits: every running search has a limit (LIMIT); a job queued behind 2 hung requests of its source gives up;
the whole run stops at --deadline seconds (default 150).
Good answers are cached in ../cache/ for 20 minutes (--fresh skips that); a bad cache file counts as a miss.
Prints one line per search (source | trip | result | request s, waiting s), "n/N done", and per-source timings.
"""
import argparse, functools, glob, hashlib, importlib, inspect, json, math, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = ["google", "almosafer", "booking", "qatar", "kuwaitairways", "flyin", "matrix"]
CALENDARS = {"QR": "qatar", "KU": "kuwaitairways"}  # airline -> its own fare calendar script
# a calendar fare joins that airline's real itinerary when (calendar / itinerary - 1) is inside this window:
# Qatar's calendar can be far too low (NRT business -32%); Kuwait Airways' is its published fare, often a bit
# above agency prices (+0.7..+6.9% vs Booking.com, round 4)
CAL_WINDOW = {"QR": (-0.02, 0.02), "KU": (-0.02, 0.10)}
LIMIT = {"google": 30, "almosafer": 25, "booking": 35, "qatar": 15, "kuwaitairways": 15, "flyin": 25,
         "matrix": 90, "kiwi_grid": 10}  # seconds one running search may take (Kiwi grid answers in 1-4 s live)
GRACE = {"google": 5, "booking": 10, "flyin": 8}  # once Almosafer answered a trip, a running request gets at most this many s more
ROW_CAP = 300  # rows kept per source per trip (the cheapest)
CABINS = {"economy": "economy", "premium": "premium", "premiumeconomy": "premium", "business": "business", "first": "first"}
SITE = {"google": "Google Flights", "almosafer": "Almosafer", "booking": "Booking.com", "qatar": "Qatar Airways",
        "kuwaitairways": "Kuwait Airways", "flyin": "Flyin", "matrix": "ITA Matrix", "kiwi": "Kiwi.com"}
CACHE = os.path.join(HERE, "..", "cache")
TTL = 20 * 60
GOOGLE_EMPTY = set()  # legs + dates Google's page showed nothing for in this run
BOOKING_NONE = set()  # (route, airline) a filtered Booking.com call found nothing for in this run
CAL, CAL_LOCK = {}, threading.Lock()  # shared calendar calls: key -> (future, started)
POOLS = {}  # source -> its pool of 2 (set in main)
HUNG = {}  # source -> requests past their limit that still hold a pool slot
TAKEN = set()  # legs of every trip already searched: flexible dates never repeat one
STATS = []  # (source, request seconds, ok) for the timing summary


def trip_kind(legs):
    if len(legs) == 1:
        return "one way"
    a, b = legs[0], legs[-1]
    if len(legs) == 2 and a["from"] == b["to"] and a["to"] == b["from"]:
        return "round trip"
    return "multi-city"


def check_plan(plan):
    """Normalise plan.json in place; stop with a plain message when it can't be searched. Returns the plan."""
    def stop(msg):
        raise SystemExit("plan.json: " + msg)

    def num(v, what, default=0):
        try:
            return int(default if v in (None, "") else v)
        except (TypeError, ValueError):
            stop("%s must be a number, not %r" % (what, v))
    cabin = re.sub(r"[\s_-]", "", str(plan.get("cabin") or "economy").lower())
    if cabin not in CABINS:
        stop("unknown cabin %r: use economy, premium (premium economy), business or first" % plan.get("cabin"))
    plan["cabin"] = CABINS[cabin]
    plan["currency"] = str(plan.get("currency") or "KWD").strip().upper()
    for k in ("airlines", "prefer"):
        if plan.get(k):
            plan[k] = [str(c).strip().upper() for c in plan[k]]
    adults, children, infants = num(plan.get("adults"), "adults", 1), num(plan.get("children"), "children"), \
        num(plan.get("infants"), "infants")
    ages = [num(x, "a child age") for x in plan.get("child_ages") or []]
    if ages:  # ages set the count: 12+ fly as adults, under 2 as lap infants
        if children and children != len(ages):
            stop("children is %d but child_ages has %d: give one age per child" % (children, len(ages)))
        adults, infants = adults + sum(x >= 12 for x in ages), infants + sum(x < 2 for x in ages)
        ages = [x for x in ages if 2 <= x < 12]
        children = len(ages)
    plan.update(adults=adults, children=children, infants=infants, child_ages=ages)
    if adults < 1:
        stop("at least 1 adult is needed")
    if infants > adults:
        stop("more lap infants (%d) than adults (%d): each infant needs its own adult" % (infants, adults))
    if adults + children > 9:
        stop("%d seats (adults + children): one booking takes at most 9; split the group" % (adults + children))
    today, trips, seen = date.today(), [], set()
    for t in plan.get("trips") or []:
        legs = t.get("legs") or []
        for l in legs:
            l["from"], l["to"] = str(l.get("from") or "").strip().upper(), str(l.get("to") or "").strip().upper()
            if not (re.fullmatch(r"[A-Z]{3}", l["from"]) and re.fullmatch(r"[A-Z]{3}", l["to"])):
                stop("airport codes must be 3 letters, got %s-%s" % (l["from"], l["to"]))
            if l["from"] == l["to"]:
                stop("a leg goes from %s to the same airport" % l["from"])
            try:
                d = date.fromisoformat(str(l.get("date")))
            except ValueError:
                stop("date %r is not YYYY-MM-DD" % l.get("date"))
            if d < today:
                stop("date %s is in the past" % d)
            if d > today + timedelta(days=330):
                stop("date %s is more than 330 days ahead: airlines don't sell that far out yet" % d)
        if not legs:
            stop("trip %r has no legs" % t.get("label"))
        if [l["date"] for l in legs] != sorted(l["date"] for l in legs):
            stop("the legs of trip %r are not in date order" % t.get("label"))
        t["flex_days"] = flex_days(t.get("flex_days"), num, stop)
        t["label"] = str(t.get("label") or auto_label(legs))
        if legs_key(legs) in seen:
            print("  note       | %s | same legs and dates as an earlier trip: searched once" % t["label"], flush=True)
            continue
        seen.add(legs_key(legs))
        if t["flex_days"] and trip_kind(legs) == "multi-city":
            print("  note       | %s | flex_days is ignored on a multi-city trip: add the date pairs as trips" % t["label"],
                  flush=True)
        trips.append(t)
    if not trips:
        stop("no trips to search")
    plan["trips"] = trips
    return plan


def auto_label(legs):
    """'KWI→LHR→KWI, 3 Dec–13 Dec'; a gap between legs starts a new part: 'KWI→JED, MED→KWI, 26 Feb–7 Mar'."""
    parts = []
    for l in legs:
        if parts and parts[-1].endswith(l["from"]):
            parts[-1] += "→" + l["to"]
        else:
            parts.append(l["from"] + "→" + l["to"])
    return "%s, %s" % (", ".join(parts), "–".join(day(l["date"]) for l in legs))


def flex_days(v, num, stop):
    """flex_days: N (both ends), [departure, return] (e.g. [0, 3]: departure fixed), or "month" (any departure day in
    the month of the trip's date; a return trip keeps its length). Returns N, [out, back], "month" or None."""
    if v == "month":
        return v
    ends = v if isinstance(v, list) else [v]
    if isinstance(v, list) and len(v) != 2:
        stop('flex_days is a number, [departure, return] or "month", not %r' % (v,))
    n = [num(x, "flex_days") for x in ends]
    if not all(0 <= x <= 10 for x in n):
        stop('flex_days: 0-10 days per end (one Kiwi grid); a whole month is "month", not %r' % (v,))
    return None if not any(n) else n if isinstance(v, list) else n[0]


def load(name):
    try:
        return importlib.import_module(name)
    except Exception as e:  # missing file, missing primp, syntax error...
        print("! %s unavailable (%s)" % (name, e), flush=True)
        return "could not load %s.py: %s" % (name, e)


def call(mod, legs, plan, airlines):
    kw = {}  # real child ages, only for sources whose search() takes them (older ones get the count only)
    if plan.get("child_ages") and "child_ages" in inspect.signature(mod.search).parameters:
        kw["child_ages"] = plan["child_ages"]
    try:
        r = mod.search(legs, adults=plan.get("adults", 1), children=plan.get("children", 0),
                       infants=plan.get("infants", 0), cabin=plan.get("cabin", "economy"),
                       currency=plan.get("currency", "KWD"), airlines=airlines, **kw)
        r = r if isinstance(r, dict) else {"ok": False, "error": "bad reply: %r" % (r,)}
    except Exception as e:
        r = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
    if r.get("error"):  # never keep an API key in an error text
        r["error"] = re.sub(r"key=[^&\s)]+", "key=hidden", str(r["error"]))[:300]
    return r


def cached_call(name, mod, legs, plan, fresh, airlines):
    """call() through a 20-minute disk cache. Only ok answers with options are saved. Returns (reply, fetched_at)."""
    key = [name, legs] + [plan.get(k) for k in ("adults", "children", "infants", "cabin", "currency")] + \
        [sorted(airlines or [])] + ([plan["child_ages"]] if plan.get("child_ages") else [])
    path = os.path.join(CACHE, "r-%s.json" % hashlib.sha1(json.dumps(key).encode()).hexdigest()[:16])
    if not fresh and os.path.exists(path) and time.time() - os.path.getmtime(path) < TTL:
        try:
            with open(path) as f:
                return json.load(f), os.path.getmtime(path)
        except (OSError, ValueError):
            pass  # a bad cache file is a miss
    route = legs_key(legs)
    if name == "google" and route in GOOGLE_EMPTY:
        return {"ok": False, "error": "Google had no flights for these legs and dates earlier in this run (skipped)"}, None
    r = call(mod, legs, plan, airlines)
    if name == "google" and not r.get("ok") and "no flights" in (r.get("error") or ""):
        GOOGLE_EMPTY.add(route)
    if r.get("ok") and r.get("results"):  # write a temp file, then swap it in: never a half-written cache file
        tmp = "%s.%d.tmp" % (path, threading.get_ident())
        try:
            with open(tmp, "w") as f:
                json.dump(r, f, default=str)
            os.replace(tmp, path)
        except (OSError, ValueError, TypeError):
            if os.path.exists(tmp):
                os.remove(tmp)
    return r, None


def start_job(pool, deadline, fn, *args):
    """Queue fn in a source pool. A job still queued when `deadline` passes is dropped without a request."""
    started = []

    def job():
        if time.time() > deadline:
            return {"ok": False, "error": "not sent (time budget used up)"}, None
        started.append(time.time())
        return fn(*args)
    return pool.submit(job), started


def wait_job(name, fut, started, limit, deadline, since=None):
    """Wait until the job is done, has run `limit` s (queue time not counted) or the deadline passes.
    `since` (a list) gets the time Almosafer answered this trip: from then on a running request gets at most GRACE s
    more (counted from its own start if it started later); it then counts as hung like one past its limit.
    A request that hangs keeps its thread (and its pool slot), but nobody waits for it. When both slots of a source
    hold hung requests, jobs still queued for it give up instead of waiting for the deadline."""
    while True:
        try:
            return fut.result(timeout=0.5)
        except FutureTimeout:
            now = time.time()
            if now > deadline:
                fut.cancel()
                return {"ok": False, "error": "timed out (time budget)"}, None
            late = bool(since and started and now - max(started[0], since[0]) > GRACE[name])
            if started and (now - started[0] > limit or late):
                with CAL_LOCK:
                    HUNG.setdefault(name, set()).add(fut)
                fut.add_done_callback(lambda f: HUNG[name].discard(f))
                return {"ok": False, "error": "timed out after %d s%s" % (
                    min(limit, now - started[0]), " (%d s after Almosafer answered)" % GRACE[name] if late else "")}, None
            if not started and len(HUNG.get(name) or ()) >= 2:
                fut.cancel()
                return {"ok": False, "error": "not sent (2 earlier %s requests hung)" % name}, None


# ---------- merge: one option per flight set, every seller kept ----------
# Contract with make_page.py: an option's price_total / currency (and every seller's) is in the plan's currency,
# except sellers marked converted (converted_from set; an option with only those is converted_only). Rows in another
# currency are dropped here, never compared as the same money.
def norm(f):  # "QR0812" / "QR-812" -> "QR812"
    c = re.sub(r"[\s-]", "", (f.get("flight") or "").upper())
    m = re.match(r"^([A-Z0-9]{2})0*(\d+)$", c)
    return m.group(1) + m.group(2) if m else c


def legs_key(legs):
    return tuple((l["from"], l["to"], l["date"]) for l in legs)


def fkey(flights):
    return tuple((norm(f), (f.get("dep") or "")[:10]) for f in flights)


def fits(o, legs):
    """False when a source answered for another airport of the city (Almosafer and Kiwi read HND as all of Tokyo)."""
    fl, i = o.get("flights") or [], 0
    for leg, s in zip(legs, o.get("stops") or []):
        if s is None or i + s + 1 > len(fl):
            break
        if fl[i].get("from") != leg["from"] or fl[i + s].get("to") != leg["to"]:
            return False
        i += s + 1
    return True


def has_airline(o, code):  # sold (flight number) or flown (codeshare "op") by that airline, or its calendar fare
    return code.upper() in (o.get("codes") or []) or \
        any(code.upper() in ((f.get("flight") or "")[:2].upper(), f.get("op")) for f in o.get("flights") or [])


def is_code(a):
    return bool(re.fullmatch(r"[A-Z0-9]{2}", a or ""))


def seller_of(o):
    return {"source": o["source"], "seller": o.get("seller") or SITE.get(o["source"], o["source"]),
            "price_total": o["price_total"], "currency": o.get("currency"), "converted": bool(o.get("converted_from")),
            "converted_from": o.get("converted_from"), "booking_url": o.get("search_url"), "note": o.get("seller_note"),
            "bags": o.get("bags")}


def tickets(rows):
    """Tickets a flight set needs: the fewest among its exact sellers (a converted Flyin fare on 2 tickets doesn't make
    an itinerary Almosafer sells as one ticket 'separate tickets')."""
    return min(o.get("tickets") or 1 for o in [o for o in rows if not o.get("converted_from")] or rows)


def as_option(rows):
    """One option from rows with the same flights: full itinerary details, every seller cheapest first,
    price = cheapest exact seller (a converted price only when there is nothing else: converted_only)."""
    full = [o for o in rows if o.get("flights") and None not in (o.get("stops") or [None])]
    base = (full or rows)[0]
    names = next((o["airlines"] for o in rows if o.get("airlines") and not all(is_code(a) for a in o["airlines"])),
                 base.get("airlines"))
    exact_rows = [o for o in rows if not o.get("converted_from")]
    low = min(o["price_total"] for o in exact_rows or rows)
    info = {}  # per-flight minutes / operator from any source; cabin only from sellers within 1% of the price
    for o in rows:  # (a dearer seller's fare can be another cabin on the same flights)
        for f in o.get("flights") or []:
            d = info.setdefault((norm(f), (f.get("dep") or "")[:10]), {})
            for k in ("cabin", "min", "op"):
                if f.get(k) is not None and (k != "cabin" or o["price_total"] <= low * 1.01):
                    d.setdefault(k, f[k])
    flights = [dict({k: v for k, v in f.items() if v is not None and k != "cabin"},
                    **info.get((norm(f), (f.get("dep") or "")[:10]), {})) for f in base.get("flights") or []]
    best = {}
    for o in rows:
        s = seller_of(o)
        k = (s["source"], s["seller"])
        if k not in best or s["price_total"] < best[k]["price_total"]:
            best[k] = s
    direct = lambda s: "direct" in (s["seller"] or "").lower()
    sellers = sorted(best.values(), key=lambda s: (round(s["price_total"], 2), not direct(s), s["converted"]))
    exact = [s for s in sellers if not s["converted"]]
    top = (exact or sellers)[0]
    o = {k: v for k, v in base.items() if k not in ("booking_url", "seller_note", "converted_from", "calendar")}
    o.update(airlines=names, flights=flights, sellers=sellers, price_total=top["price_total"], currency=top["currency"],
             source=top["source"], seller=top["seller"], search_url=top["booking_url"])
    if any(x.get("tickets") for x in rows):
        o["tickets"] = tickets(rows)
    if not exact:
        o["converted_only"] = True
    return o


def clean(o, n_legs):
    """A source row fit to merge, or None: a finite positive price, stops a list of ints (an int is taken as the one
    leg of a one way), names, codes and flight numbers as text. One bad row never costs the trip."""
    try:
        p, s, fl = o.get("price_total"), o.get("stops"), o.get("flights") or []
        if isinstance(p, bool) or not isinstance(p, (int, float)) or not math.isfinite(p) or p <= 0:
            return None
        if isinstance(s, int) and not isinstance(s, bool) and n_legs == 1:
            o = dict(o, stops=[s])
        elif s is not None and not (isinstance(s, list) and all(x is None or type(x) is int for x in s)):
            return None
        text = list(o.get("airlines") or []) + list(o.get("codes") or []) + \
            [o.get(k) or "" for k in ("seller", "currency", "converted_from")] + \
            [f.get(k) or "" for f in fl for k in ("flight", "dep", "from", "to")]
        if not all(isinstance(x, str) for x in text) or type(o.get("tickets") or 1) is not int:
            return None
        return o
    except (AttributeError, TypeError):
        return None


def merge(replies, legs, currency=None, label=None):
    """All sources' options for one trip -> one option per flight set, cheapest first. Returns (options, dropped).
    1. Full itineraries with the same flights (number + date) form one group.
    0. Bad rows and rows not in `currency` (unless converted) are skipped; at most ROW_CAP rows per source.
    2. A Google round-trip row lists the outbound only: it joins the group with that outbound whose price is closest
       (within 3%), never a group sold as separate tickets; else it stays on its own.
    3. An airline fare-calendar price (no flights: Qatar, Kuwait Airways) joins the group flown only by that airline,
       known at an exact price in the same currency, whose price is closest (inside CAL_WINDOW), as the airline's own seller; else it is
       dropped (a calendar price can be a fare the airline's site no longer sells: Qatar NRT 4,999.60 vs 7,356)."""
    rows, dropped, other = [], 0, {}
    for r in replies:
        mine = []
        for o in r.get("results") or []:
            o = clean(o, len(legs))
            if o is None:
                continue
            cur = (o.get("currency") or currency or "").upper() or None
            if currency and cur != currency and not o.get("converted_from"):  # another currency: not the same money
                other[cur] = other.get(cur, 0) + 1
                continue
            if not fits(o, legs):
                dropped += 1
                continue
            mine.append(dict(o, currency=cur, source=r["source"],
                             search_url=o.get("booking_url") or o.get("search_url") or r.get("search_url")))
        rows += sorted(mine, key=lambda o: o["price_total"])[:ROW_CAP]
    if other and label:
        print("  note       | %s | dropped %s: not the plan's currency %s" % (
            label, ", ".join("%d rows in %s" % (n, c) for c, n in other.items()), currency), flush=True)
    rows.sort(key=lambda o: o["price_total"])
    groups, byfull, part, cal = [], {}, [], []
    for o in rows:
        if o.get("calendar"):
            cal.append(o)
        elif not o.get("flights") or not all(norm(f) for f in o["flights"]):  # no flight numbers: never merged
            groups.append([o])
        elif None in (o.get("stops") or [None]):
            part.append(o)
        else:
            k = fkey(o["flights"])
            if k not in byfull:
                byfull[k] = []
                groups.append(byfull[k])
            byfull[k].append(o)

    def price(g):
        ex = [o["price_total"] for o in g if not o.get("converted_from")]
        return min(ex or [o["price_total"] for o in g])

    for o in part:  # outbound-only rows (Google round trips)
        n = (o.get("stops") or [0])[0] + 1
        k = fkey(o["flights"][:n])
        near = [g for k2, g in byfull.items() if k2[:n] == k and (g[0].get("stops") or [None])[0] == n - 1
                and not any(x["source"] == o["source"] for x in g) and tickets(g) == 1  # never onto separate tickets
                and abs(price(g) - o["price_total"]) <= 0.03 * o["price_total"]]
        if near:
            min(near, key=lambda g: abs(price(g) - o["price_total"])).append(o)
        else:
            groups.append([o])
    for o in cal:  # the airline's own calendar fare: only next to that airline's itinerary at an exact price
        c = (o.get("codes") or ["?"])[0]
        lo, hi = CAL_WINDOW.get(c, (-0.02, 0.02))
        near = [g for g in groups if g[0].get("flights") and all(c in (norm(f)[:2], f.get("op")) for f in g[0]["flights"])
                and any(not x.get("converted_from") and x.get("currency") == o.get("currency") for x in g)
                and lo <= o["price_total"] / price(g) - 1 <= hi]
        if near:
            min(near, key=lambda g: abs(price(g) - o["price_total"])).append(o)
    # exact prices first; an option known only at a converted price goes after them
    return sorted((as_option(g) for g in groups), key=lambda o: (bool(o.get("converted_only")), o["price_total"])), dropped


def cal_job(name, mod, legs, plan, fresh, deadline):
    """An airline's fare calendar, shared: one call answers many trips (Qatar: one departure day x every return day;
    Kuwait Airways: 7x7 days around the first trip that asked). Returns (future, started, mine)."""
    rt = len(legs) == 2
    want = (legs[0]["date"], legs[1]["date"] if rt else None)
    with CAL_LOCK:
        if name == "qatar":
            key = (name, legs[0]["from"], legs[0]["to"], rt, legs[0]["date"])
        else:
            near = lambda d, c: d is None or abs((date.fromisoformat(d) - date.fromisoformat(c)).days) <= 3
            key = next((k for k in CAL if k[:4] == (name, legs[0]["from"], legs[0]["to"], rt)
                        and near(want[0], k[4]) and (not rt or near(want[1], k[5]))), None) or \
                (name, legs[0]["from"], legs[0]["to"], rt) + want
        mine = key not in CAL  # the caller that made the call counts it in the timings
        if mine:
            CAL[key] = start_job(POOLS[name], deadline, cached_call, name, mod, legs, plan, fresh, None)
        return CAL[key] + (mine,)


# ---------- flexible dates ----------
def shift(d, k):
    return (date.fromisoformat(d) + timedelta(days=k)).isoformat()


def day(d):
    return date.fromisoformat(d).strftime("%-d %b")


def flex_trips(group, plan, mod, deadline, cals=(), mods=None, fresh=False):
    """Kiwi grid for a route -> the 3 cheapest date pairs besides the trip's own (one ticket, or one airline on 2
    tickets: a date hint only), never before tomorrow, as new trips for every airport of that route.
    flex_days N / [out, back]: ONE grid call (departure +-out, return +-back; 0 = that date stays fixed).
    "month": any departure day in the trip's month in 2 grid calls (Kiwi's grid spans <= 21 days), a return trip
    keeping its length (grid nights = that length; every pair is checked here too).
    Grid failed: the fallback pairs instead (N: diagonal, a 0 end stays fixed; month: sample days), at most 7.
    Named airlines with a fare calendar (cals): their 2 cheapest date pairs inside the same window are searched too,
    on the real sources (a calendar price is only a hint of a cheap date, never shown)."""
    t0, legs, f = group[0], group[0]["legs"], group[0]["flex_days"]
    rt = len(legs) == 2
    own = (legs[0]["date"], legs[1]["date"] if rt else None)
    gap = lambda a, b: (date.fromisoformat(b) - date.fromisoformat(a)).days
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    if f == "month":
        first = date.fromisoformat(own[0]).replace(day=1)
        lo, last = max(first.isoformat(), tomorrow), ((first + timedelta(days=32)).replace(day=1) - timedelta(days=1)).isoformat()
        nights = gap(*own) if rt else None
        chunks = [c for c in ((lo, min(shift(lo, 15), last)), (shift(lo, 16), last)) if c[0] <= c[1]]
        calls = [(c, (shift(c[0], nights), shift(c[1], nights)) if rt else None) for c in chunks]
        ok_pair = lambda a, b: bool(a) and lo <= a <= last and (not rt or bool(b) and gap(a, b) == nights)
        cand = [(d, shift(d, nights) if rt else None) for d in (shift(lo, k) for k in range(gap(lo, last) + 1))]
        what = "any day in %s%s" % (first.strftime("%b %Y"), ", %d-day trip" % nights if rt else "")
    else:
        no, nb = f if isinstance(f, list) else (f, f)
        nights, nb = None, nb if rt else 0
        calls = [((shift(own[0], -no), shift(own[0], no)), (shift(own[1], -nb), shift(own[1], nb)) if rt else None)]
        near = lambda d, o, n: bool(d) and abs(gap(o, d)) <= n
        ok_pair = lambda a, b: near(a, own[0], no) and (not rt or near(b, own[1], nb))
        m, clip = max(no, nb), lambda k, n: max(-n, min(n, k))
        cand = [(shift(own[0], clip(k, no)), shift(own[1], clip(k, nb)) if rt else None) for k in range(-m, m + 1)]
        what = "±%d days" % no if no == nb or not rt else "departure ±%d, return ±%d days" % (no, nb)
    rows, errs, t = [], [], time.time()
    cal_futs = [(name,) + cal_job(name, mods[name], legs, plan, fresh, deadline) for name in cals
                if not isinstance(mods[name], str)]  # started now, so they run alongside the grid
    if isinstance(mod, str) or mod is None:
        errs.append(mod or "kiwi_grid not loaded")
    else:  # at most 2 grids at a time; don't wait past LIMIT or the deadline
        fn = functools.partial(mod.grid, nights=nights) if nights else mod.grid
        jobs = [start_job(POOLS["kiwi_grid"], deadline, fn, legs[0]["from"], legs[0]["to"], o, r, plan.get("adults", 1),
                          plan.get("children", 0), plan.get("infants", 0), plan.get("cabin", "economy"),
                          plan.get("currency", "KWD"), plan.get("airlines")) for o, r in calls]
        for fut, started in jobs:
            got, err = None, None
            try:
                got = wait_job("kiwi_grid", fut, started, LIMIT["kiwi_grid"], deadline)
                got, err = (None, got[0]["error"]) if isinstance(got[0], dict) else got[:2]
            except Exception as e:
                err = "%s: %s" % (type(e).__name__, str(e)[:120])
            rows += got or []
            errs += [err] if err else []
            if started:
                STATS.append(("kiwi_grid", time.time() - started[0], bool(got) and not err))
    moved = lambda tr, a, b: [dict(tr["legs"][0], date=a)] + ([dict(tr["legs"][1], date=b)] if rt else [])
    new_pair = lambda p: (p != own or t0.get("placeholder")) and p[0] >= tomorrow and not all(legs_key(moved(tr, *p)) in TAKEN for tr in group)
    hint = lambda x: (x.get("tickets") or 1) == 1 or (x.get("airline") and "," not in x["airline"])  # one airline
    if len(calls) > 1:  # each grid comes cheapest first; 2 grids (a month) are put in one price order
        rows = sorted(rows, key=lambda x: x["price_total"])
    pairs = [(x["out"], x.get("ret")) for x in rows if hint(x)
             and ok_pair(x["out"], x.get("ret"))]
    pairs = [p for p in dict.fromkeys(pairs) if new_pair(p)][:3]
    how = "grid: cheapest %s" % ", ".join("%s→%s" % (day(a), day(b)) if b else day(a) for a, b in pairs)
    if pairs and errs:
        how += " (%d of %d grid calls failed: %s)" % (len(errs), len(calls), errs[0][:60])
    if not pairs:
        cand = list(dict.fromkeys(cand))
        pairs = [p for p in cand[::-(-len(cand) // 7)] if new_pair(p)]  # at most 7, spread over the window
        how = "grid failed (%s): %s" % ((errs or ["no one-ticket pairs"])[0][:60],
                                        "sample days" if f == "month" else "diagonal pairs")
    for name, fut, started, mine in cal_futs:  # the airline's own cheap dates (Qatar: return day only; KU: both ends)
        r, fetched = wait_job(name, fut, started, LIMIT[name], deadline)
        if mine and not fetched:
            STATS.append((name, r.get("secs") or 0, bool(r.get("calendar"))))
        cand = sorted((c for c in r.get("calendar") or [] if ok_pair(c.get("depart"), c.get("return"))
                       and isinstance(c.get("price_total"), (int, float))), key=lambda c: c["price_total"])
        new = [p for p in dict.fromkeys((c["depart"], c.get("return")) for c in cand) if p not in pairs and new_pair(p)][:2]
        pairs += new
        how += "; %s calendar: %s" % (name, ", ".join("%s→%s" % (day(a), day(b)) if b else day(a) for a, b in new)
                                      or "nothing new")
    print("  %-10s | %s %s | %s | %.1fs" % ("kiwi_grid", t0.get("route") or t0["label"], what, how, time.time() - t),
          flush=True)
    grid_price = {(x["out"], x.get("ret")): x.get("price_total") for x in rows or []}
    out = []
    with CAL_LOCK:  # never the same legs twice (the plan's own trips, other flex groups)
        for tr in group:
            for a, b in pairs:
                nl = moved(tr, a, b)
                if legs_key(nl) in TAKEN:
                    continue
                TAKEN.add(legs_key(nl))
                out.append(dict(tr, legs=nl, flex_days=None, from_grid=True, grid_price=grid_price.get((a, b)),
                                label="%s, %s" % (tr["label"].split(",")[0], "–".join(day(x) for x in (a, b) if x))))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--fresh", action="store_true", help="ignore saved answers, search live")
    ap.add_argument("--deadline", type=int, default=150, help="seconds for the whole run (default 150)")
    ap.add_argument("--extra-budget", type=int, default=20, help="seconds the extra sellers may use (default 20)")
    ap.add_argument("--sources-dir", help="folder with source modules (for tests)")
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    if a.sources_dir:  # tests: fake sources, and their own cache so fake prices never reach a real run
        global CACHE
        sys.path.insert(0, os.path.abspath(a.sources_dir))
        CACHE = os.path.join(os.path.abspath(a.sources_dir), "cache")
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.plan)), "results.json")

    plan = check_plan(json.load(open(a.plan)))
    trips = plan["trips"]
    named = list(dict.fromkeys(c.upper() for c in (plan.get("airlines") or []) + (plan.get("prefer") or [])))
    wide = bool(named) or plan.get("sellers") == "all"  # ask the extra seller (Flyin) too
    mods = {name: load(name) for name in SOURCES}
    os.makedirs(CACHE, exist_ok=True)
    for f in glob.glob(os.path.join(CACHE, "r-*.json")):  # drop expired answers
        if time.time() - os.path.getmtime(f) > TTL:
            os.remove(f)
    pools = POOLS
    pools.update({name: ThreadPoolExecutor(2) for name in SOURCES + ["kiwi_grid"]})
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    for t in trips:  # a month search's own date that is just the month start: the grid picks the days instead
        d = t["legs"][0]["date"]
        t["placeholder"] = t["flex_days"] == "month" and trip_kind(t["legs"]) != "multi-city" and \
            d <= max(d[:8] + "01", tomorrow)
    TAKEN.update(legs_key(t["legs"]) for t in trips if not t["placeholder"])
    lock, done, total = threading.Lock(), [0], [sum(not t["placeholder"] for t in trips)]
    start = time.time()
    deadline, extra_dl = start + a.deadline, start + min(a.extra_budget, a.deadline)
    print("Searching %d trips (stops after %d s; extra sellers %s)..." % (
        len(trips), a.deadline, "within %d s" % a.extra_budget if wide else "off"), flush=True)

    def report(name, trip, r, fetched, took, tag="", count=True):
        opts = r.get("results") or []
        ok = bool(r.get("ok")) and len(opts) > 0
        err = r.get("error") or (None if ok else "no results")
        secs = r.get("secs") or 0
        skipped = "not sent" in (err or "")
        if count and not fetched and not skipped:
            STATS.append((name, secs if secs else took, ok))
        when = ("cached %.0f min ago" % ((time.time() - fetched) / 60) if fetched else "%.0fs" % took
                if "timed out" in (err or "") or skipped else "%.1fs request, %.1fs waiting" % (secs, max(0, took - secs)))
        res = ("%d options" % len(opts) if ok and not r.get("calendar") else
               "%s %s (fare calendar)" % (opts[0].get("currency"), "{:,.2f}".format(opts[0]["price_total"])) if ok
               else "failed: %s" % err[:90])
        print("  %-10s | %s | %s | %s" % (name + tag, trip["label"], res, when), flush=True)
        return ok, err

    def ask(name, trip, tried, airlines=None, dl=None, tag="", since=None):
        """One source for one trip. Returns (reply, fetched_at) when it found options, else None.
        since: the trip's list for the time Almosafer answered (Almosafer adds it; the others wait GRACE s after it)."""
        mod, dl = mods[name], dl or deadline
        if isinstance(mod, str) or time.time() > dl:
            tried.append({"source": name, "ok": False, "error": mod if isinstance(mod, str) else "not sent (time budget)"})
            return None
        t0 = time.time()
        fut, started = start_job(pools[name], dl, cached_call, name, mod, trip["legs"], plan, a.fresh,
                                 airlines or plan.get("airlines"))
        r, fetched = wait_job(name, fut, started, LIMIT[name], dl, since if name != "almosafer" else None)
        ok, err = report(name, trip, r, fetched, time.time() - t0, tag)
        tried.append({"source": name + tag, "ok": ok, "error": err})
        if ok and name == "almosafer" and since is not None:
            since.append(time.time())
        return (dict(r, source=name), fetched) if ok else None

    def cal_ask(name, trip, tried):
        """An airline's own fare calendar. One call answers many trips, so calls are shared (CAL)."""
        mod, legs = mods[name], trip["legs"]
        if isinstance(mod, str):
            tried.append({"source": name, "ok": False, "error": mod})
            return None
        want = (legs[0]["date"], legs[1]["date"] if len(legs) == 2 else None)
        fut, started, mine = cal_job(name, mod, legs, plan, a.fresh, deadline)
        t0 = time.time()
        r, fetched = wait_job(name, fut, started, LIMIT[name], deadline)
        hit = next((c for c in r.get("calendar") or [] if (c.get("depart"), c.get("return")) == want
                    and isinstance(c.get("price_total"), (int, float))), None)
        if hit:
            code = [c for c, n in CALENDARS.items() if n == name][0]
            url = mod.booking_url(legs, plan.get("adults", 1), plan.get("cabin", "economy")) \
                if hasattr(mod, "booking_url") else r.get("search_url")
            o = {"airlines": [SITE[name]], "codes": [code], "price_total": round(hit["price_total"], 3),
                 "currency": hit.get("currency"), "stops": None, "duration_min": None, "flights": [], "calendar": True,
                 "seller": "%s (direct)" % SITE[name], "search_url": url,
                 "note": "Flights not listed (%s's own fare calendar); choose them on its site" % SITE[name],
                 "seller_note": "the airline's own lowest fare for these dates; pick the flights on its site"}
            r = dict(r, ok=True, results=[o], calendar=True, error=None)
        else:
            r = dict(r, ok=False, results=[], error="%s calendar has no fare for these dates" % SITE[name]
                     if r.get("calendar") else r.get("error"))
        ok, err = report(name, trip, r, fetched, time.time() - t0, count=mine)
        tried.append({"source": name, "ok": ok, "error": err})
        return (dict(r, source=name), fetched) if ok else None

    def run_trip(trip):
        try:
            res = search_trip(trip)
        except Exception as e:  # a bad reply must never cost the whole run its results.json
            res = {"label": trip.get("label"), "route": trip.get("route"), "kind": trip_kind(trip["legs"]),
                   "legs": trip["legs"], "tried": [], "ok": False, "options": [], "fetched_at": None, "cached_min": None,
                   "source": None, "search_url": None, "error": "search failed: %s: %s" % (type(e).__name__, str(e)[:120])}
        with lock:
            done[0] += 1
            print("%d/%d done (%.0fs)" % (done[0], total[0], time.time() - start), flush=True)
        return res

    def search_trip(trip):
        kind = trip_kind(trip["legs"])
        tried = []
        core = (["google"] if kind != "multi-city" else ["booking"]) + ["almosafer"]
        extra = ["flyin"] if wide and kind != "multi-city" else []
        route = tuple((l["from"], l["to"]) for l in trip["legs"])
        cals = [CALENDARS[c] for c in named if c in CALENDARS] if kind != "multi-city" else []
        answered = []  # when Almosafer answered: Google then gets at most GRACE s more
        def core_ask(n):
            r = ask(n, trip, tried, None, None, "", answered)
            if r is None and n == "google":  # Google's page came back empty (children, infants, 9 seats, some
                # routes; its results feed is often refused): Booking.com beside Almosafer instead
                r = ask("booking", trip, tried, None, None, "", answered)
            return r
        with ThreadPoolExecutor(len(core) + len(extra) + len(cals)) as ex:
            f_core = [ex.submit(core_ask, n) for n in core]
            f_more = [ex.submit(ask, n, trip, tried, None, extra_dl, "", answered) for n in extra] + \
                     [ex.submit(cal_ask, n, trip, tried) for n in cals]
            got = [x for x in (f.result() for f in f_core) if x]
            if not got and not any(x["source"] == "booking" for x in tried):  # nothing yet: Booking.com
                b = ask("booking", trip, tried)
                got += [b] if b else []
            elif got:  # a named airline in no itinerary: one Booking.com call filtered to it (extra seller)
                missing = [c for c in named if (route, c) not in BOOKING_NONE
                           and not any(has_airline(o, c) for r, _ in got for o in r["results"])]
                if missing:
                    tag = "[%s]" % ",".join(missing)
                    b = ask("booking", trip, tried, missing, extra_dl, tag)
                    got += [b] if b else []
                    err = next((x["error"] for x in list(tried) if x["source"] == "booking" + tag), "")
                    if not b and "no flights" in (err or ""):
                        BOOKING_NONE.update((route, c) for c in missing)
            got += [x for x in (f.result() for f in f_more) if x]
        if not any(not o.get("converted_only") for o in merge([r for r, _ in got], trip["legs"], plan["currency"])[0]):
            empty = [x["source"].split("[")[0] for x in tried if "found no flights" in (x["error"] or "")]
            if plan.get("airlines") and {"almosafer", "booking"} & set(empty):  # answered; the airline filter left nothing
                print("  note       | %s | no %s fares found on %s: offer to search all airlines" % (
                    trip["label"], ", ".join(plan["airlines"]), ", ".join(SITE.get(n, n) for n in dict.fromkeys(empty))), flush=True)
            else:
                x = ask("matrix", trip, tried)  # no exact price yet (maybe only a calendar or converted one): slow backup
                got += [x] if x else []
        cached = [f for _, f in got if f]
        fetched = min(cached or [time.time()])  # the oldest price in this trip
        replies = [r for r, _ in got]
        options, dropped = merge(replies, trip["legs"], plan["currency"], trip["label"])
        res = {"label": trip["label"], "route": trip.get("route"), "kind": kind, "legs": trip["legs"],
               "tried": tried, "ok": bool(options),
               "fetched_at": time.strftime("%Y-%m-%d %H:%M", time.localtime(fetched)) if got else None,
               "cached_min": round((time.time() - fetched) / 60) if cached else None,  # None = all live now
               "source": "+".join(dict.fromkeys(r["source"] for r in replies)) if got else None,
               "search_url": options[0]["search_url"] if options else None,
               "error": None if options else "; ".join("%s: %s" % (t["source"], t["error"]) for t in tried),
               "options": options}
        if dropped:
            res["dropped_other_airport"] = dropped
        for k in ("from_grid", "grid_price"):
            if trip.get(k):
                res[k] = trip[k]
        for r in replies:  # extras from booking.py
            for k in ("airline_min", "nonstop_min", "nonstop_airline"):
                if r.get(k) is not None:
                    res[k] = r[k]
        return res

    # flexible dates: one Kiwi grid per route (trips with the same route and dates share it)
    groups = {}
    for t in trips:
        if t.get("flex_days") and trip_kind(t["legs"]) != "multi-city":
            groups.setdefault((t.get("route") or t["legs"][0]["to"], tuple(l["date"] for l in t["legs"])), []).append(t)
    grid_mod = load("kiwi_grid") if groups else None
    order = sorted((i for i in range(len(trips)) if not trips[i]["placeholder"]),
                   key=lambda i: trip_kind(trips[i]["legs"]) != "multi-city")  # multi-city first
    with ThreadPoolExecutor(max(1, len(trips) + 12 * len(groups))) as ex:
        cal_names = [CALENDARS[c] for c in named if c in CALENDARS]
        grids = [ex.submit(flex_trips, g, plan, grid_mod, deadline, cal_names, mods, a.fresh) for g in groups.values()]
        futs = {}
        for i in order:
            futs[i] = ex.submit(run_trip, trips[i])
            time.sleep(0.05)  # keep that start order in the source pools
        more = []
        for g, grp in zip(grids, groups.values()):
            try:
                new = g.result()
            except Exception as e:  # a bad grid or calendar reply: search the plan's own dates only
                print("  kiwi_grid  | flexible dates failed: %s: %s" % (type(e).__name__, str(e)[:100]), flush=True)
                new = [t for t in grp if t["placeholder"]]
            with lock:
                total[0] += len(new)
            more += [ex.submit(run_trip, t) for t in new]
        results = [futs[i].result() for i in range(len(trips)) if i in futs] + [f.result() for f in more]

    data = {k: v for k, v in plan.items() if k != "trips"}
    data["searched_at"] = time.strftime("%Y-%m-%d %H:%M")
    data["run_seconds"] = round(time.time() - start, 1)
    stats = {}
    for name, secs, ok in STATS:
        s = stats.setdefault(name, {"calls": 0, "ok": 0, "secs": []})
        s["calls"] += 1
        s["ok"] += ok
        s["secs"].append(round(secs, 1))
    data["source_stats"] = stats
    data["trips"] = results
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", errors="replace") as f:  # an odd character in a name never costs the saved results
        json.dump(data, f, indent=1, ensure_ascii=False, default=str)

    print("\n%-34s %14s  %-15s %s" % ("Trip", "Cheapest", "Cheapest site", "Airline / stops / sellers"))
    for t in results:
        if t["ok"]:
            o = t["options"][0]
            print("%-34s %14s  %-15s %s / stops %s / %d seller%s" % (
                t["label"][:34], "%s %s" % (o.get("currency") or "", "{:,.2f}".format(o["price_total"])),
                SITE.get(o["source"], o["source"])[:15], ", ".join(o.get("airlines") or ["?"])[:40], o.get("stops"),
                len(o["sellers"]), "" if len(o["sellers"]) == 1 else "s"))
        else:
            print("%-34s %14s  %s" % (t["label"][:34], "none", t["error"][:80]))
    print("\nSource timings (live requests):")
    for name, s in stats.items():
        print("  %-13s %2d calls, %2d with prices, %.1f-%.1f s each" % (name, s["calls"], s["ok"], min(s["secs"]), max(s["secs"])))
    print("\nSaved %s (%.1f s)" % (out, time.time() - start), flush=True)
    sys.stderr.flush()
    os._exit(0)  # don't wait for a hung request thread; everything is saved


if __name__ == "__main__":
    main()
