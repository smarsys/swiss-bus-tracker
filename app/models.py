from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class StopMatch(BaseModel):
    stop_ref: str
    name: str
    locality: str = ""
    lat: float = 0.0
    lon: float = 0.0


class DepartureStatus(str, Enum):
    on_time = "onTime"
    delayed = "delayed"
    cancelled = "cancelled"
    scheduled = "scheduled"
    unknown = "unknown"


class Departure(BaseModel):
    line: str
    destination: str
    scheduled_time: datetime
    estimated_time: datetime | None = None
    delay_minutes: int = 0
    status: DepartureStatus = DepartureStatus.unknown
    already_passed: bool = False
    stop_name: str = ""
    mode: str = ""

    def compute_status_and_delay(self, now: datetime) -> None:
        if self.status == DepartureStatus.cancelled:
            return
        if self.estimated_time is None:
            self.status = DepartureStatus.scheduled
            self.delay_minutes = 0
        else:
            delta = (self.estimated_time - self.scheduled_time).total_seconds()
            self.delay_minutes = max(0, int(delta / 60))
            if self.delay_minutes <= 1:
                self.status = DepartureStatus.on_time
            else:
                self.status = DepartureStatus.delayed
        effective_time = self.estimated_time or self.scheduled_time
        self.already_passed = effective_time < now
