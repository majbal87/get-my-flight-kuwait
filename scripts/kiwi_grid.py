"""Date grid from ONE Kiwi MCP call: departure range x return range (up to +-10 days each).

grid("KWI", "NRT", ("2026-12-18", "2026-12-20"), ("2026-12-29", "2026-12-31"), adults=4, cabin="business")
-> [{"out", "ret", "price_total", "airline", "tickets", "booking_url"}, ...] cheapest per date pair, cheapest first.
Prices are live Kiwi prices (same as a normal Kiwi search), KWD, whole trip, all passengers, the asked cabin.
Kiwi returns only its 15 cheapest itineraries for the whole window, so a missing pair is unknown, not "no flights"
and not proof it is dearer: repeats of one itinerary can crowd it out (NRT: 19->30 missing, 6 other pairs same price). Self-transfer is OFF by default so the pairs found can be
confirmed on Google / Booking (they sell normal tickets). ret_range=None = one-way grid.
nights=N: trips of N days (Kiwi nights_in_dst_from/to = N-1..N: Kiwi counts nights at the destination, one fewer
when the flight lands the next day; live KWI-DAC nights 10 gave only 11-day trips). A fixed-length trip on a wide grid,
e.g. a whole month in 2 calls: search.py. Callers still check the length themselves.

CLI: python kiwi_grid.py KWI-NRT 2026-12-18:2026-12-20 2026-12-29:2026-12-31 --adults 4 --cabin business [--airlines EY] [--nights 10]
"""
import argparse, json, sys, time
import kiwi


def grid(origin, dest, out_range, ret_range=None, adults=1, children=0, infants=0, cabin="economy",
         currency="KWD", airlines=None, self_transfer=False, nights=None):
    legs = [{"from": origin, "to": dest, "date": out_range[0]}]
    if ret_range:
        legs.append({"from": dest, "to": origin, "date": ret_range[0]})
    a = kiwi.args_for(legs, adults, children, infants, cabin, currency, airlines, self_transfer)
    a["departureDateTo"] = kiwi.dmy(out_range[1])
    if ret_range:
        a["returnDateTo"] = kiwi.dmy(ret_range[1])
    if nights:
        a["nights_in_dst_from"], a["nights_in_dst_to"] = max(nights - 1, 0), nights
    its, err, secs = kiwi.raw(a)
    best = {}
    for it in its:
        o = kiwi.option(it, currency)
        k = (o["out"], o["ret"])
        if o["price_total"] and (k not in best or o["price_total"] < best[k]["price_total"]):
            best[k] = {"out": o["out"], "ret": o["ret"], "price_total": o["price_total"],
                       "airline": ", ".join(o["airlines"]), "tickets": o["tickets"], "booking_url": o["booking_url"]}
    return sorted(best.values(), key=lambda x: x["price_total"]), err, secs


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("route", help="FROM-TO")
    ap.add_argument("out", help="YYYY-MM-DD:YYYY-MM-DD departure range")
    ap.add_argument("ret", nargs="?", help="YYYY-MM-DD:YYYY-MM-DD return range (omit for one way)")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--infants", type=int, default=0)
    ap.add_argument("--cabin", default="economy", choices=list(kiwi.CABINS))
    ap.add_argument("--currency", default="KWD")
    ap.add_argument("--airlines", default=None)
    ap.add_argument("--self-transfer", action="store_true")
    ap.add_argument("--nights", type=int, default=None, help="only trips of exactly this many days")
    x = ap.parse_args()
    fr, to = x.route.upper().split("-")
    print("kiwi_grid: one call for %s %s x %s..." % (x.route, x.out, x.ret or "one way"), file=sys.stderr)
    rows, err, secs = grid(fr, to, x.out.split(":"), x.ret.split(":") if x.ret else None, x.adults, x.children,
                           x.infants, x.cabin, x.currency.upper(), x.airlines.upper().split(",") if x.airlines else None,
                           x.self_transfer, x.nights)
    print("kiwi_grid: %s in %ss, %d date pairs" % (err or "ok", secs, len(rows)), file=sys.stderr)
    print(json.dumps(rows, indent=1, ensure_ascii=False))
