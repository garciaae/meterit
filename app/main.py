from datetime import datetime

from fastapi import Depends, FastAPI, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import MeterLog, MeterPrice
from app.schemas import PriceResponse, ReadingCreate, ReadingResponse, StatusResponse
from app.tasks import get_prices

app = FastAPI(title="Meterit", description="Electricity meter data ingestion API")


@app.get("/ping", response_model=StatusResponse)
async def ping():
    return StatusResponse(status=200, message="OK")


@app.get("/", response_model=dict)
async def get_readings(
    limit: int = Query(default=50, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MeterLog).order_by(MeterLog.id.desc()).offset(offset).limit(limit)
    )
    readings = result.scalars().all()
    return {"readings": [ReadingResponse.model_validate(r).model_dump() for r in readings]}


@app.post("/", response_model=StatusResponse)
async def post_reading(reading: ReadingCreate, db: AsyncSession = Depends(get_db)):
    price = await _current_price(db)
    log = MeterLog(watts=reading.watts, station_id=reading.station_id, price=price)
    db.add(log)
    await db.commit()
    return StatusResponse(status=200, message="OK")


@app.get("/current_price", response_model=PriceResponse)
async def get_current_price(db: AsyncSession = Depends(get_db)):
    price = await _current_price(db)
    return PriceResponse(price=str(price))


@app.get("/force_get_prices", response_model=StatusResponse)
async def force_get_prices():
    get_prices.delay(today=True)
    return StatusResponse(status=200, message="OK")


async def _current_price(db: AsyncSession) -> float:
    """Get the current electricity price for this hour (€/kWh)."""
    result = await db.execute(
        text(
            "SELECT price FROM meterprice "
            "WHERE date = date_trunc('hour', NOW()) "
            "LIMIT 1"
        )
    )
    row = result.fetchone()
    return float(row[0]) if row else 0.0
