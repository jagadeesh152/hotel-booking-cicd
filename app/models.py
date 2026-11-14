"""Data access. SQL is explicit so the booking rule is easy to read and explain."""

import uuid
from datetime import date

from psycopg2.errors import ExclusionViolation
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError

_FREE_ROOMS = text(
    """
    SELECT r.id, r.room_number, r.price_night
    FROM rooms r
    WHERE r.room_type = :room_type
      AND (CAST(:room_number AS VARCHAR) IS NULL OR r.room_number = :room_number)
      AND NOT EXISTS (
          SELECT 1 FROM reservations x
          WHERE x.room_id = r.id AND x.status = 'confirmed'
            AND daterange(x.check_in, x.check_out, '[)')
                && daterange(CAST(:ci AS date), CAST(:co AS date), '[)')
      )
    ORDER BY r.room_number
    """
)

_INSERT = text(
    """
    INSERT INTO reservations (reference, room_id, guest_name, guest_email, check_in, check_out)
    VALUES (:ref, :room_id, :name, :email, :ci, :co)
    """
)


def free_rooms(conn: Connection, room_type: str, ci: date, co: date, room_number=None):
    return conn.execute(
        _FREE_ROOMS, {"room_type": room_type, "room_number": room_number, "ci": ci, "co": co}
    ).all()


def create_reservation(conn: Connection, req) -> dict | None:
    """Try each free room; the DB exclusion constraint is the final arbiter.

    If a concurrent request grabs a room between our SELECT and INSERT, PostgreSQL raises
    ExclusionViolation, we roll back to the savepoint and try the next room.
    Returns None when nothing is available.
    """
    for room in free_rooms(conn, req.room_type, req.check_in, req.check_out, req.room_number):
        ref = "HB-" + uuid.uuid4().hex[:10].upper()
        try:
            with conn.begin_nested():
                conn.execute(
                    _INSERT,
                    {
                        "ref": ref,
                        "room_id": room.id,
                        "name": req.guest_name,
                        "email": req.guest_email,
                        "ci": req.check_in,
                        "co": req.check_out,
                    },
                )
        except IntegrityError as exc:
            if isinstance(exc.orig, ExclusionViolation):
                continue
            raise
        nights = (req.check_out - req.check_in).days
        return {
            "reference": ref,
            "room_number": room.room_number,
            "room_type": req.room_type,
            "guest_name": req.guest_name,
            "check_in": req.check_in,
            "check_out": req.check_out,
            "nights": nights,
            "total_price": float(room.price_night) * nights,
            "status": "confirmed",
        }
    return None


def get_reservation(conn: Connection, reference: str) -> dict | None:
    row = conn.execute(
        text(
            """
            SELECT x.reference, r.room_number, r.room_type, x.guest_name, x.check_in,
                   x.check_out, x.status, r.price_night
            FROM reservations x JOIN rooms r ON r.id = x.room_id
            WHERE x.reference = :ref
            """
        ),
        {"ref": reference},
    ).first()
    if row is None:
        return None
    nights = (row.check_out - row.check_in).days
    return {
        "reference": row.reference,
        "room_number": row.room_number,
        "room_type": row.room_type,
        "guest_name": row.guest_name,
        "check_in": row.check_in,
        "check_out": row.check_out,
        "nights": nights,
        "total_price": float(row.price_night) * nights,
        "status": row.status,
    }
