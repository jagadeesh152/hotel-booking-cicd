import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from app import models
from app.config import settings
from app.database import engine, ping
from app.schemas import AvailabilityOut, DateRange, ReservationOut, ReservationRequest, RoomType

log = logging.getLogger("app.routes")
router = APIRouter()


@router.get("/health", tags=["ops"])
def health():
    """Liveness: the process is up. Does not touch the database."""
    return {"status": "ok", "version": settings.app_version}


@router.get("/ready", tags=["ops"])
def ready():
    """Readiness: the app can serve traffic (database reachable)."""
    try:
        ping()
    except Exception as exc:  # noqa: BLE001
        log.error("readiness check failed", extra={"error": str(exc)[:200]})
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "down"})
    return {"status": "ready", "database": "up", "version": settings.app_version}


def _range(
    check_in: str = Query(..., examples=["2030-01-10"]),
    check_out: str = Query(..., examples=["2030-01-12"]),
) -> DateRange:
    try:
        return DateRange(check_in=check_in, check_out=check_out)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/rooms/availability", response_model=AvailabilityOut, tags=["rooms"])
def availability(room_type: RoomType, dates: DateRange = Depends(_range)):
    with engine.connect() as conn:
        rooms = models.free_rooms(conn, room_type, dates.check_in, dates.check_out)
    numbers = [r.room_number for r in rooms]
    return AvailabilityOut(
        room_type=room_type,
        check_in=dates.check_in,
        check_out=dates.check_out,
        available_count=len(numbers),
        available_rooms=numbers,
    )


@router.post("/reservations", response_model=ReservationOut, status_code=201, tags=["reservations"])
def create_reservation(req: ReservationRequest):
    with engine.begin() as conn:
        result = models.create_reservation(conn, req)
    if result is None:
        log.info("reservation rejected: no availability", extra={"room_type": req.room_type})
        raise HTTPException(status_code=409, detail="No room available for the requested dates")
    log.info(
        "reservation confirmed",
        extra={"reference": result["reference"], "room_number": result["room_number"]},
    )
    return result


@router.get("/reservations/{reference}", response_model=ReservationOut, tags=["reservations"])
def read_reservation(reference: str):
    with engine.connect() as conn:
        result = models.get_reservation(conn, reference)
    if result is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return result
