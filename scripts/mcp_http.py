"""Tiny MCP streamable-HTTP client: JSON-RPC over POST, reply as JSON or SSE. Needs primp.

MCP("https://mcp.kiwi.com").call("search-flight", {...}) -> (text, structuredContent, isError)
Initializes once per process (initialize + notifications/initialized) and reuses the session id.
Gentle: max 2 requests in flight, request starts >= gap seconds apart, 20 s timeout per request.
The handshake (initialize + notification) is not paced and does not push the pace, so the first real call goes
straight after it; real calls (tools/call, tools/list) stay >= gap apart.
"""
import json, threading, time
from primp import Client

HDR = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
       "MCP-Protocol-Version": "2025-06-18"}


class MCP:
    def __init__(self, url, timeout=20, gap=1.5):
        self.url, self.gap, self.next, self.sid, self.n, self.ready = url, gap, 0.0, None, 0, False
        self.lock, self.slots, self.init_lock = threading.Lock(), threading.BoundedSemaphore(2), threading.Lock()
        self.c = Client(impersonate="chrome_126", timeout=timeout)

    def _wait(self, pace=True):
        with self.lock:
            start = max(time.time(), self.next) if pace else time.time()
            if pace:
                self.next = start + self.gap
            self.n += 1
            n = self.n
        time.sleep(max(0.0, start - time.time()))
        return n

    def _post(self, method, params=None, notify=False, pace=True):
        with self.slots:
            n = self._wait(pace)
            body = {"jsonrpc": "2.0", "method": method}
            if params is not None:
                body["params"] = params
            if not notify:
                body["id"] = n
            h = dict(HDR)
            if self.sid:
                h["Mcp-Session-Id"] = self.sid
            r = self.c.post(self.url, headers=h, content=json.dumps(body).encode())
        self.sid = r.headers.get("mcp-session-id") or self.sid
        if notify:
            return None
        if r.status_code >= 400:
            raise RuntimeError("HTTP %s: %s" % (r.status_code, r.text[:200]))
        txt, d = r.text, None
        if txt.lstrip().startswith("{"):
            d = json.loads(txt)
        else:  # SSE: last data: frame that is a JSON-RPC reply
            for line in txt.splitlines():
                if line.startswith("data:"):
                    try:
                        x = json.loads(line[5:].strip())
                        if "result" in x or "error" in x:
                            d = x
                    except ValueError:
                        pass
        if d is None:
            raise RuntimeError("no JSON-RPC reply: " + txt[:200])
        if "error" in d:
            raise RuntimeError("MCP error: %s" % json.dumps(d["error"])[:300])
        return d["result"]

    def init(self):
        with self.init_lock:  # other threads wait here until the session id is known
            if not self.ready:
                self._post("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                          "clientInfo": {"name": "flight-search", "version": "0.1"}}, pace=False)
                self._post("notifications/initialized", notify=True, pace=False)
                self.ready = True
        return self

    def tools(self):
        self.init()
        return self._post("tools/list", {})["tools"]

    def call(self, name, args):
        self.init()
        res = self._post("tools/call", {"name": name, "arguments": args})
        text = "\n".join(c.get("text", "") for c in res.get("content") or [] if c.get("type") == "text")
        return text, res.get("structuredContent"), res.get("isError")


def parse_cli(argv=None, extra=None):
    """Shared CLI: FROM-TO:YYYY-MM-DD legs + --adults/--children/--infants/--cabin/--currency/--airlines."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("legs", nargs="+", help="FROM-TO:YYYY-MM-DD")
    ap.add_argument("--adults", type=int, default=1)
    ap.add_argument("--children", type=int, default=0)
    ap.add_argument("--infants", type=int, default=0)
    ap.add_argument("--cabin", default="economy", choices=["economy", "premium", "business", "first"])
    ap.add_argument("--currency", default="KWD")
    ap.add_argument("--airlines", default=None, help="comma-separated IATA codes, e.g. QR,EY")
    for a, kw in (extra or []):
        ap.add_argument(a, **kw)
    a = ap.parse_args(argv)
    legs = []
    for x in a.legs:
        route, date = x.split(":")
        fr, to = route.upper().split("-")
        legs.append({"from": fr, "to": to, "date": date})
    a.legs = legs
    a.currency = a.currency.upper()
    a.airlines = [x.strip().upper() for x in a.airlines.split(",")] if a.airlines else None
    return a


def trip_type(legs):
    if len(legs) == 1:
        return "oneway"
    if len(legs) == 2 and legs[1]["from"] == legs[0]["to"] and legs[1]["to"] == legs[0]["from"]:
        return "round"
    return "multi"
