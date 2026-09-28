"""Build the ticket page (one HTML file for the Artifact tool) from results.json.

Usage: python scripts/make_page.py results.json page.html [--max 6] [--file]
--file: a complete HTML file to open in a browser (the same page wrapped as a Claude artifact wraps it).

Also prints the price matrix and the picks as text, for the chat reply: cheapest (plus any airline or dates at the
same price), best route, best nonstop, and the best price on each named airline (plan "airlines" / "prefer").
Rules it applies:
- Flags: an airport change inside a connection, on an open-jaw trip a flight between its two away cities (domestic
  hop: KIX in, HND out, a KIX–HND flight; connecting through a trip city on a multi-city trip is normal), a
  flight in a lower cabin than asked (mixed cabin), or a Google round-trip price no other site confirmed (its return
  isn't shown and it can be 10-18% low). Flagged options are shown with a note and kept out of the picks and the
  matrix (the matrix adds the flagged price with a * when it is cheaper). When every option is flagged, the picks
  use the ones missing the fewest wishes, then with the fewest flags, and show the note.
- A route where no option is in the asked cabin all the way gets "No first class found for the whole trip on this
  route; the options mix cabins." above the picks, and its picks "not first class the whole way".
- No price to compare at all: "No prices came back for <trip> (<legs>) ...: <each source's answer>." (chat and page).
- A Google round trip lists only the outbound; its unknown return counts like the outbound when comparing stops and
  flying time with full itineraries (but it is never "nonstop").
- A preferred airline counts only when it flies the long flight of every known leg (the operating airline, so a
  Qatar plane sold as JAL counts as Qatar); otherwise it is "feeder only" when it flies only short connections inside
  legs (KWI–DOH before the long flight), else "only part of the trip (DOH–MCT)".
- An airline fare-calendar price with no flights behind it (older results.json only; search.py now drops them) is
  flagged: never a pick or a clean matrix price.
- Near-identical options (same airlines and stops, price within 1%) are shown once, plus the shortest one.
- Sellers: each ticket lists every site that sells those flights (price + Book link), cheapest first; the option price is
  the cheapest exact seller. Converted prices (Flyin SAR) show as "≈" and never win a pick when an exact
  price exists (an option with converted prices only is flagged). "Best price per airline" = airline → price → site.
- Only real prices (finite numbers) in the plan's currency are compared: an option priced in another currency (not
  converted) is shown with a note but never a pick or a matrix price. Ties break on the exact price (57.70 beats 58).
- A long flight flown by another airline than the one selling it is named in the picks ("Qatar Airways (LHR–DOH flown
  by British Airways)"); in the per-airline list that airline's row says what it is sold as.
- Customer wishes (optional plan fields, kept in results.json): "nonstop": true; "max_layover_h": N (hours); per leg
  "depart_after" / "depart_before" / "arrive_before": "HH:MM" (local times, as the sources give them); "bags": N
  (checked bags per person; 0 = carry-on is fine): fewer known bags = "cabin bag only (you need 2 checked bags)", a
  weight (46 kg) is not counted, no bag data = the note "bags not stated: check before booking". An option that
  misses one is flagged "doesn't match your wish: out leaves 11:55 (you asked after 17:00)" like other flags (kept out
  of the picks; no times = "times not given", not a match). A pick line says which wishes it meets; when nothing
  matches, a plain line says so, "Closest options" lists up to 3 (fewest missed wishes, other kinds of miss first)
  with what each misses, and the picks show the best non-matching option with its note.
- "Best price per airline" (no airline named): the 8 cheapest airlines, each at its best clean option (else the one
  missing the fewest wishes, with its note); a mix of airlines counts under the one flying the longest flight.
- A connection over 8 h gets a plain note "a 17h 35m wait in AUH (out)" on picks and cards (not a flag; with a
  max_layover_h wish the wish says it). "Budget airline: checked bags usually cost extra" only in economy/premium.
- A Google round trip kept out of the picks only because its return isn't shown (maybe also a missed wish, said) and
  cheaper than the Cheapest pick: up to 2 lines "Cheaper on Google Flights (return flights not shown; confirm the
  total there): ...". A Google Flights price says "(its Book button lists the airline/agency sellers)": Google lists
  sellers, it doesn't sell.
- One-way trips that chain (SYD→KUL, then KUL→AUH: separate legs of one journey) get picks per route
  ("Cheapest (SYD → KUL)"); one-way choices from the same place keep one set of picks.
- One name per airline code (NAMES) everywhere (a raw "Oman Av (SAOG)" too; only a "(sold as …)" name stays as
  given; Booking's nonstop airline via its airline_min code). A seller is listed once per pick line. Matrix rows in date order; a cell names the airport(s) its price is
  for when the trips differ (LHR / LGW / STN). A leg leaving 00:00-04:59 gets "just after midnight: the night of
  <previous day>". Bags from the cheapest seller's fare, else from another seller of the same flights within 1% of its
  price, named ("Almosafer: cabin bag only"); a dearer fare's bags are never used (older results without per-seller
  bags: the option's). {"checked": N} or one per leg, "unit" kg/pc; 0 = "cabin bag only"; anything else is ignored.
"""
import argparse, base64, json, math, os, re, time
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlparse
from urllib.request import urlopen
try:
    import arabic  # scripts/arabic.py: the page's text in Arabic (the page switches between the two)
except ImportError:
    arabic = None

SITES = {"google": "Google Flights", "booking": "Booking.com", "matrix": "ITA Matrix", "almosafer": "Almosafer",
         "qatar": "Qatar Airways", "kuwaitairways": "Kuwait Airways", "flyin": "Flyin", "cleartrip": "Cleartrip",
         "kiwi": "Kiwi.com", "kayak": "KAYAK", "skyscanner": "Skyscanner"}  # the last two: older results.json
NAMES = {  # one name per airline code, used everywhere (sources name the same airline differently, or give the code)
    "KU": "Kuwait Airways", "J9": "Jazeera Airways", "QR": "Qatar Airways", "EK": "Emirates", "FZ": "flydubai",
    "EY": "Etihad Airways", "GF": "Gulf Air", "WY": "Oman Air", "OV": "SalamAir", "SV": "Saudia", "XY": "flynas",
    "F3": "flyadeal", "G9": "Air Arabia", "3L": "Air Arabia Abu Dhabi", "E5": "Air Arabia Egypt", "3O": "Air Arabia Maroc",
    "ME": "MEA (Middle East Airlines)", "RJ": "Royal Jordanian", "MS": "EgyptAir", "NP": "Nile Air", "SM": "Air Cairo",
    "NE": "Nesma Airlines", "IF": "Fly Baghdad", "IA": "Iraqi Airways", "TK": "Turkish Airlines", "PC": "Pegasus",
    "VF": "AJet", "XQ": "SunExpress", "AI": "Air India", "IX": "Air India Express", "6E": "IndiGo", "SG": "SpiceJet",
    "QP": "Akasa Air", "PK": "Pakistan International Airlines", "PA": "airblue", "PF": "AirSial", "9P": "Fly Jinnah",
    "ER": "SereneAir", "BG": "Biman Bangladesh", "BS": "US-Bangla Airlines", "UL": "SriLankan Airlines",
    "RA": "Nepal Airlines", "PR": "Philippine Airlines", "5J": "Cebu Pacific", "MH": "Malaysia Airlines", "AK": "AirAsia",
    "D7": "AirAsia X", "TG": "Thai Airways", "FD": "Thai AirAsia", "SQ": "Singapore Airlines", "TR": "Scoot",
    "GA": "Garuda Indonesia", "VN": "Vietnam Airlines", "CX": "Cathay Pacific", "NH": "ANA", "JL": "Japan Airlines",
    "KE": "Korean Air", "OZ": "Asiana Airlines", "CA": "Air China", "MU": "China Eastern", "CZ": "China Southern",
    "HU": "Hainan Airlines", "ET": "Ethiopian Airlines", "KQ": "Kenya Airways", "AT": "Royal Air Maroc", "TU": "Tunisair",
    "AH": "Air Algerie", "BA": "British Airways", "LH": "Lufthansa", "LX": "SWISS", "OS": "Austrian Airlines",
    "AF": "Air France", "KL": "KLM", "AZ": "ITA Airways", "A3": "Aegean Airlines", "IB": "Iberia", "UX": "Air Europa",
    "SK": "SAS", "LO": "LOT Polish Airlines", "DE": "Condor", "W6": "Wizz Air", "5W": "Wizz Air Abu Dhabi",
    "FR": "Ryanair", "U2": "easyJet", "AA": "American Airlines", "UA": "United Airlines", "DL": "Delta Air Lines",
    "AC": "Air Canada", "KC": "Air Astana", "VA": "Virgin Australia", "EN": "Air Dolomiti"}
RANK = {"economy": 1, "premium": 2, "business": 3, "first": 4}
BUDGET = {"J9", "XY", "G9", "3L", "PC", "FZ", "OV", "F3", "VF", "E5", "3O", "W6", "5W", "FR", "U2", "9P", "5J", "AK", "D7",
          "FD", "TR"}  # checked bags usually extra
AIRPORTS = dict(x.split(" ", 1) for x in (  # the city beside an airport code on the page; a code not here shows alone
    "KWI Kuwait|DXB Dubai|DWC Dubai World Central|AUH Abu Dhabi|SHJ Sharjah|RKT Ras Al Khaimah|DOH Doha|BAH Bahrain|"
    "MCT Muscat|SLL Salalah|RUH Riyadh|JED Jeddah|DMM Dammam|MED Madinah|AHB Abha|TIF Taif|TUU Tabuk|ELQ Qassim|"
    "AMM Amman|BEY Beirut|BGW Baghdad|BSR Basra|EBL Erbil|NJF Najaf|ISU Sulaymaniyah|DAM Damascus|CAI Cairo|"
    "SPX Cairo Sphinx|HBE Alexandria|SSH Sharm El Sheikh|HRG Hurghada|LXR Luxor|IKA Tehran|MHD Mashhad|"
    "IST Istanbul|SAW Istanbul Sabiha|ESB Ankara|ADB Izmir|AYT Antalya|TZX Trabzon|BJV Bodrum|DLM Dalaman|"
    "DEL Delhi|BOM Mumbai|BLR Bengaluru|MAA Chennai|HYD Hyderabad|COK Kochi|TRV Thiruvananthapuram|CCJ Kozhikode|"
    "CNN Kannur|IXE Mangaluru|CCU Kolkata|AMD Ahmedabad|GOI Goa|GOX Goa Mopa|LKO Lucknow|ATQ Amritsar|JAI Jaipur|"
    "KHI Karachi|LHE Lahore|ISB Islamabad|PEW Peshawar|SKT Sialkot|MUX Multan|DAC Dhaka|CGP Chittagong|ZYL Sylhet|"
    "CMB Colombo|KTM Kathmandu|MLE Malé|BKK Bangkok|DMK Bangkok Don Mueang|HKT Phuket|KUL Kuala Lumpur|SIN Singapore|"
    "CGK Jakarta|DPS Bali|MNL Manila|CEB Cebu|SGN Ho Chi Minh City|HAN Hanoi|HKG Hong Kong|TPE Taipei|PEK Beijing|"
    "PKX Beijing Daxing|PVG Shanghai Pudong|SHA Shanghai Hongqiao|CAN Guangzhou|CTU Chengdu|NRT Tokyo Narita|"
    "HND Tokyo Haneda|KIX Osaka Kansai|ITM Osaka Itami|NGO Nagoya|FUK Fukuoka|CTS Sapporo|ICN Seoul Incheon|"
    "GMP Seoul Gimpo|TAS Tashkent|ALA Almaty|NQZ Astana|GYD Baku|TBS Tbilisi|EVN Yerevan|LHR London Heathrow|"
    "LGW London Gatwick|STN London Stansted|LTN London Luton|LCY London City|MAN Manchester|BHX Birmingham|"
    "EDI Edinburgh|GLA Glasgow|DUB Dublin|CDG Paris CDG|ORY Paris Orly|NCE Nice|LYS Lyon|FRA Frankfurt|MUC Munich|"
    "BER Berlin|DUS Düsseldorf|HAM Hamburg|CGN Cologne|AMS Amsterdam|BRU Brussels|ZRH Zurich|GVA Geneva|VIE Vienna|"
    "PRG Prague|BUD Budapest|WAW Warsaw|FCO Rome|MXP Milan Malpensa|LIN Milan Linate|VCE Venice|NAP Naples|MAD Madrid|"
    "BCN Barcelona|AGP Málaga|LIS Lisbon|OPO Porto|ATH Athens|SKG Thessaloniki|JMK Mykonos|JTR Santorini|"
    "CPH Copenhagen|ARN Stockholm|OSL Oslo|HEL Helsinki|SVO Moscow Sheremetyevo|DME Moscow Domodedovo|"
    "LED St Petersburg|SJJ Sarajevo|TIV Tivat|TGD Podgorica|LCA Larnaca|MLA Malta|OTP Bucharest|SOF Sofia|"
    "BEG Belgrade|ZAG Zagreb|ADD Addis Ababa|NBO Nairobi|JNB Johannesburg|CPT Cape Town|DAR Dar es Salaam|"
    "ZNZ Zanzibar|EBB Entebbe|CMN Casablanca|RAK Marrakesh|TUN Tunis|ALG Algiers|KRT Khartoum|LOS Lagos|ACC Accra|"
    "SEZ Seychelles|MRU Mauritius|JFK New York JFK|EWR Newark|LGA New York LaGuardia|IAD Washington Dulles|"
    "DCA Washington Reagan|BOS Boston|ORD Chicago|ATL Atlanta|MIA Miami|MCO Orlando|DFW Dallas|IAH Houston|"
    "LAX Los Angeles|SFO San Francisco|SEA Seattle|DTW Detroit|PHL Philadelphia|YYZ Toronto|YUL Montreal|"
    "YVR Vancouver|MEX Mexico City|GRU São Paulo|SYD Sydney|MEL Melbourne|BNE Brisbane|PER Perth|AKL Auckland"
).split("|"))
# pictures: assets/airports.tsv (code, latitude, longitude, town; OurAirports, public domain) and assets/world.txt
# (Natural Earth 110m land as one SVG path, x = longitude + 180, y = 90 - latitude) draw the route maps;
# assets/logos/<code>.png are Google Flights' airline logos, each downloaded once
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
POS = {}
if os.path.exists(os.path.join(ASSETS, "airports.tsv")):
    for _l in open(os.path.join(ASSETS, "airports.tsv"), encoding="utf-8"):
        _c, _la, _lo, _town = _l.rstrip("\n").split("\t")
        POS[_c] = (float(_la), float(_lo), _town)
LAND = open(os.path.join(ASSETS, "world.txt")).read() if os.path.exists(os.path.join(ASSETS, "world.txt")) else ""
STAR = ("* Not a normal ticket (airport change, a hop between your trip's cities, a lower cabin on one flight, separate "
        "tickets, a converted price only, a Google round-trip price no other site confirmed, or an airline "
        "fare-calendar price without flights), or not what you asked for (nonstop, times, waits); kept out of the picks.")


def money(p, cur, exact=False):
    """Whole units, or up to 2 decimals with exact=True (7,354.60 vs 7,355 shows which site is cheaper)."""
    txt = "{:,.2f}".format(p) if exact and round(p, 2) != round(p) else "{:,.0f}".format(p)
    return "%s %s" % ("KD" if cur == "KWD" else cur, txt)


def sellers(o):
    """Every seller of an option, cheapest first (older results.json: the option itself plus its "also" list)."""
    if o.get("sellers"):
        return o["sellers"]
    one = [{"source": o.get("source"), "seller": o.get("seller"), "price_total": o["price_total"],
            "currency": o.get("currency"), "converted": False, "booking_url": o.get("search_url")}]
    return one + [dict(x, currency=o.get("currency"), converted=False, booking_url=None) for x in o.get("also") or []]


def seller_label(s):
    """'Almosafer', 'Qatar Airways (direct)', 'Booking.com (travel agency)', 'BUDGETAIR via KAYAK'."""
    site_name, sel = SITES.get(s.get("source"), s.get("source") or "?"), s.get("seller") or ""
    if not sel or sel == site_name:
        return site_name
    if sel.lower().startswith(site_name.lower().split()[0]):
        return sel
    return "%s via %s" % (sel, site_name)


def best_seller(o):  # the cheapest exact seller (a converted one only when there is nothing else)
    ss = sellers(o)
    return next((s for s in ss if not s.get("converted")), ss[0])


TWO_OW = "2 one-way fares"  # a seller's note (Almosafer, Flyin): outbound and return are two one-way fares


def seller_note(o):
    """The cheapest seller's own note, in plain words: '2 one-way fares (two bookings)', 'Almosafer: ...'; "" for none
    or an airline fare-calendar note (the ticket card says that one)."""
    top = best_seller(o) if o.get("sellers") else {}
    n = top.get("note") if isinstance(top.get("note"), str) else ""
    if n == TWO_OW:
        return TWO_OW + " (two bookings)"
    return "" if not n or n.startswith("the airline's own") else "%s: %s" % (seller_label(top), n)


def two_one_ways(t, o):
    """A trip out and back sold as two one-way fares (tickets 2, the cheapest seller's note '2 one-way fares'): two
    bookings, but no connection between them to miss, so a note, not a 'separate tickets' flag."""
    return (o.get("tickets") or 1) == 2 and len(t["legs"]) == 2 and seller_note(o).startswith(TWO_OW)


def when_txt(t):
    """The trip label, plus its dates only when the label doesn't already give them ('Istanbul IST one way, 5 Dec')."""
    return t["label"] if re.search(r"\d", str(t["label"])) else "%s, %s" % (t["label"], dates_key(t))


def seller_price(s, cur):
    p = money(s["price_total"], s.get("currency") or cur, True)
    return ("≈ %s (converted from %s)" % (p, s.get("converted_from") or "another currency")) if s.get("converted") else p


def day(d):  # "2026-12-19" -> "19 Dec"
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%-d %b")
    except Exception:
        return d or "?"


def dur(m):
    return "%dh %02dm" % (m // 60, m % 60) if m else ""


def stops_txt(s):
    return "?" if s is None else "Nonstop" if s == 0 else "%d stop%s" % (s, "" if s == 1 else "s")


def dates_key(t):
    return " → ".join(day(l["date"]) for l in t["legs"])


def route_key(t):
    if t.get("route"):
        return t["route"]
    legs = t["legs"]
    if t.get("kind") == "round trip":
        return "%s ⇄ %s" % (legs[0]["from"], legs[0]["to"])
    return ", ".join("%s–%s" % (l["from"], l["to"]) for l in legs)


def airports(t):  # every airport of a trip but home: "NRT", "KIX/HND" for open-jaw, "IST/CDG/LHR" for 4 legs
    legs = t["legs"]
    return "/".join(dict.fromkeys(a for l in legs for a in (l["from"], l["to"]) if a != legs[0]["from"]))


def site(url, source):
    host = urlparse(url or "").netloc
    for key, name in [("google", "Google Flights"), ("booking", "Booking.com"), ("itasoftware", "ITA Matrix"),
                      ("skyscanner", "Skyscanner")]:
        if key in host:
            return name
    return SITES.get(source, host or "the site")


def src(t, o):  # the cheapest site for an option (trips merge several sources); Google Flights only lists sellers
    k = o.get("source") or t.get("source")
    if o.get("price_total") is None:
        return SITES.get(k, k)
    top = best_seller(o)
    return seller_label(top) + (" (its Book button lists the airline/agency sellers)" if top.get("source") == "google" else "")


def days(t):  # days away: first leg date to last leg date
    try:
        a, b = (datetime.strptime(l["date"][:10], "%Y-%m-%d") for l in (t["legs"][0], t["legs"][-1]))
        return (b - a).days
    except Exception:
        return 0


# ---------- checks on one option ----------
def code(f):  # the airline flying it: codeshare "op" when known, else the flight-number prefix
    return (f.get("op") or (f.get("flight") or "")[:2]).upper()


def cal_code(o):  # an airline's own calendar fare (no flights listed): its airline code
    return (o.get("codes") or [None])[0] if not o.get("flights") else None


def leg_flights(o):
    """The option's flights split per trip leg (Google round trips: the outbound only)."""
    fl, out, i = o.get("flights") or [], [], 0
    for s in o.get("stops") or []:
        if s is None or i + s + 1 > len(fl):
            break
        out.append(fl[i:i + s + 1])
        i += s + 1
    return out


def flags(data, t, o):
    """Reasons an option is not a normal ticket."""
    legs = t["legs"]
    # open-jaw (in at one city, home from another): a flight between those two added inside a leg is a hop
    # (Japan: KIX in, HND out, a KIX–HND flight). Connecting through a trip city on a multi-city trip is normal.
    jaw = {legs[0].get("to"), legs[1].get("from")} if len(legs) == 2 and legs[0].get("to") != legs[1].get("from") else None
    want = RANK.get((data.get("cabin") or "economy").lower(), 1)
    out = []
    for leg in leg_flights(o):
        for a, b in zip(leg, leg[1:]):
            if a.get("to") and b.get("from") and a["to"] != b["from"]:
                out.append("airport change %s→%s" % (a["to"], b["from"]))
        if len(leg) > 1 and jaw:
            out += ["domestic hop %s–%s" % (f["from"], f["to"]) for f in leg if {f.get("from"), f.get("to")} == jaw]
    low = [f for f in o.get("flights") or [] if RANK.get(f.get("cabin"), want) < want]
    if low:
        out.append("mixed cabin: %s on %s" % (low[0]["cabin"], ", ".join("%s–%s" % (f["from"], f["to"]) for f in low)))
    if (o.get("tickets") or 1) > 1 and not two_one_ways(t, o):  # out/back on 2 one-way fares: a note (more_notes)
        out.append("separate tickets (%d): a missed connection is your risk" % o["tickets"])
    if o.get("converted_only"):
        out.append("converted price only (≈ from %s); check the total on the site"
                   % (sellers(o)[0].get("converted_from") or "another currency"))
    if (o.get("currency") or plan_cur(data)).upper() != plan_cur(data):
        out.append("priced in %s, not %s: not compared with the other prices" % (o["currency"], plan_cur(data)))
    if cal_code(o):
        out.append("fare calendar price only: flights and each flight's cabin not shown; check on the airline's site")
    if t.get("kind") == "round trip" and None in (o.get("stops") or []) and {s.get("source") for s in sellers(o)} == {"google"}:
        out.append(GOOGLE_RT)  # Google RT can be 10-18% low
    miss = wish(data, t, o)[1]
    if miss:
        out.append("doesn't match your wish: " + ", ".join(miss))
    return list(dict.fromkeys(out))


# ---------- the customer's wishes, overnight departures, bags ----------
def when(s):  # "2026-10-15 18:10" -> datetime; None when not given
    try:
        return datetime.strptime(str(s)[:16], "%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return None


def hhmm(v):  # a wish time "7:05" -> "07:05"; anything else None (ignored)
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", v if isinstance(v, str) else "")
    return "%02d:%s" % (int(m[1]), m[2]) if m and int(m[1]) < 24 and int(m[2]) < 60 else None


def leg_word(t, i):  # "out " / "back " on a two-leg trip home again, "leg 2 " on others, "" on a one way
    legs = t["legs"]
    if len(legs) == 1:
        return ""
    return ("out ", "back ")[i] if len(legs) == 2 and legs[0].get("from") == legs[1].get("to") else "leg %d " % (i + 1)


def max_wait(data):  # plan "max_layover_h" in hours; None when not set or not a positive number
    try:
        h = float(data.get("max_layover_h"))
    except (TypeError, ValueError):
        return None
    return h if math.isfinite(h) and h > 0 else None


def wants_nonstop(data):
    return data.get("nonstop") in (True, "true", "yes")


def wish(data, t, o):
    """(met, missed) for the customer's wishes: plan "nonstop": true, "max_layover_h": N, and per leg
    "depart_after" / "depart_before" / "arrive_before" "HH:MM" (local times, as the sources give them). An option
    without the times needed is not a match ("times not given")."""
    met, miss, legs, stops = [], [], leg_flights(o), o.get("stops") or []
    n = len(t["legs"])
    if wants_nonstop(data):
        more = [(i, s) for i, s in enumerate(stops[:n]) if s]
        if more:
            miss.append("%shas %d stop%s (you asked nonstop)" % (leg_word(t, more[0][0]), more[0][1], "" if more[0][1] == 1 else "s"))
        elif len(stops) < n or None in stops[:n]:
            miss.append("flights not given (you asked nonstop)")
        else:
            met.append("nonstop")
    mx = max_wait(data)
    if mx:
        waits, unknown = connections(o)
        unknown = unknown or len(legs) < n
        worst = max(w[:2] for w in waits) if waits else None
        if worst and worst[0] > mx * 60:
            miss.append("a %s wait in %s (you asked at most %g h)" % (dur(int(worst[0])), worst[1], mx))
        elif unknown:
            miss.append("times not given (you asked waits of at most %g h)" % mx)
        else:
            met.append("longest wait %s (at most %g h)" % (dur(int(worst[0])), mx) if worst else "no connections")
    for i, l in enumerate(t["legs"]):
        for key, word in (("depart_after", "after"), ("depart_before", "before"), ("arrive_before", "by")):
            w, leave = hhmm(l.get(key)), key.startswith("depart")
            limit = when("%s %s" % (str(l.get("date"))[:10], w)) if w else None
            if not limit:
                continue
            f = (legs[i][0] if leave else legs[i][-1]) if i < len(legs) and legs[i] else {}
            dt, ask = when(f.get("dep" if leave else "arr")), "%s%s %s" % (leg_word(t, i), word, w)
            if not dt:
                miss.append("times not given (you asked %s)" % ask)
                continue
            got = "%s%s %s%s" % (leg_word(t, i), "leaves" if leave else "lands", dt.strftime("%H:%M"),
                                 "" if dt.date() == limit.date() else dt.strftime(" on %-d %b"))
            ok = dt >= limit if key == "depart_after" else dt <= limit
            (met if ok else miss).append("%s (%s%s %s)" % (got, "" if ok else "you asked ", word, w))
    need = bags_wanted(data)
    pcs = [k for k, u in bag_list(o) or [] if u == "pc" or k == 0]  # a weight (46 kg) doesn't say how many bags
    if need and pcs:
        few = min(pcs)
        if few < need:
            miss.append("%s (you need %d checked bag%s)" % (bag_word(few, "pc"), need, "" if need == 1 else "s"))
        elif len(pcs) == len(bag_list(o)):
            met.append(bag_word(few, "pc"))
    return met, miss


def connections(o):
    """([(minutes, airport, leg index)] for each connection with both times, True when a time is missing)."""
    waits, unknown = [], False
    for i, leg in enumerate(leg_flights(o)):
        for a, b in zip(leg, leg[1:]):
            x, y = when(a.get("arr")), when(b.get("dep"))
            if x and y:
                waits.append(((y - x).total_seconds() // 60, a.get("to") or "?", i))
            else:
                unknown = True
    return waits, unknown


def long_waits(data, t, o):
    """'a 17h 35m wait in AUH (out)' for each connection over 8 h: a plain note, not a flag (a max_layover_h wish
    says it instead)."""
    if max_wait(data):
        return []
    return ["a %s wait in %s%s" % (dur(int(m)), ap, " (%s)" % leg_word(t, i).strip() if leg_word(t, i) else "")
            for m, ap, i in connections(o)[0] if m > 8 * 60]


def wishes_asked(data):
    """The plan's wishes in words ("nonstop; out after 18:00"); "" when there are none."""
    asked = ["nonstop"] if wants_nonstop(data) else []
    asked += ["waits of at most %g h" % max_wait(data)] if max_wait(data) else []
    for t in data["trips"]:
        for i, l in enumerate(t["legs"]):
            for key, word in (("depart_after", "after"), ("depart_before", "before"), ("arrive_before", "by")):
                asked += ["%s%s %s" % (leg_word(t, i), word, hhmm(l.get(key)))] if hhmm(l.get(key)) else []
    asked += [bag_word(bags_wanted(data), "pc")] if bags_wanted(data) else []
    return "; ".join(dict.fromkeys(asked))


def unmatched(data):
    """A plain line when the plan has wishes and no option meets them all; else ""."""
    asked = wishes_asked(data)
    if not asked or not all_options(data) or any(not wish(data, t, o)[1] for t, o in all_options(data)):
        return ""
    return "Nothing found matches your wishes (%s); the picks below don't: see each note." % asked


def closest(data):
    """When nothing fits every wish: 'Closest options:' and up to 3 lines, the options missing the fewest wishes
    (then with the fewest other flags, then cheapest), one per kind of miss, each saying what it misses."""
    if not unmatched(data):
        return []
    out, more, seen = [], [], set()
    for t, o in sorted(all_options(data), key=lambda x: (len(wish(data, *x)[1]), len(x[1].get("flags") or []),
                                                         x[1]["price_total"])):
        miss = wish(data, t, o)[1]
        kind = tuple(re.findall(r"\(you [^)]*\)", "; ".join(miss)))  # "(you asked nonstop)", "(you asked after 18:00)"
        other = [f for f in o.get("flags") or [] if not f.startswith("doesn't match your wish")]
        txt = "  %s — %s, %s (%s) — cheapest at %s — misses: %s%s" % (
            money(o["price_total"], o.get("currency") or plan_cur(data), True), when_txt(t), airline_txt(data, t, o),
            stops_line(o), src(t, o), ", ".join(miss), " (note: %s)" % "; ".join(other) if other else "")
        if txt not in out + more:  # the same airline and price at another time reads the same: once
            (more if kind in seen else out).append(txt)
        seen.add(kind)
    return ["Closest options (each misses a wish):"] + (out + more)[:3]  # other kinds of miss first


def night(t, o):
    """A leg leaving 00:00-04:59: 'back leaves 02:40 on Sat 7 Nov, just after midnight: the night of Fri 6 Nov'."""
    out = []
    for i, leg in enumerate(leg_flights(o)):
        dt = when(leg[0].get("dep")) if leg else None
        if dt and dt.hour < 5:
            out.append("%sleaves %s, just after midnight: the night of %s" % (
                leg_word(t, i), dt.strftime("%H:%M on %a %-d %b"), (dt - timedelta(days=1)).strftime("%a %-d %b")))
    return out


def bag_seller(o):
    """(bags, seller): the cheapest seller's own bags; if it states none, those of another seller of the same flights
    within 1% of its price (the same fare: Google 74 and Almosafer 74 cabin bag only); a dearer fare's bags are never
    borrowed. Older results (no sellers, or sellers without bags): the option's own. (None, None) when not stated."""
    ss = o.get("sellers") or []
    if not any("bags" in s for s in ss):
        return o.get("bags"), None
    top = best_seller(o)
    near = [s for s in ss if s.get("bags") is not None and abs(s["price_total"] - top["price_total"]) <= top["price_total"] * 0.01]
    s = top if top.get("bags") is not None else min(near, key=lambda s: abs(s["price_total"] - top["price_total"]), default=None)
    return (s["bags"], None if s is top else s) if s else (None, None)


def bag_list(o):
    """Checked bags of the fare (bag_seller): {"checked": N} or one per leg, "unit" kg/pc.
    [(N, "kg" or "pc")] per leg; None when not given or not readable."""
    b = bag_seller(o)[0]
    out = []
    for x in b if isinstance(b, list) else [b]:
        k = x.get("checked") if isinstance(x, dict) else None
        if isinstance(k, bool) or not isinstance(k, (int, float)) or not math.isfinite(k) or k < 0:
            return None
        if k > 3 and x.get("unit") not in ("kg", "pc"):  # no unit and a big number: kilos or pieces? not said
            return None
        out.append((k, "kg" if x.get("unit") == "kg" else "pc"))
    return out or None


def bag_word(k, unit):
    return "cabin bag only" if k == 0 else "%g kg checked bag" % k if unit == "kg" else \
        "%d checked bag%s" % (k, "" if k == 1 else "s")


def bags_wanted(data):  # plan "bags": checked bags per person wanted; 0 or not set = no bag wish
    b = 0 if isinstance(data.get("bags"), bool) else num(data.get("bags"))
    return b if b > 0 else None


def bags_txt(o):
    """'cabin bag only', '1 checked bag', '30 kg checked bag', 'out 1 checked bag, back cabin bag only'; "" when not
    given or not readable. Bags stated by another seller than the cheapest are named: 'Almosafer: cabin bag only'."""
    each = [bag_word(k, u) for k, u in bag_list(o) or []]
    if len(set(each)) <= 1:
        txt = each[0] if each else ""
    else:
        txt = ", ".join("%s %s" % ("out" if i == 0 else "back", x) if len(each) == 2 else "leg %d: %s" % (i + 1, x)
                        for i, x in enumerate(each))
    by = bag_seller(o)[1]
    return "%s: %s" % (seller_label(by), txt) if txt and by else txt


def per_leg(vals, unknown):
    """Per-leg values; a Google round trip's unknown return counts like its outbound (fair against full itineraries)."""
    vals = vals or [None]
    first = vals[0] if vals[0] is not None else unknown
    return [first if v is None else v for v in vals]


def n_stops(o):
    return sum(per_leg(o.get("stops"), 9))


def fly_min(o):
    return sum(per_leg(o.get("duration_min"), 99999))


def long_flights(leg, home):
    """The long part of a leg: the longest flight when minutes are known, else the flights not touching home."""
    if len(leg) == 1:
        return leg
    if all(f.get("min") for f in leg):
        return [max(leg, key=lambda f: f["min"])]
    return [f for f in leg if home not in (f.get("from"), f.get("to"))] or leg


def flies_long(o, c, home):
    legs = leg_flights(o)
    return bool(legs) and all(any(code(f) == c for f in long_flights(leg, home)) for leg in legs)


# ---------- picks ----------
def plan_cur(data):
    return (data.get("currency") or "KWD").upper()


def finite(o):  # a real price (not missing, NaN or infinite)
    p = o.get("price_total")
    return isinstance(p, (int, float)) and math.isfinite(p)


def usable(data, o):  # a real price in the plan's currency: the only prices compared (picks, matrix)
    return finite(o) and (o.get("currency") or plan_cur(data)).upper() == plan_cur(data)


def all_options(data):
    return [(t, o) for t in data["trips"] for o in t.get("options") or [] if usable(data, o)]


def clean(opts):
    """Options without flags; if none is clean, the ones missing the fewest wishes (each missed wish says "(you …"),
    then with the fewest flags."""
    ok = [x for x in opts if not x[1].get("flags")]
    if ok or not opts:
        return ok or opts
    n = lambda x: (sum(f.count("(you ") for f in x[1]["flags"]), len(x[1]["flags"]))
    few = min(map(n, opts))
    return [x for x in opts if n(x) == few]


def best_price(opts):
    """Cheapest; among options within 1% of it, fewer stops and a shorter journey win (5,780 in 13 h beats 5,779 in 18 h)."""
    low = min(x[1]["price_total"] for x in opts)
    near = [x for x in opts if x[1]["price_total"] <= low * 1.01]
    return min(near, key=lambda x: (n_stops(x[1]), fly_min(x[1]), x[1]["price_total"], days(x[0])))


def picks(data):
    """Cheapest overall (at equal price: fewer stops, then shorter flying time, then fewer days), and the best route:
    fewest stops, then shortest flying time, within 15% of the cheapest and the same trip type."""
    opts = clean(all_options(data))
    if not opts:
        return None, None
    cheap = min(opts, key=lambda x: (round(x[1]["price_total"], 2), n_stops(x[1]), fly_min(x[1]), days(x[0])))
    limit = cheap[1]["price_total"] * 1.15
    near = [x for x in opts if x[1]["price_total"] <= limit and len(x[0]["legs"]) == len(cheap[0]["legs"])]
    best = min(near, key=lambda x: (n_stops(x[1]), fly_min(x[1]), round(x[1]["price_total"], 2), days(x[0])))
    return cheap, best


def ties(data, cheap):
    """Other airlines or dates at the same price as the cheapest (to the fils: 58.00 is not the same as 57.70)."""
    t0, o0 = cheap
    seen, out = {(tuple(o0.get("airlines") or []), dates_key(t0))}, []
    for t, o in clean(all_options(data)):
        k = (tuple(o.get("airlines") or []), dates_key(t))
        if round(o["price_total"], 2) == round(o0["price_total"], 2) and k not in seen:
            seen.add(k)
            out.append("%s, %s (%s)" % (", ".join(k[0]) or "?", k[1], airports(t)))
    return out


GOOGLE_RT = "return not shown; price not confirmed by another site"


def google_cheaper(data):
    """Up to 2 lines under the picks: a Google round trip cheaper than the Cheapest pick, kept out of the picks only
    because its return isn't shown (and maybe a missed wish, said), fitting ones first, one per airline."""
    cheap = picks(data)[0]
    if not cheap or journey_legs(data):
        return []
    rows = [(t, o) for t, o in all_options(data) if GOOGLE_RT in (o.get("flags") or []) and
            o["price_total"] < cheap[1]["price_total"] and
            all(f == GOOGLE_RT or f.startswith("doesn't match your wish") for f in o["flags"])]
    out, seen = [], set()
    for t, o in sorted(rows, key=lambda x: (len(x[1]["flags"]), x[1]["price_total"])):
        miss = wish(data, t, o)[1]
        if tuple(o.get("airlines") or []) not in seen:
            seen.add(tuple(o.get("airlines") or []))
            out.append("Cheaper on Google Flights (return flights not shown; confirm the total there): %s — %s, %s (%s)%s" % (
                money(o["price_total"], o.get("currency") or plan_cur(data), True), airline_txt(data, t, o), when_txt(t),
                stops_line(o), " — misses: " + ", ".join(miss) if miss else ""))
    return out[:2]


def budget_note(data, cheap):  # economy / premium only (a budget airline's business fare includes bags)
    if cabin(data) not in ("economy", "premium"):
        return ""
    same = [f for t, o in clean(all_options(data)) if round(o["price_total"], 2) == round(cheap[1]["price_total"], 2)
            for f in o.get("flights") or []]
    return "Budget airline: checked bags usually cost extra." if any(code(f) in BUDGET for f in same) else ""


def nonstop(data):
    """Cheapest option with every leg known and nonstop; else Booking.com's cheapest nonstop (nonstop_min) as a
    pseudo-option. A Google round trip (return unknown) never counts."""
    opts = [x for x in clean(all_options(data)) if x[1].get("stops") and all(s == 0 for s in x[1]["stops"])]
    if opts:
        return best_price(opts)
    ns = [t for t in data["trips"] if t.get("nonstop_min")]
    if not ns:
        return None
    t = min(ns, key=lambda t: t["nonstop_min"])
    url = next((o.get("search_url") for o in t.get("options") or [] if o.get("source") == "booking"), t.get("search_url"))
    return t, {"price_total": t["nonstop_min"], "currency": plan_cur(data), "source": "booking",
               "airlines": [t.get("nonstop_airline") or "Airline on the Booking.com page"], "search_url": url,
               "stops": [0] * len(t["legs"]), "note": "Nonstop, flights on the Booking.com link"}


def airline_name(data, c):
    if c in NAMES:
        return NAMES[c]
    for t in data["trips"]:
        for a in t.get("airline_min") or []:
            if a.get("code") == c:
                return a.get("name") or c
    for t, o in all_options(data):
        fl = o.get("flights") or []
        if (fl and len(o.get("airlines") or []) == 1 and all(code(f) == c for f in fl)) or cal_code(o) == c:
            return o["airlines"][0]
    return NAMES.get(c, c)


def main_airline(o, home):
    """The one airline that flies the long flight of every leg (None when mixed or unknown)."""
    if cal_code(o):
        return cal_code(o)
    cs = [c for c in dict.fromkeys(code(f) for f in o.get("flights") or []) if flies_long(o, c, home)]
    return cs[0] if len(cs) == 1 else None


def per_airline(data):
    """Best price per airline: [(name, (t, o) or None, note)]. Named airlines (plan airlines/prefer) when given,
    else the 8 cheapest airlines found, each at its best clean option (else the one missing the fewest wishes, shown
    with its note). A mix of airlines counts under the one flying the longest flight. Price = the cheapest exact seller."""
    named = [c.upper() for c in (data.get("airlines") or []) + (data.get("prefer") or [])]
    if named:
        return [(name, x, note) for c, name, x, note in preferred(data)]
    each = {}
    for t, o in all_options(data):
        c = main_airline(o, t["legs"][0]["from"]) or longest_airline(o)
        if c:
            each.setdefault(c, []).append((t, o))
    best = {c: min(clean(xs), key=lambda x: x[1]["price_total"]) for c, xs in each.items()}
    return [(airline_name(data, c) + sold_as(c, *x), x, "")
            for c, x in sorted(best.items(), key=lambda kv: kv[1][1]["price_total"])[:8]]


def longest_airline(o):
    """The airline flying the longest flight of the whole itinerary (minutes known), for a mix of airlines."""
    fl = [f for f in o.get("flights") or [] if isinstance(f.get("min"), (int, float))]
    return code(max(fl, key=lambda f: f["min"])) if fl else None


def sold_as(c, t, o):
    """' (sold as Qatar Airways)' when airline c flies the long flights under another airline's flight numbers."""
    home = t["legs"][0]["from"]
    other = [f for leg in leg_flights(o) for f in long_flights(leg, home)
             if code(f) == c and (f.get("flight") or "")[:2].upper() != c]
    return " (sold as %s)" % ", ".join(o.get("airlines") or ["?"]) if other else ""


def airline_txt(data, t, o):
    """'Qatar Airways (LHR–DOH flown by British Airways)': a long flight flown by another airline than the seller's."""
    home = t["legs"][0]["from"]
    by = list(dict.fromkeys("%s–%s flown by %s" % (f.get("from"), f.get("to"), airline_name(data, code(f)))
                            for leg in leg_flights(o) for f in long_flights(leg, home)
                            if f.get("op") and code(f) != (f.get("flight") or "")[:2].upper()))
    return ", ".join(o.get("airlines") or ["?"]) + (" (%s)" % "; ".join(by) if by else "")


def preferred(data):
    """Per named airline (plan "airlines" and "prefer"): (code, name, pick or None, note). It must fly the long flight
    of every known leg."""
    out = []
    for c in dict.fromkeys(x.upper() for x in (data.get("airlines") or []) + (data.get("prefer") or [])):
        name, opts = airline_name(data, c), all_options(data)
        seen = [x for x in opts if any(c in (code(f), (f.get("flight") or "")[:2].upper()) for f in x[1].get("flights") or [])]
        real = [x for x in seen if flies_long(x[1], c, x[0]["legs"][0]["from"])]
        if real:
            out.append((c, name, best_price(clean(real)), ""))
        elif seen:
            hops = sorted({"%s–%s" % (f["from"], f["to"]) for t, o in seen for f in o.get("flights") or [] if code(f) == c})
            # "feeder" only when every flight of it is a short connection inside a leg (KWI–DOH before the long flight)
            feeder = all(len(leg) > 1 and f not in long_flights(leg, t["legs"][0]["from"])
                         for t, o in seen for leg in leg_flights(o) for f in leg if code(f) == c)
            where = ", ".join(hops[:4])
            out.append((c, name, None, "Feeder only: flies just the short connecting flight%s (%s), not the long flight."
                        % ("s" if len(hops) > 1 else "", where) if feeder else
                        "Only part of the trip (%s): no ticket in these results has it on every leg." % where))
        else:
            am = [(a["price_total"], t) for t in data["trips"] for a in t.get("airline_min") or []
                  if a.get("code") == c and a.get("price_total")]
            note = "Not in these results."
            if am:
                p, t = min(am, key=lambda x: x[0])
                note = ("Not in the listed flights; Booking.com shows it from %s on %s (may be only a connecting flight)."
                        % (money(p, plan_cur(data)), t["label"]))
            out.append((c, name, None, note))
    return out


def plain_error(t):
    """Short words for the page instead of raw errors (which may hold URLs or keys)."""
    words = []
    for x in t.get("tried") or [{"source": t.get("source") or "?", "error": t.get("error") or ""}]:
        err = (x.get("error") or "").lower()
        why = ("timed out" if "timed out" in err else "busy (rate-limited)" if "rate-limit" in err or "blocked" in err
               else "no flights listed" if "no flights" in err or "no results" in err or "nothing" in err
               else "not used for this trip type" if "not supported" in err else "source unavailable")
        words.append("%s: %s" % (SITES.get(x.get("source"), x.get("source")), why))
    return " · ".join(words)


def nothing_lines(data):
    """No price to compare at all: one plain line per trip, what was searched and what each source answered."""
    if all_options(data):
        return []
    return ['No prices came back for %s (%s), unknown, not "no flights": %s.' % (
        when_txt(t), ", ".join("%s–%s" % (l["from"], l["to"]) for l in t["legs"]),
        "prices only in another currency, not compared" if any(finite(o) for o in t.get("options") or [])
        else plain_error(t)) for t in data["trips"]]


def matrix(data):
    """cells[(dates, route)] = {"clean": (t, o), "flagged": (t, o), "common": airports in every trip}: the cheapest
    of each kind; None = no price. Rows in date order."""
    dates, routes, cells, when_ = [], [], {}, {}
    common = set.intersection(*[{a for l in t["legs"] for a in (l.get("from"), l.get("to"))} for t in data["trips"]] or [set()])
    for t in data["trips"]:
        d, r = dates_key(t), route_key(t)
        dates += [d] if d not in dates else []
        routes += [r] if r not in routes else []
        when_.setdefault(d, [str(l.get("date")) for l in t["legs"]])
        for o in t.get("options") or []:
            if not usable(data, o):
                continue
            slot = cells.get((d, r)) or {"clean": None, "flagged": None, "common": common}
            k = "flagged" if o.get("flags") else "clean"
            if not slot[k] or o["price_total"] < slot[k][1]["price_total"]:
                slot[k] = (t, o)
            cells[(d, r)] = slot
        cells.setdefault((d, r), None)
    return sorted(dates, key=when_.get), routes, cells


def place(t, common):
    """The airports of a trip that the other trips don't share ("STN" for London STN ⇄ Kuwait next to LHR, LGW)."""
    own = [a for l in t["legs"] for a in (l.get("from"), l.get("to")) if a not in common]
    return "/".join(dict.fromkeys(own)) or airports(t)


def cell_parts(c, cur):
    """(price text, airport, source, cheaper flagged price) for one matrix cell."""
    main = c["clean"] or c["flagged"]
    t, o = main
    txt = money(o["price_total"], o.get("currency") or cur) + ("*" if main is c["flagged"] else "")
    extra = ""
    ap = place(t, c.get("common") or set())
    if c["clean"] and c["flagged"] and c["flagged"][1]["price_total"] < o["price_total"]:
        other = place(c["flagged"][0], c.get("common") or set())
        extra = "%s*%s" % (money(c["flagged"][1]["price_total"], cur), "" if other == ap else " " + other)
    k = best_seller(o).get("source") or o.get("source") or t.get("source")
    return txt, ap, SITES.get(k, k), extra


def num(x):  # a count that may come as text ("2"); unreadable = 0
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def pax(data):
    kids = data.get("child_ages")
    parts = [("adult", num(data.get("adults", 1))), ("child", len(kids) if kids else num(data.get("children", 0))),
             ("infant", num(data.get("infants", 0)))]
    txt = ", ".join("%d %s%s" % (n, w, "" if n == 1 else ("ren" if w == "child" else "s")) for w, n in parts if n)
    if kids:
        w = "child" if len(kids) == 1 else "children"
        txt = txt.replace(w, "%s (age%s %s)" % (w, "" if len(kids) == 1 else "s", ", ".join(map(str, kids))), 1)
    return "%s · %s" % (txt, data.get("cabin", "economy"))


def stops_line(o):
    if cal_code(o) and not o.get("note"):
        return "Flights not listed (the airline's own fare calendar)"
    return o.get("note") or " / ".join(stops_txt(s) if s is not None or i == 0 else "flights %snot shown" % (
        "back " if i == 1 else "") for i, s in enumerate(o.get("stops") or [None]))


def pick_line(data, label, t, o):
    top = best_seller(o)
    ss = [s for s in sellers(o) if s != top]  # by value: an option without "sellers" builds new dicts on each call
    others = "; also " + ", ".join("%s %s" % (seller_label(s), seller_price(s, o.get("currency", "KWD"))) for s in ss[:4]) \
        if ss else ""
    note = " (note: %s)" % "; ".join(o["flags"]) if o.get("flags") else ""
    return "%s: %s — %s, %s (%s) — cheapest at %s%s%s%s" % (
        label, money(o["price_total"], o.get("currency", "KWD"), True), when_txt(t),
        airline_txt(data, t, o), stops_line(o), src(t, o), others, note, "".join(" — " + x for x in more_notes(data, t, o)))


def more_notes(data, t, o):
    """Wishes the option meets, the seller's note (2 one-way fares), a leg leaving just after midnight, its bags:
    one short note each."""
    met, miss = wish(data, t, o)
    bags = bags_txt(o) or ("bags not stated: check before booking" if bags_wanted(data) else "")
    bags = "" if bags in met else bags  # "fits your wishes: 2 checked bags" already says it
    mixed = "not %s the whole way" % CABIN_WORD.get(cabin(data), cabin(data)) \
        if route_key(t) in no_cabin_routes(data) and not in_cabin(data, o) else ""
    return ([mixed] if mixed else []) + (["fits your wishes: " + "; ".join(met)] if met and not miss else []) + \
        ([seller_note(o)] if seller_note(o) else []) + night(t, o) + long_waits(data, t, o) + ([bags] if bags else [])


# ---------- the asked cabin not sold on a route ----------
CABIN_WORD = {"economy": "economy", "premium": "premium economy", "business": "business class", "first": "first class"}


def cabin(data):
    return (data.get("cabin") or "economy").lower()


def in_cabin(data, o):  # every flight with a known cabin is in the asked cabin
    return all(f.get("cabin") not in RANK or f["cabin"] == cabin(data) for f in o.get("flights") or [])


def no_cabin_routes(data):
    """Routes where no priced option is in the asked cabin all the way (every one mixes cabins)."""
    has = {}
    for t in data["trips"]:
        opts = [o for o in t.get("options") or [] if usable(data, o)]
        if opts:
            has[route_key(t)] = has.get(route_key(t), False) or any(in_cabin(data, o) for o in opts)
    return [r for r, ok in has.items() if not ok]


def cabin_lines(data):
    """'No first class found for the whole trip on this route; the options mix cabins.' per such route."""
    many = len({route_key(t) for t in data["trips"]}) > 1
    return ["No %s found for the whole trip on %s; the options mix cabins." % (
        CABIN_WORD.get(cabin(data), cabin(data)), ("the route " + r) if many else "this route") for r in no_cabin_routes(data)]


def collapse(opts):
    """Near-identical options (same airlines, stops and flags, price within 1%) shown once: the cheapest, plus the
    shortest when shorter. The kept card says how many similar ones were hidden. Airline order does not matter."""
    bands = []  # [key, [members]]
    for o in sorted(opts, key=lambda o: (o["price_total"], fly_min(o))):
        k = (tuple(sorted(o.get("airlines") or [])), tuple(o.get("stops") or []), bool(o.get("flags")))
        b = next((b for b in bands if b[0] == k and o["price_total"] <= b[1][0]["price_total"] * 1.01), None)
        if b:
            b[1].append(o)
        else:
            bands.append([k, [o]])
    out = []
    for _, m in bands:
        short = min(m, key=fly_min)
        keep = [m[0]] + ([short] if fly_min(short) < fly_min(m[0]) else [])
        out += [dict(o, similar=len(m) - len(keep)) if i == 0 else o for i, o in enumerate(keep)]
    return out


# ---------- HTML ----------
CSS = """
:root{--bg:#eef2f7;--card:#fff;--ink:#0f1e30;--muted:#5b6b7f;--line:#d9e1ea;--accent:#1559b7;--accent-ink:#fff;
--soft:#e5eefa;--good:#127a4a;--good-soft:#e1f4ea;--warn:#9a5600;--back:#c96a05;--leg2:#7b4bc4;--leg3:#0f8a8a;
--sea:#e3edf7;--land:#cbd8e5;--land-edge:#b2c2d3;--tile:#fff;--stub:#f6f9fc;--stop:#b91c1c;--stop-soft:#fdeceb;--glow:0 4px 14px rgba(21,89,183,.32);
--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;--sans:"Public Sans",system-ui,-apple-system,"Segoe UI",sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#0b121b;--card:#131e2b;
--ink:#e4ebf3;--muted:#93a3b7;--line:#263447;--accent:#6aabf5;--accent-ink:#08121e;--soft:#182b42;--good:#5fcf94;
--good-soft:#12301f;--warn:#f2b35e;--back:#f0a04b;--leg2:#b393f0;--leg3:#4fd0cf;--sea:#0f1b29;--land:#23364c;
--land-edge:#30496a;--tile:#f3f6fa;--stub:#162333;--stop:#ff6b6b;--stop-soft:#3a1c1e;--glow:0 4px 18px rgba(106,171,245,.28)}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#0b121b;--card:#131e2b;--ink:#e4ebf3;--muted:#93a3b7;--line:#263447;
--accent:#6aabf5;--accent-ink:#08121e;--soft:#182b42;--good:#5fcf94;--good-soft:#12301f;--warn:#f2b35e;--back:#f0a04b;
--leg2:#b393f0;--leg3:#4fd0cf;--sea:#0f1b29;--land:#23364c;--land-edge:#30496a;--tile:#f3f6fa;--stub:#162333;--stop:#ff6b6b;--stop-soft:#3a1c1e;--glow:0 4px 18px rgba(106,171,245,.28)}
body{background:var(--bg);color:var(--ink);font:15px/1.5 var(--sans);margin:0}
.wrap{max-width:1080px;margin:0 auto;padding:28px 16px 56px;display:grid;grid-template-columns:minmax(0,1fr);gap:36px}
h1{font-size:clamp(1.7rem,3.4vw,2.4rem);line-height:1.12;margin:0;text-wrap:balance;letter-spacing:-.015em}
h2{font-size:1.25rem;line-height:1.25;margin:0;text-wrap:balance}
.sub,.note{color:var(--muted);margin:0}.note{font-size:.85rem}.warn{color:var(--warn);font-size:.85rem;margin:0}
.mono{font-family:var(--mono);font-variant-numeric:tabular-nums}
.eyebrow{font-size:.72rem;letter-spacing:.09em;text-transform:uppercase;color:var(--muted);font-weight:700}
header.hero{background:var(--card);border:1px solid var(--line);border-radius:18px;overflow:hidden;display:grid;
grid-template-columns:minmax(0,1fr) minmax(0,1.15fr)}
.hero .txt{padding:26px 24px;display:grid;gap:12px;align-content:center}
.hero .pic{background:var(--sea);display:grid;align-items:center}.hero .pic svg{width:100%;height:auto;display:block}
.chips{display:flex;flex-wrap:wrap;gap:6px}
.chip{font-size:.78rem;padding:3px 10px;border-radius:99px;background:var(--soft);font-weight:600}
.lead{margin:0;padding:10px 14px;border-inline-start:4px solid var(--good);background:var(--good-soft);border-radius:0 10px 10px 0;
font-weight:600}
.block{display:grid;gap:14px}.head{display:grid;gap:2px}
.picks{display:grid;gap:22px}.pick{display:grid;gap:8px}
.pickhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 12px;padding-inline:4px}.pickhead .note{flex-basis:100%}
.wins{display:flex;flex-wrap:wrap;gap:6px;flex-basis:100%;margin-bottom:4px}.win{font-size:.78rem;font-weight:700;padding:3px 10px;border-radius:99px;background:var(--good-soft);color:var(--good);border:1px solid var(--good)}.win.rank{color:var(--accent);border-color:var(--accent);background:var(--soft)}.win.none{color:var(--stop);border-color:var(--stop);background:var(--stop-soft)}
.pick:first-child .ticket{border:2px solid var(--good)}
.sort{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-top:8px}.sort span{font-size:.84rem;color:var(--muted);margin-inline-end:4px}
.sort button{font:600 .84rem var(--sans);color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:99px;
padding:7px 14px;cursor:pointer}.sort button:hover{border-color:var(--accent)}
.sort button[aria-pressed=true]{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
.sort button:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
.airline,.air{display:flex;align-items:center;gap:10px;font-weight:700;min-width:0}.logos{display:flex;gap:4px;flex:none}
.logo{width:34px;height:34px;border-radius:9px;background:var(--tile) center/80% no-repeat;border:1px solid var(--line);
flex:none;display:inline-grid;place-items:center;font:700 .66rem var(--mono);color:#3b4a5c;font-style:normal}
.logo.sm{width:22px;height:22px;border-radius:6px;font-size:.55rem}
.price{display:grid;gap:2px}.big{font-family:var(--mono);font-size:1.9rem;font-weight:600;line-height:1.1;font-variant-numeric:tabular-nums}
.scope{font-size:.8rem;font-weight:700;color:var(--good)}
svg.map{display:block;width:100%;height:auto;border-radius:12px;background:var(--sea)}
svg.map .land{fill:var(--land);stroke:var(--land-edge);stroke-width:.7px}
svg.map .fly{fill:none;stroke:var(--c);stroke-width:2.4px;stroke-linecap:round;vector-effect:non-scaling-stroke}
svg.map .fly.t1{stroke-dasharray:7 5}
svg.map circle{fill:var(--card);stroke:var(--ink);stroke-width:1.6px;vector-effect:non-scaling-stroke}
svg.map circle.home{fill:var(--ink)}svg.map circle.end{fill:var(--accent);stroke:var(--card)}
svg.map circle.stop{fill:var(--stop);stroke:var(--card);stroke-width:2px}
svg.map .pl{font-family:var(--sans);font-weight:600;fill:var(--muted)}
svg.map .pin{stroke:var(--muted);stroke-width:1px;vector-effect:non-scaling-stroke}
svg.map text{fill:var(--ink);font-family:var(--mono);font-weight:700;paint-order:stroke;stroke:var(--sea);
stroke-linejoin:round}svg.map text:not([text-anchor]){text-anchor:middle}
.hero svg.map{border-radius:0}.hero svg.map .fly{stroke-width:1.8px;stroke-dasharray:none;opacity:.85}
.t0{--c:var(--accent)}.t1{--c:var(--back)}.t2{--c:var(--leg2)}.t3{--c:var(--leg3)}
.tag{font-size:.66rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:2px 7px;border-radius:5px;
color:var(--card);background:var(--c)}
.also{display:grid;gap:6px;margin:0;padding:12px 16px;border-radius:12px;background:var(--card);border:1px solid var(--line)}
.also div{font-size:.88rem;color:var(--muted)}.also b{color:var(--ink)}
.tip{padding:10px 14px;border:1px dashed var(--warn);border-radius:10px;color:var(--ink)}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:14px;background:var(--card)}
table{border-collapse:collapse;width:100%;font-size:.9rem}
th,td{padding:10px 14px;border-bottom:1px solid var(--line);text-align:start;white-space:nowrap;vertical-align:middle}
tr:last-child td{border-bottom:0}th{font-size:.74rem;color:var(--muted);font-weight:700;letter-spacing:.05em;text-transform:uppercase}
td small{color:var(--muted);font-weight:400;display:block;font-family:var(--sans);font-size:.76rem}
td.low{background:var(--good-soft)}td.low a{color:var(--good)}
td a{color:inherit;text-decoration:none;display:inline-flex;align-items:center;gap:8px;font-weight:600}
td a:hover{text-decoration:underline}td a:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
td .who{display:flex;align-items:center;gap:10px;font-weight:600}
.trip{display:grid;gap:12px;scroll-margin-top:16px}.trip>div:first-child{display:grid;gap:2px}
.tickets{display:grid;gap:14px}
.ticket{background:var(--card);border:1px solid var(--line);border-radius:16px;overflow:hidden}
.ticket>.top{display:grid;grid-template-columns:minmax(0,1fr) 250px}
.ticket>summary{list-style:none;cursor:pointer}.ticket>summary::-webkit-details-marker{display:none}
.ticket>summary:focus-visible{outline:3px solid var(--accent);outline-offset:-3px;border-radius:16px}
.ticket[open]{border-color:var(--accent)}.ticket[open] .body{grid-template-columns:minmax(0,1fr)}
.ticket[open] .body>svg.map{display:none}
.hint{justify-self:start;display:inline-flex;align-items:center;gap:8px;font-size:.84rem;font-weight:700;color:var(--accent);
padding:6px 14px;border:1px solid var(--line);border-radius:99px;background:var(--soft)}
.hint::after{content:"";width:6px;height:6px;border-right:2px solid;border-bottom:2px solid;transform:translateY(-2px) rotate(45deg)}
.ticket[open] .hint::after{transform:translateY(2px) rotate(-135deg)}
summary:hover .hint{border-color:var(--accent)}.hint .c,.ticket[open] .hint .o{display:none}.ticket[open] .hint .c{display:inline}
.more{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:22px;padding:18px;border-top:2px dashed var(--line);
align-items:start}.trail{display:grid;gap:18px}.tleg{display:grid;gap:8px}
.steps{list-style:none;margin:0;padding:0;display:grid}
.steps li{position:relative;padding-inline-start:28px}
.steps li::before{content:"";position:absolute;inset-inline-start:7px;top:0;bottom:0;border-inline-start:2px solid var(--c)}
.steps li:first-child::before{top:.8em}.steps li:last-child::before{bottom:auto;height:.8em}
.steps .pt::after,.steps .stop::after{content:"";position:absolute;inset-inline-start:1px;top:.35em;width:10px;height:10px;
border-radius:50%;background:var(--card);border:2px solid var(--c)}
.steps .pt{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 10px}
.steps .pt .tm{font-family:var(--mono);font-weight:600;font-size:1.05rem;font-variant-numeric:tabular-nums}
.steps .pt .ap{color:var(--muted);font-size:.86rem}.steps .pt .ap b,.stop .ap b{font-family:var(--mono);color:var(--ink);margin-inline-end:4px}
.hop{padding-block:10px;font-size:.82rem;color:var(--muted);display:flex;flex-wrap:wrap;align-items:center;gap:4px 8px}
.hop b{font-family:var(--mono);color:var(--ink)}
.steps .stop{padding-block:6px}.steps .stop::before{border-inline-start-style:dashed}
.steps .stop::after{background:var(--stop);border-color:var(--card);width:14px;height:14px;inset-inline-start:-1px;top:1.05em}
.stop .box{background:var(--stop-soft);border:1px solid var(--stop);border-radius:10px;padding:8px 12px;display:grid;gap:2px}
.stop .sh{display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 8px;font-weight:700}
.stop .sh .n{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--stop)}
.stop .st{font-size:.84rem;color:var(--muted);font-variant-numeric:tabular-nums}.stop .st b{color:var(--ink);font-family:var(--mono)}
.stop .w{font-weight:700;color:var(--ink);white-space:nowrap}.stop.long .w{color:var(--warn)}.ticket .big{font-size:1.5rem;white-space:nowrap}
.ticket .main{padding:16px 18px;display:grid;gap:12px;align-content:start;min-width:0}
.ticket .body{display:grid;grid-template-columns:minmax(0,1fr) 210px;gap:18px;align-items:center}
.ticket .stub{padding:16px 18px;border-inline-start:2px dashed var(--line);background:var(--stub);display:grid;gap:8px;
align-content:center;justify-items:end;text-align:end}
.legs{display:grid;gap:14px}.leg{display:grid;gap:8px}.leg+.leg{border-top:1px solid var(--line);padding-top:14px}
.leghead{display:flex;align-items:center;gap:8px;font-size:.82rem;color:var(--muted)}
.route{display:grid;grid-template-columns:minmax(0,1fr) minmax(90px,1.4fr) minmax(0,1fr);gap:14px;align-items:center}
.end .tm{font-family:var(--mono);font-size:1.3rem;font-weight:600;font-variant-numeric:tabular-nums;line-height:1.15}
.end .ap{font-size:.82rem;color:var(--muted)}.end .ap b{font-family:var(--mono);color:var(--ink);margin-right:4px}
.end.to{text-align:end}
.plus{font-size:.7rem;color:var(--warn);margin-left:3px;vertical-align:super;font-weight:700}
.mid{display:grid;gap:5px;text-align:center;font-size:.76rem;color:var(--muted)}
.mid.direct span:first-child{color:var(--good);font-weight:700}
.bar{position:relative;height:2px;background:var(--c);display:flex;justify-content:space-evenly;align-items:center;margin-inline:4px 8px}
.bar::after{content:"\\2708\\FE0E";position:absolute;right:-12px;top:50%;transform:translateY(-54%);font-size:14px;color:var(--c)}
.bar i{width:10px;height:10px;border-radius:50%;background:var(--stop);border:2px solid var(--card)}
.via{font-size:.8rem;color:var(--muted)}.via .long{color:var(--warn);font-weight:700}
.ticket .main .note,.ticket .main .warn{margin:0}
.badge{font-size:.72rem;padding:2px 8px;border-radius:99px;background:var(--soft);color:var(--accent);font-weight:700}
a.book{background:var(--accent);color:var(--accent-ink);text-decoration:none;padding:11px 18px;border-radius:10px;
font-weight:800;font-size:.95rem;justify-self:stretch;text-align:center;box-shadow:var(--glow)}
.picks a.book{font-size:1.05rem;padding:14px 20px}
a.book::after,a.buy::after{content:"\\2197";display:inline-block;margin-inline-start:6px}
[dir=rtl] a.book::after,[dir=rtl] a.buy::after{transform:scaleX(-1)}
a.book:hover,a.buy:hover{filter:brightness(1.08)}a.book:focus-visible,a.buy:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
.sellers{grid-column:1/-1;background:var(--soft);border-top:1px solid var(--line);padding:12px 18px 14px;display:grid;
grid-template-columns:repeat(auto-fill,minmax(min(290px,100%),1fr));gap:8px}
.sellers .eyebrow{grid-column:1/-1;color:var(--accent)}
.seller{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:0 12px;background:var(--card);
border:1px solid var(--line);border-radius:10px;padding:8px;padding-inline-start:12px;font-size:.85rem}
.seller .who{min-width:0;font-weight:700}.seller .p{font-family:var(--mono);font-variant-numeric:tabular-nums;grid-column:1}
.seller a.buy{grid-row:1/3;grid-column:2}
.seller.top{border:2px solid var(--good);color:var(--good)}.seller.conv{color:var(--muted)}
a.buy{background:var(--accent);color:var(--accent-ink);text-decoration:none;font-weight:800;font-size:.86rem;padding:9px 14px;
border-radius:8px;white-space:nowrap;box-shadow:var(--glow)}
.seller:not(.top) a.buy{background:var(--card);color:var(--accent);box-shadow:inset 0 0 0 2px var(--accent)}
a.mini{display:inline-block;color:var(--accent);background:var(--card);font-weight:800;text-decoration:none;font-size:.86rem;
padding:8px 14px;border-radius:8px;white-space:nowrap;box-shadow:inset 0 0 0 2px var(--accent)}
a.mini::after{content:"\\2197";display:inline-block;margin-inline-start:6px}[dir=rtl] a.mini::after{transform:scaleX(-1)}
a.mini:hover{text-decoration:none;filter:brightness(1.08)}a.mini:focus-visible{outline:3px solid var(--ink);outline-offset:2px}
.fail{background:var(--card);border:1px dashed var(--line);border-radius:12px;padding:14px 16px;color:var(--muted)}
.part{padding-top:8px;border-top:2px solid var(--line)}
[hidden]{display:none!important}.switch{max-width:1080px;margin:0 auto;padding:16px 16px 0;display:flex;justify-content:flex-end;gap:8px}
.switch button{font:600 .82rem var(--sans);color:var(--ink);background:var(--card);border:1px solid var(--line);
border-radius:99px;padding:7px 14px;cursor:pointer}.switch button:hover{border-color:var(--accent)}
.switch button:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.switch button[lang=ar]{font-family:"IBM Plex Sans Arabic",var(--sans)}
main[lang=ar]{--sans:"IBM Plex Sans Arabic","Public Sans",system-ui,sans-serif;font-family:var(--sans)}
main[lang=ar] .eyebrow,main[lang=ar] .tag,main[lang=ar] th,main[lang=ar] .stop .sh .n{letter-spacing:0;text-transform:none}
main[lang=ar] .eyebrow{font-size:.8rem}main[lang=ar] .tag{font-size:.74rem}main[lang=ar] th{font-size:.8rem}
main[lang=ar] .big,main[lang=ar] .mono,main[lang=ar] td a,main[lang=ar] .steps .tm{font-family:var(--sans);font-variant-numeric:tabular-nums}
.plus{unicode-bidi:isolate;direction:ltr}
[dir=rtl] .bar::after{right:auto;left:-12px;transform:translateY(-54%) scaleX(-1)}
[dir=rtl] .lead{border-radius:10px 0 0 10px}svg.map{direction:ltr}
@media (max-width:860px){header.hero{grid-template-columns:1fr}.ticket .body{grid-template-columns:1fr}.more{grid-template-columns:1fr}.more svg.map{order:-1}
.ticket .body svg.map{max-width:360px}}
@media (max-width:600px){.ticket>.top{grid-template-columns:1fr}.ticket .stub{border-inline-start:0;border-top:2px dashed var(--line);
justify-items:start;text-align:start}.ticket .stub a.book{justify-self:stretch;text-align:center}.big{font-size:1.6rem}
.end .tm{font-size:1.1rem}}
"""


def town(c):  # the city beside a code: "Tokyo Narita"; else the airport's town from assets/airports.tsv; else ""
    return AIRPORTS.get(c) or (POS.get(c) or (0, 0, ""))[2]


def city(c):  # "Tokyo Narita (NRT)"; a code nobody knows: "ZZQ"
    return "%s (%s)" % (town(c), c) if town(c) else str(c or "?")


def named(c):  # "AUH (Abu Dhabi)": the code, its place in brackets
    return "%s (%s)" % (c, town(c)) if town(c) else str(c or "?")


def logo_file(c):
    """An airline's logo (Google Flights' 70px picture) in assets/logos, downloaded once; None when not available."""
    p = os.path.join(ASSETS, "logos", c + ".png")
    if not os.path.exists(p):
        try:
            png = urlopen("https://www.gstatic.com/flights/airline_logos/70px/%s.png" % c, timeout=5).read()
            time.sleep(0.3)  # one logo at a time, never a burst
        except Exception:
            return None
        if png[:4] != b"\x89PNG":
            return None
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(png)
    return p


def logo(c, name, small=False):
    """An airline's logo tile (its picture comes once per page, from logo_css); no logo: its code in the tile."""
    cls = "logo sm" if small else "logo"
    if c and re.fullmatch(r"[A-Z0-9]{2}", c) and logo_file(c):
        return '<i class="%s lg-%s" role="img" aria-label="%s"></i>' % (cls, c, escape(name))
    return '<i class="%s" aria-hidden="true">%s</i>' % (cls, escape((c or name or "?")[:2].upper()))


def logo_css(html):  # each logo used on the page, once, as a picture inside the page (the viewer loads nothing)
    return "".join(".lg-%s{background-image:url(data:image/png;base64,%s)}" % (
        c, base64.b64encode(open(logo_file(c), "rb").read()).decode())
        for c in sorted(set(re.findall(r'class="logo(?: sm)? lg-([A-Z0-9]{2})"', html))))


def al_pairs(o):
    """[(airline code or None, name)] for the option's airlines (for their logos)."""
    al = [a for a in o.get("airlines") or [] if isinstance(a, str)]
    by_name = {v: k for k, v in NAMES.items()}
    cs = o.get("codes") if isinstance(o.get("codes"), list) and len(o["codes"]) == len(al) else \
        list(dict.fromkeys(str(f.get("flight") or "")[:2].upper() for f in o.get("flights") or [] if isinstance(f, dict)))
    return [(by_name.get(re.sub(r" \(.*", "", a)) or (str(cs[i]).upper() if len(cs) == len(al) else None), a)  # "(sold as …)"
            for i, a in enumerate(al)]


def airline_row(o, cls="air"):  # logos + names: "[EY] Etihad Airways"
    ps = al_pairs(o)
    return '<div class="%s"><span class="logos">%s</span><span>%s</span></div>' % (
        cls, "".join(logo(c, n) for c, n in ps[:3]), escape(", ".join(o.get("airlines") or ["Airline not shown"])))


def xy(c):  # an airport on the world drawing
    p = POS.get(c)
    return (p[1] + 180, 90 - p[0]) if p else None


def route_map(paths, ratio=1.8, size=0.046, cls="map"):
    """A drawn map: the land around the airports and each path (colour class, [airport codes]) as curved flights,
    left of the direction of travel (out and back on the same route bow apart). The first airport is home (filled),
    each path's last airport is ringed, stops are red dots, named first (they get the room). "" when a place is unknown."""
    paths = [(k, cs) for k, cs in paths if len(cs) > 1]
    pts = {c: xy(c) for _, cs in paths for c in cs}
    if not paths or None in pts.values():
        return ""
    if max(x for x, _ in pts.values()) - min(x for x, _ in pts.values()) > 180:  # across the Pacific: one piece
        pts = {c: (x + 360 if x < 180 else x, y) for c, (x, y) in pts.items()}
    xs, ys = [x for x, _ in pts.values()], [y for _, y in pts.values()]
    lw = {c: max(len(named(c)), len(c) + len(arabic.text(named(c)[len(c):])) if arabic else 0) * .58 for c in pts}
    # a label's width in font sizes: room for the English or the Arabic label, whichever is longer
    fs = 0
    for _ in range(4):  # the crop fits the points and their labels (the labels grow with the crop)
        lo, hi = min(x - lw[c] * fs / 2 for c, (x, _) in pts.items()), max(x + lw[c] * fs / 2 for c, (x, _) in pts.items())
        pad = max(4, 0.12 * max(hi - lo, max(ys) - min(ys)))
        x0, y0, w, h = lo - pad, min(ys) - pad - fs, hi - lo + 2 * pad, max(ys) - min(ys) + 2 * pad + fs * 1.6
        if w < h * ratio:
            x0, w = x0 - (h * ratio - w) / 2, h * ratio
        else:
            y0, h = y0 - (w / ratio - h) / 2, w / ratio
        fs = w * size
    out = ['<svg class="%s" viewBox="%.2f %.2f %.2f %.2f" role="img" aria-label="Route map: %s">' % (
        cls, x0, y0, w, h, escape("; ".join(" → ".join(cs) for _, cs in paths))),
        '<use href="#land" class="land"/><use href="#land" x="360" class="land"/><use href="#land" x="-360" class="land"/>']
    for k, cs in paths:
        d = "M%.2f %.2f" % pts[cs[0]]
        for a, b in zip(cs, cs[1:]):
            (ax, ay), (bx, by) = pts[a], pts[b]
            d += " Q%.2f %.2f %.2f %.2f" % ((ax + bx) / 2 + (by - ay) * .2, (ay + by) / 2 - (bx - ax) * .2, bx, by)
        out.append('<path class="fly %s" d="%s"/>' % (k, d))
    home, ends = paths[0][1][0], {cs[-1] for _, cs in paths} | {cs[0] for _, cs in paths}
    for c, (x, y) in pts.items():
        out.append('<circle class="%s" cx="%.2f" cy="%.2f" r="%.2f"/>' % (
            "home" if c == home else "end" if c in ends else "stop", x, y, fs * (.3 if c in ends else .28)))
    boxes, labels = [], ""
    for c, (x, y) in sorted(pts.items(), key=lambda p: (p[0] != home, p[0] in ends)):  # each label above its dot, else below, right, left…: inside the map, never on
        spot = None                 # another label; no room: the code alone; still none: the dot alone
        for place, bw in ((named(c)[len(c):], lw[c] * fs), ("", len(c) * .62 * fs)):
            for lx, ly, anchor, bx in ((x, y - fs * .6, "middle", x - bw / 2), (x, y + fs * 1.3, "middle", x - bw / 2),
                                       (x + fs * .55, y + fs * .35, "start", x + fs * .55),
                                       (x - fs * .55, y + fs * .35, "end", x - fs * .55 - bw),
                                       (x, y - fs * 1.7, "middle", x - bw / 2), (x, y + fs * 2.4, "middle", x - bw / 2),
                                       (x, y - fs * 2.9, "middle", x - bw / 2), (x, y + fs * 3.6, "middle", x - bw / 2)):
                if x0 <= bx and bx + bw <= x0 + w and y0 + fs <= ly <= y0 + h - fs * .2 and not any(
                        bx < b[0] + b[2] + fs * .3 and b[0] < bx + bw + fs * .3 and ly - fs * 1.1 < b[1] and b[1] - fs * 1.1 < ly
                        for b in boxes):
                    spot = (lx, ly, anchor, bx, bw, place)
                    break
            if spot:
                break
        if spot:
            lx, ly, anchor, bx, bw, place = spot
            boxes.append((bx, ly, bw))
            if abs(ly - y) > fs * 2:  # a label moved away from a crowd: a thin line back to its dot
                labels += '<line class="pin" x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f"/>' % (
                    x, y, x, ly - fs * .9 if ly > y else ly + fs * .15)
            labels += '<text x="%.2f" y="%.2f"%s>%s%s</text>' % (
                lx, ly, "" if anchor == "middle" else ' text-anchor="%s"' % anchor, escape(c),
                '<tspan class="pl">%s</tspan>' % escape(place) if place else "")
    out.append('<g font-size="%.2f" stroke-width="%.2f">%s</g></svg>' % (fs, fs * .28, labels))
    return "".join(out)


def option_paths(t, o):  # each leg the site listed, as flown: [("t0", ["KWI", "AUH", "NRT"]), ("t1", [...])]
    out = []
    for i in range(len(t["legs"])):
        p = leg_parts(o, i)
        if p:
            out.append(("t%d" % min(i, 3), [p[1]] + [s for s, _ in p[5]] + [p[3]]))
    return out


def long_day(d):  # "2026-12-19" -> "Sat 19 Dec"
    try:
        return datetime.strptime(d[:10], "%Y-%m-%d").strftime("%a %-d %b")
    except Exception:
        return d or "?"


def leg_tag(t, i):
    return leg_word(t, i).strip().capitalize() or "One way"


def tag(t, i):  # the coloured leg name: Out (blue) / Back (orange), the same colours as its line on the map
    return '<b class="tag t%d">%s</b>' % (min(i, 3), escape(leg_tag(t, i)))


def trip_route(t):  # "Kuwait (KWI) ⇄ Tokyo Narita (NRT)"; other trips leg by leg
    legs = t["legs"]
    if t.get("kind") == "round trip" and len(legs) == 2:
        return "%s ⇄ %s" % (city(legs[0]["from"]), city(legs[0]["to"]))
    return ", ".join("%s → %s" % (city(l["from"]), city(l["to"])) for l in legs)


def travellers(data):
    kids = data.get("child_ages")
    n = num(data.get("adults", 1)) + (len(kids) if kids else num(data.get("children", 0))) + num(data.get("infants", 0))
    return "%d traveller%s" % (n, "" if n == 1 else "s")


def scope(data, t):
    """What a price covers, said under every price: 'Whole trip, out and back · 4 travellers' / 'One way · 1 traveller'
    (a bare price next to 'Tokyo return' read as the flight back only)."""
    legs = t["legs"]
    what = "One way" if len(legs) == 1 else "Whole trip, out and back" if legs[-1]["to"] == legs[0]["from"] \
        else "Whole trip, all %d legs" % len(legs)
    return "%s · %s" % (what, travellers(data))


def leg_parts(o, i):
    """One leg as flown: (departure time, from, arrival time, to, days later, [(stop, wait minutes or None)], flight
    numbers, flying minutes); None when the site didn't list that leg (a Google round trip's return)."""
    fl = leg_flights(o)
    if i >= len(fl) or not fl[i]:
        return None
    fs, durs = fl[i], o.get("duration_min") or []
    dep, arr = when(fs[0].get("dep")), when(fs[-1].get("arr"))
    stops = [(a.get("to") or "?", (when(b.get("dep")) - when(a.get("arr"))).total_seconds() // 60
              if when(a.get("arr")) and when(b.get("dep")) else None) for a, b in zip(fs, fs[1:])]
    return ((fs[0].get("dep") or "")[11:16], fs[0].get("from") or "?", (fs[-1].get("arr") or "")[11:16],
            fs[-1].get("to") or "?", (arr.date() - dep.date()).days if dep and arr else 0, stops,
            [f.get("flight") for f in fs if f.get("flight")], durs[i] if i < len(durs) else None)


def leg_rows(t, o):
    """Every trip leg as a route: time, airport code and city at both ends, the stops on a line between them, flying
    time; then where each stop is, how long the wait, the flight numbers. A leg the site didn't list says so."""
    e, out = escape, ""
    for i, l in enumerate(t["legs"]):
        head = '<div class="leghead">%s <span>%s</span></div>' % (tag(t, i), e(long_day(l["date"])))
        p = leg_parts(o, i)
        if not p:
            out += '<div class="leg">%s<div class="note">%s → %s: flights not shown by %s; choose them on its page.</div></div>' % (
                head, e(city(l["from"])), e(city(l["to"])), e(seller_label(best_seller(o))))
            continue
        dt, a, at, b, plus, stops, nums, mins = p
        end = '<div class="end%s"><div class="tm">%s%s</div><div class="ap"><b>%s</b> %s</div></div>'
        mid = ('<div class="mid%s"><span>%s</span><div class="bar">%s</div><span>%s</span></div>' % (
            " direct" if not stops else "", "Nonstop" if not stops else "%s · %s" % (
                stops_txt(len(stops)), e(", ".join(named(s) for s, _ in stops))), "<i></i>" * len(stops), dur(mins) if mins else ""))
        via = ["%s%s" % (e(city(s)), (', <span class="long">%s wait</span>' if m > 8 * 60 else ", %s wait") % dur(int(m))
                         if m and m > 0 else "") for s, m in stops]  # a wait over 8 h stands out; none below 0 (bad data)
        detail = ("Change in " + "; then ".join(via) + " · " if via else "") + ("Flights " + e(", ".join(nums)) if nums else "")
        out += '<div class="leg t%d">%s<div class="route">%s%s%s</div>%s</div>' % (
            min(i, 3), head, end % ("", e(dt), "", e(a), e(town(a))), mid,
            end % (" to", e(at), '<span class="plus">+%d</span>' % plus if plus else "", e(b), e(town(b))),
            '<div class="via">%s</div>' % detail if detail else "")
    return out


def trail(data, t, o):
    """The opened ticket: each leg flight by flight; at each stop where it is (code and place), when it lands and
    leaves, the wait (over 8 h in the warning colour). A leg the site didn't list says so."""
    e, out, fl = escape, "", leg_flights(o)
    for i, l in enumerate(t["legs"]):
        fs = fl[i] if i < len(fl) else None
        p = leg_parts(o, i)
        head = '<div class="leghead">%s <span>%s</span>%s</div>' % (tag(t, i), e(long_day(l["date"])), (
            " <span>%s</span>" % e(" · ".join(x for x in ("Nonstop" if not p[5] else stops_txt(len(p[5])), dur(p[7])) if x)))
            if p else "")
        if not fs:
            out += '<div class="tleg">%s<div class="note">%s → %s: flights not shown by %s; choose them on its page.</div></div>' % (
                head, e(city(l["from"])), e(city(l["to"])), e(seller_label(best_seller(o))))
            continue
        d0 = when(fs[0].get("dep"))

        def tm(v):  # "11:40" and "+1" when it is a later day than the leg's first take-off
            d = when(v)
            plus = (d.date() - d0.date()).days if d and d0 else 0
            return "<b>%s</b>%s" % (e((v or "")[11:16] or "?"), '<span class="plus">+%d</span>' % plus if plus else "")

        def point(v, c):
            return '<li class="pt"><span class="tm">%s</span><span class="ap"><b>%s</b>%s</span></li>' % (
                tm(v), e(c), e(town(c)))
        steps = [point(fs[0].get("dep"), fs[0].get("from") or "?")]
        for k, f in enumerate(fs):
            c, n = code(f), f.get("flight") or ""
            who = airline_name(data, c) if c else ""
            steps.append('<li class="hop">%s<b>%s</b>%s%s%s</li>' % (
                logo(c, who, True) if c else "", e(n), (" · %s%s" % ("flown by " if n[:2].upper() != c else "", e(who)))
                if who else "", " · <span>%s flight</span>" % dur(f["min"]) if f.get("min") else "",
                " · <span>%s</span>" % e(f["cabin"].capitalize()) if f.get("cabin") else ""))
            if k + 1 < len(fs):
                g, a = fs[k + 1], f.get("to") or "?"
                m = (when(g.get("dep")) - when(f.get("arr"))).total_seconds() // 60 \
                    if when(f.get("arr")) and when(g.get("dep")) else None
                change = '<div class="warn">Airport change: %s → %s</div>' % (e(named(a)), e(named(g.get("from") or "?"))) \
                    if g.get("from") and g.get("from") != a else ""
                steps.append('<li class="stop%s"><div class="box"><div class="sh"><span class="n">%s</span>'
                             '<span class="ap"><b>%s</b>%s</span></div><div class="st"><span>Lands</span> %s · '
                             '<span>Leaves</span> %s%s</div>%s</div></li>' % (
                                 " long" if m and m > 8 * 60 else "", "Stop" if len(fs) == 2 else "Stop %d" % (k + 1),
                                 e(a), e(town(a)), tm(f.get("arr")), tm(g.get("dep")),
                                 ' · <span class="w">%s wait</span>' % dur(int(m)) if m and m > 0 else "", change))
        steps.append(point(fs[-1].get("arr"), fs[-1].get("to") or "?"))
        out += '<div class="tleg t%d">%s<ol class="steps">%s</ol></div>' % (min(i, 3), head, "".join(steps))
    return out


def ticket(data, t, o, cur):
    e = escape
    top = best_seller(o)
    url = top.get("booking_url") or o.get("search_url") or t.get("search_url") or ""
    name = seller_label(top)
    notes = ('<div class="warn">Note: %s</div>' % e("; ".join(o["flags"]))) if o.get("flags") else ""
    if seller_note(o):  # 2 one-way fares, or another note of the seller's
        notes += '<div class="note">%s</div>' % e(seller_note(o))
    elif top.get("note"):  # an airline's calendar fare: alone (no flights) or matched to these flights
        notes += '<div class="note">%s: %s</div>' % (e(name), e(top["note"] if not o.get("flights") else
                                                          "its own fare calendar shows this price for these dates; choose these flights on its site"))
    rows = ""
    ss = sellers(o)
    if len(ss) > 1:  # the same flights at several sites: every price with its own Book link
        for s in ss:
            cls = " top" if s == top else " conv" if s.get("converted") else ""
            u = s.get("booking_url")
            rows += ('<div class="seller%s"><span class="who">%s%s</span><span class="p">%s</span>%s</div>' % (
                cls, e(seller_label(s)), " · cheapest" if s == top else "", e(seller_price(s, cur)),
                ('<a class="buy" href="%s" target="_blank" rel="noopener">Book</a>' % e(u)) if u else ""))
        rows = '<div class="sellers"><div class="eyebrow">%d sites sell these flights</div>%s</div>' % (len(ss), rows)
    notes += "".join('<div class="note">%s</div>' % e(x[:1].upper() + x[1:]) for x in night(t, o))  # long waits: in the leg
    notes += ('<div class="note">Bags: %s</div>' % e(bags_txt(o))) if bags_txt(o) else ""
    if o.get("similar"):
        notes += '<div class="note">+%d similar option%s (other flight times, about the same price) on the site</div>' % (
            o["similar"], "" if o["similar"] == 1 else "s")
    link = ('<a class="book" href="%s" target="_blank" rel="noopener">Book on %s</a>' % (e(url), e(name))) if url else ""
    paths = option_paths(t, o)
    if paths:  # a tap opens the stops and flights (a ticket without listed flights has nothing more to show)
        notes += '<span class="hint"><span class="o">%s</span><span class="c">Hide details</span></span>' % (
            "Show where it stops" if any(len(cs) > 2 for _, cs in paths) else "Show flight details")
    card = ('<div class="main">%s<div class="body"><div class="legs">%s</div>%s</div>%s</div>'
            '<div class="stub"><div class="price"><div class="big">%s</div><div class="scope">%s</div>%s</div>'
            '<span class="badge">%s%s</span>%s</div>%s') % (
        airline_row(o), leg_rows(t, o), route_map(paths), notes,
        e(("≈ " if top.get("converted") else "") + money(o["price_total"], o.get("currency") or cur, True))
        if o.get("price_total") is not None else "?", e(scope(data, t)),
        '<div class="note">%s</div>' % e("converted from %s" % (top.get("converted_from") or "another currency"))
        if top.get("converted") else "", "cheapest at " if len(ss) > 1 else "", e(name), link, rows)
    st, mins, fl = o.get("stops") or [], o.get("duration_min") or [], o.get("flights") or []
    full = len(st) == len(mins) == len(t["legs"]) and None not in st + mins  # every leg listed: stops and time known
    dep = when(fl[0].get("dep")) if fl else None
    sort = ' data-p="%s" data-m="%s" data-s="%s" data-d="%s" data-f="%d"' % (  # for the sort buttons ("" = unknown: last)
        o["price_total"] if finite(o) else "", sum(mins) if full else "", sum(st) if full else "",
        dep.hour * 60 + dep.minute if dep else "", 1 if o.get("flags") else 0)
    if not paths:
        return '<div class="ticket"%s><div class="top">%s</div></div>' % (sort, card)
    return '<details class="ticket"%s><summary class="top">%s</summary><div class="more"><div class="trail">%s</div>%s</div></details>' % (
        sort, card, trail(data, t, o), route_map(paths, ratio=1.45, size=.036, cls="map wide"))


def journey_legs(data):
    """Routes to pick on their own: one-way trips that chain (one lands where another leaves: SYD→KUL, KUL→AUH) are
    separate legs of one journey, so one "Cheapest" across them means nothing. [] for any other plan."""
    ow = [t for t in data["trips"] if len(t["legs"]) == 1]
    if not any(a["legs"][0]["to"] == b["legs"][0]["from"] for a in ow for b in ow):
        return []
    return list(dict.fromkeys(route_key(t) for t in data["trips"]))


NO_NONSTOP = "No nonstop found on this route"
WINS = ("Cheapest", "Best route", "Best nonstop", "Best on ")  # pick labels a ticket wins outright: shown with a tick


def is_nonstop(o):  # every leg known and nonstop
    return bool(o.get("stops")) and all(s == 0 for s in o["stops"])


def nth(n):
    return "%d%s" % (n, "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th"))


def cheapest_airlines(opts):
    """[(airline code, its cheapest option)], cheapest first; a mix of airlines counts under the one flying the long
    flights (else the longest flight), as in the per-airline list."""
    each = {}
    for t, o in opts:
        c = main_airline(o, t["legs"][0]["from"]) or longest_airline(o)
        if c:
            each.setdefault(c, []).append((t, o))
    return sorted(((c, best_price(xs)) for c, xs in each.items()), key=lambda kv: kv[1][1]["price_total"])


def win_chip(label):  # a won box gets a tick, the missing nonstop a warning, a rank stays plain
    if label.startswith(NO_NONSTOP):
        return '<span class="win none">⚠ %s</span>' % escape(label)
    if label.startswith(WINS):
        return '<span class="win">✓ %s</span>' % escape(label)
    return '<span class="win rank">%s</span>' % escape(label)


def pick_cards(data):
    """[[labels], (t, o) or None, [notes]]; the same option under several labels becomes one card. Separate legs of
    one journey (journey_legs) get their own picks: "Cheapest (SYD → KUL)"."""
    if journey_legs(data):
        return [[["%s (%s)" % (l, r) for l in labels], x, notes] for r in journey_legs(data)
                for labels, x, notes in pick_cards(dict(data, trips=[t for t in data["trips"] if route_key(t) == r]))]
    cheap, best = picks(data)
    if not cheap:
        return []
    cards = []

    def add(label, x, note=""):
        for c in cards:
            if x is not None and c[1] is not None and c[1][1] is x[1]:  # same option dict
                c[0].append(label)
                c[2] += [note] if note else []
                return
        cards.append([[label], x, [note] if note else []])
    same = ties(data, cheap)
    add("Cheapest", cheap, ("Same price: " + "; ".join(same)) if same else "")
    add("Best route", best)
    if nonstop(data):
        add("Best nonstop", nonstop(data))
    else:
        cards[0][0].append(NO_NONSTOP)
    for c, name, x, note in preferred(data):
        add("Best on " + name, x, note)
    # a bags wish and a pick with bags not stated: under the first such pick, the cheapest clean option whose stated
    # bags meet the wish (checked pieces on every leg), unless that option is already a pick
    need = bags_wanted(data)
    ok = [x for x in all_options(data) if need and not x[1].get("flags") and bag_list(x[1])
          and all(u == "pc" and k >= need for k, u in bag_list(x[1]))]
    top = min(ok, key=lambda x: x[1]["price_total"], default=None)
    card = next((c for c in cards if c[1] and not bags_txt(c[1][1])), None)
    if top and card and all(c[1] is None or c[1][1] is not top[1] for c in cards):
        t, o = top
        card[2].insert(0, "Cheapest with your bags confirmed: %s — %s, %s, %s, at %s (%s)" % (
            money(o["price_total"], o.get("currency", "KWD"), True), airline_txt(data, t, o), when_txt(t),
            stops_line(o), seller_label(best_seller(o)), bags_txt(o)))
    # at least 3 picks: the cheapest airlines not shown yet ("2nd cheapest airline"), then the next cheapest options
    opts = clean(all_options(data))
    shown = [c[1] for c in cards if c[1]]
    air = lambda x: main_airline(x[1], x[0]["legs"][0]["from"]) or longest_airline(x[1])
    rank = cheapest_airlines(opts)
    nrank = cheapest_airlines([x for x in opts if is_nonstop(x[1])])
    for i, (c, x) in enumerate(rank):
        if len(shown) >= 3:
            break
        if c not in {air(y) for y in shown}:
            j = next((k for k, (c2, y) in enumerate(nrank) if c2 == c and y[1] is x[1]), None)
            cards.append([["%s cheapest airline" % nth(i + 1)] + (["%s best nonstop airline" % nth(j + 1)] if j else []),  # 1st = Best nonstop
                          x, []])
            shown.append(x)
    for x in sorted(opts, key=lambda x: x[1]["price_total"]):
        if len(shown) >= 3:
            break
        if all(x[1] is not y[1] for y in shown):
            cards.append([["Next cheapest"], x, []])
            shown.append(x)
    if budget_note(data, cheap):
        cards[0][2].append(budget_note(data, cheap))
    for c in cards:  # the no-nonstop warning after the boxes won
        c[0].sort(key=lambda l: l.startswith(NO_NONSTOP))
    return cards


def names(o):
    """The option's airline names, one per code (NAMES), so an airline has the same name everywhere; a name a source
    wrote with a note in brackets, or a code NAMES doesn't know, stays as given."""
    al = o.get("airlines")
    if not isinstance(al, list):
        return al
    cs = o.get("codes") if isinstance(o.get("codes"), list) and len(o["codes"]) == len(al) else \
        list(dict.fromkeys(str(f.get("flight") or "")[:2].upper() for f in o.get("flights") or [] if isinstance(f, dict)))
    cs = cs if len(cs) == len(al) else al
    return [a if "(sold as" in str(a) else NAMES.get(str(c).upper(), a) for c, a in zip(cs, al)]


def prepare(data):
    """Defaults for loose results: a trips list, a label on every trip, one name per airline."""
    data["trips"] = data.get("trips") or []
    for t in data["trips"]:
        t["label"] = t.get("label") or "%s, %s" % (route_key(t), dates_key(t))
        if t.get("kind") == "round trip":  # "Tokyo return" read as the flight back only
            for k in ("label", "route"):
                t[k] = re.sub(r"\breturn\b", "round trip", t[k]) if isinstance(t.get(k), str) else t.get(k)
        for o in t.get("options") or []:
            o["airlines"] = names(o)
        raw = {a.get("name"): a.get("code") for a in t.get("airline_min") or []}  # Booking's names -> code
        if t.get("nonstop_airline") in raw:
            t["nonstop_airline"] = NAMES.get(raw[t["nonstop_airline"]], t["nonstop_airline"])
        for a in t.get("airline_min") or []:
            a["name"] = NAMES.get(a.get("code"), a.get("name"))
    return data


NOTHING = "Nothing searched: the plan had no trips."


BODY = "<!--body-->"
SWITCH = """<script>(function(){
var root=document.documentElement,en=document.querySelector('main[lang=en]'),ar=document.querySelector('main[lang=ar]'),
bl=document.getElementById('b-lang'),bt=document.getElementById('b-theme');
function get(k){try{return localStorage.getItem(k)}catch(e){return null}}
function put(k,v){try{localStorage.setItem(k,v)}catch(e){}}
function dark(){var t=root.getAttribute('data-theme');return t?t==='dark':matchMedia('(prefers-color-scheme: dark)').matches}
function names(){var a=ar&&!ar.hidden,d=dark();bt.textContent=a?(d?'الوضع الفاتح':'الوضع الداكن'):(d?'Light mode':'Dark mode');
bt.setAttribute('aria-pressed',d?'true':'false')}
function lang(l){if(!ar){bl.hidden=true;names();return}var a=l==='ar';en.hidden=a;ar.hidden=!a;
bl.textContent=a?'English':'العربية';bl.lang=a?'en':'ar';root.lang=a?'ar':'en';names()}
bl.onclick=function(){var l=ar.hidden?'ar':'en';lang(l);put('lang',l);window.scrollTo(0,0)};
bt.onclick=function(){var t=dark()?'light':'dark';root.setAttribute('data-theme',t);put('theme',t);names()};
var t=get('theme');if(t)root.setAttribute('data-theme',t);
lang(get('lang')||(/^#ar/.test(location.hash)?'ar':'en'));
function val(t,k){var v=t.getAttribute('data-'+k);return v===null||v===''?Infinity:+v}
function sortBy(k){[].forEach.call(document.querySelectorAll('.sort button'),function(b){
b.setAttribute('aria-pressed',b.getAttribute('data-k')===k?'true':'false')});
[].forEach.call(document.querySelectorAll('.trip .tickets'),function(box){
var ts=[].filter.call(box.children,function(c){return c.classList.contains('ticket')});if(!ts.length)return;
ts.forEach(function(t,i){if(!t.hasAttribute('data-i'))t.setAttribute('data-i',i)});
var tail=ts[ts.length-1].nextSibling;
ts.sort(function(a,b){return val(a,'f')-val(b,'f')||val(a,k)-val(b,k)||val(a,'p')-val(b,'p')||val(a,'i')-val(b,'i')});
ts.forEach(function(t){box.insertBefore(t,tail)})});put('sort',k)}
[].forEach.call(document.querySelectorAll('.sort button'),function(b){b.onclick=function(){sortBy(b.getAttribute('data-k'))}});
var s=get('sort');if(s&&s!=='p')sortBy(s);
})();</script>"""


def finish(h, title_ar=None):
    """The page body twice, English and Arabic (arabic.translate; its trip ids get "ar-"), one shown at a time, with a
    language switch and a light/dark switch, each remembered per viewer; every airline logo once at the end.
    title_ar: the page name the customer gave, in Arabic (the plan's "title_ar"), in place of the translated h1."""
    head, body = "\n".join(h).split(BODY, 1)
    ar = arabic.translate(body).replace('id="trip-', 'id="ar-trip-').replace('href="#trip-', 'href="#ar-trip-') \
        if arabic else ""
    if ar and title_ar:
        ar = re.sub(r"<h1>.*?</h1>", lambda m: "<h1>%s</h1>" % escape(title_ar), ar, count=1)
    page = (head + '<nav class="switch" aria-label="Page options"><button type="button" id="b-lang" lang="ar">العربية'
            '</button><button type="button" id="b-theme">Dark mode</button></nav><main class="wrap" lang="en">' + body +
            "</main>" + ('<main class="wrap" lang="ar" dir="rtl" hidden>%s</main>' % ar if ar else "") + SWITCH)
    return page + "<style>%s</style>" % logo_css(page)


def build(data, max_n):
    prepare(data)
    e, cur = escape, plan_cur(data)
    t0 = data["trips"][0]["legs"][0] if data["trips"] else {"from": "?", "to": "?"}
    title = data.get("title") or "%s → %s Fares" % (t0["from"], t0["to"])
    cheap, _ = picks(data)
    fetched = sorted(t["fetched_at"] for t in data["trips"] if t.get("fetched_at"))
    when = (fetched[0] if fetched[0] == fetched[-1] else "%s to %s" % (fetched[0], fetched[-1][11:])) if fetched \
        else data.get("searched_at", "")
    flown = list(dict.fromkeys((min(i, 1), l["from"], l["to"]) for t in data["trips"] for i, l in enumerate(t["legs"])))
    hero = route_map([("t%d" % i, [a, b]) for i, a, b in flown], ratio=1.7, size=.027)  # every route searched
    h = ['<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
         '<title>%s</title>' % e(title),
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@400;600;700&family=Public+Sans:wght@400;600;700&display=swap">',
         '<style>%s</style>' % CSS,
         '<svg width="0" height="0" style="position:absolute" aria-hidden="true"><defs><path id="land" vector-effect="non-scaling-stroke" d="%s"/></defs></svg>%s' % (LAND, BODY),
         '<header class="hero"><div class="txt"><div class="eyebrow">Flight search · whole-trip prices</div><h1>%s</h1>'
         '<div class="chips">%s</div><p class="lead">Every price is the total for the whole trip (every flight, out and '
         'back) for all %s, in %s.</p></div>%s</header>' % (
             e(title), "".join('<span class="chip">%s</span>' % e(x[:1].upper() + x[1:]) for x in pax(data).split(" · ") + (
                 ["from " + city(t0["from"])] if data["trips"] else []) + (["prices fetched " + when] if when else [])),
             e(travellers(data)), e(cur), '<div class="pic">%s</div>' % hero if hero else "")]
    if not data["trips"]:
        h.append('<div class="fail">%s</div>' % e(NOTHING))
        return finish(h, data.get("title_ar"))
    cards = pick_cards(data)
    h += ['<div class="fail">%s</div>' % e(x) for x in nothing_lines(data)]
    h += ['<p class="warn">%s</p>' % e(x) for x in cabin_lines(data) + [unmatched(data)] if x]
    h += ['<p class="note">%s</p>' % e(x.strip()) for x in closest(data)]
    if cards:
        h.append('<div class="block"><div class="head"><h2>Top picks</h2><p class="sub">Chosen from whole-trip prices: '
                 'the cheapest, the best route (fewest stops, shortest flying), the best nonstop and the best on each '
                 'airline you named. A tick marks each one a ticket wins; the next cheapest airlines fill up to three.</p></div>')
        if any(x for _, x, _ in cards):
            h.append('<section class="picks">')
        for labels, x, extra in cards:
            if x is None:
                continue
            t, o = x  # the same ticket as in "Every option, trip by trip", under what it was picked for
            met, miss = wish(data, t, o)
            mixed = "not %s the whole way" % CABIN_WORD.get(cabin(data), cabin(data)) \
                if route_key(t) in no_cabin_routes(data) and not in_cabin(data, o) else ""
            notes = list(extra) + ([mixed] if mixed else []) + (["fits your wishes: " + "; ".join(met)] if met and not miss else [])
            stops = [stops_line(o)] if o.get("note") or cal_code(o) else []  # no flights listed: say so
            by = airline_txt(data, t, o)  # said only when it adds something ("… flown by British Airways")
            line = " · ".join([when_txt(t)] + ([by] if by != ", ".join(o.get("airlines") or []) else []) + stops)
            h.append('<div class="pick"><div class="pickhead"><div class="wins">%s</div><b>%s</b>%s</div>%s</div>' % (
                "".join(win_chip(l) for l in labels), e(line), "".join('<div class="note">%s</div>' % e(n[:1].upper() + n[1:]) for n in notes),
                ticket(data, t, o, cur)))
        if any(x for _, x, _ in cards):
            h.append('</section>')
        also = [(labels, extra) for labels, x, extra in cards if x is None]
        if also:
            h.append('<div class="also">%s</div>' % "".join('<div><b>%s:</b> %s</div>' % (
                e(" · ".join(labels)), e(" ".join(extra) or "nothing found")) for labels, extra in also))
        h += ['<p class="note tip">%s</p>' % e(x) for x in google_cheaper(data)]
        h.append('</div>')
    rows = per_airline(data)
    by_name = {v: k for k, v in NAMES.items()}
    if rows:
        named = data.get("airlines") or data.get("prefer")
        h.append('<section class="block"><div class="head"><h2>Best price per airline</h2><p class="sub">%s</p></div><div class="scroll"><table>'
                 '<tr><th>Airline</th><th>Whole trip</th><th>Cheapest site</th><th>Trip</th><th></th></tr>' % (
                     "The airlines you named: each one's cheapest whole-trip price and the site that sells it."
                     if named else "The cheapest price found on each airline (a mix of airlines counts under the one "
                     "flying the longest flight); a note says what that option misses."))
        for name, x, note in rows:
            who = '<div class="who">%s<span>%s</span></div>' % (logo(by_name.get(name.split(" (sold as")[0]), name, True), e(name))
            if x is None:
                h.append('<tr><td>%s</td><td colspan="4"><small>%s</small></td></tr>' % (who, e(note)))
                continue
            t, o = x
            b = best_seller(o)
            u = b.get("booking_url") or o.get("search_url")
            h.append('<tr><td>%s</td><td class="mono"><b>%s</b></td><td>%s</td><td>%s<small>%s</small></td><td>%s</td></tr>' % (
                who, e(seller_price(b, cur)), e(seller_label(b)), e(when_txt(t)),
                e("note: " + "; ".join(o["flags"])) if o.get("flags") else "",
                ('<a class="mini" href="%s" target="_blank" rel="noopener">Book</a>' % e(u)) if u else ""))
        h.append('</table></div></section>')
    dates, routes, cells = matrix(data)
    tid = {id(t): "trip-%d" % i for i, t in enumerate(data["trips"])}  # a matrix price jumps to its trip's tickets
    low = round(cheap[1]["price_total"], 2) if cheap else None
    h.append('<section class="block"><div class="head"><h2>Whole-trip totals by date</h2><p class="sub">The cheapest '
             'normal ticket for each dates and route; tap a price to see its flights.</p></div>'
             '<div class="scroll"><table><tr><th>Dates</th>%s</tr>' % "".join("<th>%s</th>" % e(r) for r in routes))
    starred = False
    for d in dates:
        row = "<tr><td class=\"mono\">%s</td>" % e(d)
        for r in routes:
            c = cells.get((d, r), "n/a")
            if c == "n/a":
                row += "<td>–</td>"
            elif c is None:
                row += "<td><small>no price</small></td>"
            else:
                txt, ap, s, extra = cell_parts(c, cur)
                starred = starred or "*" in txt + extra
                low_r = low if not journey_legs(data) else round(min(
                    (x[1]["price_total"] for x in clean([y for y in all_options(data) if route_key(y[0]) == r])), default=0), 2)
                hit = c["clean"] and round(c["clean"][1]["price_total"], 2) == low_r
                main = (c["clean"] or c["flagged"])
                lg = (al_pairs(main[1]) or [(None, "")])[0]
                row += '<td class="mono%s"><a href="#%s">%s%s</a><small>%s · %s%s</small></td>' % (
                    " low" if hit else "", tid[id(main[0])], logo(lg[0], lg[1], True) if lg[1] else "", e(txt),
                    e(ap), e(s or ""), e(" · " + extra) if extra else "")
        h.append(row + "</tr>")
    h.append('</table></div><p class="note">Totals are for the whole trip and all travellers. %s'
             'Check the final total on the airline or Google page before paying.</p></section>' % (e(STAR) + " " if starred else ""))
    h.append('<div class="head part"><h2>Every option, trip by trip</h2><p class="sub">Each ticket: the flights out and '
             'back on a map, times, stops and waits, and every site that sells it.</p><div class="sort" role="group" '
             'aria-label="Sort the tickets"><span>Sort by</span><button type="button" data-k="p" aria-pressed="true">'
             'Cheapest</button><button type="button" data-k="m" aria-pressed="false">Fastest</button><button type="button" '
             'data-k="s" aria-pressed="false">Fewest stops</button><button type="button" data-k="d" aria-pressed="false">'
             'Leaves earliest</button></div></div>')
    for t in data["trips"]:
        h.append('<section class="trip" id="%s"><div><h2>%s</h2><p class="sub">%s · %s%s</p></div><div class="tickets">' % (
            tid[id(t)], e(t["label"]), e(trip_route(t)), e(" → ".join(long_day(l["date"]) for l in t["legs"])),
            e(" · " + t["kind"]) if t.get("kind") else ""))
        priced = [o for o in t.get("options") or [] if finite(o)]
        if t.get("ok") and priced:
            ok_, flagged = collapse([o for o in priced if not o.get("flags")]), collapse([o for o in priced if o.get("flags")])
            shown = (ok_ + flagged)[:max_n]  # normal tickets first, flagged ones after
            if ok_ and flagged and flagged[0]["price_total"] < ok_[0]["price_total"] and all(x is not flagged[0] for x in shown):
                shown = shown[:max_n - 1] + flagged[:1]  # a cheaper flagged ticket stays in view, with its note
            h += [ticket(data, t, o, cur) for o in shown]
            codes = {code(f) for o in shown for f in o.get("flights") or []}
            more = sorted((a for a in t.get("airline_min") or [] if a.get("code") not in codes and a.get("price_total")),
                          key=lambda a: a["price_total"])[:8]
            if more:
                h.append('<p class="note">More airlines on Booking.com (cheapest each, flights on its page; some only '
                         'fly a connecting flight): %s</p>' % e(" · ".join("%s %s" % (a["name"], money(a["price_total"], cur))
                                                                          for a in more)))
        else:
            h.append('<div class="fail">No price found (unknown, not "no flights"). %s</div>' % e(plain_error(t)))
        h.append('</div></section>')
    h.append('<p class="note">Prices change quickly. This page only searches; nothing was booked. Maps: Natural Earth, '
             'OurAirports. Logos: Google Flights.</p>')
    return finish(h, data.get("title_ar"))


# What a Claude artifact wraps the page in, so the saved file looks and works the same in a browser.
FILE_TOP = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,'
            'initial-scale=1"><style>:root{color-scheme:light}body{margin:0;padding:0}img{max-width:100%}'
            '[hidden]{display:none!important}</style></head><body>\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("page")
    ap.add_argument("--max", type=int, default=6, help="tickets shown per trip")
    ap.add_argument("--file", action="store_true", help="a complete HTML file, not a Claude artifact")
    a = ap.parse_args()
    data = prepare(json.load(open(a.results)))
    for t in data["trips"]:
        for o in t.get("options") or []:
            o["flags"] = flags(data, t, o)
    with open(a.page, "w") as f:
        f.write((FILE_TOP + build(data, a.max) + "</body></html>") if a.file else build(data, a.max))
    # text version for the chat
    if not data["trips"]:
        print(NOTHING)
        print("Saved %s" % a.page)
        return
    cur = plan_cur(data)
    dates, routes, cells = matrix(data)
    print("| Dates | " + " | ".join(routes) + " |")
    print("|---" * (len(routes) + 1) + "|")
    starred = False
    for d in dates:
        row = []
        for r in routes:
            c = cells.get((d, r), "n/a")
            if c in ("n/a", None):
                row.append("–" if c == "n/a" else "no price")
                continue
            txt, ap_, s, extra = cell_parts(c, cur)
            starred = starred or "*" in txt + extra
            row.append("%s %s (%s)%s" % (txt, ap_, s, (" [%s]" % extra) if extra else ""))
        print("| %s | %s |" % (d, " | ".join(row)))
    if starred:
        print(STAR)
    for x in nothing_lines(data) + cabin_lines(data) + [unmatched(data)] + closest(data):
        if x:
            print(x)
    for labels, x, extra in pick_cards(data):
        head = " · ".join(l for l in labels if not l.startswith(NO_NONSTOP))
        warn = ["%s." % l for l in labels if l.startswith(NO_NONSTOP)]
        print((pick_line(data, head, *x) if x else head + ":") + "".join("\n  " + n for n in extra + warn))
    for x in google_cheaper(data):
        print(x)
    rows = per_airline(data)
    if rows:
        print("Best price per airline:")
        for name, x, note in rows:
            print("  %s → %s" % (name, "%s → %s (%s)%s" % (seller_price(best_seller(x[1]), cur), seller_label(best_seller(x[1])),
                                                              when_txt(x[0]),
                                                              " (note: %s)" % "; ".join(x[1]["flags"]) if x[1].get("flags") else "")
                                     if x else note))
    print("Saved %s" % a.page)


if __name__ == "__main__":
    main()
