# Meterit

Electricity consumption monitoring and PVPC pricing API. Receives real-time power readings from an ESP8266 sensor and stores them alongside hourly electricity prices from Spain's grid operator (REE/ESIOS).

## Architecture

```
┌─────────────┐         ┌──────────────────────────────────┐
│  ESP8266     │         │  LXC Container (Debian 12)       │
│  Power Meter │─POST──▶ │                                  │
└─────────────┘   /      │  ┌────────┐     ┌────────────┐  │
                         │  │ Nginx  │────▶│  Uvicorn   │  │
                         │  │ :80    │     │  FastAPI    │  │
                         │  └────────┘     └─────┬──────┘  │
                         │                       │         │
                         │              ┌────────┴───────┐ │
                         │              │  PostgreSQL 15  │ │
                         │              │  ┌───────────┐  │ │
                         │              │  │ meterlog   │  │ │
                         │              │  │ meterprice │  │ │
                         │              │  └───────────┘  │ │
                         │              └────────┬───────┘ │
                         │                       │         │
                         │  ┌────────┐  ┌────────┴───────┐ │
                         │  │ Celery │──│     Redis      │ │
                         │  │ Beat   │  │                │ │
                         │  └────┬───┘  └────────────────┘ │
                         │       │                         │
                         └───────┼─────────────────────────┘
                                 │
                    Daily 20:45  │
                                 ▼
                         ┌───────────────┐
                         │  ESIOS API    │
                         │  (REE Spain)  │
                         │  PVPC Prices  │
                         └───────────────┘
```

## Data Flow

1. **ESP8266** reads power consumption every ~5 seconds and `POST`s `{watts, station_id}` to the API
2. **FastAPI** looks up the current electricity price and stores the reading with the price attached
3. **Celery Beat** fetches next-day PVPC prices daily at 20:45 UTC from the ESIOS API
4. Prices are stored in **€/kWh** (converted from €/MWh returned by ESIOS)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Last 50 readings (`?limit=N&offset=N` for pagination) |
| `POST` | `/` | Insert reading: `{"watts": 123.4, "station_id": 1}` |
| `GET` | `/current_price` | Current PVPC electricity price (€/kWh) |
| `GET` | `/force_get_prices` | Trigger manual price download from ESIOS |
| `GET` | `/ping` | Health check |
| `GET` | `/docs` | Swagger UI (auto-generated) |

## Database Schema

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│         meterlog             │     │        meterprice            │
├─────────────────────────────┤     ├─────────────────────────────┤
│ id           BIGSERIAL PK   │     │ id           BIGSERIAL PK   │
│ time_created TIMESTAMP      │     │ price        FLOAT (€/kWh)  │
│ time_updated TIMESTAMP      │     │ date         TIMESTAMP UQ   │
│ watts        FLOAT          │     │ time_created TIMESTAMP      │
│ station_id   INT            │     │ time_updated TIMESTAMP      │
│ price        FLOAT (€/kWh)  │     │ percentage   FLOAT          │
└─────────────────────────────┘     └─────────────────────────────┘
```

## Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.11 |
| Framework | FastAPI + Uvicorn |
| Database | PostgreSQL 15 |
| Task Queue | Celery 5.4 + Redis 7 |
| ORM | SQLAlchemy 2.0 (async) |
| Reverse Proxy | Nginx |
| OS | Debian 12 (Bookworm) |

## Setup

```bash
# Clone
git clone git@github.com:garciaae/meterit.git
cd meterit

# Virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configuration
cp .env.example .env
# Edit .env with your database credentials and ESIOS API token

# Create database tables
python3 -c "
from app.database import Base
from app.models import MeterLog, MeterPrice
from app.config import settings
from sqlalchemy import create_engine
engine = create_engine(settings.database_url_sync)
Base.metadata.create_all(engine)
"

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Celery Workers

```bash
# Worker
celery -A app.tasks.celery_app worker --loglevel=info

# Beat scheduler (daily price fetch at 20:45 UTC)
celery -A app.tasks.celery_app beat --loglevel=info
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `DATABASE_URL_SYNC` | PostgreSQL sync connection string (for Celery) |
| `REDIS_URL` | Redis connection string |
| `REE_TOKEN` | ESIOS API token ([request here](https://www.esios.ree.es/en/page/api)) |

## Migration from Legacy

The `migrate_data.py` script handles migration from the previous MariaDB-based Flask app:
- Transfers all `meterlog` and `meterprice` records
- Converts prices from €/MWh to €/kWh
- Processes in batches of 100K rows
- Handles duplicate detection via `ON CONFLICT`

```bash
python3 migrate_data.py --maria-host 192.168.1.174
```
