import logging
from datetime import datetime, timedelta

import requests
from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, text

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery("meterit", broker=settings.redis_url, backend=settings.redis_url)

celery_app.conf.beat_schedule = {
    "get_prices_daily": {
        "task": "app.tasks.get_prices",
        "schedule": crontab(hour="20", minute="45"),
    },
}
celery_app.conf.timezone = "UTC"


def get_sync_engine():
    return create_engine(settings.database_url_sync)


@celery_app.task(name="app.tasks.get_prices")
def get_prices(today: bool = False):
    """Fetch PVPC electricity prices from ESIOS API and store in DB."""
    logger.info("Fetching electricity prices from ESIOS")

    if today:
        fetch_date = datetime.utcnow().date()
    else:
        fetch_date = (datetime.utcnow() + timedelta(days=1)).date()

    url = (
        f"https://api.esios.ree.es/indicators/1001?"
        f"start_date={fetch_date:%d-%m-%Y}T00%3A00&"
        f"end_date={fetch_date:%d-%m-%Y}T23%3A30"
    )
    logger.info("Fetching URL: %s", url)

    response = requests.get(
        url,
        headers={
            "content-type": "application/json",
            "accept": "application/json; application/vnd.esios-api-v2+json",
            "x-api-key": settings.ree_token,
            "Host": "api.esios.ree.es",
        },
    )
    response.raise_for_status()

    values = response.json().get("indicator", {}).get("values", [])
    engine = get_sync_engine()

    inserted = 0
    for value in values:
        if value.get("geo_id") == 8741:  # peninsula
            price_kwh = value["value"] / 1000  # €/MWh → €/kWh
            dt = value["datetime"]
            with engine.connect() as conn:
                conn.execute(
                    text(
                        "INSERT INTO meterprice (price, date, percentage) "
                        "VALUES (:price, :date, 0) "
                        "ON CONFLICT (date) DO UPDATE SET "
                        "price = EXCLUDED.price, "
                        "time_updated = NOW()"
                    ),
                    {"price": price_kwh, "date": dt},
                )
                conn.commit()
            inserted += 1

    logger.info("Inserted/updated %d price records for %s", inserted, fetch_date)
    return inserted
