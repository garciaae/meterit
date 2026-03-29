from datetime import datetime

from pydantic import BaseModel


class ReadingCreate(BaseModel):
    watts: float
    station_id: int = 1


class ReadingResponse(BaseModel):
    id: int
    time_created: datetime
    time_updated: datetime | None
    watts: float
    station_id: int
    price: float

    model_config = {"from_attributes": True}


class PriceResponse(BaseModel):
    price: str


class StatusResponse(BaseModel):
    status: int
    message: str
