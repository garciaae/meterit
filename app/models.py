from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MeterLog(Base):
    __tablename__ = "meterlog"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    time_created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    time_updated: Mapped[datetime | None] = mapped_column(DateTime, onupdate=func.now())
    watts: Mapped[float] = mapped_column(Float, default=0)
    station_id: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Float, default=0)


class MeterPrice(Base):
    __tablename__ = "meterprice"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    price: Mapped[float] = mapped_column(Float, default=0)
    date: Mapped[datetime] = mapped_column(DateTime, unique=True)
    time_created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    time_updated: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    percentage: Mapped[float] = mapped_column(Float, default=0)
