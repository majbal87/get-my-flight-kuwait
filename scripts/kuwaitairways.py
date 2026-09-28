"""Kuwait Airways (KU) own fares over plain HTTP: the Amadeus fare calendar the kuwaitairways.com home page uses.

Two calls, ~1-2 s in all: POST airlines.api.amadeus.com/v1/security/oauth2/token with the public client id/secret
printed in the kuwaitairways.com home page (guest office KWIKU08AA), then POST /v2/search/air-calendars.
One reply = KU's cheapest bookable fare for every date pair within +/-3 days (7x7 grid for a round trip),
native KWD, total for all passengers. KU flights only, no flight numbers or times (calendar level).
One way and round trip. Economy (CFFKU) and business (CFFBUS). The booking site (digital.kuwaitairways.com)
is behind an Imperva wall, so search_url is the kuwaitairways.com booking page.

CLI: python kuwaitairways.py KWI-LHR:2026-12-10 LHR-KWI:2026-12-17 --adults 2 --cabin business
"""
import json, sys, threading, time
from primp import Client

API = "https://airlines.api.amadeus.com"
CLIENT = {"client_id": "rd47SmVxC8079PaYyKzy8Ih5a6ldb2V6", "client_secret": "dN5J0QBZKAFqWHSb",
          "grant_type": "client_credentials", "guest_office_id": "KWIKU08AA"}  # from kuwaitairways.com/en getToken()
FAMILIES = {"economy": "CFFKU", "business": "CFFBUS"}
HDR = {"Origin": "https://www.kuwaitairways.com", "Referer": "https://www.kuwaitairways.com/"}
SLOTS = threading.BoundedSemaphore(2)
_lock, _next, _tok = threading.Lock(), [0.0], {"t": None, "exp": 0}
_client = Client(impersonate="chrome_126", timeout=20)


def _wait(gap=1.5):
    with _lock:
        start = max(time.time(), _next[0])
        _next[0] = start + gap
    time.sleep(max(0.0, start - time.time()))


def _token():
    """(token, fresh). A fresh token was just fetched: the calendar call may follow without a wait."""
    if _tok["t"] and time.time() < _tok["exp"]:
        return _tok["t"], False
    _wait()
    r = _client.post(API + "/v1/security/oauth2/token", headers=HDR, data=CLIENT)
    d = r.json()
    _tok.update(t=d["access_token"], exp=time.time() + int(d.get("expires_in", 1799)) - 60)
    return _tok["t"], True


def search(legs, adults=1, children=0, infants=0, cabin="economy", currency="KWD", airlines=None):
    rt = len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]
    out = {"ok": False, "source": "kuwaitairways", "error": None,
           "search_url": "https://www.kuwaitairways.com/en/book-a-flight", "results": []}
    if airlines and "KU" not in [a.upper() for a in airlines]:
        out["error"] = "Kuwait Airways sells KU flights only"
        return out
    if cabin not in FAMILIES or (len(legs) > 1 and not rt) or infants:
        out["error"] = "Kuwait Airways script: economy/business, one way or round trip, no infants"
        return out
    its = [{"departureDateTime": l["date"] + "T00:00:00.000", "originLocationCode": l["from"],
            "destinationLocationCode": l["to"], "isRequestedBound": i == 0} for i, l in enumerate(legs)]
    trav = [{"passengerTypeCode": "ADT"}] * adults + [{"passengerTypeCode": "CHD"}] * children
    body = {"commercialFareFamilies": [FAMILIES[cabin]], "itineraries": its, "travelers": trav,
            "searchPreferences": {"showMilesPrice": False}}
    t = time.time()
    try:
        with SLOTS:
            tok, fresh = _token()
            if fresh:  # the calendar call goes right after the token; the next search waits the gap from now
                with _lock:
                    _next[0] = max(_next[0], time.time() + 1.5)
            else:
                _wait()
            print("kuwaitairways: calendar", file=sys.stderr)
            r = _client.post(API + "/v2/search/air-calendars", headers=dict(HDR, Authorization="Bearer " + tok),
                             json=body)
        out["secs"] = round(time.time() - t, 1)
        if r.status_code != 200:
            out["error"] = "Kuwait Airways HTTP %s: %s" % (r.status_code, r.text[:120])
            return out
        d = r.json()
        curs = (d.get("dictionaries") or {}).get("currency") or {}  # decimal places per returned currency
        cal = []
        for x in d.get("data") or []:
            p = x["prices"]["totalPrices"][0]
            dec = 10 ** (curs.get(p["currencyCode"]) or {}).get("decimalPlaces", 3)
            cal.append({"depart": x["departureDate"], "return": x.get("returnDate"), "price_total": p["total"] / dec,
                        "currency": p["currencyCode"], "fare_family": x.get("fareFamilyCode"),
                        "airports": ["%s-%s" % (b["originLocationCode"], b["destinationLocationCode"]) for b in x.get("bounds") or []]})
        out["calendar"] = sorted(cal, key=lambda c: c["price_total"])
        want = (legs[0]["date"], legs[1]["date"] if rt else None)
        hit = next((c for c in cal if (c["depart"], c["return"]) == want), None)
        if hit:
            out["results"] = [{"airlines": ["Kuwait Airways"], "price_total": round(hit["price_total"], 3),
                               "currency": hit["currency"], "stops": None, "duration_min": None, "flights": [],
                               "airports": hit["airports"], "fare_family": hit["fare_family"], "seller": "Kuwait Airways"}]
        out["ok"] = bool(hit)
        if not hit:
            out["error"] = "Kuwait Airways has no fare on these dates (see calendar for nearby dates)"
    except Exception as e:
        why = "timed out" if "timed out" in str(e) else "%s: %s" % (type(e).__name__, str(e)[:150])
        out.update(error="Kuwait Airways failed: " + why, secs=round(time.time() - t, 1))
    return out


if __name__ == "__main__":
    from almosafer import cli
    cli(search)
