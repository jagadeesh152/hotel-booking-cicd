"""Fire simultaneous bookings for the SAME room and show that only one is confirmed.

Usage:  python scripts/race_demo.py [base_url]      (default https://localhost)
Uses only the standard library. Self-signed certificates are accepted for the demo.
"""

import json
import ssl
import sys
import threading
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta

BASE = sys.argv[1] if len(sys.argv) > 1 else "https://localhost"
N = 10
CTX = ssl._create_unverified_context()  # demo only (self-signed cert)

# a random far-future window so repeated runs never collide with earlier bookings
start = date.today() + timedelta(days=400 + uuid.uuid4().int % 3000)
payload = json.dumps(
    {
        "room_type": "suite",
        "room_number": "301",
        "guest_name": "Race Demo",
        "guest_email": "race@example.com",
        "check_in": start.isoformat(),
        "check_out": (start + timedelta(days=2)).isoformat(),
    }
).encode()

results: list[int] = []
barrier = threading.Barrier(N)


def book() -> None:
    req = urllib.request.Request(
        f"{BASE}/reservations", data=payload, headers={"Content-Type": "application/json"}
    )
    barrier.wait()  # release all threads at the same instant
    try:
        with urllib.request.urlopen(req, context=CTX) as r:
            results.append(r.status)
    except urllib.error.HTTPError as e:
        results.append(e.code)


threads = [threading.Thread(target=book) for _ in range(N)]
[t.start() for t in threads]
[t.join() for t in threads]

print(f"{N} simultaneous requests for room 301, {start} -> {start + timedelta(days=2)}")
print(f"  201 Created : {results.count(201)}")
print(f"  409 Conflict: {results.count(409)}")
print(f"  other       : {[c for c in results if c not in (201, 409)]}")
print("PASS: exactly one booking confirmed" if results.count(201) == 1 else "FAIL")
sys.exit(0 if results.count(201) == 1 else 1)
