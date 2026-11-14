from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

D = date.today() + timedelta(days=60)


def d(offset: int) -> str:
    return (D + timedelta(days=offset)).isoformat()


def body(room_type="standard", ci=0, co=2, room_number=None, name="Asha Rao"):
    payload = {
        "room_type": room_type,
        "guest_name": name,
        "guest_email": "asha@example.com",
        "check_in": d(ci),
        "check_out": d(co),
    }
    if room_number:
        payload["room_number"] = room_number
    return payload


# ---------- operations ----------
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/ready")
    assert r.status_code == 200 and r.json()["database"] == "up"


# ---------- availability ----------
def test_availability_seed_data(client):
    r = client.get(
        "/rooms/availability", params={"room_type": "suite", "check_in": d(0), "check_out": d(1)}
    )
    assert r.status_code == 200
    assert r.json()["available_count"] == 2


def test_availability_drops_after_booking(client):
    assert client.post("/reservations", json=body("suite")).status_code == 201
    r = client.get(
        "/rooms/availability", params={"room_type": "suite", "check_in": d(0), "check_out": d(2)}
    )
    assert r.json()["available_count"] == 1


def test_availability_rejects_bad_dates(client):
    r = client.get(
        "/rooms/availability", params={"room_type": "suite", "check_in": d(3), "check_out": d(1)}
    )
    assert r.status_code == 422


def test_availability_rejects_unknown_room_type(client):
    r = client.get(
        "/rooms/availability", params={"room_type": "castle", "check_in": d(0), "check_out": d(1)}
    )
    assert r.status_code == 422


# ---------- reservations ----------
def test_create_reservation_returns_unique_references(client):
    a = client.post("/reservations", json=body()).json()
    b = client.post("/reservations", json=body()).json()
    assert a["reference"].startswith("HB-") and a["reference"] != b["reference"]
    assert a["nights"] == 2 and a["total_price"] == 160.0


def test_get_reservation_by_reference(client):
    ref = client.post("/reservations", json=body()).json()["reference"]
    r = client.get(f"/reservations/{ref}")
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    assert client.get("/reservations/HB-NOPE").status_code == 404


def test_reject_checkout_before_checkin(client):
    assert client.post("/reservations", json=body(ci=3, co=1)).status_code == 422


def test_reject_past_checkin(client):
    p = body()
    p["check_in"] = (date.today() - timedelta(days=1)).isoformat()
    p["check_out"] = date.today().isoformat()
    assert client.post("/reservations", json=p).status_code == 422


def test_reject_invalid_email(client):
    p = body()
    p["guest_email"] = "not-an-email"
    assert client.post("/reservations", json=p).status_code == 422


# ---------- overlap rule ----------
def test_overlapping_dates_same_room_rejected(client):
    assert (
        client.post("/reservations", json=body(room_number="301", room_type="suite")).status_code
        == 201
    )
    r = client.post("/reservations", json=body(room_number="301", room_type="suite", ci=1, co=3))
    assert r.status_code == 409


def test_back_to_back_stays_allowed(client):
    assert (
        client.post(
            "/reservations", json=body(room_number="301", room_type="suite", ci=0, co=2)
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/reservations", json=body(room_number="301", room_type="suite", ci=2, co=4)
        ).status_code
        == 201
    )


def test_second_room_used_when_first_is_taken(client):
    a = client.post("/reservations", json=body("suite")).json()
    b = client.post("/reservations", json=body("suite")).json()
    assert {a["room_number"], b["room_number"]} == {"301", "302"}
    assert client.post("/reservations", json=body("suite")).status_code == 409


# ---------- concurrency (the key acceptance test) ----------
def _post(payload):
    with TestClient(app) as c:
        return c.post("/reservations", json=payload).status_code


def test_two_concurrent_requests_for_same_room_only_one_confirms(client):
    payload = body("suite", room_number="301")
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(_post, [payload, payload]))
    assert codes == [201, 409]


def test_many_concurrent_requests_never_overbook(client):
    # 2 suites exist; 10 simultaneous requests for the same dates -> exactly 2 succeed.
    payload = body("suite")
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(_post, [payload] * 10))
    assert codes.count(201) == 2
    assert codes.count(409) == 8
