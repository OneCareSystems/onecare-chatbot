"""A tiny stand-in for the Spring Boot clinic API, so Django can be tested while Spring Boot is not running.
Usage (from the project folder):   python tools/mock_spring.py [--port 9090] [--token dev-spring-token] [--mode ok|down|slow]

  GET /api/internal/clinic/hours                 -> opening hours
  GET /api/internal/clinic/availability?date=..  -> doctors with free slots
Rules it copies from the real contract: Bearer service token required (otherwise 401), hours and availability only.
Modes: ok (default) | down (always HTTP 503) | slow (answers after 10 s, to test the timeout)."""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HOURS = [{"day": d, "open": "09:00", "close": "17:00", "closed": False} for d in
         ("MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY")] + [
        {"day": "SATURDAY", "open": "09:00", "close": "13:00", "closed": False},
        {"day": "SUNDAY", "open": None, "close": None, "closed": True}]
DOCTORS = [{"name": "Dr Perera", "availableSlots": 4}, {"name": "Dr Silva", "availableSlots": 0},
           {"name": "Dr Fernando", "availableSlots": 2}]


def make_handler(token, mode):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body):
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            url = urlparse(self.path)
            auth = self.headers.get("Authorization", "")
            print(f"{self.command} {self.path} auth={'yes' if auth else 'none'}")
            if auth != f"Bearer {token}":
                return self._send(401, {"success": False, "message": "Unauthorized"})
            if mode == "down":
                return self._send(503, {"success": False, "message": "Service unavailable"})
            if mode == "slow":
                time.sleep(10)
            if url.path == "/api/internal/clinic/hours":
                return self._send(200, {"success": True, "data": {"days": HOURS}})
            if url.path == "/api/internal/clinic/availability":
                date = parse_qs(url.query).get("date", [""])[0]
                return self._send(200, {"success": True, "data": {"date": date, "doctors": DOCTORS}})
            self._send(404, {"success": False, "message": "Not found"})

        def log_message(self, *args):
            pass
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9090)
    parser.add_argument("--token", default="dev-spring-token")
    parser.add_argument("--mode", choices=["ok", "down", "slow"], default="ok")
    args = parser.parse_args()
    print(f"Mock Spring on http://127.0.0.1:{args.port}  token={args.token}  mode={args.mode}   (Ctrl+C to stop)")
    ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.token, args.mode)).serve_forever()