import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.config import settings

RoomType = Literal["standard", "deluxe", "suite"]
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DateRange(BaseModel):
    check_in: date
    check_out: date

    @model_validator(mode="after")
    def validate_range(self):
        if self.check_out <= self.check_in:
            raise ValueError("check_out must be after check_in")
        if self.check_in < date.today():
            raise ValueError("check_in cannot be in the past")
        if (self.check_out - self.check_in).days > settings.max_stay_nights:
            raise ValueError(f"maximum stay is {settings.max_stay_nights} nights")
        return self


class ReservationRequest(DateRange):
    room_type: RoomType
    guest_name: str = Field(min_length=1, max_length=100)
    guest_email: str = Field(max_length=254)
    room_number: str | None = Field(default=None, max_length=10)

    @field_validator("guest_email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if not _EMAIL.match(v):
            raise ValueError("invalid email address")
        return v


class ReservationOut(BaseModel):
    reference: str
    room_number: str
    room_type: RoomType
    guest_name: str
    check_in: date
    check_out: date
    nights: int
    total_price: float
    status: str


class AvailabilityOut(BaseModel):
    room_type: RoomType
    check_in: date
    check_out: date
    available_count: int
    available_rooms: list[str]
